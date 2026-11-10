#!/usr/bin/env python3
"""Generate this workspace's dashboard from its own documents and file tree. Standard library only.

  python workspace_dashboard/build_dashboard.py                build the page
  python workspace_dashboard/build_dashboard.py --check        fail on broken links in the living documents
  python workspace_dashboard/build_dashboard.py --doctor       say what was found and what nearly parsed
  python workspace_dashboard/build_dashboard.py --check-staged fail if staged work has no staged documentation
  python workspace_dashboard/build_dashboard.py --watch        refresh until its window is closed

The page holds no content of its own. Everything specific to this workspace comes from
dashboard_config.json, the documents it names and workspace_dashboard/words.json.
"""
from __future__ import annotations

import base64
import fnmatch
import hashlib
import html
import json
import math
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote

KIT_DIR = Path(__file__).resolve().parent
ROOT = KIT_DIR.parent
KIT_NAME = KIT_DIR.name
CONFIG_PATH = ROOT / "dashboard_config.json"
ART_DIR = KIT_DIR / "art" / "web"
THEME_CSS = KIT_DIR / "theme.css"
THEME_JS = KIT_DIR / "theme.js"
WORDS = KIT_DIR / "words.json"
GUESTBOOK = KIT_DIR / "Guestbook.md"
DOCUMENT_TYPES = {".md", ".txt", ".rtf"}
ACTIVITY_LIMIT = 10
RUNE_LENGTH = {"none": 10, "idea": 10, "local": 22, "blocked": 22, "live": 36}
HOT_PROJECTS = 5
HOT_DAYS = 14
DEFAULT_CREDIT = "Art that came with this kit"
RUNES = "ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ"
LOCK_BASE, LOCK_RANGE, LOCK_TRIES = 49152, 65536 - 49152, 8
UPDATER_ENV = "WSDASH_UPDATER"

SECRET_DEFAULTS = (".env*", "*.env", "*.pem", "*.key", "*.pfx", "*.p12", "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*",
                   "*.kdbx", "*.kdb", "*.jks", "*.keystore", "*.ppk", "*.p8", "*.pkcs12", "*.ovpn", "*.tfvars", "*.tfstate*", "_netrc", ".s3cfg", ".boto",
                   ".azure", ".gnupg", "secring.*", ".my.cnf", ".yarnrc*", ".git-credentials",
                   "*credential*", "*secret*", "*token*", "*passw*", "*passphrase*", "*private_key*", "*privatekey*",
                   "*private-key*", "*api key*", "*api_key*", "*api-key*", "*apikey*", ".aws", ".ssh", ".npmrc", ".pypirc",
                   ".netrc", ".mcp.json", "mcp.json", ".claude", ".pgpass", ".dockercfg", ".docker", ".kube", "kubeconfig",
                   "service-account*", "service_account*", "vault*", "wallet*", "keys.*", "pwd.*", "login data",
                   "*.env.*", "env.local", "env.prod*", "env.dev*", "env.stag*", "env.test*", "*creds*", "auth.json", "cookies*", "pass.txt")
HIDDEN_DEFAULTS = (".git", "__pycache__", "node_modules", ".venv", "venv", "target", ".next", ".gradle",
                   "__MACOSX", ".pytest_cache", ".mypy_cache", ".tox")
# A list of forms, so it cannot catch everything. README says so.
TOKEN_LIKE = re.compile(r"sk-[A-Za-z0-9_-]{16,}|[sr]k_(?:live|test)_[A-Za-z0-9]{10,}|(?:AKIA|ASIA)[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}"
                        r"|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|msy_[A-Za-z0-9_-]{16,}"
                        r"|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----"
                        r"|(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"
                        r"|(?i:password|passwd|pwd|api[_ -]?key|client[_-]?secret|auth[_-]?token|access[_-]?token)[\"']?\s*"
                        r"(?:=\s*[\"']?[^\s\"',;]{4,}|:\s*[\"']?(?=[^\s\"',;]*[\d_!@#$%^&*+/=-])[^\s\"',;]{4,})")
# A label beside a value: token: x, secret = x, pass: x, "api_key": "x". Also a list of forms: README says what it misses.
_LABEL = (r"(?<![\w-])(?P<prefix>[\w.-]*[_.-])?(?:password|passwd|passphrase|passcode|pass|pwd|secret(?:[_-]?key)?|token|credentials?|api[_ -]?key|apikey"
          r"|access[_-]?key|private[_-]?key)")
_VALUE = r"(?:\"(?P<dq>[^\"\n]+)\"|'(?P<sq>[^'\n]+)'|(?P<bare>[^\s\"'`*,;|<>()\[\]&]+))"
LABELLED = re.compile(rf"{_LABEL}[*_`\"'\]]*\s*(?P<sep>=>|:=|:|=|\uff1a)[\s*_`]*{_VALUE}(?P<rest>[^\n]*)", re.I)
AUTH_HEADER = re.compile(rf"(?<![\w-])(?:proxy-)?authorization[*_`\"']*\s*[:=\uff1a][\s*_`]*(?:(?:bearer|basic|token|digest)\s+)?{_VALUE}", re.I)
BEARER = re.compile(r"(?<![\w-])bearer\s+(?P<bare>(?=[A-Za-z0-9._~+/=-]*[\d._~+/=-])[A-Za-z0-9._~+/=-]{8,})", re.I)
# Looser labels: plurals, TOKEN_PROD, dbpass, "token (prod)", a bare "key", arrows and dashes, a value in brackets. These read
# like ordinary writing too, so they count only when the value looks generated: see shaped().
LOOSE = re.compile(r"(?:(?<![\w.-])[\w.-]*?(?:pass[ ]word|passwords?|passwd|passphrases?|pass|pwd|pw|creds|secrets?|tokens?|credentials?|api[_-]?keys?|apikeys?|access[_-]?keys?|private[_-]?keys?)"
                   r"(?:[_.-]\w+)*|(?<![\w\"'.-])key)(?:\s*\([^()\n]{1,20}\))?[*_`\"'\]]*"
                   r"(?:\s*(?:=>|:=|:|=|\uff1a|->|\u2192)|\s+[-\u2013\u2014](?=\s))[\s*_`\"']*(?P<open>[<(|\[]?)(?P<bare>[^\s\"'`*,;|<>()\[\]&]+)(?P<close>\]\()?", re.I)
CLI_FLAG = re.compile(r"(?<!\S)--?(?:password|passwd|pass|pwd|token|secret|api[_-]?key|auth[_-]?token|access[_-]?token)(?:\s+|=)[\"']?(?P<bare>[^\s\"'`]+)", re.I)
MYSQL_FLAG = re.compile(r"\b(?:mysql\w*|mariadb\w*)\b[^\n]*?\s-p(?P<bare>[^\s\"'`]{4,})", re.I)
COOKIE = re.compile(r"(?<![\w-])(?:set-)?cookie[*_`\"']*\s*[:\uff1a]\s*(?P<pairs>[^\s=;]+=[^\n]+)", re.I)
URL_SECRET = re.compile(r"(?:[?&]|&amp;)(?:sig|signature|x-amz-signature|x-amz-credential|auth|key|session(?:id)?|sid)=(?P<bare>[^\s&#\"'<>)]+)", re.I)
TAG_SECRET = re.compile(r"(?:<|&lt;)(?P<tag>password|passwd|pass|pwd|secret|token|api[_-]?key)(?:>|&gt;)(?P<bare>[^<&\s]+)(?:<|&lt;)/(?P=tag)(?:>|&gt;)", re.I)
# These labels are everyday words, so the value must look strongly generated: see generated().
EVERYDAY_LABEL = re.compile(r"(?<![\w.-])(?:[\w-]*[_-])?(?:pin|auth|session)(?:[_-]\w+)*(?:\s*\([^()\n]{1,20}\))?[*_`\"'\]]*"
                            r"\s*(?:=>|:=|:|=|\uff1a|->|\u2192)[\s*_`\"']*[<(|\[]?(?P<bare>[^\s\"'`*,;|<>()\[\]&]+)", re.I)
# A label and a value with no separator, or joined by a word or a table bar: password X, the password is X, | password | X |.
SPACED_LABEL = re.compile(r"(?<![\w.-])(?:pass[ ]word|passwords?|passwd|passphrases?|pwd|tokens?|secrets?|api[_ -]?keys?)(?:\s+(?:is|was|as|of))?[*_`\"']*"
                          r"(?:\s*\|\s*|\s+)[*_`\"']*(?P<bare>[^\s\"'`*,;|<>()\[\]&]+)", re.I)
LOGIN_PAIR = re.compile(r"(?<![\w-])login[*_`\"']*\s*[:=\uff1a]\s*[^\s/]+\s*/\s*(?P<bare>[^\s\"'`,;]+)", re.I)
COMMAND_SECRET = re.compile(r"\bsshpass\b[^\n]*?\s-p\s*[\"']?(?P<bare>[^\s\"'`]{4,})|\bcurl\b[^\n]*?\s(?:-u\s*|--user[\s=]+)[\"']?[^\s:\"']+:(?P<pair>[^\s\"'`]{4,})", re.I)
TOKEN_LABEL = re.compile(r"(?:password|passwd|pwd|api[_ -]?key|client[_-]?secret|auth[_-]?token|access[_-]?token)[\"']?\s*[:=]\s*[\"']?", re.I)
# Ordinary phrases ending in a label word. They count only when the value looks strongly generated.
ORDINARY_LABEL = re.compile(r"(?:\b(?:hall|boarding|bus|ski|season|day|guest|press|backstage)\s+pass|\b(?:by|over|under|sur|tres|com)pass"
                            r"|\b(?:answer|cache|sort|primary|foreign|map|partition|shard|hot|music|piano)\s+key)[*_`\"'\]]*\s*(?:=>|:=|:|=|\uff1a|->|\u2192)?[\s*_`\"']*$", re.I)
LINK_LABEL = re.compile(r"\[([^\[\]\n]+)\]\([^()\s]*\)")
SPACED_LETTERS = re.compile(r"(?<!\S)(?:\w[ \t]){3,}\w(?!\w)")
HIDDEN_CHARACTERS = dict.fromkeys(map(ord, "\u00ad\u034f\u061c\u180e\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff"))
LOOKALIKES = str.maketrans("\u0430\u0435\u043e\u0440\u0441\u0445\u0443\u0456\u0455\u0458\u0410\u0412\u0415\u041a\u041c\u041d\u041e\u0420\u0421\u0422\u0425\u0423\u0406\u0405\u03bf\u03b1\u0391\u039f\u03a1\u03a4",
                           "aeopcxyisjABEKMHOPCTXYISoaAOPT")
INLINE_TAGS = frozenset("b strong i em code u s small mark font tt span".split())
PAGE_TAG = re.compile(r"</?([A-Za-z][\w-]*)[^<>]*>")
COMMIT_SOURCE = "Commit messages"
CONFIG_SOURCE = "dashboard_config.json"
HIDDEN_NAME_SHAPE = re.compile(r"(?:pass|pwd|auth|key|api|token|secret)(?P<sep>[=-])(?P<value>[^./\\\s]+)", re.I)
# Words that follow a label in ordinary prose or settings, so they are not values.
NOT_VALUES = frozenset("""is are was were be must should will can may see in on at to of for the a an and or not no yes none null nil true false
    required optional needed missing unknown tbd todo expired rotated revoked empty unset here there this that it value string key token bearer basic
    password secret pass passphrase credentials everything all ok okay green red failed fail passed done""".split())
PRIVATE_BLOCK = (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), re.compile(r"-----END [A-Z ]*PRIVATE KEY-----"))
# Code files only: a design document in specs/ or a test_plan.md is not a test.
CODE = r"\.(?:py|js|jsx|mjs|cjs|ts|tsx|lua|go|rs|rb|java|kt|cs|swift|c|cc|cpp|php|sh|ps1|pl|ex|exs|scala|dart)$"
TEST_PATTERNS = [rf"(^|/)(tests?|specs?|__tests__)/.+{CODE}", rf"(^|/)test_[^/]+{CODE}", rf"_tests?{CODE}",
                 rf"\.(test|spec){CODE}", r"(^|/)[^/]*Tests?\.(java|kt|cs|swift)$"]
EDITORS = {"vscode": ("vscode://file/{path}:{line}", "Open in VS Code"),
           "cursor": ("cursor://file/{path}:{line}", "Open in Cursor"),
           "zed": ("zed://file/{path}:{line}", "Open in Zed")}

DEFAULTS = {
    "title": "", "tagline": "", "id": "",
    "overview": "docs/Works_in_Development.md", "ledger": "docs/project-ledger.md", "decisions": "docs/decision-log.md",
    "output": f"{KIT_NAME}/Workspace_Dashboard.html",
    "needs_heading": "Items for the user",
    "links": [], "live_record": None, "count_files": {},
    "preservation_glob": "preservation/*/COPIES.tsv",
    "activity_skip": ["build/", "dist/", "out/", "coverage/", "preservation/"],
    "activity_skip_types": [".pyc"],
    "unlinked_skip": ["preservation/", "tests/", "test/", "spec/", "__tests__/"],
    "hidden_folders": [], "secret_patterns": [],
    "status_words": {"live": ["live", "shipped", "released", "in production", "done", "deployed", "published"],
                     "blocked": ["blocked", "disabled"],
                     "idea": ["proposal", "suggestion", "handoff", "idea", "planned", "not started", "not begun", "to do", "backlog"],
                     "local": ["local", "locally", "built", "building", "working", "works", "in progress", "under way", "underway", "ongoing", "active",
                               "wip", "draft", "drafted", "drafting", "started", "prototype", "beta", "alpha", "testing", "tested", "implemented", "in development",
                               "existing", "delivered", "unblocked", "half done", "partly done", "partially done", "almost done", "nearly done", "mostly done"]},
    "heat": {"none": 1, "idea": 1, "local": 2, "blocked": 2, "live": 3},
    "heat_marks": [25, 50, 75, 100],
    "poll_seconds": 60, "watch_seconds": 20,
    "editor": "vscode", "motion": "always", "reveal_links": False,
    "max_folder_rows": 300, "max_file_rows": 3000,
    "doc_only_prefixes": ["docs/", "preservation/"], "doc_only_files": ["README.md", "CLAUDE.md", ".gitignore"],
}

# Found while building and shown on the page and in the console. A bad word or link is never fatal.
PROBLEMS = []


def note_problem(text):
    if text not in PROBLEMS:
        PROBLEMS.append(text)


def read_text(path):
    """UTF-8 with or without a BOM, UTF-16 with one, and anything else with a warning."""
    raw = Path(path).read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16", "replace")
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            note_problem(f"{Path(path).name} is not UTF-8. Characters it could not read were replaced.")
            text = raw.decode("utf-8", "replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_or_note(path, label):
    """The text of a file, or None with a problem noted. A folder or locked file in its place is never fatal."""
    try:
        return read_text(path)
    except OSError as error:
        note_problem(f"{label} could not be read ({error.strerror or 'read error'}).")
        return None


def load_config():
    config = json.loads(json.dumps(DEFAULTS))
    if not CONFIG_PATH.exists():
        note_problem("dashboard_config.json is missing, so this page uses the defaults.")
        return config
    text = read_or_note(CONFIG_PATH, "dashboard_config.json")
    if text is None:
        return config
    try:
        loaded = json.loads(text)
        if not isinstance(loaded, dict):
            raise ValueError("the top level must be an object")
    except RecursionError:
        note_problem("dashboard_config.json could not be read (it is nested too deeply), so this page uses the defaults.")
        return config
    except ValueError as error:
        note_problem(f"dashboard_config.json could not be read ({error}), so this page uses the defaults.")
        return config
    for key, value in loaded.items():
        if key.startswith("_"):
            continue
        if key not in DEFAULTS:
            note_problem(f"dashboard_config.json: unknown key '{key}' was ignored.")
        elif value is None and key != "live_record":
            continue
        elif key == "live_record":
            if value is None or isinstance(value, dict):
                config[key] = value
            else:
                note_problem("dashboard_config.json: 'live_record' must be an object or null.")
        elif key == "heat":
            if isinstance(value, dict) and all(isinstance(v, int) and v >= 0 for v in value.values()):
                config[key].update(value)
            else:
                note_problem("dashboard_config.json: 'heat' must map status kinds to whole numbers and was ignored.")
        elif key == "status_words" and isinstance(value, dict):
            config[key].update({k: v for k, v in value.items() if isinstance(v, list)})
        elif isinstance(DEFAULTS[key], list) and not (isinstance(value, list) and all(isinstance(v, (str, dict, int)) for v in value)):
            note_problem(f"dashboard_config.json: '{key}' must be a list and was ignored.")
        elif type(value) is not type(DEFAULTS[key]) and DEFAULTS[key] is not None:
            note_problem(f"dashboard_config.json: '{key}' has the wrong type and was ignored.")
        else:
            config[key] = value
    return config


CONFIG = load_config()


def workspace_id():
    """Stable per folder. It names browser storage and the updater lock so two dashboards never collide."""
    if isinstance(CONFIG["id"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", CONFIG["id"]):
        return CONFIG["id"]
    text = str(ROOT).casefold() if os.name == "nt" else str(ROOT)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


WORKSPACE_ID = workspace_id()
# Says which folder holds a lock, so a copied "id" cannot pass for this workspace's own updater.
LOCK_BANNER = f"wsdash {WORKSPACE_ID} " + hashlib.sha256(str(ROOT).casefold().encode("utf-8")).hexdigest()[:12]
STORAGE_NS = "wsdash-" + WORKSPACE_ID
TITLE = CONFIG["title"].strip() or f"{ROOT.name} Workspace"


def lock_ports():
    """Where the updater may hold its lock: a hash of this workspace into the high range, then fallbacks."""
    start = int(hashlib.sha256(("lock:" + WORKSPACE_ID).encode("utf-8")).hexdigest()[:8], 16) % LOCK_RANGE
    return [LOCK_BASE + (start + index * 251) % LOCK_RANGE for index in range(LOCK_TRIES)]


def inside_root(rel):
    """The workspace-relative path for a configured or linked path, or None if it leaves the workspace."""
    if not isinstance(rel, str) or not rel or re.match(r"^[A-Za-z]:|^[\\/]", rel):
        return None
    try:
        return (ROOT / rel).resolve().relative_to(ROOT).as_posix()
    except (ValueError, OSError):
        return None


def configured_path(key):
    rel = inside_root(CONFIG[key])
    if rel is None:
        note_problem(f"dashboard_config.json: '{key}' must be a path inside this workspace. Using the default.")
        rel = DEFAULTS[key]
    return rel


def writable_by_kit(path, mark):
    """True if a build may write here: nothing is there yet, or the file holds the mark of a page or data file this kit wrote."""
    if not path.exists():
        return True
    try:
        return path.is_file() and mark in path.read_bytes()
    except OSError:
        return False


PAGE_MARK, DATA_MARK = b'<body data-stamp="', b"window.onDashData("


def data_path_for(page):
    return page.with_name(page.stem + "_data.js")


def output_path():
    """Where the page goes. A configured path is refused unless it is an .html the kit may write, so no file of yours is replaced."""
    rel = configured_path("output")
    page = ROOT / rel
    if os.name == "nt" and re.search(r'[<>:"|?*]', rel):
        note_problem("dashboard_config.json: 'output' has characters this system does not allow in a file name. Using the default.")
        rel = DEFAULTS["output"]
    elif rel != DEFAULTS["output"] and not (page.suffix.lower() == ".html" and writable_by_kit(page, PAGE_MARK)
                                          and writable_by_kit(data_path_for(page), DATA_MARK)):
        note_problem(f"dashboard_config.json: 'output' {rel} was left alone: it must be an .html path that is free or already this kit's page. Using the default.")
        rel = DEFAULTS["output"]
    return rel


OVERVIEW_REL, LEDGER_REL, DECISIONS_REL = (configured_path(k) for k in ("overview", "ledger", "decisions"))
OUTPUT_REL = output_path()
OUTPUT = ROOT / OUTPUT_REL
DATA_OUTPUT = data_path_for(OUTPUT)
DATA_REL = DATA_OUTPUT.relative_to(ROOT).as_posix()
WORDS_REL = WORDS.relative_to(ROOT).as_posix()
GUESTBOOK_REL = GUESTBOOK.relative_to(ROOT).as_posix()
OVERVIEW, LEDGER, DECISIONS = ROOT / OVERVIEW_REL, ROOT / LEDGER_REL, ROOT / DECISIONS_REL
LIVING_DOCS = ((OVERVIEW_REL, "Overview"), (LEDGER_REL, "Ledger"), (DECISIONS_REL, "Decision log"))
KIT_FILES = {"dashboard_config.json", "Open_Dashboard.cmd", "Open_Dashboard.sh"}
LAUNCHER_MARK = b"Builds this workspace's dashboard"


def unedited_starters():
    """The configured documents still exactly as the installer wrote them. They are the kit's words, not this workspace's work."""
    loaded = None
    try:
        loaded = json.loads((KIT_DIR / "starter_docs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    hashes = set(loaded) if isinstance(loaded, list) else set()
    found = set()
    for rel, _ in LIVING_DOCS:
        try:
            if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() in hashes:
                found.add(rel)
        except OSError:
            continue
    return found


UNEDITED_STARTERS = unedited_starters()
WATCH_SECONDS = max(2, int(CONFIG["watch_seconds"]))
POLL_SECONDS = max(5, int(CONFIG["poll_seconds"]))
HEAT = CONFIG["heat"]
for _kind, _value in DEFAULTS["heat"].items():
    HEAT.setdefault(_kind, _value)
SECRET_PATTERNS = tuple(p.rstrip("/").casefold() for p in (*SECRET_DEFAULTS, *CONFIG["secret_patterns"]) if isinstance(p, str))
HIDDEN_PARTS = {*HIDDEN_DEFAULTS, *(p for p in CONFIG["hidden_folders"] if isinstance(p, str))}
ACTIVITY_SKIP = tuple(p for p in CONFIG["activity_skip"] if isinstance(p, str))
ACTIVITY_SKIP_TYPES = {str(p).lower() for p in CONFIG["activity_skip_types"]}
LAUNCHER = "Open_Dashboard.cmd" if os.name == "nt" else "Open_Dashboard.sh"


def launcher_is_ours():
    """A launcher the workspace already had is not this kit's, so the page must not send anyone to it."""
    try:
        return LAUNCHER_MARK in (ROOT / LAUNCHER).read_bytes()
    except OSError:
        return False


LINK_SCHEME = "wsdash-" + hashlib.sha256(("links:" + WORKSPACE_ID).encode("utf-8")).hexdigest()[:8]
REVEAL_SCHEME = LINK_SCHEME if CONFIG["reveal_links"] is True and os.name == "nt" else ""


def url_segments(path):
    return quote(path, safe="/")


ART_URL = url_segments(Path(os.path.relpath(ART_DIR, OUTPUT.parent)).as_posix())
ROOT_URL = url_segments(Path(os.path.relpath(ROOT, OUTPUT.parent)).as_posix())


def asset(name):
    return f"{ART_URL}/{quote(name, safe='/')}"


LINK = re.compile(r"\[([^\]\[]{1,500})\]\(\s*(<[^>]+>|(?:[^()\s]|\([^()\s]*\))+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
DECISION = re.compile(r"^#{2,3} ((?:[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)*-\d+[A-Za-z]?)|\d{4}-\d{2}-\d{2})\b\W*(.*)$")
SAFE_WEB = re.compile(r"^(https?:|mailto:)", re.I)
FENCE = re.compile(r"^\s*(```|~~~)")


def find_links(text):
    return [(label, url[1:-1] if url.startswith("<") else url) for label, url in LINK.findall(text)]


def unfenced(text):
    """(line number, line), leaving out fenced code, which is an example and not content."""
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            yield number, line


# --- Git, which is optional. No function here may raise for the state of the repository.

GIT_NOTE = {"text": ""}


def git(*args):
    try:
        result = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=120)
    except (OSError, subprocess.SubprocessError):
        GIT_NOTE["text"] = GIT_NOTE["text"] or "Git is not installed here"
        return None
    if result.returncode != 0:
        if "dubious ownership" in result.stderr:
            GIT_NOTE["text"] = "Git refuses this folder: dubious ownership"
        elif "not a git repository" in result.stderr.lower():
            GIT_NOTE["text"] = "Not a git repository"
        return None
    return result.stdout


def split_z(text):
    return [p for p in (text or "").split("\0") if p]


def own_pathspec():
    """Everything in this folder except the kit and the generated page, so its own files never count as work."""
    excludes = {KIT_NAME, OUTPUT_REL, DATA_REL, *KIT_FILES, *UNEDITED_STARTERS}
    return [".", *(f":(exclude,literal){p}" for p in sorted(excludes))]


def git_usable():
    state = git("rev-parse", "--is-inside-work-tree")
    if state is None or state.strip() != "true":
        GIT_NOTE["text"] = GIT_NOTE["text"] or "Not a git repository"
        return False
    return True


def git_history(usable):
    """(commit lines, commit count, uncommitted count or None), scoped to this folder."""
    if not usable:
        return [], 0, None
    log = git("log", "-25", "--date=short", "--format=%ad  %s", "--", ".")
    count = git("rev-list", "--count", "HEAD", "--", ".")
    status = git("status", "--short", "-uall", "--", *own_pathspec())  # -uall counts files, not collapsed folders
    if count is None:
        GIT_NOTE["text"] = "No commits yet"
    commits = (log or "").splitlines()
    uncommitted = len([l for l in status.splitlines() if l]) if status is not None else None
    return commits, int(count.strip()) if count else 0, uncommitted


def commit_times():
    """When Git last saw each file that has no uncommitted change, so a fresh clone's new file dates do not read as new work."""
    log, dirty = git("log", "-300", "--relative", "--format=@@%at", "--name-only", "--", "."), git("diff", "--name-only", "--relative", "HEAD", "--", ".")
    if log is None or dirty is None:
        return {}
    times, when = {}, 0
    for line in log.splitlines():
        if line.startswith("@@"):
            when = int(line[2:])
        elif line:
            times.setdefault(line, when)
    for path in dirty.splitlines():
        times.pop(path, None)
    return times


# --- What may appear on the page.

def is_secret(rel):
    for segment in rel.split("/"):
        folded = segment.casefold()
        if any(fnmatch.fnmatchcase(folded, pattern) for pattern in SECRET_PATTERNS) or TOKEN_LIKE.search(segment) or name_holds_credential(segment):
            return True
    return False


def name_holds_credential(segment):
    """A file named like a credential form: pass=x.txt, dbpass-FaKe5.txt. A dash also needs mixed case, so api-reference2.md stays."""
    if credential_values(segment)[0]:
        return True
    for match in HIDDEN_NAME_SHAPE.finditer(segment):
        value = match.group("value")
        if shaped(value) and (match.group("sep") == "=" or re.search(r"[a-z][A-Z]", value)):
            return True
    return False


def is_own(rel):
    return rel in (OUTPUT_REL, DATA_REL) or rel in KIT_FILES or rel == KIT_NAME or rel.startswith(KIT_NAME + "/")


def is_hidden(rel):
    return bool(HIDDEN_PARTS.intersection(rel.split("/")))


def walk_files():
    found = []

    def stays_inside(path):
        return Path(os.path.realpath(path)).is_relative_to(ROOT)
    for folder, subfolders, names in os.walk(ROOT):
        # realpath, because a Windows junction is not always reported as a link.
        subfolders[:] = [s for s in subfolders if s not in HIDDEN_PARTS and stays_inside(os.path.join(folder, s))]
        base = Path(folder).relative_to(ROOT).as_posix()
        found += [name if base == "." else f"{base}/{name}" for name in names
                  if not os.path.islink(os.path.join(folder, name)) or stays_inside(os.path.join(folder, name))]
    return found


def workspace_files(usable):
    """(listed, ignored by Git, hidden secret paths). The hidden paths are never written to the page."""
    listed = split_z(git("ls-files", "-z", "-co", "--exclude-standard")) if usable else walk_files()
    ignored = split_z(git("ls-files", "-z", "-oi", "--exclude-standard")) if usable else []
    secrets = set()

    def visible(path):
        if is_hidden(path) or is_own(path) or path in UNEDITED_STARTERS:
            return False
        if is_secret(path):
            secrets.add(path)
            return False
        return (ROOT / path).exists()
    return sorted(set(filter(visible, listed))), sorted(set(filter(visible, ignored))), sorted(secrets)


def name_pattern(name):
    """A hidden name as it may be written: in any case, percent-encoded, wrapped over lines or split by Markdown marks.
    A single plain word, such as a folder called tokens, counts only beside a slash, so ordinary prose keeps its meaning."""
    if name.isalpha():
        return rf"(?:(?<=[/\\]){re.escape(name)}|{re.escape(name)}(?=[/\\]))"
    parts = []
    for piece in re.findall(r"\w+|\s+|.", name):
        if piece.isspace():
            parts.append(r"(?:[\s*`~]+|%20)")
        elif re.match(r"\w", piece):
            parts.append(re.escape(piece))
        else:
            parts.append(f"(?:{re.escape(piece)}|%{ord(piece):02x})")
    return "[*`~]*".join(parts)


FREE_WORD = re.compile(r"\w+://\S+|[^\s()\[\]<>\"'`*~,;:|=]+")


def phrase_patterns():
    """Patterns with a space, such as *api key*, as they appear in a file name written in text: my api key.txt."""
    found = []
    for pattern in SECRET_PATTERNS:
        words = pattern.strip("*").split()
        if len(words) > 1 and not any(c in pattern.strip("*") for c in "*?["):
            found.append(r"[\w.-]*" + r"\s+".join(map(re.escape, words)) + r"[\w.-]*\.\w{1,8}(?!\w)")
    return re.compile("|".join(found), re.I) if found else None


PHRASES = phrase_patterns()


def secret_word(word):
    """True for a file-like word matching the secret patterns, even if no such file is on disk now. A plain word
    such as 'tokens' stays, so ordinary prose keeps its meaning. Web addresses are left whole."""
    word = word.rstrip(".!?").replace("\\", "/")
    if "://" in word or not ("/" in word or word.startswith(".") or re.search(r"\.\w{1,8}$", word)):
        return False
    return is_secret(word)


def hide_pattern_names(text):
    if PHRASES:
        text = PHRASES.sub("[hidden name]", text)

    def replace(match):
        word = match.group(0)
        kept = word[len(word.rstrip(".!?")):]
        return "[hidden name]" + kept if secret_word(word) else word
    return FREE_WORD.sub(replace, text)


def labelled_value(match):
    """The value beside a label, or None when the words read as prose: 'The password: is required', 'Pass: 12 of 14'."""
    value = match.group("dq") or match.group("sq")
    if value:
        return value
    value = match.group("bare").rstrip(".!?:")
    if not value or value.lower() in NOT_VALUES:
        return None
    if lone_number(match, value):
        return value
    if re.fullmatch(r"[\d.,%/]+", value) and sum(c.isdigit() for c in value) < 6:
        return None
    if match.group("sep") == ":" and value.isalpha() and len(match.group("rest").split()) >= 2:
        return None
    return value


def lone_number(match, value):
    """'pass: 74251' alone on its line is a PIN. 'Tests pass: 1200', 'pass: 12 of 14' and 'max_tokens: 4000' are counts."""
    start = match.string.rfind("\n", 0, match.start()) + 1
    return (value.isdigit() and len(value) >= 4 and not match.group("prefix") and not match.group("rest").strip()
            and not match.string[start:match.start()].strip(" \t-*+#>"))


def shaped(value):
    """True for a word that looks generated rather than written: letters with digits, or inner capitals in a long word.
    Versions, variables, web addresses and file names do not count."""
    if len(value) < 6 or value.lower() in NOT_VALUES or re.match(r"[$%{]|v?\d+(\.\d+)+", value, re.I) or "://" in value or re.search(r"\.[A-Za-z]\w{0,4}$", value):
        return False
    letters, digits = re.search(r"[A-Za-z]", value), re.search(r"\d", value)
    return bool(letters and digits) or (len(value) >= 8 and bool(re.search(r"[a-z][A-Z]", value)))


def generated(value):
    """Stricter than shaped(), for labels that are everyday words: 'auth: oauth2' and 'session: sprint12' stay."""
    if len(value) < 8 or not shaped(value) or re.match(r"\d{4}-\d{2}", value):
        return False
    return (bool(re.search(r"[a-z][A-Z]", value)) or len(re.findall(r"[A-Za-z]\d|\d[A-Za-z]", value)) >= 3
            or (len(value) >= 12 and not re.search(r"[-_./:]", value)))


def ordinary_label(match, value):
    """'Hall pass: Sunday', 'bypass: route42', 'Answer key: b2c3d4'. Never for a value that looks strongly generated."""
    return bool(match.group("bare")) and bool(ORDINARY_LABEL.search(match.string[:match.start("bare")])) and not generated(value)


def read_as_shown(line):
    """The line as a reader sees it: entities decoded, invisible characters gone, common lookalikes and spaced letters read plainly."""
    shown = unicodedata.normalize("NFKC", html.unescape(line).translate(HIDDEN_CHARACTERS)).translate(LOOKALIKES)
    return SPACED_LETTERS.sub(lambda m: re.sub(r"[ \t]", "", m.group(0)), shown)


def credential_values(line):
    """(does this line hold a credential form, the values found on it). The line is also read percent-decoded and as a
    reader sees it, and a Markdown link's label is read alone, so '](' cannot excuse a value in it."""
    views = {line, unquote(line) if "%" in line else line, read_as_shown(line)}
    views |= {label for view in tuple(views) for label in LINK_LABEL.findall(view)}
    hit, values = False, []
    for view in views:
        more_hit, more = line_forms(view)
        hit, values = hit or more_hit, values + more
    return hit, values


def line_forms(line):
    values = []
    for found in TOKEN_LIKE.finditer(line):
        label = TOKEN_LABEL.match(found.group(0))
        if label and found.group(0)[label.end():].rstrip(".!?:").lower() in NOT_VALUES:
            continue
        values.append(found.group(0))
        if "://" in line[:found.start()] and ":" in found.group(0):
            values.append(found.group(0).split(":", 1)[1])
    hit = bool(values)
    for match in LABELLED.finditer(line):
        value = labelled_value(match)
        if value and not ordinary_label(match, value):
            hit = True
            values.append(value)
    for form in (AUTH_HEADER, BEARER):
        for match in form.finditer(line):
            groups = match.groupdict()
            value = groups.get("dq") or groups.get("sq") or groups.get("bare")
            if value and value.rstrip(".!?:").lower() not in NOT_VALUES:
                hit = True
                values.append(value)
    for match in LOOSE.finditer(line):
        value = match.group("bare").rstrip(".!?:")
        if shaped(value) and (generated(value) or not (match.group("close") or ordinary_label(match, value))):
            hit = True
            values.append(value)
    for form, test in ((EVERYDAY_LABEL, generated), (SPACED_LABEL, generated), (LOGIN_PAIR, shaped)):
        for match in form.finditer(line):
            value = match.group("bare").rstrip(".!?:")
            if test(value) and not ordinary_label(match, value):
                hit = True
                values.append(value)
    for match in COMMAND_SECRET.finditer(line):
        value = match.group("bare") or match.group("pair")
        if not re.match(r"[$%{<]", value):
            hit = True
            values.append(value)
    for form in (CLI_FLAG, URL_SECRET):
        for match in form.finditer(line):
            value = match.group("bare").rstrip(".!?:")
            if shaped(value):
                hit = True
                values.append(value)
    for form in (MYSQL_FLAG, TAG_SECRET):
        for match in form.finditer(line):
            hit = True
            values.append(match.group("bare"))
    for match in COOKIE.finditer(line):
        hit = True
        values += re.findall(r"=([^;\s]+)", match.group("pairs"))
    return hit, values


def value_pattern(value):
    """A value in any case. One that looks generated also counts inside a longer word, split by Markdown marks, or in base64.
    A plain word or a number counts only whole, so ordinary words around it keep their meaning."""
    if len(value) >= 8 and shaped(value):
        marked = "[*_`~]*".join(map(re.escape, value))
        encoded = base64.b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
        return f"{marked}|{re.escape(encoded)}"
    return rf"(?<!\w){re.escape(value)}(?!\w)"


def withhold_lines(text):
    """(text with each credential line blanked, so line numbers stay true, count of lines withheld, values found).
    A private key block goes whole, up to its END line, because its body matches no form of its own."""
    lines, count, values, in_key = text.split("\n"), 0, [], False
    for index, line in enumerate(lines):
        hit, found = credential_values(line)
        if PRIVATE_BLOCK[0].search(line):
            in_key = True
        if in_key or hit:
            count += 1
            values += found
            lines[index] = ""
        if in_key and PRIVATE_BLOCK[1].search(line):
            in_key = False
    return "\n".join(lines), count, values


class Scrubber:
    """Takes hidden names and credentials out of anything read from a document or a commit message: a line holding a
    credential form goes whole, the value is removed wherever else it appears, and file-like words matching the secret patterns go."""

    def __init__(self, secrets, values=()):
        self.withheld = {}
        self.value_list = sorted({v for v in values if len(v) >= 4}, key=len, reverse=True)
        forms = [f for v in self.value_list for f in (v, quote(v, safe=""))]
        self.values = re.compile("|".join(map(value_pattern, forms)), re.I) if forms else None
        names = set()
        for rel in secrets:
            names.add(rel)
            names.update(s for s in rel.split("/") if is_secret(s))
        alternatives = "|".join(name_pattern(n) for n in sorted(names, key=len, reverse=True))
        # The lookahead lets a longer visible name through: config.env.example is not the hidden config.env.
        self.names = re.compile(rf"(?<![\w.-])(?:{alternatives})(?![\w-]|\.\w)", re.I) if names else None

    def __call__(self, text, where):
        text, count, _ = withhold_lines(text)
        if count:
            self.report(where, count)
        return self.scrub_kept(text)

    def scrub_kept(self, text):
        if self.values:
            text = self.values.sub("[hidden value]", text)
        if self.names:
            text = self.names.sub(lambda m: "[hidden name]" + "\n" * m.group(0).count("\n"), text)  # keeps line numbers true
        return hide_pattern_names(text)

    def config_text(self, text):
        """A field of dashboard_config.json. gather() has already counted the file's lines, so a line is not reported twice."""
        text, count, _ = withhold_lines(text)
        if count and CONFIG_SOURCE not in self.withheld:
            self.report(CONFIG_SOURCE, count)
        return self.scrub_kept(text)

    def report(self, where, count):
        def note(total):
            source, advice = (("Git history", "It stays in Git history until that history is rewritten, so change the credential.") if where == COMMIT_SOURCE
                              else ("the file", "Remove the credential from the file."))
            return (f"{where}: {total} line{' looks' if total == 1 else 's look'} like a credential and {'was' if total == 1 else 'were'} withheld from this page, with other copies of "
                    f"the matched values. Detection is by pattern and can miss things, so this says nothing about what else {source} or the page holds. {advice}")
        before = self.withheld.get(where, 0)
        if note(before) in PROBLEMS:
            PROBLEMS.remove(note(before))
        self.withheld[where] = before + count
        note_problem(note(before + count))

    def clean_json(self, raw, where):
        """A JSON file cannot lose a line and still parse, so an entry holding a credential goes instead."""
        drop = object()

        def clean(value, key=""):
            if isinstance(value, str):
                if credential_values(f"{key}: {value}" if key and key != "key" else value)[0] or credential_values(value)[0]:
                    self.report(where, 1)
                    return drop
                return self(value, where)
            if isinstance(value, list):
                return [c for c in (clean(v) for v in value) if c is not drop]
            if isinstance(value, dict):
                pairs = {k: clean(v, k) for k, v in value.items()}
                return drop if any(v is drop for v in pairs.values()) else pairs
            return value
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            pairs = {k: clean(v, k) for k, v in loaded.items()}
            return {k: v for k, v in pairs.items() if v is not drop}
        return loaded

    def holds_value(self, text):
        return bool(self.values and self.values.search(text))

    def leaks(self, text):
        if self.names and self.names.search(text) or (PHRASES and PHRASES.search(text)):
            return True
        return any(secret_word(m.group(0)) for m in FREE_WORD.finditer(text))


# --- Parsing the documents. Tolerant, because a page that silently reads nothing is worse than a crash.

def classify_link(url, base):
    """('web', url), ('local', workspace path), or ('refused', url) for script URLs and paths that leave the workspace."""
    if SAFE_WEB.match(url):
        return "web", url
    if url.startswith("#"):
        return "anchor", url
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", url) or url.startswith(("/", "\\")):
        return "refused", url
    path = unquote(url.split("#", 1)[0])
    try:
        return "local", (base / path).resolve().relative_to(ROOT).as_posix()
    except (ValueError, OSError):
        return "refused", url


def broken_links(texts=None):
    """Each problem with a link in the living documents. Reported on the page, never fatal to a build."""
    broken = []
    for rel, _ in LIVING_DOCS:
        doc = ROOT / rel
        text = (texts or {}).get(rel) if texts else (read_or_note(doc, rel) if doc.is_file() else None)
        if text is None:
            continue
        for number, line in unfenced(text):
            if line.lstrip().startswith("~~"):
                continue
            for _, url in find_links(line):
                kind, target = classify_link(url, doc.parent)
                if kind == "refused":
                    broken.append(f"{rel}:{number} -> {url} (not shown as a link: only web links and files in this workspace are)")
                elif kind == "local" and is_secret(target):
                    broken.append(f"{rel}:{number} -> a private-looking path (not shown)")
                elif kind == "local" and not (ROOT / target).exists():
                    broken.append(f"{rel}:{number} -> {url}")
    return broken


def project_link(label, url, base):
    kind, target = classify_link(url, base)
    if kind == "web":
        return label, target
    if kind == "local" and not is_secret(target):
        return label, target
    return label, ""  # shown as plain words


STATUS_LINE = (re.compile(r"^\*\*\s*status\s*:\s*(.+?)\s*\*\*\s*$", re.I), re.compile(r"^\*\*\s*status\s*:\s*\*\*\s*(.+)$", re.I),
               re.compile(r"^status\s*:\s*(.+)$", re.I))
NEXT_LINE = (re.compile(r"^\*\*\s*next\s*:\s*\*\*\s*(.*)$", re.I), re.compile(r"^\*\*\s*next\s*:\s*(.+?)\s*\*\*\s*$", re.I),
             re.compile(r"^next\s*:\s*(.+)$", re.I))
BULLET = re.compile(r"^[-*] ")


def first_match(patterns, text):
    for pattern in patterns:
        found = pattern.match(text)
        if found:
            return found.group(1)
    return None


def parse_projects(text, base=None):
    """Read groups and projects from the overview structure."""
    base = base or OVERVIEW.parent
    projects, group, current = [], "", None
    field = None
    for _, line in unfenced(text):
        if line.startswith("## "):
            group, current, field = line[3:].strip(), None, None
        elif line.startswith("### "):
            current = {"group": group, "name": line[4:].strip(), "status": "", "next": "", "summary": "", "links": []}
            projects.append(current)
            field = "summary"
        elif current is not None:
            stripped = line.strip()
            status = first_match(STATUS_LINE, stripped)
            if status is not None:
                current["status"], field = status, "summary"
                continue
            following = first_match(NEXT_LINE, stripped)
            if following is not None:
                current["next"], field = following, "next"
                continue
            if not stripped:
                if field == "summary" and current["summary"]:
                    field = None
                elif field == "next":
                    field = None
                continue
            if find_links(stripped) and not re.sub(r"[|\s]", "", LINK.sub("", stripped)):
                current["links"] += [project_link(label, url, base) for label, url in find_links(stripped)]
                field = None
            elif field in ("summary", "next") and not BULLET.match(stripped):
                current[field] = (current[field] + " " + stripped).strip()
            else:
                current["links"] += [project_link(label, url, base) for label, url in find_links(stripped)]
    return projects


NEED_ITEM = re.compile(r"^(?:[-*+]|\d+[.)]) +")


def needs_sections(text):
    """The lines under each needs heading. A repeated heading is read too, so nothing under it is lost."""
    wanted = "## " + CONFIG["needs_heading"].strip().casefold()
    lines = [line for _, line in unfenced(text)]
    sections = []
    for index, line in enumerate(lines):
        if line.strip().casefold() == wanted:
            rest = lines[index + 1:]
            stop = next((i for i, later in enumerate(rest) if re.match(r"^##? ", later)), len(rest))
            sections.append(rest[:stop])
    return sections


def needs_section(text):
    sections = needs_sections(text)
    return [line for section in sections for line in section] if sections else None


def parse_user_items(text):
    items, current = [], None
    for line in needs_section(text) or []:
        start = NEED_ITEM.match(line)
        if start:
            current = [line[start.end():].strip()]
            items.append(current)
        elif current is not None and line.strip():
            current.append(line.strip())
    return [" ".join(parts) for parts in items]


def stray_need_lines(text):
    """Lines in a needs section before its first list item. They hold words the page cannot show as items."""
    stray = []
    for line in needs_section(text) or []:
        if NEED_ITEM.match(line):
            break
        if line.strip():
            stray.append(line.strip())
    return stray


def document_notes(rel, text):
    """Things that make a document read as emptier than it is. Named here so the page never claims 'nothing' in silence."""
    opened = None
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            opened = None if opened else number
    if opened:
        note_problem(f"{rel}:{opened} opens a code fence that never closes, so everything after that line is ignored.")
    if rel == LEDGER_REL:
        if len(needs_sections(text)) > 1:
            note_problem(f"{rel} has the heading '## {CONFIG['needs_heading']}' more than once. All of them were read. Merge them into one.")
        stray = stray_need_lines(text)
        if stray:
            note_problem(f"{rel}: {len(stray)} line{'' if len(stray) == 1 else 's'} under '## {CONFIG['needs_heading']}' {'is' if len(stray) == 1 else 'are'} not a list item, so not shown. Start each item with '- '. First: {stray[0][:60]}")


def parse_decisions(text):
    found = []
    for number, line in unfenced(text):
        match = DECISION.match(line)
        if match:
            found.append({"id": match.group(1), "title": match.group(2).strip(), "line": number})
    return found


def word_hit(text, words):
    """A whole word or phrase, not negated or qualified: 'not live', 'half done', 'unblocked', 'alive' and 'live soon' do not count."""
    for word in words:
        for match in re.finditer(rf"(?<![\w-]){re.escape(str(word).lower())}(?![\w])", text):
            if re.search(r"\b(not|never|isn't|aren't|no longer|half|almost|nearly|partly|partially|mostly)[\s-]+((yet|quite|fully|really)[\s-]+)?$", text[:match.start()]):
                continue
            if re.match(r"\s+(soon|later|pending|planned|next)\b", text[match.end():]):
                continue
            return True
    return False


def status_kind(status):
    """A status with no recognised word claims nothing, so it counts as an idea, never as built."""
    return read_status(status) or "idea"


def read_status(status):
    """The kind a status names, or None if no word in it is recognised."""
    if not status:
        return "none"
    words = CONFIG["status_words"]
    lowered = status.lower()
    if word_hit(lowered, words.get("blocked", [])):
        return "blocked"
    # The first clause says what exists today; later clauses describe what is still to come.
    lowered = lowered.split(";", 1)[0]
    if word_hit(lowered, words.get("live", [])):
        return "live"
    if word_hit(lowered, words.get("idea", [])):
        return "idea"
    return "local" if word_hit(lowered, words.get("local", [])) else None


def explorer_url(rel):
    return REVEAL_SCHEME + ":" + quote(rel, safe="/")


def encoded_path(path):
    """A path for a URL. POSIX and Windows roots both lose the leading slash, so no double slash appears."""
    return quote(path.lstrip("/"), safe="/:")


def editor_setup():
    """(URL template or None for plain relative links, tooltip)."""
    editor = CONFIG["editor"]
    if editor in EDITORS:
        return EDITORS[editor]
    if editor == "none":
        return None, "Open the file"
    if "{path}" in editor and re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", editor):
        return editor, "Open in your editor"
    note_problem("dashboard_config.json: 'editor' must be vscode, cursor, zed, none or a URL template with {path}. Using none.")
    return None, "Open the file"


EDITOR_TEMPLATE, EDITOR_TITLE = editor_setup()


def file_url(rel, line=None):
    if EDITOR_TEMPLATE is None:
        return f"{ROOT_URL}/{url_segments(rel)}"
    url = EDITOR_TEMPLATE.replace("{path}", encoded_path((ROOT / rel).as_posix()))
    return url.replace("{line}", str(line)) if line else url.replace(":{line}", "").replace("{line}", "")


def esc(value):
    return html.escape(str(value), quote=True)


def inline(text):
    """Flatten links, escape prose, then show Markdown code and bold in a readable form."""
    out = esc(LINK.sub(lambda m: m.group(1), text))
    out = re.sub(r"~~(.+?)~~", r"<s>\1</s>", out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", out)


def path_links(rel, label=None):
    label = label if label is not None else PurePosixPath(rel).name
    name = f'<a href="{esc(file_url(rel))}" title="{esc(EDITOR_TITLE)}">{esc(label)}</a>'
    if not REVEAL_SCHEME:
        return name
    return f'{name} <a class="reveal" href="{esc(explorer_url(rel))}" title="Show in File Explorer: {esc(rel)}">Show in Explorer</a>'


def created_time(info):
    """Creation time where the system really has one. Linux's st_ctime is something else, so it reports None."""
    born = getattr(info, "st_birthtime", None)
    if born is None and os.name == "nt":
        born = info.st_ctime
    return int(born) if born is not None else None


def recent_activity(paths, stat=None, limit=ACTIVITY_LIMIT, committed=None):
    """Newest changed and created entries, split into documents and other files."""
    stat = stat or (lambda rel: (ROOT / rel).stat())
    documents, files = [], []
    created_known = True
    for rel in paths:
        suffix = PurePosixPath(rel).suffix.lower()
        if rel.startswith(ACTIVITY_SKIP) or suffix in ACTIVITY_SKIP_TYPES or is_own(rel):
            continue
        try:
            info = stat(rel)
        except OSError:
            continue
        created = created_time(info)
        created_known = created_known and created is not None
        last_commit = (committed or {}).get(rel)
        changed = min(int(info.st_mtime), last_commit) if last_commit else int(info.st_mtime)
        if created and last_commit:
            created = min(created, last_commit)
        entry = {"path": rel, "changed": changed, "created": created or 0}
        (documents if suffix in DOCUMENT_TYPES else files).append(entry)

    def newest(entries, key):
        return sorted(entries, key=lambda e: (-e[key], e["path"]))[:limit]
    return {"files_changed": newest(files, "changed"), "files_created": newest(files, "created"),
            "docs_changed": newest(documents, "changed"), "docs_created": newest(documents, "created"),
            "created_known": created_known}


def covered_by(path, linked):
    return any(path == item or path.startswith(item.rstrip("/") + "/") for item in linked)


# --- The fire section. Its words are in words.json; its numbers are counted here from real files, and anything
# whose evidence has gone, or whose number is absent or zero, is dropped rather than shown.

def plain(text):
    """Markdown to plain words."""
    return re.sub(r"[*`~]", "", LINK.sub(lambda m: m.group(1), text))


def first_sentence(text, limit=170):
    sentence = re.split(r"(?<=[.!?])\s", plain(text), maxsplit=1)[0]
    return sentence if len(sentence) <= limit else sentence[:limit].rsplit(" ", 1)[0] + "..."


def open_items(items):
    return [i for i in items if not i.startswith("~~")]


def spark_pool(items):
    """Short labels for things the developer can look at now, leaving out what waits on someone else."""
    labels = []
    for item in open_items(items):
        lead = re.match(r"\*\*(.+?)\*\*", item)
        label = plain(lead.group(1)).rstrip(":") if lead and " " in plain(lead.group(1)).strip() else first_sentence(item)
        if "waiting on" not in label.lower():
            labels.append(label)
    return labels


def assign_project_ids(projects):
    seen = set()
    for index, project in enumerate(projects):
        slug = re.sub(r"[^\w]+", "-", project["name"].lower()).strip("-_")
        slug = "p-" + slug if slug else f"p-{index}"
        project["id"] = f"{slug}-{index}" if slug in seen else slug
        seen.add(project["id"])


def is_web(target):
    return bool(SAFE_WEB.match(target))


def hot_projects(projects, committed=None, limit=HOT_PROJECTS, now=None):
    """Projects under way whose own files changed in the last HOT_DAYS, dated as the sidebar dates them. Living documents
    change for every project. If every card would qualify, none is marked, because the badge would then say nothing."""
    floor = (now or time.time()) - HOT_DAYS * 86400
    living = {OVERVIEW_REL, LEDGER_REL, DECISIONS_REL, "README.md", "CHANGELOG.md"}
    stamps = []
    for project in projects:
        newest = 0
        for _, target in project["links"]:
            if not target or is_web(target) or target in living or not (ROOT / target).exists():
                continue
            changed = (ROOT / target).stat().st_mtime
            last_commit = (committed or {}).get(target)
            newest = max(newest, min(changed, last_commit) if last_commit else changed)
        if newest >= floor and status_kind(project["status"]) not in ("idea", "none"):
            stamps.append((newest, project["id"]))
    hot = {pid for _, pid in sorted(stamps, reverse=True)[:limit]}
    return set() if len(hot) >= len(projects) else hot


def live_count(spec):
    """Optional: how many things the named record says are out in the world. None if there is no record."""
    if not spec:
        return None
    rel = inside_root(spec.get("path"))
    if rel is None or is_secret(rel) or not (ROOT / rel).is_file():
        note_problem("The live record named in dashboard_config.json was not found or looks private, so the page makes no claim about it.")
        return None
    for field in ("section", "match"):
        if spec.get(field) is not None and not isinstance(spec[field], str):
            note_problem(f"dashboard_config.json: live_record '{field}' must be text, so the page makes no claim about it.")
            return None
    text = read_or_note(ROOT / rel, rel)
    if text is None:
        return None
    if spec.get("section"):
        found = re.search(rf"^#+ {re.escape(spec['section'])}\s*$(.*?)(?=^#+ |\Z)", text, re.M | re.S)
        if not found:
            note_problem(f"The live record {rel} has no section called {spec['section']!r}.")
            return None
        text = found.group(1)
    lines = text.splitlines()
    rows = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        is_rule = bool(re.fullmatch(r"\|[\s:|-]+\|", stripped))
        heads_table = index + 1 < len(lines) and re.fullmatch(r"\|[\s:|-]+\|", lines[index + 1].strip())
        if (stripped.startswith("|") and not is_rule and not heads_table) or BULLET.match(line):
            rows.append(stripped)
    if spec.get("match"):
        try:
            rows = [r for r in rows if re.search(spec["match"], r)]
        except re.error as error:
            note_problem(f"dashboard_config.json: live_record 'match' is not a valid pattern ({error}).")
            return None
    return len(rows)


def heat_summary(kinds):
    """Progress as a share of the goal, every project alight from its first idea."""
    if not kinds:
        return {"heat": 0, "next_mark": 0, "mark_steps": 0}
    top = max(HEAT.values()) * len(kinds) or 1
    heat = sum(HEAT[k] for k in kinds)
    share = round(100 * heat / top)
    marks = sorted(m for m in CONFIG["heat_marks"] if isinstance(m, int)) or [100]
    mark = next((m for m in marks if 100 * heat < m * top), marks[-1])
    return {"heat": share, "next_mark": mark, "mark_steps": max(0, math.ceil(mark * top / 100 - heat))}


def count_matching(paths, patterns, name):
    compiled = []
    for pattern in patterns if isinstance(patterns, list) else [patterns]:
        try:
            compiled.append(re.compile(pattern))
        except (re.error, TypeError) as error:
            note_problem(f"dashboard_config.json: count_files '{name}' has a bad pattern ({error}).")
    return sum(1 for path in paths if any(p.search(path) for p in compiled))


def preservation_logs():
    try:
        found = [p for p in ROOT.glob(CONFIG["preservation_glob"]) if p.is_file()]
    except (ValueError, NotImplementedError, OSError):
        note_problem("dashboard_config.json: 'preservation_glob' must be a relative pattern.")
        return []
    inside = [p for p in found if p.resolve().is_relative_to(ROOT) and not is_secret(p.resolve().relative_to(ROOT).as_posix())]
    if len(inside) != len(found):
        note_problem("dashboard_config.json: 'preservation_glob' matched files outside this workspace or with private-looking names. They were not counted.")
    return inside


def fire_facts(projects, decisions, paths, commits=0):
    kinds = [status_kind(p["status"]) for p in projects]
    facts = {"commits": commits, "decisions": len(decisions), "files": len(paths), "projects": len(projects),
             "under_way": sum(k in ("local", "blocked") for k in kinds), **heat_summary(kinds)}
    for name, patterns in {"tests": TEST_PATTERNS, **CONFIG["count_files"]}.items():
        facts[name] = count_matching(paths, patterns, name)
    logs = preservation_logs()
    if logs:
        facts["preserved"] = sum(max(0, len([l for l in (read_or_note(p, p.name) or "").splitlines() if l.strip()]) - 1) for p in logs)
    live = live_count(CONFIG["live_record"])
    if live is not None:
        facts["live_total"] = live
    return facts


def fill(template, facts, where):
    """Numbers into words. None, so the caller drops the line, if a number is absent or zero or the text is malformed."""
    if not isinstance(template, str):
        note_problem(f"words.json: {where} must be text.")
        return None
    names = re.findall(r"\{(\w+)\}", template)
    leftover = re.sub(r"\{\w+\}", "", template)
    if "{" in leftover or "}" in leftover:
        note_problem(f"words.json: {where} has a stray brace and was dropped.")
        return None
    for name in names:
        if name not in facts and name not in ("preserved", "live_total", "commits"):
            note_problem(f"words.json: {where} uses unknown number {{{name}}} and was dropped.")
            return None
        if not facts.get(name):
            return None
    filled = re.sub(r"\{(\w+)\}", lambda m: str(facts[m.group(1)]), template)
    return re.sub(r"\b1 ([a-z]+)s\b", r"1 \1", filled)  # "1 decision", never "1 decisions"


def squeezed(text):
    return " ".join(text.split())


def evidence_text(rel):
    """The squeezed text of a file a quote may cite, or None. Hidden files, the kit and unedited starters never count."""
    target = inside_root(rel)
    if target is None or is_secret(target) or is_hidden(target) or is_own(target) or target in UNEDITED_STARTERS:
        return None
    path = ROOT / target
    if not path.is_file() or path.stat().st_size > 5_000_000:
        return None
    text = read_or_note(path, target)
    return None if text is None else squeezed(text)


def picture(name, where):
    if (ART_DIR / name).is_file():
        return asset(name)
    note_problem(f"words.json: {where} names the image {name!r}, which is not in the art folder.")
    return asset("placeholder.png")


NUMBER_WORD = re.compile(r"\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\w+teen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
                         r"|hundred|hundreds|thousand|thousands|million|millions|billion|billions|dozen|dozens)\b", re.I)
PERSON_NAME = re.compile(r"^[A-Z][a-z]+(?: [A-Z][a-z'-]+)+$")


def typed_numbers(text):
    """Numbers written by hand, in digits or words. {name} slots are counted from files, so they do not count here."""
    text = re.sub(r"\{\w+\}", "", text)
    return re.findall(r"\d+", text) + NUMBER_WORD.findall(text)


def check_claims(words):
    """Claims the build cannot verify, reported on the page and by the doctor."""
    for key in ("marquee", "about"):
        for index, text in enumerate(words[key]):
            if typed_numbers(text):
                note_problem(f"words.json: {key}[{index}] has a typed number, but the page promises its numbers come from files. Use a {{number}} name, or remove it.")
    for index, friend in enumerate(words["friends"]):
        if not friend.get("placeholder") and PERSON_NAME.match(friend["name"]):
            note_problem(f"words.json: friends[{index}] looks like a real person's name. Friends are made-up characters, so do not put words in a real person's mouth.")
    profile = words["profile"]
    if not profile.get("placeholder") and profile["name"] == "The Director":
        note_problem("words.json: the profile is marked as filled in but still has the starter name.")


def display_name(entry):
    return f"{entry['name']} (placeholder)" if entry.get("placeholder") else entry["name"]


def usable_words(words, facts):
    """Fill in the numbers. Returns the kept lines and comments, and a sentence for each thing that had to be dropped."""
    lines, comments, dropped = [], [], []
    check_claims(words)

    def drop(reason):
        dropped.append(reason)
        note_problem(reason)
    for index, line in enumerate(words["lines"]):
        if line.get("placeholder"):
            continue
        text, source = squeezed(line["text"]), evidence_text(line["file"])
        if len(text) < MIN_QUOTE_CHARS or len(text.split()) < MIN_QUOTE_WORDS:
            drop(f"words.json: lines[{index}] is too short to stand as a quote (at least {MIN_QUOTE_WORDS} words and {MIN_QUOTE_CHARS} characters), so it was dropped.")
        elif source is None or text not in source:
            drop(f"words.json: lines[{index}] quote not found in {line['file']}, so it was dropped.")
        else:
            # The file is the source. A name is shown only if the file itself carries it, so nobody is credited by assertion.
            who, target = squeezed(str(line.get("who", ""))), inside_root(line["file"])
            lines.append({"text": line["text"], "who": who if who and who in source else target, "href": file_url(target)})
    for index, friend in enumerate(words["friends"]):
        evidence = friend.get("evidence")
        if evidence is not None:
            source = evidence_text(friend.get("file", ""))
            if not isinstance(evidence, str):
                drop(f"words.json: friends[{index}].evidence must be text.")
                continue
            if source is None or squeezed(evidence) not in source:
                drop(f"words.json: friends[{index}].evidence was not found in its file, so the comment was dropped.")
                continue
        if evidence is None and not friend.get("placeholder") and not re.search(r"\{\w+\}", friend["says"]):
            drop(f"words.json: friends[{index}].says has no {{number}} name and no evidence, so nothing backs it and it was dropped.")
            continue
        if any(number.casefold() not in (evidence or "").casefold() for number in typed_numbers(friend["says"])):
            drop(f"words.json: friends[{index}].says has a number that is not counted from a file. Use a {{number}} name, or evidence holding that number.")
            continue
        text = fill(friend["says"], facts, f"friends[{index}].says")
        if text is not None:
            comments.append({"name": display_name(friend), "pic": picture(friend["pic"], f"friends[{index}]"), "text": text})
    if not lines:
        lines.append({"text": "No quotes yet. Copy a real line from a file in this workspace into words.json and it will appear here.",
                      "who": "Placeholder: words.json", "href": file_url(WORDS_REL), "placeholder": True})
    return lines, comments, dropped


MIN_QUOTE_CHARS, MIN_QUOTE_WORDS = 12, 3
FALLBACK_WORDS = {
    "heading": "KEEP THE FIRE LIT",
    "marquee": ["this page remembers so you don't have to"],
    "about": ["Every number on this page comes from the real files."],
    "paintings": [{"key": "", "title": "No painting yet", "focus": "50% 50%", "credit": "Placeholder"}], "lines": [], "friends": [],
    "loops": {"spark": {"title": "SPARK", "when": "Under a minute.", "button": "roll again"},
              "campfire": {"title": "CAMPFIRE", "when": "About 20 minutes.", "button": "roll again"},
              "beacon": {"title": "BEACON", "when": "Weeks."}},
    "late_night": {},
    "profile": {"name": "Nobody yet", "tagline": "", "mood": "", "network": "", "interests": [], "placeholder": True},
    "marks": [], "construction": "UNDER CONSTRUCTION", "webring": "This site is a member of the WEBRING",
    "badges": [], "song": "Keep the Fire Lit (MIDI version)", "mascot": {},
}
REQUIRED_FIELDS = {"paintings": ("key", "title"), "lines": ("text", "file"), "friends": ("pic", "name", "says"),
                   "marks": ("title", "fact", "meaning"), "badges": ("text",)}


def load_words(scrub):
    """words.json, checked. Each thing wrong with it is reported by key, and the rest of the page still builds."""
    words = json.loads(json.dumps(FALLBACK_WORDS))
    if not WORDS.exists():
        note_problem(f"{WORDS_REL} is missing, so the fire section has only its plain defaults.")
        return words
    raw = read_or_note(WORDS, WORDS_REL)
    if raw is None:
        return words
    try:
        loaded = scrub.clean_json(raw, WORDS_REL)
        if not isinstance(loaded, dict):
            raise ValueError("the top level must be an object")
    except RecursionError:
        note_problem(f"{WORDS_REL} could not be read (it is nested too deeply), so the fire section has only its plain defaults.")
        return words
    except ValueError as error:
        note_problem(f"{WORDS_REL} could not be read ({error}), so the fire section has only its plain defaults.")
        return words
    for key, fallback in FALLBACK_WORDS.items():
        if key not in loaded:
            note_problem(f"words.json: '{key}' is missing, using a plain default.")
        elif type(loaded[key]) is not type(fallback):
            note_problem(f"words.json: '{key}' has the wrong type, using a plain default.")
        else:
            words[key] = loaded[key]
    for key in ("marquee", "about"):
        words[key] = [v for v in words[key] if isinstance(v, str)]
    for key, fields in REQUIRED_FIELDS.items():
        kept = []
        for index, entry in enumerate(words[key]):
            if isinstance(entry, dict) and all(isinstance(entry.get(f), str) for f in fields):
                kept.append(entry)
            else:
                note_problem(f"words.json: {key}[{index}] needs {', '.join(fields)} and was dropped.")
        words[key] = kept
    for name, fallback in FALLBACK_WORDS["loops"].items():
        given = words["loops"].get(name)
        words["loops"][name] = {**fallback, **(given if isinstance(given, dict) else {})}
    for field, fallback in FALLBACK_WORDS["profile"].items():
        if field != "placeholder":  # removing the flag is how a profile is marked as filled in
            words["profile"].setdefault(field, fallback)
    if not isinstance(words["profile"]["interests"], list):
        note_problem("words.json: profile.interests must be a list and was dropped.")
        words["profile"]["interests"] = []
    late = words["late_night"]
    if late and not all(isinstance(late.get(f), str) for f in ("pic", "name", "says")):
        note_problem("words.json: late_night needs pic, name and says and was dropped.")
        words["late_night"] = {}
    usable = []
    for index, art in enumerate(words["paintings"]):
        if not art["key"]:
            continue
        if (ART_DIR / f"{art['key']}.jpg").is_file():
            usable.append(art)
        else:
            note_problem(f"words.json: paintings[{index}] has no image at art/web/{art['key']}.jpg and was dropped.")
    words["paintings"] = usable or FALLBACK_WORDS["paintings"]
    return words


def painting_url(art):
    return asset(f"{art['key']}.jpg") if art["key"] else asset("placeholder.png")


def parse_guestbook(text):
    found = re.search(r"^## Signatures\s*$(.*)", text, re.M | re.S)
    return [l[2:].strip() for l in (found.group(1) if found else "").splitlines() if l.startswith("- ")]


def rune_ring(projects, facts):
    parts = []
    count = len(projects) or 1
    for index, project in enumerate(projects):
        kind = status_kind(project["status"])
        angle = 2 * math.pi * index / count - math.pi / 2
        x1, y1 = 150 + 84 * math.cos(angle), 150 + 84 * math.sin(angle)
        reach = 84 + RUNE_LENGTH[kind]
        x2, y2 = 150 + reach * math.cos(angle), 150 + reach * math.sin(angle)
        coords = f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"'
        status = plain(project["status"]) or "No status yet"
        name = plain(project["name"])
        parts.append(f'<a class="rune {kind}" href="#{esc(project["id"])}" data-id="{esc(project["id"])}" data-name="{esc(name)}" '
                     f'data-status="{esc(status)}" aria-label="{esc(name)}: {esc(status)}"><line class="hit" {coords}/><line class="mark" {coords}/></a>')
    points = [(150 + 72 * math.cos(2 * math.pi * i * 4 / 9 - math.pi / 2), 150 + 72 * math.sin(2 * math.pi * i * 4 / 9 - math.pi / 2)) for i in range(9)]
    star = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return (f'<svg class="ring" viewBox="0 0 300 300" role="group" aria-label="One rune for each project">'
            f'<g class="ring-spin"><path id="rune-path" fill="none" d="M150,150 m-134,0 a134,134 0 1,1 268,0 a134,134 0 1,1 -268,0"/>'
            f'<text class="runes"><textPath href="#rune-path">{(RUNES + " ") * 3}</textPath></text></g>'
            f'<g class="ring-back"><polygon class="star" points="{star}"/></g>{"".join(parts)}'
            f'<text class="heat" x="150" y="160">{facts["heat"]}%</text><text class="heat-label" x="150" y="178">lit</text></svg>')


def odometer(value, ident="", animated=True, places=6):
    cells = "".join(f"<b>{d}</b>" for d in str(value).zfill(places))
    data = f' data-value="{value}"' if animated else ""
    return f'<span class="odo"{ident}{data}>{cells}</span>'


def flame():
    return f'<img class="ficon" src="{asset("flame_icon.gif")}" alt="">'


def render_fire_top(words, facts, projects, title):
    rng = random.Random(1999)
    first_art = words["paintings"][0]
    embers = "".join(f'<span class="ember" style="--x:{rng.randint(3, 97)}%;--t:{rng.uniform(3, 7):.1f}s;--d:{rng.uniform(0, 7):.1f};--dx:{rng.randint(-40, 40)}px"></span>' for _ in range(16))
    filled = [fill(m, facts, f"marquee[{i}]") for i, m in enumerate(words["marquee"])]
    crawl = "".join(f"<span>{esc(m)}</span><i>*</i>" for m in filled if m is not None) or f"<span>{esc(title)}</span><i>*</i>"
    about = "".join(f"<li>{flame()}<span>{esc(a)}</span></li>" for a in words["about"])
    kinds = [status_kind(p["status"]) for p in projects]
    tally = lambda *names: sum(k in names for k in kinds)
    loops = words["loops"]
    die = f'<img src="{asset("die.png")}" alt="">'
    steps = facts["mark_steps"]
    if not projects:
        tip = "No projects yet"
    elif steps:
        tip = f"{steps} step{'' if steps == 1 else 's'} to the {facts['next_mark']}% mark"
    else:
        tip = "Every project is burning at its hottest"
    return f"""<section id="fire" class="fire" aria-label="{esc(words['heading'])}">
<div class="marquee" aria-hidden="true"><div>{crawl}{crawl}{crawl}{crawl}</div></div>
<div class="fire-top"><figure class="aura" id="art-figure"><div class="aura-flames"></div><div class="aura-glow"></div>
<button class="art-frame" id="art-next" title="Next painting" aria-label="Show the next painting"><img id="art-a" src="{painting_url(first_art)}" alt=""><img id="art-b" class="off" alt=""><span class="art-burn"></span>{embers}</button>
<figcaption><span id="art-credit">{esc(first_art.get('credit', DEFAULT_CREDIT))}</span>: <b id="art-title">{esc(first_art['title'])}</b>. Click it for the next one.</figcaption></figure>
<div class="fire-words"><h2 class="flame-text">{esc(words['heading'])}</h2><blockquote id="line"></blockquote>
<p class="from" id="line-box">From <a id="line-from" href="#"></a> <button id="line-next" class="btn" type="button">another line</button></p>
<ul class="about">{about}</ul>
<div class="song" id="song"><span class="bars"><i></i><i></i><i></i><i></i></span><span>Profile song: {esc(words['song'])}</span><button id="song-play" class="btn" type="button">&#9654; play</button></div></div></div>
<div class="fire-hr" aria-hidden="true"></div>
<div class="fires">
<article class="loop"><h3>{flame()}{esc(loops['spark'].get('title', ''))}</h3><p class="when">{esc(loops['spark'].get('when', ''))}</p><p class="pick" id="spark"></p><p class="go"><a href="#needs">See it under Needs you</a><button id="spark-roll" class="btn" type="button">{die}{esc(loops['spark'].get('button', 'roll again'))}</button></p></article>
<article class="loop"><h3>{flame()}{esc(loops['campfire'].get('title', ''))}</h3><p class="when">{esc(loops['campfire'].get('when', ''))}</p><p class="pick" id="campfire"></p><p class="go"><a id="campfire-go" href="#projects">Go to the project</a><button id="campfire-roll" class="btn" type="button">{die}{esc(loops['campfire'].get('button', 'roll again'))}</button></p></article>
<article class="loop beacon"><h3>{flame()}{esc(loops['beacon'].get('title', ''))}</h3><p class="when">{esc(loops['beacon'].get('when', ''))}</p><div class="beacon-body">{rune_ring(projects, facts)}<div class="ring-side">
<p class="ring-tip" id="ring-tip">{esc(tip)}<small>Point at a rune to see its project.</small></p>
<ul class="legend"><li class="live"><i></i>{tally('live')} blazing, live or shipped</li><li class="local"><i></i>{tally('local')} burning, built locally</li><li class="blocked"><i></i>{tally('blocked')} smothered, blocked for now</li><li><i></i>{tally('idea', 'none')} sparks, ideas</li></ul>
<p class="fine">Heat: idea {HEAT['idea']}, built {HEAT['local']}, blocked {HEAT['blocked']}, live {HEAT['live']}. A step is one project moving up one.</p></div></div></article>
</div></section>"""


def render_friend_space(words, facts, signatures):
    profile = words["profile"]
    placeholder = bool(profile.get("placeholder"))
    interests = "" if placeholder else "".join(
        f"<tr><th>{esc(row[0])}</th><td>{esc(row[1])}</td></tr>" for row in profile["interests"]
        if isinstance(row, list) and len(row) == 2)
    interest_box = f'<table class="interests">{interests}</table>' if interests else '<div class="box-body"><span class="ph">Nothing filled in yet.</span></div>'
    marks = "".join(f'<div class="mark-row"><div><b class="t">{esc(m["title"])}</b><small>{esc(m["meaning"])}</small></div>{odometer(facts[m["fact"]])}</div>'
                    for m in words["marks"] if facts.get(m["fact"]))
    friends = "".join(f'<figure class="friend"><button type="button" data-name="{esc(display_name(f))}">{esc(display_name(f))}<img src="{picture(f["pic"], "friends")}" alt=""></button></figure>' for f in words["friends"])
    guests = "".join(f'<p class="guest">{inline(g)}</p>' for g in reversed(signatures[-3:])) or '<p class="guest">Nobody yet. Be first!!!</p>'
    badge_rows = []
    for badge in words["badges"]:
        target = inside_root(badge.get("file", "")) if badge.get("file") else None
        if target and not is_secret(target) and (ROOT / target).exists():
            badge_rows.append(f'<a class="b88" href="{esc(file_url(target))}">{esc(badge["text"])}</a>')
        else:
            badge_rows.append(f'<span class="b88">{esc(badge["text"])}</span>')
    hits = odometer(1, ' id="hits"', animated=False)
    name_label = '<span class="ph"> (placeholder)</span>' if placeholder else ""
    owner = esc(profile["name"])
    # Nothing here is claimed until someone has really filled it in: a count of starter entries is not a count of friends.
    real_friends = sum(1 for f in words["friends"] if not f.get("placeholder"))
    friend_count = f"{real_friends} friend{'' if real_friends == 1 else 's'}"
    friend_title = "Friend Space: no real friends yet" if not real_friends else f"Friend Space: {friend_count}" if placeholder else f"{owner}'s Friend Space: {friend_count}"
    mood = "" if placeholder else f'<p class="mood"><b>Mood:</b> {esc(profile["mood"])} {flame()}</p>'
    network = "" if placeholder or not profile["network"] else f'<div class="network">{esc(profile["network"])}</div>'
    construction = fill(words["construction"], facts, "construction") or "UNDER CONSTRUCTION"
    return f"""<section id="friends" class="fire friend-space" aria-label="Friend Space">
<div><div class="box"><div class="box-body"><p class="flame-name">{owner}{name_label}</p><p class="tagline">{esc(profile['tagline'])}</p>
<div class="emblem-wrap"><img class="emblem" src="{asset('emblem.png')}" alt=""></div>
{mood}<p class="online"><span class="is-on">Online Now!</span><span class="is-off">Updater off</span></p></div></div>
<div class="box"><h3>Interests</h3>{interest_box}</div>
<div class="box"><h3>Marks</h3><div class="box-body">{marks}<div class="hits">You are visitor number<br>{hits}<br><small>A true count, in this browser. It's just you, and that's plenty.</small></div></div></div></div>
<div>{network}
<div class="box"><h3>{friend_title}</h3><div class="box-body"><div class="top8">{friends}</div></div></div>
<div class="box"><h3>Friends Comments</h3><div class="box-body"><p class="ph">Flavor text from made-up characters. Their numbers are counted from real files.</p><div class="comments" id="comments"></div><p><button id="more-comments" class="btn" type="button">more comments</button></p></div></div></div>
<div class="strip"><div class="construction"><span>{esc(construction)}</span></div>
<div class="strip-row"><div class="box blue"><h3>Webring</h3><div class="box-body">{esc(words['webring'])} <span class="ph">(decoration: it only walks this page's own projects)</span><div class="ring-nav"><button id="ring-prev" class="btn" type="button">&lt;&lt; prev</button><button id="ring-random" class="btn" type="button">random</button><button id="ring-next" class="btn" type="button">next &gt;&gt;</button></div></div></div>
<div class="box blue"><h3>Guestbook</h3><div class="box-body">{guests}<a href="{esc(file_url(GUESTBOOK_REL))}">Sign the guestbook</a></div></div></div>
<div class="badges">{"".join(badge_rows)}</div></div></section>"""


def fire_data(words, facts, projects, items, lines, comments):
    camps = [{"name": plain(p["name"]), "next": first_sentence(p["next"]), "id": p["id"]} for p in projects if p["next"]]
    late, mascot = words["late_night"], words["mascot"]
    image = mascot.get("image") if isinstance(mascot.get("image"), str) else ""
    data = {"art": [{"src": painting_url(a), "title": a["title"], "focus": a.get("focus", "50% 50%"), "credit": a.get("credit", DEFAULT_CREDIT)} for a in words["paintings"]],
            "lines": lines, "comments": comments, "sparks": spark_pool(items), "camps": camps,
            "projects": [p["id"] for p in projects],
            "mascot": {"img": asset(image), "word": str(mascot.get("word", ""))[:24].lower()} if image and (ART_DIR / image).is_file() else None,
            "late": {"name": display_name(late), "pic": picture(late["pic"], "late_night"), "says": late["says"]} if late else None}
    return json.dumps(data).replace("</", "<\\/").replace("<!--", "<\\!--")


def build_html(g):
    projects, items, decisions, tracked, ignored = g["projects"], g["items"], g["decisions"], g["tracked"], g["ignored"]
    words, facts, broken, secrets = g["words"], g["facts"], g["broken"], g["secrets"]
    hot = g["hot"]
    linked = {t for p in projects for _, t in p["links"] if t and not is_web(t)}
    skip = tuple(s for s in CONFIG["unlinked_skip"] if isinstance(s, str))
    unlinked = [p for p in tracked if not covered_by(p, linked) and not p.startswith(skip) and p not in (OVERVIEW_REL, LEDGER_REL, DECISIONS_REL)]

    cards = []
    groups = {}
    for project in projects:
        groups.setdefault(project["group"], []).append(project)
    for group, members in groups.items():
        cards.append(f'<h3 class="group">{esc(group)}</h3><div class="cards">')
        for p in members:
            kind = status_kind(p["status"])
            rows = []
            for label, target in p["links"]:
                if not target:
                    rows.append(f"<li>{esc(label)}</li>")
                elif is_web(target):
                    rows.append(f'<li><a href="{esc(target)}">{esc(label)}</a></li>')
                else:
                    rows.append(f"<li>{path_links(target, label)}</li>")
            links = "".join(rows)
            cards.append(
                f'<article class="card" id="{esc(p["id"])}" data-filter>'
                f'<h4>{esc(p["name"])}' + (f'<span class="hot" title="Its files changed in the last {HOT_DAYS} days">HOT!</span>' if p["id"] in hot else "") + '</h4>'
                + (f'<p class="status {kind}">{inline(p["status"])}</p>' if p["status"] else "")
                + (f'<p>{inline(p["summary"])}</p>' if p["summary"] else "")
                + (f'<p class="next"><strong>Next:</strong> {inline(p["next"])}</p>' if p["next"] else "")
                + (f"<ul class=\"links\">{links}</ul>" if links else "")
                + "</article>")
        cards.append("</div>")
    if not projects:
        cards.append(f'<div class="panel">No projects found in {esc(OVERVIEW_REL)}. Add one with a "### Project name" heading.</div>')

    if not g["ledger_found"]:
        empty_item = f"<li>The ledger {esc(LEDGER_REL)} is missing, so this list cannot say what is waiting.</li>"
    elif not g["needs_found"]:
        empty_item = f'<li>{esc(LEDGER_REL)} has no "## {esc(CONFIG["needs_heading"])}" section, so this list cannot say what is waiting.</li>'
    elif g["stray_needs"]:
        empty_item = f'<li>{esc(LEDGER_REL)} has words under this heading, but no list items this page can show. See the problems above.</li>'
    else:
        empty_item = "<li>Nothing waiting.</li>"
    item_html = "".join(f'<li data-filter>{inline(i)}</li>' for i in open_items(items)) or empty_item
    item_html += "".join(f'<li class="slain" data-filter><span class="slain-tag">SLAIN!</span>{inline(i)}</li>'
                         for i in items if i.startswith("~~"))
    decision_rows = "".join(
        f'<li data-filter><a href="{esc(file_url(DECISIONS_REL, d["line"]))}">{esc(d["id"])}</a> {esc(d["title"])}</li>'
        for d in reversed(decisions)) or f"<li>No decisions found in {esc(DECISIONS_REL)}.</li>"
    commit_rows = "".join(f"<li>{esc(c)}</li>" for c in g["commits"]) or f"<li>{esc(GIT_NOTE['text'] or 'No commits to show')}.</li>"

    budget = {"rows": max(1, CONFIG["max_file_rows"])}

    def tree(paths):
        folders = {}
        for path in paths:
            top = path.split("/", 1)[0] if "/" in path else "(workspace root)"
            folders.setdefault(top, []).append(path)
        parts = []
        for top, members in folders.items():
            limit = min(max(1, CONFIG["max_folder_rows"]), budget["rows"])
            budget["rows"] -= min(limit, len(members))
            rows = "".join(f'<li data-filter>{path_links(m, m)}</li>' for m in members[:limit])
            if len(members) > limit:
                rows += f'<li class="more">+{len(members) - limit} more not shown</li>'
            reveal = "" if top.startswith("(") or not REVEAL_SCHEME else f' <a class="reveal" href="{esc(explorer_url(top))}">Show in Explorer</a>'
            parts.append(f'<details data-tree><summary>{esc(top)} <span class="count">{len(members)}</span>{reveal}</summary><ul class="files">{rows}</ul></details>')
        return "".join(parts)

    entries = [(OVERVIEW_REL, "Overview"), (LEDGER_REL, "Ledger"), (DECISIONS_REL, "Decision log")]
    logs = preservation_logs()
    if logs:
        entries.append((logs[0].relative_to(ROOT).as_posix(), "Preserved originals"))
    entries.append((WORDS_REL, "Words on this page"))
    living = [f"<li>{path_links(rel, label)}</li>" for rel, label in entries if (ROOT / rel).exists()]
    for link in CONFIG["links"]:
        if not isinstance(link, dict) or not isinstance(link.get("label"), str):
            note_problem("dashboard_config.json: each entry in 'links' needs a label and a path or url.")
        elif isinstance(link.get("url"), str) and is_web(link["url"]):
            living.append(f'<li><a href="{esc(link["url"])}">{esc(g["scrub"].config_text(link["label"]))}</a></li>')
        elif inside_root(link.get("path")) and not is_secret(inside_root(link["path"])) and (ROOT / inside_root(link["path"])).exists():
            living.append(f"<li>{path_links(inside_root(link['path']), g['scrub'](link['label'], 'A link label'))}</li>")
        else:
            note_problem(f"dashboard_config.json: the link '{g['scrub'](link['label'], 'A link label')}' points at nothing, so it was left off.")

    hidden_note = ""
    if secrets:
        hidden_note = f"<p>{len(secrets)} file{'' if len(secrets) == 1 else 's'} left off this page because their names look private.</p>"
    main_tree = tree(tracked)
    unlinked_tree = tree(unlinked)
    ignored_block = ""
    if g["usable"]:
        ignored_block = f'<details data-tree><summary>Ignored by Git <span class="count">{len(ignored)}</span></summary>{tree(ignored)}</details>'
    # A title set in the config is checked like a document. The default is only the folder's own name.
    title = (g["scrub"].config_text(TITLE).strip() or f"{ROOT.name} Workspace") if CONFIG["title"].strip() else TITLE
    tagline = g["scrub"].config_text(CONFIG["tagline"])
    fire_top = render_fire_top(words, facts, projects, title)
    friend_space = render_friend_space(words, facts, g["signatures"])
    fire_json = fire_data(words, facts, projects, items, g["lines"], g["comments"])
    warnings = []
    if g["missing"]:
        rows = "".join(f"<li>{esc(m)}</li>" for m in g["missing"])
        warnings.append(f'<section class="warn"><h2>Still to fill in ({len(g["missing"])})</h2><ul>{rows}</ul></section>')
    if PROBLEMS:
        rows = "".join(f"<li>{esc(g['scrub'](p, 'A build note'))}</li>" for p in list(PROBLEMS))
        warnings.append(f'<section class="warn"><h2>Problems found while building ({len(PROBLEMS)})</h2><ul>{rows}</ul></section>')
    if broken:
        rows = "".join(f"<li>{esc(b)}</li>" for b in broken)
        warnings.append(f'<section class="warn"><h2>Broken links in the living documents ({len(broken)})</h2><ul>{rows}</ul></section>')

    head_script = json.dumps(STORAGE_NS)
    return PAGE.format(
        title=esc(title), tagline=f'<span class="sub">{esc(tagline)}</span>' if tagline else "",
        ns=head_script, respect_os="true" if CONFIG["motion"] == "respect-os" else "false",
        theme_css=read_text(THEME_CSS).replace("{{ART}}", ART_URL), theme_js=read_text(THEME_JS),
        fire_top=fire_top, friend_space=friend_space, fire_json=fire_json,
        widget_js=widget_js(),
        data_src=url_segments(DATA_OUTPUT.name),
        now=esc(g["now"]), change_note=esc(g["change_note"]), warning="".join(warnings), live_off=esc(live_off_text()),
        project_count=len(projects), item_count=len(open_items(items)), decision_count=len(decisions),
        file_count=len(tracked) + len(ignored), items=item_html, cards="".join(cards),
        decisions=decision_rows, commits=commit_rows, tree=main_tree, ignored_block=ignored_block,
        unlinked_tree=unlinked_tree, unlinked_count=len(unlinked), hidden_note=hidden_note,
        living="".join(living), kit_version=esc(g["version"]),
    )


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>window.DASH_NS={ns};document.documentElement.style.setProperty("--clock",(Date.now()/1000%86400)+"s");try{{var calm=localStorage.getItem(window.DASH_NS+"-calm");if(calm==="1"||(calm===null&&{respect_os}&&matchMedia("(prefers-reduced-motion: reduce)").matches))document.documentElement.classList.add("calm")}}catch(e){{}}</script>
<style>
{theme_css}
</style></head><body>
<div class="sky" aria-hidden="true"></div><div class="sky twinkle" aria-hidden="true"></div><div class="page-flames" aria-hidden="true"></div>
<header><div class="head-title"><h1>{title}</h1>{tagline}</div>
<input type="search" id="q" placeholder="Search projects, decisions and files" aria-label="Search">
<span class="meta"><span id="built">Built {now}</span>. <span id="changes">{change_note}</span>. <span id="live">{live_off}</span>. <button id="calm-toggle" class="btn" type="button">Stop the fire</button></span></header>
<div class="layout">
<aside aria-label="Recent files"><section class="widget"><h2>Files changed</h2><ul id="files_changed"></ul></section><section class="widget created"><h2>Files created</h2><ul id="files_created"></ul></section></aside>
<main>
<nav><a href="#needs">Needs you ({item_count})</a><a href="#projects">Projects ({project_count})</a><a href="#history">Decisions ({decision_count})</a><a href="#files">All files ({file_count})</a></nav>
{warning}
{fire_top}
<section id="needs"><h2>Needs you</h2><div class="panel"><ul class="needs">{items}</ul></div></section>
{friend_space}
<section><h2>Living documents</h2><div class="panel">
<ul class="links">{living}</ul></div></section>
<section id="projects"><h2>Projects</h2>{cards}</section>
<section id="history"><h2>History</h2><div class="two">
<div class="panel"><strong>Decisions, newest first</strong><ul class="scroll">{decisions}</ul></div>
<div class="panel"><strong>Recent commits</strong><ul class="scroll">{commits}</ul></div></div></section>
<section id="files"><h2>All files</h2><div class="panel">{hidden_note}
<details data-tree><summary>Not linked from any project <span class="count">{unlinked_count}</span></summary>{unlinked_tree}</details>
{ignored_block}
<h3 class="group">Workspace files</h3>{tree}</div></section>
<p class="foot">Kit build {kit_version}. A local page: it holds this computer's folder paths, so it is not for sharing.</p>
</main>
<aside aria-label="Recent documents"><section class="widget"><h2>Documents changed</h2><ul id="docs_changed"></ul></section><section class="widget created"><h2>Documents created</h2><ul id="docs_created"></ul></section></aside>
</div>
<script>
{widget_js}
</script>
<script src="{data_src}"></script>
<script>
const q = document.getElementById("q");
q.addEventListener("input", () => {{
  const term = q.value.trim().toLowerCase();
  document.body.classList.toggle("searching", !!term);
  document.querySelectorAll("[data-filter]").forEach(el => el.classList.toggle("hide", term && !el.textContent.toLowerCase().includes(term)));
  document.querySelectorAll("[data-tree]").forEach(el => {{
    if (term) el.open = !!el.querySelector("[data-filter]:not(.hide)");
    else el.open = false;
  }});
  document.querySelectorAll("h3.group + .cards").forEach(el => {{
    const empty = term && !el.querySelector(".card:not(.hide)");
    el.classList.toggle("hide", !!empty); el.previousElementSibling.classList.toggle("hide", !!empty);
  }});
}});
</script>
<script>window.FIRE = {fire_json};</script>
<script>
{theme_js}
</script></body></html>
"""


def live_off_text():
    if launcher_is_ours():
        return f"Live updates off: open with {LAUNCHER}"
    return f"Live updates off: run {KIT_NAME}/build_dashboard.py --watch"


def live_on_text():
    return "Live: reloads once a minute" if POLL_SECONDS == 60 else f"Live: reloads every {POLL_SECONDS} seconds"


def widget_js():
    settings = {"poll": POLL_SECONDS, "fresh": max(90, WATCH_SECONDS * 4), "liveOn": live_on_text(), "liveOff": live_off_text(),
                "editor": EDITOR_TEMPLATE, "editorTitle": EDITOR_TITLE, "rootUrl": ROOT_URL, "reveal": REVEAL_SCHEME}
    return WIDGET_JS.replace("__SETTINGS__", json.dumps(settings).replace("</", "<\\/"))


WIDGET_JS = r"""
const WIDGETS = __SETTINGS__;
const POLL_SECONDS = WIDGETS.poll;
const pathUrl = (path) => path.split("/").map(encodeURIComponent).join("/");
// The same address the generator writes, so a link from a widget and a link in a list agree.
function fileHref(root, path) {
  if (!WIDGETS.editor) return WIDGETS.rootUrl + "/" + pathUrl(path);
  const full = (root + "/" + path).replace(/^\/+/, "");
  return WIDGETS.editor.replace("{path}", pathUrl(full).replace(/%3A/g, ":")).replace(":{line}", "").replace("{line}", "");
}
function ago(sec) {
  const d = Math.max(0, Date.now() / 1000 - sec);
  if (d < 60) return "just now";
  if (d < 3600) return Math.floor(d / 60) + " min ago";
  if (d < 86400) return Math.floor(d / 3600) + " hr ago";
  return Math.floor(d / 86400) + " days ago";
}
window.onDashData = function (data) {
  document.getElementById("built").textContent = "Updated " + data.built;
  document.getElementById("changes").textContent = data.change_note;
  // Only the updater marks its builds. A page built by hand a moment ago is not live.
  const fresh = !!data.updater && Date.now() / 1000 - data.built_at < WIDGETS.fresh;
  document.getElementById("live").textContent = fresh ? WIDGETS.liveOn : WIDGETS.liveOff;
  document.documentElement.classList.toggle("live-on", fresh);
  if (!data.created_known) document.querySelectorAll(".widget.created").forEach(el => { el.hidden = true; });
  for (const [id, key] of [["files_changed", "changed"], ["files_created", "created"], ["docs_changed", "changed"], ["docs_created", "created"]]) {
    const list = document.getElementById(id);
    list.replaceChildren(...data[id].map(item => {
      const li = document.createElement("li");
      const open = document.createElement("a");
      open.href = fileHref(data.root, item.path);
      open.textContent = item.path.split("/").pop();
      open.title = WIDGETS.editorTitle + ": " + item.path;
      const when = document.createElement("small");
      when.textContent = ago(item[key]) + " · " + item.path;
      if (Date.now() / 1000 - item[key] < 3600) {
        const fresh = document.createElement("span");
        fresh.className = "new";
        fresh.textContent = "NEW!";
        li.append(fresh);
      }
      li.append(open);
      if (WIDGETS.reveal) {
        const show = document.createElement("a");
        show.className = "reveal";
        show.href = WIDGETS.reveal + ":" + pathUrl(item.path);
        show.textContent = "Show in Explorer";
        li.append(" ", show);
      }
      li.append(when);
      return li;
    }));
  }
};
function refreshData() {
  const tag = document.createElement("script");
  tag.src = document.querySelector('script[src$="_data.js"]').getAttribute("src") + "?t=" + Date.now();
  tag.onload = tag.onerror = () => tag.remove();
  document.head.append(tag);
}
// A reload must not take anything from the person using the page: a search, selected text or a song.
function inUse() {
  const search = document.getElementById("q");
  return !!search.value || document.activeElement === search || !!String(getSelection())
    || !!(window.pageBusy && window.pageBusy());
}
let reloadDue = false;
function pollOnce() {
  if (document.hidden) { reloadDue = true; return; }
  if (inUse()) { refreshData(); return; }
  if (window.beforePageReload) window.beforePageReload();
  location.reload();
}
setInterval(pollOnce, POLL_SECONDS * 1000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && reloadDue) { reloadDue = false; pollOnce(); }
});
"""


def check_staged():
    """Opt-in, for a pre-commit hook. Paths are relative to this folder; staged files elsewhere in a monorepo are not its business."""
    staged = split_z(git("diff", "--cached", "--name-only", "-z", "--relative"))
    prefixes = tuple(p for p in CONFIG["doc_only_prefixes"] if isinstance(p, str))
    only_docs = {p for p in CONFIG["doc_only_files"] if isinstance(p, str)}
    required = {LEDGER_REL, DECISIONS_REL}
    work = [p for p in staged if p not in only_docs and not p.startswith(prefixes) and p != OVERVIEW_REL and not is_own(p) and p not in KIT_FILES]
    if work and not required.intersection(staged):
        print("Commit blocked: these changes have no documentation with them.")
        print(f"Update {LEDGER_REL} (current state) or {DECISIONS_REL} (why):")
        for path in work[:20]:
            print(f"  {path}")
        return 1
    return 0


def asset_names():
    return sorted(p.name for p in ART_DIR.iterdir()) if ART_DIR.is_dir() else []


def write_atomic(path, text):
    """So a browser reloading at the wrong moment never reads half a page."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    try:
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.2)
    finally:
        if temporary.exists():
            temporary.unlink()


def gather():
    """Everything the page is made from, read once."""
    usable = git_usable()
    tracked, ignored, secrets = workspace_files(usable)
    missing, raw_docs = [], {}
    for rel, label in LIVING_DOCS:
        path = ROOT / rel
        text = read_or_note(path, rel) if path.is_file() else None
        if text is None:
            missing.append(f"{label} document not found at {rel}.")
        else:
            raw_docs[rel] = text
    commits, commit_count, uncommitted = git_history(usable)
    raw_guestbook = (read_or_note(GUESTBOOK, GUESTBOOK_REL) or "") if GUESTBOOK.exists() else ""
    # Every value is known before any text is scrubbed, so one found in the last file also leaves the first.
    others = [read_text(p) for p in (WORDS, CONFIG_PATH) if p.is_file()]
    values = [v for text in (*raw_docs.values(), *commits, raw_guestbook, *others) for v in withhold_lines(text)[2]]
    scrub = Scrubber(secrets, values)
    secrets = sorted({*secrets, *(p for p in tracked + ignored if scrub.holds_value(p))})
    tracked, ignored = [p for p in tracked if p not in secrets], [p for p in ignored if p not in secrets]
    scrub = Scrubber(secrets, values)
    config_lines = withhold_lines(read_text(CONFIG_PATH))[1] if CONFIG_PATH.is_file() else 0
    if config_lines:  # its fields are only scrubbed as the page uses them, so an unused entry would go unreported
        scrub.report(CONFIG_SOURCE, config_lines)
    texts = {}
    for rel, text in raw_docs.items():
        texts[rel] = scrub(text, rel)
        document_notes(rel, texts[rel])
    projects = parse_projects(texts.get(OVERVIEW_REL, ""))
    items = parse_user_items(texts.get(LEDGER_REL, ""))
    needs_found = needs_section(texts.get(LEDGER_REL, "")) is not None
    decisions = parse_decisions(texts.get(DECISIONS_REL, ""))
    assign_project_ids(projects)
    commits = [line for line in (scrub(c, COMMIT_SOURCE) for c in commits) if line.strip()]
    words = load_words(scrub)
    facts = fire_facts(projects, decisions, tracked + ignored, commit_count)
    lines, comments, dropped = usable_words(words, facts)
    counts = {key: sum(1 for entry in words[key] if entry.get("placeholder")) for key in ("friends", "lines")}
    named = [f"{label} {counts[key]}" for key, label in (("friends", "friends"), ("lines", "quotes")) if counts[key]]
    named += [key for key in ("late_night", "profile") if words[key].get("placeholder")]
    placeholders = sum(counts.values()) + sum(1 for key in ("profile", "late_night") if words[key].get("placeholder"))
    if placeholders:
        missing.append(f"{placeholders} placeholder{'' if placeholders == 1 else 's'} in {WORDS_REL} still to replace ({', '.join(named)}): friends and profile are labelled, quotes stay hidden.")
    uncredited = sum(1 for art in words["paintings"] if art["key"] and "credit" not in art)
    if uncredited:
        missing.append(f"{uncredited} painting{'' if uncredited == 1 else 's'} in {WORDS_REL} still {'has' if uncredited == 1 else 'have'} the kit's default credit. Ask whether the owner made them, then set each 'credit', or swap them.")
    if uncommitted is None:
        change_note = GIT_NOTE["text"] or "Git state unknown"
    elif uncommitted:
        change_note = f"{uncommitted} uncommitted change{'s' if uncommitted != 1 else ''} outside the dashboard"
    elif commit_count:
        whole = git("status", "--short", "-uall", "--", ".")
        own = len([l for l in (whole or "").splitlines() if l])
        change_note = ("Git state unknown" if whole is None else f"Nothing outside the dashboard is uncommitted, but {own} of its own file{'' if own == 1 else 's'} {'is' if own == 1 else 'are'} not committed"
                       if own else "Everything is committed")
    else:
        change_note = GIT_NOTE["text"] or "No commits yet"
    committed = commit_times() if usable else {}
    guestbook_text = scrub(raw_guestbook, GUESTBOOK_REL)
    broken = broken_links(texts) if texts else []
    return {"raw_docs": raw_docs, "usable": usable, "tracked": tracked, "ignored": ignored, "secrets": secrets, "scrub": scrub, "missing": missing,
            "texts": texts, "projects": projects, "items": items, "needs_found": needs_found, "decisions": decisions,
            "stray_needs": stray_need_lines(texts.get(LEDGER_REL, "")), "committed": committed,
            "ledger_found": LEDGER_REL in texts, "commits": commits, "uncommitted": uncommitted, "words": words, "facts": facts,
            "lines": lines, "comments": comments, "dropped": dropped, "change_note": change_note, "guestbook": guestbook_text,
            "signatures": parse_guestbook(guestbook_text), "broken": broken, "hot": hot_projects(projects, committed),
            "now": datetime.now().strftime("%Y-%m-%d %H:%M"), "version": read_version()}


def read_version():
    path = KIT_DIR / "VERSION"
    return (read_or_note(path, "VERSION") or "unknown").strip() if path.exists() else "unknown"


def page_stamp(g):
    """The page rebuilds when anything shown on it would change, including the folder it now lives in."""
    config_text = read_text(CONFIG_PATH) if CONFIG_PATH.is_file() else ""
    parts = {"root": ROOT.as_posix(), "config": config_text, "texts": g["texts"],
             "facts": g["facts"], "lines": g["lines"], "comments": g["comments"], "hot": sorted(g["hot"]),
             "tracked": g["tracked"], "ignored": g["ignored"], "secrets": len(g["secrets"]), "commits": g["commits"],
             "broken": g["broken"], "problems": PROBLEMS, "missing": g["missing"], "assets": asset_names(), "version": g["version"],
             "guestbook": g["guestbook"], "words": g["words"], "launcher": launcher_is_ours(),
             "generator": Path(__file__).read_text(encoding="utf-8"),
             "css": read_text(THEME_CSS), "js": read_text(THEME_JS)}
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def count_of(number, word):
    return f"{number} {word}{'' if number == 1 else 's'}"


def resolved_note(items):
    resolved = len(items) - len(open_items(items))
    return f", {resolved} resolved" if resolved else ""


def known_forms(value):
    """A string as the page may write it: plain, HTML-escaped, URL-encoded or inside JSON."""
    return {value, esc(value), encoded_path(value), url_segments(value), json.dumps(value)[1:-1], json.dumps(esc(value))[1:-1]}


def scan_view(text, g):
    """What the final scan reads. These parts are already allowed: the fixed theme, the workspace's own folder path, the
    default title made from its name, and listed paths, which passed is_secret and may only share part of a hidden name."""
    if THEME_CSS.is_file() and THEME_JS.is_file():
        text = text.replace(read_text(THEME_CSS).replace("{{ART}}", ART_URL), "").replace(read_text(THEME_JS), "")
    text = text.replace(widget_js(), "")
    allowed = {*known_forms(ROOT.as_posix()), *known_forms(str(ROOT))}
    if not CONFIG["title"].strip():
        allowed |= known_forms(TITLE)
    leaks = g["scrub"].leaks
    for path in g["tracked"] + g["ignored"]:
        if leaks(path):
            allowed |= known_forms(path)
            for segment in path.split("/"):
                if leaks(segment):
                    allowed |= known_forms(segment)
    for form in sorted(allowed, key=len, reverse=True):
        text = text.replace(form, "")
    return text


def shown_lines(text):
    """Page or document source as lines of reading text. Tags go, their attribute values stay on lines of their own, JSON
    and HTML escapes are decoded. So 'required</p>' reads as the word it is, and 'token -&gt; x' as the form it is."""
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text).replace("\\/", "/").replace('\\"', '"').replace("\\n", "\n")

    def tag(match):
        attributes = re.findall(r"""=\s*(?:"([^"]*)"|'([^']*)')""", match.group(0))
        if match.group(1).lower() in INLINE_TAGS and not attributes:
            return ""
        return "\n" + "\n".join(a or b for a, b in attributes) + "\n"
    return html.unescape(PAGE_TAG.sub(tag, text)).split("\n")


def shows_credential(text):
    return any(credential_values(line)[0] for line in shown_lines(text))


def leak_report(g, page, data_text):
    """None, or a sentence saying where a hidden name or credential came from. It never repeats the thing itself."""
    scanned = scan_view((page or "") + data_text, g)
    leaks = g["scrub"].leaks
    # A value that is also a word of the generator's own fixed text proves nothing, so only other values stop a build.
    fixed = Path(__file__).read_text(encoding="utf-8").casefold()
    for value in g["scrub"].value_list:
        # A bare number could be a port or a time on the page, so it leaves the text it was found beside but stops nothing.
        if not value.isdigit() and value.casefold() not in fixed and any(re.search(value_pattern(form), scanned, re.I) for form in known_forms(value)):
            return "a value from a withheld credential line would have appeared on the page, coming from the file list or another part of the page"
    if leaks(scanned):
        kind, found = "a name matching a hidden-name pattern", lambda text: leaks(squeezed(plain(text)))
    elif shows_credential(scanned):
        kind, found = "something that looks like a credential", shows_credential
    else:
        return None
    sources = [(read_text(CONFIG_PATH) if CONFIG_PATH.is_file() else "", "dashboard_config.json"),
               *((text, rel) for rel, text in g["texts"].items()), (g["guestbook"], GUESTBOOK_REL), ("\n".join(g["commits"]), "a commit message"),
               (json.dumps(g["words"]), WORDS_REL), *((text, rel) for rel, text in g.get("raw_docs", {}).items())]
    source = next((name for text, name in sources if found(text)), "the file list or another part of the page")
    return f"{kind} would have appeared on the page, coming from {source}"


def missing_theme():
    return [p.name for p in (THEME_CSS, THEME_JS) if not p.is_file()]


def build():
    if missing_theme():
        print(f"Build stopped: {' and '.join(missing_theme())} missing from {KIT_NAME}/. Run the kit's install_dashboard.py on this workspace again to put it back.")
        return 1
    for path, mark in ((OUTPUT, PAGE_MARK), (DATA_OUTPUT, DATA_MARK)):
        if not writable_by_kit(path, mark):
            print(f"Build stopped: {path.relative_to(ROOT).as_posix()} already exists and is not this kit's, so it was left alone. Move it, or set 'output' in dashboard_config.json.")
            return 2
    g = gather()
    stamp = page_stamp(g)
    data = {"built": g["now"], "built_at": int(time.time()), "change_note": g["change_note"], "updater": os.environ.get(UPDATER_ENV) == "1",
            "root": ROOT.as_posix() if EDITOR_TEMPLATE else "", **recent_activity(g["tracked"] + g["ignored"], committed=g["committed"])}
    data_text = "window.onDashData(" + json.dumps(data) + ");\n"
    page_changed = not OUTPUT.exists() or f'data-stamp="{stamp}"' not in read_text(OUTPUT)
    page = build_html(g).replace("<body>", f'<body data-stamp="{stamp}">', 1) if page_changed else None
    report = leak_report(g, page, data_text)
    if report:
        print(f"Build stopped: {report}. Nothing was written. Fix it there, and do not work around this check.")
        return 2
    write_atomic(DATA_OUTPUT, data_text)
    if page is not None:
        write_atomic(OUTPUT, page)
    print(f"Built {OUTPUT_REL}: {count_of(len(g['projects']), 'project')}, {count_of(len(open_items(g['items'])), 'item')} for you{resolved_note(g['items'])}, "
          f"{count_of(len(g['decisions']), 'decision')}, {count_of(len(g['tracked']) + len(g['ignored']), 'file')}.")
    for line in g["missing"] + PROBLEMS:
        print(f"Note: {line}")
    return 0


def doctor():
    """What each document parsed to, and what looked close but did not parse."""
    g = gather()
    print(f"Workspace: {ROOT}\nWorkspace id: {WORKSPACE_ID}\nStorage namespace: {STORAGE_NS}\nUpdater lock port: {lock_ports()[0]}\nExplorer link scheme, if enabled: {LINK_SCHEME}")
    print(f"Git: {'usable' if g['usable'] else GIT_NOTE['text']}")
    answers = lock_answers()
    running = next(((port, answer.split()[3:]) for port, answer in answers.items() if is_own_lock(answer)), None)
    if running:
        print(f"Updater: running on lock port {running[0]}, PID {running[1][0] if running[1] else 'not reported'}.")
    else:
        print("Updater: not running.")
    if CONFIG["motion"] == "always":
        print("Motion: 'always', which ignores the browser's reduce-motion signal. If the owner has not asked for that, ask, or list it under Items for the user.")
    print("This checks only. It does not rebuild the page: run build_dashboard.py with no options for that.")
    print(f"Found: {count_of(len(g['projects']), 'project')}, {count_of(len(open_items(g['items'])), 'item')} for the user{resolved_note(g['items'])}, {count_of(len(g['decisions']), 'decision')}, "
          f"{count_of(len(g['tracked']) + len(g['ignored']), 'file')}, {len(g['secrets'])} hidden as private.")
    print(f"Numbers: {json.dumps(g['facts'], sort_keys=True)}")
    print(f"Quotes kept: {sum(1 for l in g['lines'] if not l.get('placeholder'))}. Comments kept: {len(g['comments'])}. Dropped: {len(g['dropped'])}.")
    for rel, text in g["texts"].items():
        for number, line in unfenced(text):
            if "](" in line and len(re.findall(r"\]\(", line)) > len(find_links(line)):
                print(f"Close: {rel}:{number} has link-like text that did not parse: {line.strip()[:90]}")
    if OVERVIEW_REL in g["texts"] and not g["projects"]:
        print(f"Close: {OVERVIEW_REL} has no ### project headings.")
    for project in g["projects"]:
        if not project["status"]:
            print(f"Close: project '{project['name']}' has no status line.")
        else:
            kind = status_kind(project["status"])
            unread = ""
            if not read_status(project["status"]):
                unread = (" The first clause held no recognised word, so it counts as an idea." if ";" in project["status"]
                          else " No recognised status word, so it counts as an idea.")
            print(f"Status: {project['name']}: '{project['status']}' reads as {kind}, heat {HEAT[kind]}.{unread}")
    if LEDGER_REL in g["texts"] and not g["needs_found"]:
        print(f"Close: {LEDGER_REL} has no '## {CONFIG['needs_heading']}' section.")
    if DECISIONS_REL in g["texts"]:
        for number, line in unfenced(g["texts"][DECISIONS_REL]):
            if re.match(r"^#{2,3} ", line) and not DECISION.match(line):
                print(f"Close: {DECISIONS_REL}:{number} is a heading without a decision ID: {line.strip()[:70]}")
    if missing_theme():
        print(f"Close: {' and '.join(missing_theme())} missing, so a build would stop.")
    else:
        report = leak_report(g, build_html(g), "")
        if report:
            print(f"Close: a build would stop: {report}.")
    if CONFIG["id"]:
        for answer in answers.values():
            if answer.startswith(f"wsdash {WORKSPACE_ID} ") and not is_own_lock(answer):
                print(f"Close: another workspace runs with the id '{WORKSPACE_ID}', so the two share browser storage. Give one a different id, or remove it.")
                break
    for line in g["missing"] + g["broken"] + PROBLEMS:
        print(f"Note: {line}")
    return 0


def answer_lock(server):
    """Tells a second updater that this port is held by this workspace, and by nothing else."""
    while True:
        try:
            connection, _ = server.accept()
            with connection:
                connection.sendall(f"{LOCK_BANNER} {os.getpid()}\n".encode("ascii"))
        except OSError:
            return


def ask_lock(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3) as connection:
            connection.settimeout(0.3)
            return connection.recv(64).decode("ascii", "replace").strip()
    except OSError:
        return ""


def is_own_lock(answer):
    return answer.split()[:3] == LOCK_BANNER.split()


def lock_answers():
    """What each lock port in use says. The first free port ends the search, since an updater takes the first it can."""
    answers = {}
    for port in lock_ports():
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
                break
            except OSError:
                pass
        answers[port] = ask_lock(port)
    return answers


def take_lock():
    """The lock socket, None if this workspace's updater already runs, or False if no port is free.
    A port held by anything else, even a workspace with a copied id, is skipped."""
    held = None
    for port in lock_ports():
        server = socket.socket()
        try:
            server.bind(("127.0.0.1", port))
        except OSError:
            server.close()
            answer = ask_lock(port)
            if is_own_lock(answer):
                if held:
                    held.close()
                return None
            if answer.startswith(f"wsdash {WORKSPACE_ID} "):
                print(f"Another workspace uses the id '{WORKSPACE_ID}', so the two share browser storage. Give one a different id.", flush=True)
            continue
        if held is None:
            held = server
        else:
            server.close()
    if held is None:
        return False
    held.listen(4)
    threading.Thread(target=answer_lock, args=(held,), daemon=True).start()
    return held


def watch():
    lock = take_lock()
    if lock is None:
        print("This workspace's dashboard updater is already running.")
        return 0
    if lock is False:
        print("The updater did not start: every port it could use for its lock is taken, so it could not make sure only one runs. A build by hand still works.")
        return 1
    print("Updating the dashboard. Close this window to stop.", flush=True)
    while True:
        # A fresh process each time, so an edit to this file takes effect without a restart. An
        # updater running old code in memory would overwrite the page with the old design.
        result = subprocess.run([sys.executable, str(Path(__file__).resolve())], cwd=ROOT, env={**os.environ, UPDATER_ENV: "1"})
        if result.returncode != 0:  # a file mid-save should not stop the updater
            print("Update failed, will retry.", flush=True)
        time.sleep(WATCH_SECONDS)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if args == ["--check-staged"]:
        return check_staged()
    if args == ["--check"]:
        broken = broken_links()
        for line in broken:
            print(f"Broken link: {line}")
        print(f"{len(broken)} broken links" if broken else "Living document links are valid")
        print("This checks only. It does not rebuild the page: run build_dashboard.py with no options for that.")
        return 1 if broken else 0
    if args == ["--doctor"]:
        return doctor()
    if args == ["--watch"]:
        return watch()
    if args:
        raise SystemExit(__doc__)
    return build()


if __name__ == "__main__":
    sys.exit(main())
