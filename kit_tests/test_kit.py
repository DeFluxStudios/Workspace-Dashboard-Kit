#!/usr/bin/env python3
"""Tests for the workspace dashboard kit. Standard library only. Simulated: they install into temporary folders.

  python kit_tests/test_kit.py

Each test names what it protects, by decision DASHBOARD-KIT-001 and the section of START_HERE.md or README.md.
KIT_TEST_ROOT chooses where temporary workspaces go; otherwise the system's temporary folder. The browser test is
skipped if no Chrome or Edge is found, or if KIT_TEST_BROWSER=0.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
INSTALLER = KIT / "install_dashboard.py"
FOLDER = "workspace_dashboard"
PAGE = f"{FOLDER}/Workspace_Dashboard.html"
DATA = f"{FOLDER}/Workspace_Dashboard_data.js"
# Words from the workspace this kit was cut from. None may reach another workspace or the kit itself. The list stays with
# that workspace, whose own test passes it in here, so the kit does not carry the names it must not carry.
SOURCE_WORDS = tuple(w for w in os.environ.get("KIT_SOURCE_WORDS", "").split("|") if w)
TEXT_TYPES = (".py", ".js", ".css", ".json", ".md", ".html", ".cmd", ".sh", ".ps1", ".sample")
GENERATED = {PAGE, DATA}
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@example.invalid", "PYTHONDONTWRITEBYTECODE": "1"}
for leaked in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):  # a commit hook running the tests must not point them here
    ENV.pop(leaked, None)
HAS_GIT = shutil.which("git") is not None


def run(*args, cwd=None, env=None, timeout=60):
    return subprocess.run(list(map(str, args)), cwd=cwd, env=env or ENV, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", stdin=subprocess.DEVNULL, timeout=timeout)


def snapshot(root):
    """Every file under a folder, with its hash and modified time, ignoring what Git itself keeps."""
    found = {}
    for path in Path(root).rglob("*"):
        if path.is_file() and ".git" not in path.relative_to(root).parts:
            found[path.relative_to(root).as_posix()] = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
    return found


def remove_tree(root):
    """Git marks its objects read-only, which stops Windows deleting them, so clear that first."""
    for path in Path(root).rglob("*"):
        if path.is_file():
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    shutil.rmtree(root, ignore_errors=True)


class KitCase(unittest.TestCase):
    def setUp(self):
        base = os.environ.get("KIT_TEST_ROOT")
        if base:
            Path(base).mkdir(parents=True, exist_ok=True)
        self.base = Path(tempfile.mkdtemp(prefix="kit_", dir=base)).resolve()
        self.addCleanup(remove_tree, self.base)

    def workspace(self, name="alpha"):
        path = self.base / name
        path.mkdir(parents=True)
        return path

    def install(self, target, *flags, expect=0):
        result = run(sys.executable, "-B", INSTALLER, target, *flags)
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        return result.stdout

    def build(self, target, *flags, env=None, expect=0):
        result = run(sys.executable, "-B", target / FOLDER / "build_dashboard.py", *flags, cwd=target, env=env)
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        return result.stdout

    def page(self, target):
        return (target / PAGE).read_text(encoding="utf-8")

    def data(self, target):
        return (target / DATA).read_text(encoding="utf-8")

    def git(self, target, *args):
        result = run("git", "-c", "commit.gpgsign=false", *args, cwd=target)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def set_config(self, target, **values):
        path = target / "dashboard_config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config.update(values)
        path.write_text(json.dumps(config), encoding="utf-8")

    def set_words(self, target, **values):
        path = target / FOLDER / "words.json"
        words = json.loads(path.read_text(encoding="utf-8"))
        words.update(values)
        path.write_text(json.dumps(words), encoding="utf-8")

    def fire_json(self, target):
        return json.loads(re.search(r"window\.FIRE = (.*?);</script>", self.page(target), re.S).group(1).replace("<\\/", "</"))


class InstallerSafety(KitCase):
    """DASHBOARD-KIT-001, README 'What gets written where': adding files is the installer's only effect."""

    def test_nothing_existing_is_overwritten(self):
        """Protects START_HERE rule 5: an existing launcher, config or document survives, byte for byte."""
        target = self.workspace()
        mine = {"docs/project-ledger.md": "my ledger\n", "Open_Dashboard.cmd": "mine\n", "README.md": "mine\n", ".gitignore": "x\n",
                "dashboard_config.json": '{"title": "Mine"}\n', f"{FOLDER}/words.json": "{}\n", f"{FOLDER}/theme.js": "// mine\n"}
        for rel, text in mine.items():
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            (target / rel).write_text(text, encoding="utf-8")
        before = snapshot(target)
        output = self.install(target)
        after = snapshot(target)
        for rel in mine:
            self.assertEqual(before[rel], after[rel], rel)
            if rel not in ("README.md", ".gitignore"):  # not kit files, so the installer has no reason to name them
                self.assertIn(f"keep     {rel}", output)
        self.assertEqual(set(before) - set(after), set())

    def test_force_replaces_program_files_but_never_user_data(self):
        """Protects README: --force is explicit, and even then config, words and documents stay."""
        target = self.workspace()
        self.install(target)
        (target / FOLDER / "theme.js").write_text("// old\n", encoding="utf-8")
        for rel in (f"{FOLDER}/words.json", "docs/project-ledger.md", "dashboard_config.json"):
            (target / rel).write_text("{}\n", encoding="utf-8")
        self.install(target)
        self.assertEqual((target / FOLDER / "theme.js").read_text(encoding="utf-8"), "// old\n")
        self.install(target, "--force")
        self.assertNotEqual((target / FOLDER / "theme.js").read_text(encoding="utf-8"), "// old\n")
        self.assertEqual((target / "docs/project-ledger.md").read_text(encoding="utf-8"), "{}\n")
        self.assertEqual((target / "dashboard_config.json").read_text(encoding="utf-8"), "{}\n")

    def test_reinstall_is_idempotent(self):
        """Protects install requirement 'safe to re-run': no source file changes and the page does not rebuild."""
        target = self.workspace()
        self.install(target)
        self.build(target)  # one further build must also settle
        before = snapshot(target)
        output = self.install(target)
        after = snapshot(target)
        self.assertIn("0 written", output)
        for rel in before:
            if rel != DATA:  # the data file holds the build time
                self.assertEqual(before[rel], after[rel], rel)
        self.assertEqual(set(before), set(after))

    def test_dry_run_changes_nothing_and_names_every_file(self):
        """Protects START_HERE step 2: a preview has no effect."""
        target = self.workspace()
        (target / "a.txt").write_text("a", encoding="utf-8")
        before = snapshot(target)
        output = self.install(target, "--dry-run")
        self.assertEqual(snapshot(target), before)
        self.assertIn(f"would write    {FOLDER}/build_dashboard.py", output)
        self.assertIn("would write    dashboard_config.json", output)

    def test_refuses_a_target_inside_the_kit(self):
        """Protects install requirement: the kit never installs into itself."""
        for target in (KIT, KIT / "payload", KIT / "starter"):
            before = snapshot(KIT / "starter")
            self.assertIn("Refused", self.install(target, expect=2))
            self.assertEqual(snapshot(KIT / "starter"), before)

    def test_outputs_ignored_by_nested_gitignore_and_root_gitignore_untouched(self):
        """Protects 'adding files is the only effect', and keeps a page with local paths out of commits."""
        if not HAS_GIT:
            self.skipTest("Git required")
        target = self.workspace()
        self.git(target, "init", "-q")
        (target / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
        self.install(target)
        self.assertEqual((target / ".gitignore").read_text(encoding="utf-8"), "*.tmp\n")
        ignored = self.git(target, "check-ignore", PAGE, DATA)
        self.assertIn(PAGE, ignored)
        self.assertIn(DATA, ignored)

    def test_existing_config_decides_where_starters_go(self):
        """Protects START_HERE step 2: a workspace with its own documents gets no starters beside them."""
        target = self.workspace()
        (target / "ROADMAP.md").write_text("## Now\n\n### Thing\n\n**Status: Shipped**\n", encoding="utf-8")
        (target / "dashboard_config.json").write_text('{"overview": "ROADMAP.md", "ledger": "notes/ledger.md"}', encoding="utf-8")
        self.install(target)
        self.assertFalse((target / "docs/Works_in_Development.md").exists())
        self.assertTrue((target / "notes/ledger.md").exists())
        self.assertIn("Thing", self.page(target))


class SecretNames(KitCase):
    """DASHBOARD-KIT-001, README 'Privacy', START_HERE rule 6: credentials never reach the page."""

    FILES = {".env": "PASSWORD_VALUE_ONE", ".env.local": "PASSWORD_VALUE_TWO", "server.pem": "PEM_VALUE", "deploy.key": "KEY_VALUE",
             "id_rsa": "RSA_VALUE", "my api key.txt": "API_VALUE", "aws_credentials.json": "CRED_VALUE",
             "config/secrets/db.yml": "DB_VALUE", "auth_token.txt": "TOKEN_VALUE", ".ssh/known_hosts": "SSH_VALUE"}
    NAMES = [".env", "server.pem", "deploy.key", "id_rsa", "api key", "api%20key", "aws_credentials", "secrets", "auth_token", "known_hosts"]

    def make(self, with_git):
        target = self.workspace()
        for rel, value in self.FILES.items():
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            (target / rel).write_text(value, encoding="utf-8")
        (target / "normal.md").write_text("A plain file.\n", encoding="utf-8")
        if with_git:
            self.git(target, "init", "-q")
            (target / ".gitignore").write_text(".env\nserver.pem\n", encoding="utf-8")
            self.git(target, "add", "-A")
            self.git(target, "commit", "-qm", "the file server.pem changed")
        self.install(target)
        docs = target / "docs"
        (docs / "Works_in_Development.md").write_text(
            "## G\n\n### P\n\n**Status: Local**\n\nCopy .env first, then read auth_token.txt.\n\n[The env](../.env) | [Readme](../normal.md)\n", encoding="utf-8")
        self.set_words(target, lines=[{"text": "PASSWORD_VALUE_ONE", "who": "x", "file": ".env"},
                                      {"text": "A plain file.", "who": "x", "file": "normal.md"}])
        self.build(target)
        return target

    def assert_clean(self, target):
        scanned = self.page(target) + self.data(target)
        # The theme is fixed text; scan what the build wrote. The theme has none of these names either.
        for name in self.NAMES:
            self.assertNotIn(name.lower(), scanned.lower(), name)
        for value in self.FILES.values():
            self.assertNotIn(value, scanned)
        self.assertIn("normal.md", scanned)
        self.assertIn("left off this page", scanned)

    def test_no_secret_names_or_content_without_git(self):
        self.assert_clean(self.make(False))

    @unittest.skipUnless(HAS_GIT, "Git required")
    def test_no_secret_names_or_content_with_git_including_ignored_and_commit_subjects(self):
        self.assert_clean(self.make(True))

    def test_a_quote_cannot_use_a_secret_or_outside_file_as_evidence(self):
        """Protects the evidence check: a words entry cannot pull text from a hidden file or outside the workspace."""
        target = self.make(False)
        outside = self.base / "outside.txt"
        outside.write_text("OUTSIDE_TEXT", encoding="utf-8")
        self.set_words(target, lines=[{"text": "PASSWORD_VALUE_ONE", "who": "x", "file": ".env"},
                                      {"text": "OUTSIDE_TEXT", "who": "x", "file": "../outside.txt"},
                                      {"text": "OUTSIDE_TEXT", "who": "x", "file": str(outside)}])
        self.build(target)
        page = self.page(target)
        self.assertNotIn("PASSWORD_VALUE_ONE", page)
        self.assertNotIn("OUTSIDE_TEXT", page)

    def test_token_like_strings_in_documents_are_hidden_and_reported(self):
        """Protects: documents are shown on the page, so a pasted key must not be."""
        target = self.workspace()
        self.install(target)
        key = "ghp_" + "a1B2" * 8
        (target / "docs/project-ledger.md").write_text(f"## Items for the user\n\n- Use {key} here\n", encoding="utf-8")
        output = self.build(target)
        self.assertNotIn(key, self.page(target))
        self.assertIn("looks like a credential", output)

    def test_final_scan_stops_the_build_if_a_name_gets_through(self):
        """Protects the post-build scan: a name reaching the page by a route the scrubber does not cover stops the build,
        and the message and the doctor name the source without repeating the name."""
        target = self.workspace()
        self.install(target)
        (target / "server.pem").write_text("x", encoding="utf-8")
        before = self.page(target)
        self.set_config(target, editor="myed://server.pem/{path}")  # only the scan can catch this one
        output = self.build(target, expect=2)
        self.assertIn("Nothing was written", output)
        self.assertIn("coming from dashboard_config.json", output)
        self.assertNotIn("server.pem", output)
        self.assertEqual(self.page(target), before)
        doctor = self.build(target, "--doctor")
        self.assertIn("a build would stop", doctor)
        self.assertNotIn("server.pem", doctor)


class TwoWorkspaces(KitCase):
    """DASHBOARD-KIT-001, README 'Two dashboards at once'."""

    def facts(self, target):
        output = self.build(target, "--doctor")
        return {"port": int(re.search(r"lock port: (\d+)", output).group(1)),
                "ns": re.search(r"Storage namespace: (\S+)", output).group(1)}

    def test_different_ports_and_namespaces_and_no_shared_keys(self):
        one, two = self.workspace("one"), self.workspace("two")
        self.install(one)
        self.install(two)
        a, b = self.facts(one), self.facts(two)
        self.assertNotEqual(a["port"], b["port"])
        self.assertNotEqual(a["ns"], b["ns"])
        for fact in (a, b):
            self.assertTrue(49152 <= fact["port"] <= 65535)
        self.assertIn(json.dumps(a["ns"]), self.page(one))
        self.assertIn(json.dumps(b["ns"]), self.page(two))
        for page in (self.page(one), self.page(two)):
            self.assertNotIn("fire-calm", page)
            self.assertNotIn("fire-hits", page)
            self.assertNotIn("fire-state", page)
            # Every storage call in the theme goes through the namespacing helper.
            self.assertEqual(re.findall(r"(?:localStorage|sessionStorage)\.\w+Item\(\s*\"", page), [])

    def start_watch(self, target):
        process = subprocess.Popen([sys.executable, "-B", str(target / FOLDER / "build_dashboard.py"), "--watch"], cwd=target, env=ENV,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                   stdin=subprocess.DEVNULL)
        self.addCleanup(self.stop, process)
        return process

    @staticmethod
    def stop(process):
        process.kill()
        process.wait(timeout=10)
        if process.stdout:
            process.stdout.close()

    def test_two_updaters_run_and_a_second_for_one_workspace_stands_down(self):
        """Protects the updater lock. Leaves no process or port behind."""
        one, two = self.workspace("one"), self.workspace("two")
        self.install(one)
        self.install(two)
        for target in (one, two):
            self.set_config(target, watch_seconds=30)
        first, second = self.start_watch(one), self.start_watch(two)
        self.assertIn("Updating", first.stdout.readline())
        self.assertIn("Updating", second.stdout.readline())
        repeat = self.build(one, "--watch")
        self.assertIn("already running", repeat)
        self.assertIsNone(first.poll())
        self.assertIsNone(second.poll())
        port = self.facts(one)["port"]
        self.stop(first)
        self.stop(second)
        with socket.socket() as probe:
            time.sleep(0.1)
            probe.bind(("127.0.0.1", port))  # free again

    def test_port_held_by_something_else_moves_to_the_next(self):
        """Protects 'collisions handled': an unrelated program on the port does not silently stop the updater."""
        target = self.workspace()
        self.install(target)
        self.set_config(target, watch_seconds=30)
        with socket.socket() as squatter:
            squatter.bind(("127.0.0.1", self.facts(target)["port"]))
            squatter.listen(1)
            process = self.start_watch(target)
            self.assertIn("Updating", process.stdout.readline())
            self.assertIn("already running", self.build(target, "--watch"))
            self.stop(process)


class AnyWorkspace(KitCase):
    """DASHBOARD-KIT-001, generator requirement: builds and says plainly what is missing, in any state of workspace."""

    def assert_built(self, target):
        page = self.page(target)
        self.assertIn("Stop the fire", page)
        self.assertIn(f"Kit build {(KIT / 'VERSION').read_text(encoding='utf-8').strip()}", page)
        return page

    def test_no_git_and_no_documents(self):
        """Git absent from PATH, then every document deleted. Page builds and says so, with no invented numbers."""
        target = self.workspace()
        self.install(target)
        for name in ("Works_in_Development.md", "project-ledger.md", "decision-log.md"):
            (target / "docs" / name).unlink()
        env = {**ENV, "PATH": ""}
        self.build(target, env=env)
        page = self.assert_built(target)
        self.assertIn("Overview document not found", page)
        self.assertIn("cannot say what is waiting", page)
        self.assertIn("No decisions found", page)
        self.assertNotIn("Nothing waiting", page)
        self.assertIn("Git is not installed", page)
        self.assertNotIn("commits!!!", json.dumps(self.fire_json(target)))
        self.assertNotIn("0 steps", page)

    def test_not_a_repository(self):
        target = self.workspace()
        self.install(target)
        (target / "work.py").write_text("x = 1\n", encoding="utf-8")
        self.build(target)
        page = self.assert_built(target)
        self.assertIn("work.py", page)
        self.assertNotIn("Ignored by Git", page)

    @unittest.skipUnless(HAS_GIT, "Git required")
    def test_repository_with_no_commits(self):
        target = self.workspace()
        self.git(target, "init", "-q")
        self.install(target)
        self.assertIn("No commits yet", self.assert_built(target))

    @unittest.skipUnless(HAS_GIT, "Git required")
    def test_committed_workspace_settles_at_once_and_counts_only_its_own_changes(self):
        """Protects: the kit's own files and page never count as uncommitted work, and builds settle."""
        target = self.workspace()
        self.git(target, "init", "-q")
        (target / "a.py").write_text("x", encoding="utf-8")
        self.git(target, "add", "a.py")
        self.git(target, "commit", "-qm", "first")
        self.install(target)
        for rel in ("dashboard_config.json", "Open_Dashboard.cmd", "Open_Dashboard.sh", "docs", FOLDER):
            self.git(target, "add", rel)
        self.git(target, "commit", "-qm", "second")
        self.build(target)
        before = self.page(target)
        self.assertIn("Everything is committed", before + self.data(target))
        self.build(target)
        self.assertEqual(self.page(target), before)

    @unittest.skipUnless(HAS_GIT, "Git required")
    def test_workspace_inside_a_larger_repository_is_scoped_to_itself(self):
        """Protects monorepos: siblings are not counted and do not block the commit check."""
        outer = self.workspace("outer")
        self.git(outer, "init", "-q")
        target = outer / "sub"
        target.mkdir()
        (outer / "sibling.py").write_text("x", encoding="utf-8")
        (target / "own.py").write_text("x", encoding="utf-8")
        self.install(target)
        data = self.data(target)
        self.assertNotIn("sibling.py", self.page(target) + data)
        self.git(outer, "add", "sibling.py")
        self.assertEqual(run(sys.executable, "-B", target / FOLDER / "build_dashboard.py", "--check-staged", cwd=target).returncode, 0)
        self.git(outer, "add", "sub/own.py")
        self.assertEqual(run(sys.executable, "-B", target / FOLDER / "build_dashboard.py", "--check-staged", cwd=target).returncode, 1)
        self.git(outer, "add", "sub/docs/project-ledger.md")
        self.assertEqual(run(sys.executable, "-B", target / FOLDER / "build_dashboard.py", "--check-staged", cwd=target).returncode, 0)

    def test_path_with_spaces_and_non_ascii(self):
        """Protects the audit's awkward path trial: spaces, accents, # and & in the folder and in file names."""
        target = self.workspace("sp\u00e9ce \u6f22\u5b57 #1 & co")
        (target / "caf\u00e9 notes.md").write_text("caf\u00e9\n", encoding="utf-8")
        (target / "a#b c.md").write_text("x\n", encoding="utf-8")
        self.install(target, "--name", "Caf\u00e9 <b>Board</b>")
        page = self.assert_built(target)
        self.assertIn("Caf\u00e9 &lt;b&gt;Board&lt;/b&gt;", page)
        self.assertIn("caf\u00e9 notes.md", page)
        self.assertIn("a%23b%20c.md", page)
        self.assertIn('url("art/web/fire_red.gif")', page)

    @unittest.skipUnless(HAS_GIT, "Git required")
    def test_git_lists_non_ascii_names(self):
        """Protects: Git's quoted paths must not make accented files silently vanish."""
        target = self.workspace()
        self.git(target, "init", "-q")
        (target / "caf\u00e9 notes.md").write_text("x\n", encoding="utf-8")
        self.install(target)
        self.assertIn("caf\u00e9 notes.md", self.page(target))

    @unittest.skipUnless(SOURCE_WORDS, "the source workspace's own test passes the word list")
    def test_no_source_words_in_a_fresh_install(self):
        """Protects generator requirement: nothing from the source workspace on another workspace's page or files."""
        target = self.workspace()
        self.install(target)
        for path in target.rglob("*"):
            if path.is_file() and path.suffix in TEXT_TYPES:
                # The temporary folder's random name is not part of the kit's output.
                text = path.read_text(encoding="utf-8").replace(target.as_posix(), "")
                for word in SOURCE_WORDS:
                    self.assertNotIn(word.lower(), text.lower(), f"{word} in {path.name}")
        names = [p.name.lower() for p in target.rglob("*")]
        self.assertFalse([n for n in names if "top8" in n or "skull" in n or "frog_head" in n])

    @unittest.skipUnless(SOURCE_WORDS, "the source workspace's own test passes the word list")
    def test_no_source_words_in_the_kit_itself(self):
        """Protects README: the folder and zip that travel carry no source names and no path from the PC they were made on."""
        for path in KIT.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and (path.suffix in TEXT_TYPES or path.name == "VERSION"):
                text = path.read_text(encoding="utf-8").lower()
                for word in SOURCE_WORDS:
                    self.assertNotIn(word.lower(), text, f"{word} in {path.name}")

    def test_no_em_dashes_anywhere_a_person_reads(self):
        """Protects the developer's rule: no em dashes in text a person reads on the page, or in the kit's documents."""
        target = self.workspace()
        self.install(target)
        self.assertNotIn("\u2014", self.page(target))
        for path in KIT.rglob("*.md"):
            self.assertNotIn("\u2014", path.read_text(encoding="utf-8"), path.name)

    def test_kit_folder_and_generated_output_stay_off_the_lists(self):
        """Protects: the kit's own art and scripts do not flood activity widgets or file counts."""
        target = self.workspace()
        (target / "real.py").write_text("x", encoding="utf-8")
        self.install(target)
        data = json.loads(self.data(target)[len("window.onDashData("):-3])
        paths = [e["path"] for key in ("files_changed", "docs_changed") for e in data[key]]
        self.assertIn("real.py", paths)
        self.assertFalse([p for p in paths if p.startswith(FOLDER) or p in ("dashboard_config.json", "Open_Dashboard.cmd")])
        self.assertNotIn("fire_red.gif</a>", self.page(target))

    def test_row_caps_show_the_true_count(self):
        """Protects page size: a huge folder shows '+N more' and its real number."""
        target = self.workspace()
        (target / "lots").mkdir()
        for index in range(40):
            (target / "lots" / f"f{index}.txt").write_text("x", encoding="utf-8")
        self.install(target)
        self.set_config(target, max_folder_rows=10)
        self.build(target)
        page = self.page(target)
        self.assertIn('<span class="count">40</span>', page)
        self.assertIn("+30 more not shown", page)

    def test_output_can_move_and_art_addresses_follow(self):
        """Protects config 'output': image, cursor and data addresses are computed relative to the page."""
        target = self.workspace()
        self.install(target)
        self.set_config(target, output="pages/my board/Board.html")
        self.build(target)
        page = (target / "pages/my board/Board.html").read_text(encoding="utf-8")
        self.assertIn('url("../../workspace_dashboard/art/web/fire_red.gif")', page)
        self.assertIn('src="Board_data.js"', page)
        self.assertTrue((target / "pages/my board/Board_data.js").exists())
        self.assertNotIn("{{ART}}", page)

    def test_moved_folder_rebuilds_with_new_paths(self):
        """Protects the stamp: a copied folder never keeps links into the source workspace."""
        target = self.workspace("first")
        self.install(target)
        moved = self.base / "second"
        shutil.copytree(target, moved)
        self.build(moved)
        self.assertNotIn(target.as_posix().replace(" ", "%20"), self.page(moved))
        self.assertIn("second", self.page(moved))


class ParsersAndWords(KitCase):
    """DASHBOARD-KIT-001, starter/HOW_TO_FILL.md: tolerant parsers, and words that cannot crash or mislead."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("kit_generator", KIT / "payload" / "build_dashboard.py")
        cls.dash = importlib.util.module_from_spec(spec)
        sys.dont_write_bytecode = True
        spec.loader.exec_module(cls.dash)

    def test_starter_examples_parse_exactly_as_documented(self):
        """Protects section 8 of the kit: each starter's fenced example is in the exact parser format."""
        def example(name):
            return re.search(r"```markdown\n(.*?)```", (KIT / "starter" / name).read_text(encoding="utf-8"), re.S).group(1)
        project = self.dash.parse_projects(example("Works_in_Development.md"), self.dash.ROOT / "docs")[0]
        self.assertEqual((project["group"], project["name"], project["status"]), ("Group name", "Project name", "Local candidate"))
        self.assertEqual(project["summary"], "One short paragraph, which may run over two lines.")
        self.assertEqual(project["next"], "The next step.")
        self.assertEqual(project["links"], [("Readme", "README.md"), ("Site", "https://example.com/")])
        items = self.dash.parse_user_items(example("project-ledger.md"))
        self.assertEqual(items[0], "**Look at this:** one thing to do, continued on an indented line.")
        self.assertTrue(items[1].startswith("~~"))
        self.assertEqual([d["id"] for d in self.dash.parse_decisions(example("decision-log.md"))], ["ABC-001", "DEF-TWO-002"])

    def test_tolerant_status_next_and_last_section(self):
        """Protects against a page that looks fine while claiming nothing was found."""
        for line in ("**Status: Done**", "**Status:** Done", "Status: Done", "**status: Done**"):
            self.assertEqual(self.dash.parse_projects(f"### P\n\n{line}\n")[0]["status"], "Done", line)
        for line in ("**Next:** go", "**Next: go**", "next: go"):
            self.assertEqual(self.dash.parse_projects(f"### P\n\n{line}\n")[0]["next"], "go", line)
        self.assertEqual(self.dash.parse_user_items("## Items for the user\n\n* star\n- dash\n"), ["star", "dash"])
        self.assertEqual(self.dash.parse_decisions("```\n## FENCED-1 x\n```\n## adr-2 y\n## 2026-11-04 z\n"),
                         [{"id": "adr-2", "title": "y", "line": 4}, {"id": "2026-11-04", "title": "z", "line": 5}])

    def test_status_kinds_use_whole_words_and_negation(self):
        """Protects heat and legends, which must not lie."""
        cases = {"Live on the server; price check pending": "live", "Shipped": "live", "In production": "live", "Done": "live",
                 "Delivered to client": "local", "Deliverable draft": "local", "Alive": "idea", "Olive branch": "idea",
                 "Not live yet": "idea", "Live soon": "idea", "Unblocked now": "local", "Blocked": "blocked",
                 "Tested locally; disabled and blocked from deployment": "blocked", "Proposal": "idea",
                 "Existing script; expanded story is a proposal": "local", "": "none"}
        for status, kind in cases.items():
            self.assertEqual(self.dash.status_kind(status), kind, status)

    def test_links_with_titles_parens_and_angle_brackets(self):
        self.assertEqual(self.dash.find_links('[d](e.md "t") [f](<g h.md>) [x](x_(1).md)'),
                         [("d", "e.md"), ("f", "g h.md"), ("x", "x_(1).md")])

    def test_doctor_reports_link_like_text_that_did_not_parse(self):
        """Protects against project links vanishing while the link check still says valid."""
        target = self.workspace()
        self.install(target)
        (target / "docs/project-ledger.md").write_text("## Items for the user\n\n- see [a](../my file.md)\n", encoding="utf-8")
        self.assertIn("link-like text that did not parse", self.build(target, "--doctor"))

    def test_counts_of_one_read_as_singular(self):
        """Protects the words: no '1 decisions' and no '1 steps'."""
        target = self.workspace()
        self.install(target)
        (target / "docs/decision-log.md").write_text("## ABC-1: one\n", encoding="utf-8")
        (target / "docs/Works_in_Development.md").write_text("## G\n\n### P\n\n**Status: Proposal**\n", encoding="utf-8")
        self.build(target)
        page = self.page(target)
        self.assertIn("1 decision written", page)
        self.assertNotIn("1 decisions", page)
        self.assertNotIn("1 steps", page)

    def test_only_safe_links_are_ever_links(self):
        """Protects a local page from script links pasted into a document."""
        base = self.dash.ROOT / "docs"
        for url in ("javascript:alert(1)", "data:text/html,x", "C:/Users/a.md", "/etc/passwd", "../../../outside.md"):
            self.assertEqual(self.dash.classify_link(url, base)[0], "refused", url)
        self.assertEqual(self.dash.classify_link("HTTP://A.B", base), ("web", "HTTP://A.B"))
        target = self.workspace()
        self.install(target)
        (target / "docs/Works_in_Development.md").write_text("## G\n\n### P\n\n[bad](javascript:alert`1`)\n", encoding="utf-8")
        output = self.build(target, "--check", expect=1)
        self.assertIn("not shown as a link", output)
        self.build(target)
        self.assertNotIn('href="javascript', self.page(target))

    def test_bom_utf16_and_broken_utf8_documents(self):
        """Protects a PowerShell edit from emptying the dashboard or crashing the build."""
        target = self.workspace()
        self.install(target)
        doc = "## G\n\n### Marked\n\n**Status: Live**\n"
        (target / "docs/Works_in_Development.md").write_bytes(b"\xef\xbb\xbf" + doc.encode("utf-8"))
        (target / "docs/project-ledger.md").write_bytes(("## Items for the user\n\n- Wide one\n").encode("utf-16"))
        (target / "docs/decision-log.md").write_bytes(b"## ABC-1: caf\xe9\n")
        words = target / FOLDER / "words.json"
        words.write_bytes(b"\xef\xbb\xbf" + words.read_bytes())
        output = self.build(target)
        self.assertIn("1 project, 1 item for you, 1 decision,", output)
        self.assertIn("not UTF-8", output)
        self.assertIn("Marked", self.page(target))

    def test_bad_words_are_reported_by_key_and_never_crash(self):
        """Protects: one bad word in a hand-edited file does not stop the dashboard."""
        target = self.workspace()
        self.install(target)
        self.set_words(target, marquee=["{unknown_number} things", "stray { brace", "good"], paintings=[], song=7,
                       friends=[{"name": "no pic"}, {"pic": "gone.png", "name": "n", "says": "hello"}],
                       marks=[{"title": "T", "fact": "nope", "meaning": "m"}], late_night={"name": "x"})
        output = self.build(target)
        for expected in ("marquee[0] uses unknown number", "marquee[1] has a stray brace", "'song' has the wrong type", "friends[0] needs", "late_night needs"):
            self.assertIn(expected, output)
        page = self.page(target)
        self.assertIn("No painting yet", page)
        self.assertIn("placeholder.png", page)
        self.assertNotIn("unknown_number", self.fire_json(target)["comments"])
        words = target / FOLDER / "words.json"
        words.write_text("{ broken", encoding="utf-8")
        self.assertIn("could not be read", self.build(target))
        words.unlink()
        self.assertIn("words.json is missing", self.build(target))
        self.assertIn("Stop the fire", self.page(target))
        (target / "dashboard_config.json").write_text("[1]", encoding="utf-8")
        self.assertIn("could not be read", self.build(target))

    def test_placeholders_are_hidden_or_labelled_and_quotes_need_evidence(self):
        """Protects section 6: starter words never pass for real, and every quote is checked against a real file."""
        target = self.workspace()
        (target / "story.md").write_text("We keep\nthe receipts.\n", encoding="utf-8")
        self.install(target)
        fire = self.fire_json(target)
        self.assertNotIn("REPLACE", self.page(target))
        self.assertEqual(len(fire["lines"]), 1)
        self.assertTrue(fire["lines"][0]["placeholder"])
        self.assertTrue(all("(placeholder)" in c["name"] for c in fire["comments"]))
        self.assertIn('(placeholder)</span>', self.page(target))
        self.assertIn("placeholders in workspace_dashboard/words.json", self.page(target))
        self.set_words(target, lines=[{"text": "We keep the receipts.", "who": "Story", "file": "story.md"},
                                      {"text": "Never written anywhere.", "who": "Nobody", "file": "story.md"},
                                      {"text": "the fire", "who": "Self", "file": "workspace_dashboard/words.json"}])
        output = self.build(target)
        lines = self.fire_json(target)["lines"]
        self.assertEqual([l["text"] for l in lines], ["We keep the receipts."])
        self.assertIn("quote not found in story.md", output)
        self.assertNotIn("Never written anywhere", self.page(target))
        self.assertIn("quote not found in story.md", self.page(target))
        self.assertEqual(lines[0]["who"], "story.md")  # 'Story' is not in the file, so the file is the source

    def test_nothing_brags_about_zero(self):
        """Protects section 'no pressure' and honesty: a fact that is absent or zero drops its line."""
        target = self.workspace()
        self.install(target)
        comments = json.dumps(self.fire_json(target)["comments"])
        page = self.page(target)
        for phrase in ("on guard duty", "originals saved", "things out in the world", "0 commits", "0 decisions written"):
            self.assertNotIn(phrase, comments)
        self.assertNotIn("0 projects on the anvil", page)
        self.assertIn("I just like the fire", comments)
        self.assertNotIn("THE BLADE", page)

    def test_live_record_is_optional_and_generic(self):
        """Protects config 'live_record': counted from a named section, claimed only if it exists."""
        target = self.workspace()
        self.install(target)
        self.set_words(target, marks=[{"title": "OUT", "fact": "live_total", "meaning": "things out"}])
        self.build(target)
        self.assertNotIn(">OUT<", self.page(target))
        (target / "REL.md").write_text("## Shipped\n\n| Name | State |\n|---|---|\n| a | Match |\n| b | No |\n\n- c Match\n\n## Other\n\n- d\n", encoding="utf-8")
        self.set_config(target, live_record={"path": "REL.md", "section": "Shipped"})
        self.assertIn('"live_total": 3', self.build(target, "--doctor"))
        self.set_config(target, live_record={"path": "REL.md", "section": "Shipped", "match": "Match"})
        self.assertIn('"live_total": 2', self.build(target, "--doctor"))
        self.set_config(target, live_record={"path": "gone.md"})
        self.assertIn("was not found", self.build(target))

    def test_preservation_only_when_it_exists(self):
        """Protects: no claim of a safety net that is not there."""
        target = self.workspace()
        self.install(target)
        self.assertNotIn("Preserved originals", self.page(target))
        (target / "preservation/a").mkdir(parents=True)
        (target / "preservation/a/COPIES.tsv").write_text("sha\twhen\tpath\nx\ty\tz\n", encoding="utf-8")
        self.build(target)
        self.assertIn("Preserved originals", self.page(target))
        self.assertIn('"preserved": 1', self.build(target, "--doctor"))

    def test_broad_test_patterns(self):
        """Protects the {tests} number, which read 0 on most layouts."""
        paths = ["test/a.py", "spec/b.rb", "__tests__/c.js", "src/d.test.ts", "e_test.go", "src/test/java/F.java", "GTest.java", "src/app.py"]
        self.assertEqual(self.dash.count_matching(paths, self.dash.TEST_PATTERNS, "tests"), 7)

    def test_editor_setting(self):
        """Protects config 'editor': no VS Code means no dead vscode links."""
        target = self.workspace()
        (target / "a#b c.md").write_text("x", encoding="utf-8")
        self.install(target)
        self.assertIn("vscode://file/", self.page(target))
        self.set_config(target, editor="none")
        self.build(target)
        page = self.page(target)
        self.assertNotIn("vscode://", page)
        self.assertIn('href="../a%23b%20c.md"', page)
        self.assertNotIn(target.name, json.loads(self.data(target)[len("window.onDashData("):-3])["root"])

    def test_motion_setting_and_stop_switch(self):
        """Protects 'what the developer wants': forced on by default, opt-out available, switch always there."""
        target = self.workspace()
        self.install(target)
        self.assertIn("&&false&&matchMedia", self.page(target))
        self.set_config(target, motion="respect-os")
        self.build(target)
        self.assertIn("&&true&&matchMedia", self.page(target))
        self.assertIn('id="calm-toggle"', self.page(target))

    def test_text_colors_are_readable(self):
        """Protects 'sound color theory': the theme's inks stay readable on its panels."""
        def luminance(color):
            values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            r, g, b = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
            return 0.2126 * r + 0.7152 * g + 0.0722 * b
        for ink in ("#f4eeee", "#c4b8ba", "#ff7d8c", "#70d0ff", "#ffb454", "#a98a90"):
            self.assertGreaterEqual((luminance(ink) + 0.05) / (luminance("#1a1115") + 0.05), 4.5, ink)

    def test_every_art_file_the_starter_names_exists(self):
        words = json.loads((KIT / "starter/words.json").read_text(encoding="utf-8"))
        web = KIT / "payload/art/web"
        names = [a["key"] + ".jpg" for a in words["paintings"]] + [f["pic"] for f in words["friends"]]
        names += ["fire_red.gif", "fire_blue.gif", "fire_text.gif", "flame_icon.gif", "stars.png", "stars_twinkle.png",
                  "cursor_sword.png", "die.png", "emblem.png", "mascot.png", "placeholder.png"]
        for name in names:
            self.assertTrue((web / name).is_file(), name)
        for phrase in ("in a row", "days since", "hurry", "don't lose", "streak bonus"):
            self.assertNotIn(phrase, json.dumps(words).lower())


class ReviewFindings(KitCase):
    """DASHBOARD-KIT-001, CHANGELOG 0.1.0-test.2: each of these was seen failing in a simulated review before it was fixed."""

    def ledger(self, target, text):
        (target / "docs/project-ledger.md").write_text("## Items for the user\n\n" + text, encoding="utf-8")

    def needs(self, target):
        return re.search(r'<ul class="needs">(.*?)</ul>', self.page(target), re.S).group(1)

    def overview(self, target, *statuses):
        cards = "".join(f"### P{i}\n\n**Status: {status}**\n\n" for i, status in enumerate(statuses))
        (target / "docs/Works_in_Development.md").write_text("## G\n\n" + cards, encoding="utf-8")

    def test_high_hidden_file_beside_a_longer_visible_name_still_builds(self):
        """Protects README 'Privacy': a harmless neighbor must not stop the build, and the hidden name still stays off."""
        for hidden, visible in ((".mcp.json", ".mcp.json.example"), ("server.pem", "server.pem.txt"), ("mcp.json", "mcp.json copy.txt")):
            target = self.workspace(f"w{hidden}")
            (target / hidden).write_text("HIDDEN_VALUE", encoding="utf-8")
            (target / visible).write_text("x", encoding="utf-8")
            self.install(target)
            page = self.page(target)
            self.assertIn(f">{visible}<", page)
            self.assertNotIn(f">{hidden}<", page)
            self.assertNotIn("HIDDEN_VALUE", page)
            self.ledger(target, f"- Copy {hidden} from {visible}, then see {hidden}.\n")
            self.build(target)
            self.assertNotIn(f"see {hidden}", self.needs(target))
            if " " not in visible:  # with a space, prose cannot tell the two names apart, so the safe reading wins
                self.assertIn(f"from {visible},", self.needs(target))

    def test_high_builds_on_the_oldest_installed_python(self):
        """Protects README 'By hand': the stated minimum must really work, so this runs on the oldest Python on this PC."""
        command = oldest_python()
        if not command:
            self.skipTest("no older Python found")
        self.assertIn("Python 3.9 or newer", (KIT / "README.md").read_text(encoding="utf-8"))
        target = self.workspace()
        result = run(*command, "-B", INSTALLER, target)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Stop the fire", self.page(target))

    def test_high_output_setting_cannot_replace_a_file(self):
        """Protects the installer's 'adding files is its only effect': output falls back to the default and says so."""
        for index, output in enumerate(("README.md", "src/keep.txt", "src/page.html", "src", "dashboard_config.json", f"{FOLDER}/build_dashboard.py")):
            target = self.workspace(f"w{index}")
            for rel, text in (("README.md", "MINE"), ("src/keep.txt", "MINE"), ("src/page.html", "MINE")):
                (target / rel).parent.mkdir(parents=True, exist_ok=True)
                (target / rel).write_text(text, encoding="utf-8")
            (target / "dashboard_config.json").write_text(json.dumps({"output": output}), encoding="utf-8")
            config = (target / "dashboard_config.json").read_bytes()
            self.install(target)
            for rel in ("README.md", "src/keep.txt", "src/page.html"):
                self.assertEqual((target / rel).read_text(encoding="utf-8"), "MINE", output)
            self.assertEqual((target / "dashboard_config.json").read_bytes(), config)
            self.assertIn("was left alone", self.page(target))
            self.assertFalse((target / "README_data.js").exists())
            self.assertIn(b"import", (target / FOLDER / "build_dashboard.py").read_bytes())

    def test_high_a_qualified_status_is_not_live_and_the_doctor_shows_how_it_read(self):
        """Protects START_HERE 'Plain truth': the Beacon must not call half-done work blazing."""
        target = self.workspace()
        self.install(target)
        self.overview(target, "Half done", "Half-done", "Almost done, tests failing", "Nearly finished and done soon", "Not started", "Not done yet", "Partly deployed")
        self.build(target)
        self.assertIn("0 blazing", self.page(target))
        doctor = self.build(target, "--doctor")
        self.assertIn("'Half done' reads as local", doctor)
        self.assertIn("'Not started' reads as idea", doctor)
        self.overview(target, "Done")
        self.assertIn("'Done' reads as live", self.build(target, "--doctor"))

    def test_high_the_steps_give_the_rebuild_command_and_checks_say_they_do_not_rebuild(self):
        """Protects START_HERE step 5: following it exactly must not mean looking at a stale page."""
        steps = (KIT / "START_HERE.md").read_text(encoding="utf-8")
        step_five = steps[steps.index("**5. "):steps.index("**6. ")]
        self.assertLess(step_five.index("build_dashboard.py\n"), step_five.index("--doctor"))
        self.assertIn("build_dashboard.py\n", (KIT / "starter/HOW_TO_FILL.md").read_text(encoding="utf-8"))
        target = self.workspace()
        self.install(target)
        before = (target / PAGE).stat().st_mtime_ns
        for flag in ("--doctor", "--check"):
            self.assertIn("does not rebuild", self.build(target, flag))
        self.assertEqual((target / PAGE).stat().st_mtime_ns, before)

    def test_workspace_folder_named_like_a_hidden_file_still_builds(self):
        """Protects any workspace: its own path and default title are not a leak."""
        for index, (folder, rel) in enumerate((("secrets", "secrets/db.yaml"), (".env", ".env"), ("secrets/app", "secrets/db.yaml"))):
            target = self.base / f"w{index}" / folder
            target.mkdir(parents=True)
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            (target / rel).write_text("x", encoding="utf-8")
            self.install(target)
            self.assertNotIn("db.yaml", self.page(target))

    def test_the_ledger_never_claims_nothing_in_silence(self):
        """Protects START_HERE 'Plain truth': 'Nothing waiting' only when the section is really empty."""
        target = self.workspace()
        self.install(target)
        self.ledger(target, "1. numbered item\n+ plus item\n")
        self.build(target)
        self.assertIn("numbered item", self.needs(target))
        self.assertIn("plus item", self.needs(target))
        self.ledger(target, "prose only\n")
        output = self.build(target)
        self.assertNotIn("Nothing waiting", self.needs(target))
        self.assertIn("not a list item", output)
        self.ledger(target, "- first\n\n## Items for the user\n\n- second\n")
        output = self.build(target)
        self.assertIn("second", self.needs(target))
        self.assertIn("more than once", output)
        self.ledger(target, "- visible\n```\n- lost\n")
        self.assertIn("never closes", self.build(target, "--doctor"))
        self.ledger(target, "")
        self.build(target)
        self.assertIn("Nothing waiting", self.needs(target))

    def test_credential_forms_and_token_names_never_reach_the_page(self):
        """Protects START_HERE rule 6, in documents, file names, the title and the tagline. All values here are fake."""
        fakes = ("password=ZZFAKEPLAINPW", "sk_live_" + "FAKE" * 6, "AIza" + "FAKE" * 7, "github_pat_" + "FAKE" * 6, "msy_" + "FAKE" * 5,
                 "eyJGQUtFRkFLRQ.eyJGQUtFRkFLRQ.c2lnbmF0dXJl", "ASIA" + "FAKE" * 4, "https://fakeuser:ZZFAKEURLPW@example.invalid/x", '"api_key": "abc123xyz"')
        target = self.workspace()
        (target / ("sk-" + "FAKE" * 6 + ".txt")).write_text("x", encoding="utf-8")
        (target / ("AKIA" + "FAKE" * 4)).mkdir()
        (target / ("AKIA" + "FAKE" * 4) / "x.txt").write_text("x", encoding="utf-8")
        self.install(target)
        self.ledger(target, "".join(f"- value {fake}\n" for fake in fakes) + "- The password: is required, see https://example.invalid/x\n")
        self.set_config(target, title="AKIA" + "FAKE" * 4, tagline="sk-" + "FAKE" * 6)
        self.build(target)
        scanned = self.page(target) + self.data(target)
        for leaked in (*fakes, "ZZFAKE", "AKIAFAKE", "sk-FAKE"):
            self.assertNotIn(leaked, scanned)
        self.assertIn("The password: is required", scanned)  # ordinary prose survives

    def test_common_credential_file_names_are_hidden(self):
        """Protects README 'Privacy': names listed here must stay off every list, and their contents unread."""
        names = (".htpasswd", ".pgpass", "private_key.txt", "passphrase.txt", "service-account.json", ".dockercfg", "passwd", "pwd.txt",
                 ".kube/config", "keys.txt", "wallet.dat", "kubeconfig", "vault.yml", "Login Data", ".git-credentials", "APIKEY.txt", "SECRET", ".ENV", "x.KEY")
        target = self.workspace()
        for name in names:
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            (target / name).write_text("ZZFAKE777", encoding="utf-8")
        (target / "plain.txt").write_text("x", encoding="utf-8")
        self.install(target)
        page = self.page(target)
        for name in names:
            self.assertNotIn(f">{name}<", page)
        self.assertNotIn("ZZFAKE777", page)
        self.assertIn(">plain.txt<", page)

    def test_reformatted_hidden_names_and_ordinary_words(self):
        """Protects the scrubber both ways: encoded, wrapped and marked names go, and a plain word stays in prose."""
        target = self.workspace()
        (target / "my api key.txt").write_text("x", encoding="utf-8")
        (target / ".env").write_text("x", encoding="utf-8")
        (target / "tokens").mkdir()
        (target / "tokens/a.txt").write_text("x", encoding="utf-8")
        self.install(target)
        self.ledger(target, "- a my%20api%20key.txt b\n- c %2Eenv d\n- e my api\n  key.txt f\n- g `my api key`.txt h\n- i my **api** key.txt j\n"
                            "- Rotate the tokens before release\n- See tokens/a.txt now\n")
        output = self.build(target)
        self.assertIn("Built", output)
        needs = self.needs(target)
        for left in ("api", "%2Eenv", "tokens/a"):
            self.assertNotIn(left, needs)
        self.assertIn("Rotate the tokens before release", needs)

    def test_a_launcher_page_or_generator_of_your_own_is_respected(self):
        """Protects START_HERE rule 5, and the promise that 'generated' means generated."""
        target = self.workspace("launcher")
        (target / "Open_Dashboard.cmd").write_text("@echo MINE\n", encoding="utf-8")
        (target / "Open_Dashboard.sh").write_text("echo MINE\n", encoding="utf-8")
        output = self.install(target, "--force")
        self.assertIn("MINE", (target / "Open_Dashboard.cmd").read_text(encoding="utf-8"))
        self.assertIn("MINE", (target / "Open_Dashboard.sh").read_text(encoding="utf-8"))
        self.assertIn("left alone", output)
        self.assertNotIn("Open it with", output)
        self.assertNotIn("open with Open_Dashboard", self.page(target))

        target = self.workspace("page")
        for rel, text in ((PAGE, "MY PAGE\n"), (DATA, "MY JS\n")):
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            (target / rel).write_text(text, encoding="utf-8")
        before = snapshot(target)
        self.assertIn("Refused", self.install(target, expect=2))
        self.assertEqual(snapshot(target), before)

        target = self.workspace("generator")
        (target / FOLDER).mkdir()
        (target / FOLDER / "build_dashboard.py").write_text("print('mine ran')\n", encoding="utf-8")
        output = self.install(target, expect=2)
        self.assertIn("was not run", output)
        self.assertNotIn("mine ran", output)
        self.assertNotIn("generated", output)

    def test_bad_input_gives_a_message_never_a_traceback_or_half_an_install(self):
        """Protects START_HERE 'If something goes wrong'. Installer first, then the generator."""
        for index, config in enumerate(("[]", '"hello"', "[" * 200000)):
            target = self.workspace(f"c{index}")
            (target / "dashboard_config.json").write_text(config, encoding="utf-8")
            result = run(sys.executable, "-B", INSTALLER, target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stdout + result.stderr)
            self.assertIn("could not be read", self.page(target))
        target = self.workspace("docs_is_a_file")
        (target / "docs").write_text("a file", encoding="utf-8")
        before = snapshot(target)
        self.assertIn("Refused", self.install(target, expect=2))
        self.assertEqual(snapshot(target), before)
        target = self.workspace("config_is_a_folder")
        (target / "dashboard_config.json").mkdir()
        self.assertIn("Refused", self.install(target, expect=2))
        self.assertEqual(snapshot(target), {})
        target = self.workspace("nul_in_a_path")
        (target / "dashboard_config.json").write_text('{"overview": "a\\u0000b.md"}', encoding="utf-8")
        self.assertIn("Refused", self.install(target, expect=2))

        target = self.workspace("generator")
        (target / "README.md").write_text("- a\n", encoding="utf-8")
        (target / "notes.md").write_text("Real words are here.\n", encoding="utf-8")
        self.install(target)
        for record in ({"path": "README.md", "section": 5}, {"path": "README.md", "match": 5}):
            self.set_config(target, live_record=record)
            self.assertIn("must be text", self.build(target))
        self.set_config(target, live_record=None)
        self.set_words(target, friends=[{"pic": "avatar_1.png", "name": "n", "says": "hi", "evidence": 5, "file": "notes.md"}])
        self.assertIn("evidence must be text", self.build(target))
        words = target / FOLDER / "words.json"
        words.write_text("[" * 200000, encoding="utf-8")
        self.assertIn("nested too deeply", self.build(target))
        (target / FOLDER / "Guestbook.md").unlink()
        (target / FOLDER / "Guestbook.md").mkdir()
        self.assertIn("could not be read", self.build(target))
        (target / FOLDER / "theme.css").unlink()
        output = self.build(target, expect=1)
        self.assertIn("theme.css missing", output)

    def test_words_cannot_pass_for_evidence(self):
        """Protects START_HERE rule 4: invented figures, fake attributions and meaningless matches stay off the page."""
        target = self.workspace()
        (target / "notes.md").write_text("Ship it.\nThe quick brown fox jumps.\nGrace Hopper wrote 12 words here.\n", encoding="utf-8")
        self.install(target)
        self.set_words(target, lines=[{"text": "Ship it.", "who": "x", "file": "notes.md"}, {"text": "t", "who": "x", "file": "notes.md"},
                                      {"text": "The quick brown fox jumps.", "who": "Albert Einstein", "file": "notes.md"},
                                      {"text": "wrote 12 words here", "who": "Grace Hopper", "file": "notes.md"}],
                       friends=[{"pic": "avatar_1.png", "name": "Sarah", "says": "We closed 1,372 tickets."},
                                {"pic": "avatar_2.png", "name": "ok", "says": "{files} files, hello."},
                                {"pic": "avatar_3.png", "name": "cited", "says": "It wrote 12 words.", "evidence": "wrote 12 words", "file": "notes.md"}])
        self.build(target)
        fire = self.fire_json(target)
        self.assertEqual([(l["text"], l["who"]) for l in fire["lines"]],
                         [("The quick brown fox jumps.", "notes.md"), ("wrote 12 words here", "Grace Hopper")])
        self.assertEqual([c["name"] for c in fire["comments"]], ["ok", "cited"])
        self.assertIn("Flavor text", self.page(target))

    def test_counts_leave_out_the_kit_and_claims_need_backing(self):
        """Protects 'own_pathspec' and 'Plain truth': an empty workspace reports nothing it does not have."""
        target = self.workspace()
        output = self.install(target)
        self.assertIn("11 placeholders", self.page(target))
        doctor = self.build(target, "--doctor")
        self.assertIn('"files": 0', doctor)
        self.assertIn("0 files", output + doctor)
        self.assertIn("has no ### project headings", doctor)
        page = self.page(target)
        self.assertIn("All files (0)", page)
        self.assertNotIn(">dashboard_config.json<", page)
        for claim in ("8 friends", "extended network", "Mood:"):
            self.assertNotIn(claim, page)
        self.assertIn("no real friends yet", page)
        self.assertIn("decoration", page)
        self.ledger(target, "- edited\n")
        self.build(target)
        self.assertIn("All files (1)", self.page(target))
        self.assertIn('Not linked from any project <span class="count">0<', self.page(target))

    @unittest.skipUnless(HAS_GIT, "Git required")
    def test_change_count_is_files_and_a_fresh_clone_is_not_new_work(self):
        """Protects the header and the activity widgets from a misleading reading of Git and file dates."""
        target = self.workspace()
        self.git(target, "init", "-q")
        (target / "old.py").write_text("x", encoding="utf-8")
        self.git(target, "add", "old.py")
        result = run("git", "-c", "commit.gpgsign=false", "commit", "-qm", "old", cwd=target,
                     env={**ENV, "GIT_AUTHOR_DATE": "2020-01-01T00:00:00", "GIT_COMMITTER_DATE": "2020-01-01T00:00:00"})
        self.assertEqual(result.returncode, 0, result.stderr)
        (target / "new").mkdir()
        (target / "new/one.py").write_text("x", encoding="utf-8")
        (target / "new/two.py").write_text("x", encoding="utf-8")
        self.install(target)
        data = json.loads(self.data(target)[len("window.onDashData("):-3])
        self.assertEqual(data["change_note"], "2 uncommitted changes outside the dashboard")
        changed = {e["path"]: e["changed"] for e in data["files_changed"]}
        self.assertLess(changed["old.py"], 1600000000)
        self.assertGreater(changed["new/one.py"], 1600000000)

    def test_only_the_updater_marks_the_page_live(self):
        """Protects the header: a page built by hand a moment ago must not say Live."""
        target = self.workspace()
        self.install(target)
        self.assertIn('"updater": false', self.data(target))
        self.assertIn("!!data.updater", self.page(target))
        self.set_config(target, watch_seconds=30)
        process = subprocess.Popen([sys.executable, "-B", str(target / FOLDER / "build_dashboard.py"), "--watch"], cwd=target, env=ENV,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        self.addCleanup(process.wait, 10)
        self.addCleanup(process.kill)
        for _ in range(100):
            if '"updater": true' in self.data(target):
                break
            time.sleep(0.1)
        self.assertIn('"updater": true', self.data(target))

    def test_a_copied_id_and_a_full_set_of_ports(self):
        """Protects README 'Two dashboards at once': a copied id does not stop another workspace, and no port means no second updater."""
        one, two = self.workspace("one"), self.workspace("two")
        for target in (one, two):
            (target / "dashboard_config.json").write_text('{"id": "sharedid", "watch_seconds": 30}', encoding="utf-8")
            self.install(target)
        first = subprocess.Popen([sys.executable, "-B", str(one / FOLDER / "build_dashboard.py"), "--watch"], cwd=one, env=ENV, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
        self.addCleanup(first.stdout.close)
        self.addCleanup(first.wait, 10)
        self.addCleanup(first.kill)
        self.assertIn("Updating", first.stdout.readline())  # the first holds its lock and answers before the second starts
        second = subprocess.Popen([sys.executable, "-B", str(two / FOLDER / "build_dashboard.py"), "--watch"], cwd=two, env=ENV, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
        self.addCleanup(second.stdout.close)
        self.addCleanup(second.wait, 10)
        self.addCleanup(second.kill)
        self.assertIn("share browser storage", second.stdout.readline())
        self.assertIn("Updating", second.stdout.readline())
        self.assertIn("share browser storage", self.build(one, "--doctor"))
        self.assertIsNone(first.poll())
        first.kill()
        second.kill()
        first.wait(10)
        second.wait(10)

        target = self.workspace("full")
        self.install(target)
        spec = importlib.util.spec_from_file_location("kit_ports", target / FOLDER / "build_dashboard.py")
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        generator.ask_lock = lambda port: ""  # each probe of a port that is not listening would wait out its timeout
        held = [socket.socket() for _ in generator.lock_ports()]
        output = io.StringIO()
        try:
            for server, number in zip(held, generator.lock_ports()):
                server.bind(("127.0.0.1", number))
            with contextlib.redirect_stdout(output):
                self.assertEqual(generator.watch(), 1)
            self.assertIn("did not start", output.getvalue())
        finally:
            for server in held:
                server.close()

    def test_preservation_glob_stays_inside_and_long_lines_stay_fast(self):
        """Protects 'plain truth' and the updater's cycle: outside files give no number, and a line of brackets is not slow."""
        target = self.workspace()
        (self.base / "outside.tsv").write_text("a\nb\nc\nd\n", encoding="utf-8")
        (target / "dashboard_config.json").write_text('{"preservation_glob": "../*.tsv"}', encoding="utf-8")
        self.install(target)
        doctor = self.build(target, "--doctor")
        self.assertNotIn('"preserved"', doctor)
        self.assertIn("outside this workspace", doctor)
        (target / "docs/Works_in_Development.md").write_text("[" * 32000 + "\n", encoding="utf-8")
        started = time.time()
        self.build(target)
        self.assertLess(time.time() - started, 3)

    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_file_walk_does_not_follow_a_junction_out(self):
        """Protects 'the workspace's own data': files outside are not listed by a workspace without Git."""
        target = self.workspace()
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "plain.txt").write_text("x", encoding="utf-8")
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(target / "linked"), str(outside)], capture_output=True, stdin=subprocess.DEVNULL)
        if made.returncode != 0:
            self.skipTest("could not make a junction")
        self.addCleanup(os.rmdir, target / "linked")
        self.install(target)
        self.assertNotIn("linked/plain.txt", self.page(target))


def oldest_python():
    """The command for the oldest Python this PC has, older than the one running the tests, or None."""
    if shutil.which("py"):
        versions = re.findall(r"-(?:V:)?(\d+)\.(\d+)", run("py", "-0").stdout)
        older = sorted((int(a), int(b)) for a, b in versions if (int(a), int(b)) < sys.version_info[:2])
        return ["py", f"-{older[0][0]}.{older[0][1]}"] if older else None
    for minor in range(9, sys.version_info[1]):
        if shutil.which(f"python3.{minor}"):
            return [f"python3.{minor}"]
    return None


class SecondReview(KitCase):
    """DASHBOARD-KIT-001, 0.1.0-test.3: each test holds one verified review finding fixed. Plain truth and privacy, START_HERE."""

    def cards(self, target, *bodies):
        (target / "docs" / "Works_in_Development.md").write_text("## G\n\n" + "\n".join(bodies), encoding="utf-8")

    @unittest.skipUnless(HAS_GIT, "Git required")
    def test_names_only_in_git_history_are_hidden(self):
        """Protects START_HERE step 5: a credential file gone from disk must not be named by its commit subject."""
        target = self.workspace()
        self.git(target, "init", "-q")
        (target / "a.txt").write_text("x", encoding="utf-8")
        self.git(target, "add", ".")
        self.git(target, "commit", "-qm", "add .env and my api key.txt, rotate the tokens")
        self.git(target, "commit", "-q", "--allow-empty", "-m", "remove credentials.json")
        self.install(target)
        text = self.page(target) + self.data(target)
        for name in (".env ", "api key.txt", "credentials.json"):
            self.assertNotIn(name, text)
        self.assertIn("rotate the tokens", text)

    def test_common_credential_names_are_hidden(self):
        """Protects README 'Privacy': near misses of the .env rule and common credential names."""
        target = self.workspace()
        names = ("prod.env.bak", "env.production", "creds.txt", "auth.json", "cookies.txt", "pass.txt")
        for name in names:
            (target / name).write_text("x", encoding="utf-8")
        self.install(target)
        text = self.page(target) + self.data(target)
        for name in names:
            self.assertNotIn(name, text)

    def test_utf16_config_is_read_by_the_installer(self):
        """Protects README 'What gets written where': a mapped document gets no stray starter, whatever the config's encoding."""
        target = self.workspace()
        (target / "dashboard_config.json").write_text('{"title":"U16","overview":"plan/status.md"}', encoding="utf-16")
        output = self.install(target)
        self.assertNotIn("could not be read", output)
        self.assertFalse((target / "docs" / "Works_in_Development.md").exists())
        self.assertTrue((target / "plan" / "status.md").exists())

    def test_preflight_refuses_before_any_write(self):
        """Protects the installer's promise that every path is checked before the first write."""
        for name, value in (("folder", FOLDER), ("long", "x" * 5000 + ".md")):
            target = self.workspace(name)
            (target / "dashboard_config.json").write_text(json.dumps({"overview": value}), encoding="utf-8")
            result = run(sys.executable, "-B", INSTALLER, target)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual([p.name for p in target.iterdir()], ["dashboard_config.json"])

    @unittest.skipUnless(os.name == "nt", "Windows file name rules")
    def test_forbidden_output_name_falls_back(self):
        """Protects START_HERE 'If something goes wrong': a bad output value is a note, not a traceback."""
        target = self.workspace()
        (target / "dashboard_config.json").write_text('{"output": "a<b>?.html"}', encoding="utf-8")
        self.assertIn("does not allow", self.install(target))
        self.assertTrue((target / PAGE).is_file())

    def test_launcher_names_its_workspace(self):
        """Protects README 'Two dashboards at once': an updater can be told apart in a process list."""
        target = self.workspace()
        self.install(target)
        self.assertIn(b'"%~dp0workspace_dashboard\\build_dashboard.py" --watch', (target / "Open_Dashboard.cmd").read_bytes())
        self.assertIn(b'"$PWD/workspace_dashboard/build_dashboard.py" --watch', (target / "Open_Dashboard.sh").read_bytes())

    def test_doctor_reports_the_updater_pid(self):
        """Protects stopping an updater by its own PID, without touching another workspace's."""
        target = self.workspace()
        self.install(target)
        self.assertIn("Updater: not running", self.build(target, "--doctor"))
        process = subprocess.Popen([sys.executable, "-B", str(target / FOLDER / "build_dashboard.py"), "--watch"], cwd=target, env=ENV,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        deadline, output = time.time() + 15, ""
        while time.time() < deadline and f"PID {process.pid}" not in output:
            output = self.build(target, "--doctor")
        self.assertIn(f"PID {process.pid}", output)

    def test_default_credit_makes_no_claim(self):
        """Protects 'Plain truth': a stranger's page must not call the kit's paintings their art, and must say the credit is open."""
        target = self.workspace()
        output = self.install(target)
        self.assertNotIn("Your art", self.page(target))
        self.assertIn("Art that came with this kit", self.page(target))
        self.assertIn("4 paintings", output)
        self.assertIn("default credit", self.page(target))
        self.assertIn("Motion: 'always'", self.build(target, "--doctor"))

    def test_decisions_do_not_claim_reasons(self):
        """Protects 'Plain truth': a bare heading has no reason, so the starter words must not claim one."""
        words = (KIT / "starter" / "words.json").read_text(encoding="utf-8")
        self.assertNotIn("reasons", words)

    def test_prose_in_a_spec_folder_is_not_a_test(self):
        """Protects 'Plain truth': only code files count as tests."""
        target = self.workspace()
        for rel in ("specs/design.md", "tests/notes.txt", "test_plan.md"):
            (target / rel).parent.mkdir(exist_ok=True)
            (target / rel).write_text("notes", encoding="utf-8")
        self.install(target)
        self.assertIn('"tests": 0', self.build(target, "--doctor"))
        (target / "tests" / "test_a.py").write_text("x", encoding="utf-8")
        self.assertIn('"tests": 1', self.build(target, "--doctor"))

    def test_unbacked_friends_are_dropped_and_claims_noted(self):
        """Protects START_HERE step 4 Words: a comment needs a number or evidence, and typed figures are reported."""
        target = self.workspace()
        (target / "a.md").write_text("x", encoding="utf-8")
        self.install(target)
        self.set_words(target, friends=[{"pic": "avatar_1.png", "name": "Linus Torvalds", "says": "I reviewed this code and it is the best."},
                                        {"pic": "avatar_2.png", "name": "spoon", "says": "Seventy customers. {files} files."},
                                        {"pic": "avatar_3.png", "name": "fork", "says": "{files} files here."}],
                       marquee=["1,500,000 downloads"], about=["We have nine hundred customers."],
                       profile={"name": "The Director", "tagline": "", "mood": "", "network": "", "interests": []})
        output = self.build(target)
        self.assertEqual([c["name"] for c in self.fire_json(target)["comments"]], ["fork"])
        for note in ("marquee[0] has a typed number", "about[0] has a typed number", "friends[0] looks like a real person", "still has the starter name"):
            self.assertIn(note, output)

    def test_hot_needs_recent_work_and_must_mean_something(self):
        """Protects 'Plain truth': HOT! is not on old files, not on ideas, and not on every card."""
        target = self.workspace()
        for name in ("new1", "new2", "idea", "old"):
            (target / f"{name}.txt").write_text("x", encoding="utf-8")
        old = time.time() - 40 * 86400
        os.utime(target / "old.txt", (old, old))
        self.install(target)
        card = "### {0}\n\n**Status: {1}**\n\n[f](../{0}.txt)\n"
        self.cards(target, card.format("new1", "Working"), card.format("idea", "Not started"), card.format("old", "Working"))
        self.build(target)
        self.assertEqual(self.page(target).count('class="hot"'), 1)
        self.cards(target, card.format("new1", "Working"), card.format("new2", "Working"))
        self.build(target)
        self.assertNotIn('class="hot"', self.page(target))

    def test_under_way_leaves_out_ideas_and_blanks(self):
        """Protects 'Plain truth': a card marked not started is not on the anvil."""
        target = self.workspace()
        self.install(target)
        self.cards(target, "### a\n\n**Status: Working**\n", "### b\n\n**Status: Not started**\n", "### c\n", "### d\n\n**Status: Blocked**\n", "### e\n\n**Status: Live**\n")
        self.assertIn('"under_way": 2', self.build(target, "--doctor"))

    def test_placeholder_note_and_heading_name_what_is_left(self):
        """Protects 'Visible means real': the note says which placeholders remain, and the invented name heads nothing."""
        target = self.workspace()
        self.install(target)
        self.set_words(target, friends=[{"pic": "avatar_1.png", "name": "spoon", "says": "{projects} here."}], lines=[], late_night={})
        self.build(target)
        page = self.page(target)
        self.assertIn("still to replace (profile)", page)
        self.assertNotIn("The Director&#x27;s Friend Space", page)
        self.assertIn("Friend Space: 1 friend", page)

    def test_zip_script_warns_about_older_zips_without_deleting(self):
        """Protects README 'The one prompt': there must be no doubt which zip is current. Deleting one is the developer's call."""
        old = self.base / "workspace_dashboard_kit_0.0.0.zip"
        old.write_bytes(b"x")
        result = run(sys.executable, "-B", KIT / "make_kit_zip.py", "--out", self.base / "new.zip")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("older zips", result.stdout)
        self.assertTrue(old.exists())


class Package(KitCase):
    """DASHBOARD-KIT-001, README 'In this kit'."""

    def test_zip_has_no_pycache_and_installs(self):
        (KIT / "kit_tests" / "__pycache__").mkdir(exist_ok=True)  # the zip must leave this out even when it exists
        self.addCleanup(shutil.rmtree, KIT / "kit_tests" / "__pycache__", ignore_errors=True)
        out = self.base / "kit.zip"
        result = run(sys.executable, "-B", KIT / "make_kit_zip.py", "--out", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(out) as archive:
            names = archive.namelist()
            archive.extractall(self.base / "unzipped")
        self.assertFalse([n for n in names if "__pycache__" in n or n.endswith(".pyc")])
        self.assertIn("workspace_dashboard_kit/START_HERE.md", names)
        target = self.workspace()
        result = run(sys.executable, "-B", self.base / "unzipped/workspace_dashboard_kit/install_dashboard.py", target)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((target / PAGE).exists())

    def test_kit_holds_no_generated_output_or_credentials(self):
        """Protects: no page with local paths and no credential file travels with the kit."""
        for path in KIT.rglob("*"):
            self.assertNotIn(path.name, ("Workspace_Dashboard.html", "Workspace_Dashboard_data.js", ".mcp.json"))
            self.assertNotIn("api key", path.name.lower())

    def test_version_is_semver_and_kit_is_reasonably_small(self):
        version = (KIT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$")
        size = sum(p.stat().st_size for p in KIT.rglob("*") if p.is_file())
        self.assertLess(size, 3_000_000)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell required")
    def test_explorer_handler_refuses_everything_outside(self):
        """Protects the opt-in Explorer links, validate-only: nothing is registered or opened by this test."""
        target = self.workspace()
        self.install(target)
        (target / "docs/My File.md").write_text("x", encoding="utf-8")
        handler = target / FOLDER / "optional/explorer_links/open_in_explorer.ps1"
        cases = {"wsdash-abcd1234:docs/My%20File.md": 0, "wsdash-abcd1234:C:/Windows/System32/calc.exe": 1, "wsdash-abcd1234:../../Windows": 1,
                 f"wsdash-abcd1234:../{target.name}-other/x": 1, "wsdash-abcd1234:%5C%5Cserver%5Cshare": 1, "wsdash-abcd1234:docs/not-real.md": 1}
        for link, expected in cases.items():
            result = run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", handler, "-Link", link, "-ValidateOnly")
            self.assertEqual(result.returncode, expected, f"{link}: {result.stdout}{result.stderr}")


class ThirdReview(KitCase):
    """README 'Privacy' and HOW_TO_FILL. Simulated, and every credential here is fake."""

    def git(self, target, *args):
        result = run("git", *args, cwd=target)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def built(self, ledger="", overview=None, **words):
        target = self.workspace(f"w{getattr(self, 'count', 0)}")
        self.install(target)
        (target / "docs/project-ledger.md").write_text(f"## Items for the user\n\n{ledger}", encoding="utf-8")
        if overview:
            (target / "docs/Works_in_Development.md").write_text(overview, encoding="utf-8")
        return target, self.build(target)

    def test_each_labelled_form_withholds_the_line_and_every_copy_of_the_value(self):
        forms = {"Authorization: Bearer ZZFAKEBEARER9": "ZZFAKEBEARER9", "Authorization: Bearer zzfakealpha": "zzfakealpha",
                 "token: ZZFAKETOKEN9": "ZZFAKETOKEN9", "secret = ZZFAKESECRET": "ZZFAKESECRET", "pass: zzfakepass": "zzfakepass",
                 "passphrase: zzfakephrase": "zzfakephrase", "**token:** `ZZFAKEMARKED9`": "ZZFAKEMARKED9",
                 'pass: "zz fake quoted"': "zz fake quoted", "DB_PASS=ZZFAKEDB": "ZZFAKEDB"}
        for form, value in forms.items():
            with self.subTest(form):
                self.count = getattr(self, "count", 0) + 1
                target, output = self.built(f"- CONTEXTWORD {form} more\n- Keep this line about Rotate the tokens\n- Elsewhere {value} again\n")
                scanned = self.page(target) + self.data(target)
                self.assertNotIn(value, scanned)
                self.assertNotIn("CONTEXTWORD", scanned)
                self.assertIn("Rotate the tokens", scanned)
                self.assertIn("[hidden value]", scanned)
                self.assertIn("docs/project-ledger.md: 1 line looks like a credential", output)

    def test_value_in_a_later_source_leaves_earlier_documents_and_file_lists(self):
        target = self.workspace()
        (target / "zzfakeshared.txt").write_text("x", encoding="utf-8")
        self.install(target)
        (target / "docs/Works_in_Development.md").write_text("## G\n\n### P\n\n**Status: Live**\n\nUses zzfakeshared here.\n", encoding="utf-8")
        (target / "docs/decision-log.md").write_text("Notes\n\npass: zzfakeshared\n", encoding="utf-8")
        self.build(target)
        self.assertNotIn("zzfakeshared", self.page(target) + self.data(target))

    def test_private_key_block_goes_whole(self):
        target, output = self.built("- before\n-----BEGIN PRIVATE KEY-----\nZZFAKEBODY\n-----END PRIVATE KEY-----\n- after item\n")
        self.assertNotIn("ZZFAKEBODY", self.page(target))
        self.assertIn("3 lines look like a credential", output)
        self.assertIn("after item", self.page(target))

    def test_words_entry_with_a_credential_is_dropped_and_the_file_still_parses(self):
        target = self.workspace()
        self.install(target)
        self.set_words(target, webring="token: ZZFAKEWORD9")
        output = self.build(target)
        self.assertNotIn("ZZFAKEWORD9", self.page(target))
        self.assertNotIn("could not be read", output)

    def test_prose_survives(self):
        prose = ("Rotate the tokens", "The password: is required, see the guide", "Tests pass: 12 of 14", "First token: needs a new home soon",
                 "max_tokens: 4000", "bypass the bearer token check", "Authorization: required")
        target, output = self.built("".join(f"- {line}\n" for line in prose))
        page = self.page(target)
        for line in prose:
            self.assertIn(line, page)
        self.assertNotIn("withheld", output)

    def test_note_is_truthful(self):
        target, output = self.built("- token: ZZFAKE1\n- secret = ZZFAKE2\n")
        self.assertIn("docs/project-ledger.md: 2 lines look like a credential", output)
        self.assertIn("Detection is by pattern and can miss things", output)
        for claim in ("clean", "no credentials", "safe"):
            self.assertNotIn(claim, " ".join(l for l in output.splitlines() if "withheld" in l).lower())
        readme = (KIT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Detection is by pattern and can miss things", readme)

    def test_more_credential_file_names_are_hidden(self):
        names = ("id_ecdsa", "id_dsa", ".netrc", ".npmrc", ".pypirc", "a.pfx", "a.p12", "a.kdbx", "credentials.json", "service-account-prod.json",
                 ".aws/credentials", "a.jks", "a.ppk", "_netrc", ".s3cfg", "ZZ.KDBX")
        target = self.workspace()
        for name in names:
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            (target / name).write_text("ZZFAKE777", encoding="utf-8")
        (target / "plain.txt").write_text("x", encoding="utf-8")
        self.install(target)
        text = self.page(target) + self.data(target)
        for name in names:
            self.assertNotIn(name, text)
        self.assertNotIn("ZZFAKE777", text)
        self.assertIn("plain.txt", text)

    @unittest.skipUnless(HAS_GIT, "Git required")
    def test_header_does_not_say_committed_with_untracked_files(self):
        target = self.workspace()
        self.git(target, "init", "-q")
        (target / "a.py").write_text("x", encoding="utf-8")
        self.git(target, "add", "a.py")
        self.git(target, "commit", "-qm", "first")
        self.install(target)
        text = self.page(target) + self.data(target)
        self.assertNotIn("Everything is committed", text)
        self.assertIn("not committed", text)
        (target / "new.txt").write_text("x", encoding="utf-8")
        self.build(target)
        self.assertNotIn("Everything is committed", self.page(target) + self.data(target))

    def test_unrecognised_status_is_an_idea_at_heat_one(self):
        target = self.workspace()
        self.install(target)
        (target / "docs/Works_in_Development.md").write_text("## G\n\n### P\n\n**Status: Purple monkey**\n", encoding="utf-8")
        doctor = self.build(target, "--doctor")
        self.assertIn("'Purple monkey' reads as idea, heat 1. No recognised status word", doctor)

    def test_low_items(self):
        theme = (KIT / "payload/theme.js").read_text(encoding="utf-8")
        self.assertIn("campGo.hidden = !F.camps.length", theme)
        target, _ = self.built("- **Word:** the longer explanation here. More.\n")
        fire = re.search(r"window\.FIRE = (.*?);</script>", self.page(target), re.S).group(1)
        self.assertEqual(json.loads(fire)["sparks"], ["Word: the longer explanation here."])


def find_browser():
    if os.environ.get("KIT_TEST_BROWSER") == "0":
        return None
    candidates = [shutil.which(n) for n in ("chrome", "google-chrome", "chromium", "msedge")]
    candidates += [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    return next((c for c in candidates if c and Path(c).exists()), None)


class FourthReview(KitCase):
    """README 'Privacy'. Simulated, and every credential here is fake."""
    V = "FaKe0883x9Zq"

    def built(self, ledger="", overview=None, expect=0):
        self.count = getattr(self, "count", 0) + 1
        target = self.workspace(f"r{self.count}")
        self.install(target)
        (target / "docs/project-ledger.md").write_text(f"## Items for the user\n\n{ledger}", encoding="utf-8")
        if overview:
            (target / "docs/Works_in_Development.md").write_text(overview, encoding="utf-8")
        return target, self.build(target, expect=expect)

    def needs(self, target):
        return re.search(r'id="needs">(.*?)</section>', self.page(target), re.S).group(1)

    def test_more_labelled_forms_are_withheld(self):
        forms = ("tokens: V", "passwords: V", "secrets: V", "TOKEN_PROD=V", "PASSWORD_2=V", "API_KEY_OLD=V", "mytoken=V", "dbpass=V", "bottoken: V",
                 "token (prod): V", "token -> V", "password - V", "--password V", "--token V", "mysql -uroot -pV", "Cookie: sessionid=V",
                 "https://example.invalid/x?sig=V", "key: V", "token: <V>", "secret: (V)", "secret: |V|", "secret: [V]", "<password>V</password>",
                 "token\uff1aV", "[lbl](https://example.invalid/token%3A%20V)")
        for form in forms:
            with self.subTest(form):
                target, output = self.built(f"- CONTEXT {form.replace('V', self.V)}\n")
                self.assertNotIn(self.V, self.page(target))
                self.assertNotIn("CONTEXT", self.page(target))
                self.assertIn("looks like a credential", output)

    def test_short_numeric_value_alone_on_its_line(self):
        target, output = self.built("- pass: 74251\n- token: 74xxx\n")
        for value in ("74251", "74xxx"):
            self.assertNotIn(value, self.needs(target))
        self.assertIn("2 lines look like a credential", output)

    def test_ordinary_writing_stays(self):
        prose = ("Tests pass: 1200", "Tests pass: 12 of 14", "max_tokens: 4000", "tokens: 1500 used", "secrets: none", "Use the --token option", "password - rotate quarterly",
                 "compass: north", "key: the old one", "token: [the docs](https://example.invalid/d)", "api-reference2.md is the guide")
        target, output = self.built("".join(f"- {line}\n" for line in prose))
        self.assertNotIn("withheld", output)
        needs = self.needs(target)
        for word in ("1200", "4000", "1500 used", "--token option", "rotate quarterly", "the old one", "the docs"):
            self.assertIn(word, needs)

    def test_altered_copies_of_a_value_go(self):
        for copy in ("FAKERPT7X9ZQ", "fakerpt7x9zq", "FaKeRpt7x9Zq_old", "prodFaKeRpt7x9Zq", "FaKeR**pt7x9Zq**", "RmFLZVJwdDd4OVpx"):
            with self.subTest(copy):
                target, _ = self.built("- token: FaKeRpt7x9Zq\n", f"# W\n\n### Thing\n\nStatus: Local\n\nSummary {copy} end\n")
                page = self.page(target).lower()
                self.assertNotIn("pt7x9zq", page)
                self.assertNotIn("rmflzvj", page)

    def test_plain_word_value_goes_only_whole(self):
        target, _ = self.built("- pass: orange\n", "# W\n\n### Thing\n\nStatus: Local\n\nAn ORANGE and some oranges.\n")
        page = self.page(target)
        self.assertNotIn("ORANGE", page)
        self.assertIn("oranges", page)

    def test_encoded_link_in_a_project_document(self):
        target, output = self.built("", f"# W\n\n### Thing\n\nStatus: Local\n\nSee [lbl](https://example.invalid/token%3A%20{self.V})\n")
        self.assertNotIn(self.V, self.page(target))
        self.assertIn("docs/Works_in_Development.md: 1 line looks like a credential", output)

    def test_value_only_in_the_config_is_reported(self):
        target = self.workspace("cfg")
        self.install(target)
        self.set_config(target, _note="token: FaKeRpt7x9Zq")
        (target / "docs/Works_in_Development.md").write_text("# W\n\n### P\n\nStatus: Local\n\nFaKeRpt7x9Zq\n", encoding="utf-8")
        output = self.build(target)
        self.assertIn("dashboard_config.json: 1 line looks like a credential", output)
        self.assertNotIn("FaKeRpt7x9Zq", self.page(target))
        self.assertIn("withheld from", self.page(target))

    def test_credential_shaped_file_names_are_hidden(self):
        names = ("dbpass-FaKeShape5.txt", "auth=FaKeShape7.txt", "key=FaKeShape8.txt", "api-FaKeShape9.key.txt", "pass=FaKeShape1.txt")
        target = self.workspace("names")
        for name in names:
            (target / name).write_text("x", encoding="utf-8")
        (target / "api-reference2.md").write_text("x", encoding="utf-8")
        self.install(target)
        self.build(target)
        page = self.page(target) + self.data(target)
        self.assertNotIn("FaKeShape", page)
        self.assertIn("api-reference2.md", page)

    def test_stop_message_names_the_pattern_and_the_document(self):
        target = self.workspace("stop")
        self.install(target)
        spec = importlib.util.spec_from_file_location("dash_stop", target / FOLDER / "build_dashboard.py")
        dash = importlib.util.module_from_spec(spec)
        sys.modules["dash_stop"] = dash
        spec.loader.exec_module(dash)
        g = {"scrub": dash.Scrubber([]), "tracked": [], "ignored": [], "texts": {}, "guestbook": "", "commits": [], "words": {},
             "raw_docs": {"docs/a.md": "see old.env.bak"}}
        report = dash.leak_report(g, "<p>old.env.bak</p>", "")
        self.assertIn("a name matching a hidden-name pattern", report)
        self.assertIn("docs/a.md", report)

    def test_counts_and_doctor_wording(self):
        target, output = self.built("- A\n- B\n- ~~Old thing~~\n", "# W\n\n### Planner\n\nStatus: Not live; planned\n")
        self.assertIn("2 items for you, 1 resolved", output)
        self.assertIn("Needs you (2)", self.page(target))
        doctor = self.build(target, "--doctor")
        self.assertIn("2 items for the user, 1 resolved", doctor)
        self.assertIn("The first clause held no recognised word", doctor)


@unittest.skipUnless(find_browser(), "Chrome or Edge required")
class RenderedPage(KitCase):
    """DASHBOARD-KIT-001: the page script must really run on a fresh install. Headless, throwaway profile, no network."""

    def render(self, page):
        profile = self.base / "profile"
        result = subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-first-run", "--disable-background-networking",
                                 "--disable-sync", "--disable-component-update", "--disable-extensions", f"--user-data-dir={profile}",
                                 "--virtual-time-budget=2500", "--dump-dom", page.as_uri()],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=40)
        return result.stdout

    def test_fresh_install_runs_and_survives_empty_data(self):
        """Protects the audit's blank-section failure: quotes empty must not kill comments, Spark or the counter."""
        target = self.workspace("sp\u00e9ce & co")
        (target / "a#b c.md").write_text("x", encoding="utf-8")
        self.install(target)
        dom = self.render(target / PAGE)
        self.assertIn("No quotes yet", dom)
        self.assertRegex(dom, r'class="comment[ "]')
        self.assertIn("Fill in the dashboard", re.search(r'id="spark">(.*?)</p>', dom, re.S).group(1))
        self.assertIn("a%23b%20c.md", re.search(r'id="docs_changed">(.*?)</ul>', dom, re.S).group(1))
        self.assertIn('id="hits"><b>0</b><b>0</b><b>0</b><b>0</b><b>0</b><b>1</b>', dom)
        # A second workspace in the same browser profile starts its own count: file pages share storage otherwise.
        other = self.workspace("other")
        self.install(other)
        self.assertIn('id="hits"><b>0</b><b>0</b><b>0</b><b>0</b><b>0</b><b>1</b>', self.render(other / PAGE))
        self.assertIn('id="hits"><b>0</b><b>0</b><b>0</b><b>0</b><b>0</b><b>2</b>', self.render(target / PAGE))
        page = self.page(target)
        fire = re.search(r"window\.FIRE = (.*?);</script>", page, re.S).group(1)
        emptied = page.replace(fire, json.dumps({**json.loads(fire), "lines": [], "art": [], "projects": [], "sparks": [], "camps": []}))
        (target / "emptied.html").write_text(emptied.replace('src="art/', 'src="workspace_dashboard/art/').replace('src="Workspace_Dashboard_data.js"', 'src="workspace_dashboard/Workspace_Dashboard_data.js"'), encoding="utf-8")
        dom = self.render(target / "emptied.html")
        self.assertRegex(dom, r'class="comment[ "]')
        self.assertRegex(dom, r'id="line"[^>]* hidden|hidden[^>]*id="line"')
        self.assertIn("Nothing here right now", dom)


class FifthReview(KitCase):
    """README 'Privacy', CHANGELOG 0.1.0-test.6. Simulated, and every credential here is fake."""

    V = "FaKe7Qx9Zt36"

    def built(self, ledger="", overview=None, expect=0):
        self.count = getattr(self, "count", 0) + 1
        target = self.workspace(f"five{self.count}")
        self.install(target)
        (target / "docs/project-ledger.md").write_text(f"## Items for the user\n\n{ledger}", encoding="utf-8")
        if overview:
            (target / "docs/Works_in_Development.md").write_text(overview, encoding="utf-8")
        return target, self.build(target, expect=expect)

    def test_common_labels_are_withheld(self):
        forms = ("pw: V", "passcode: V", "pin: V", "auth: V", "creds: V", "session: V", "login: fake / V", "pass word: V", "sshpass -p V ssh x",
                 "curl -u fake:V https://example.invalid", "password V", "password as V", "password | V", "password\tV", "the password is V",
                 "p a s s w o r d: V", "pass\u200bword: V", "p\u0430ssword: V", "password&#58; V")
        for form in forms:
            with self.subTest(form):
                target, output = self.built(f"- CONTEXT {form.replace('V', self.V)}\n")
                self.assertNotIn(self.V, self.page(target))
                self.assertNotIn("CONTEXT", self.page(target))
                self.assertIn("looks like a credential", output)

    def test_a_form_written_as_a_markdown_link_is_withheld(self):
        for form in ("[token -> V](https://example.invalid/)", "[--token V](https://example.invalid/)", "token: [V](https://example.invalid/)"):
            for overview in (False, True):
                with self.subTest(form, overview=overview):
                    line = form.replace("V", self.V)
                    target, output = self.built(*(("", f"# W\n\n### P\n\nStatus: Local\n\nCTRL see {line} now\n") if overview else (f"- CTRL {line}\n",)))
                    self.assertNotIn(self.V, self.page(target))
                    self.assertIn("looks like a credential", output)

    def test_a_commit_link_is_withheld_with_git_history_wording(self):
        target = self.workspace("fivegit")
        self.install(target)
        for args in (("init", "-q"), ("add", "-A"), ("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", f"[token -> {self.V}](https://example.invalid/)")):
            self.assertEqual(run("git", *args, cwd=target).returncode, 0)
        output = self.build(target)
        self.assertNotIn(self.V, self.page(target))
        self.assertIn("Commit messages: 1 line looks like a credential", output)
        self.assertIn("It stays in Git history", output)
        self.assertNotIn("Remove the credential from the file", output)

    def test_a_word_after_a_label_does_not_stop_the_build(self):
        lines = ("password: required", "Password: required.", "password: none", "password: unknown", "password: unset", "API key: required", "api_key: required",
                 "access_token: unset", "client_secret: required", "pwd: required", "passwd: missing", "auth_token: todo", "**Password:** required", "password: yes", "password=required")
        for line in lines:
            with self.subTest(line):
                target, output = self.built(f"- {line}\n", f"# W\n\n### P\n\nStatus: Local\n\n{line}\n")
                self.assertNotIn("stopped", output)
                self.assertNotIn("withheld", output)
                word = re.split(r"[:=]", line)[-1].strip(" *.")
                self.assertIn(word, re.search(r'id="needs">(.*?)</section>', self.page(target), re.S).group(1))

    def test_last_scan_names_the_document_and_decodes_the_page(self):
        target = self.workspace("fivestop")
        self.install(target)
        spec = importlib.util.spec_from_file_location("dash_five", target / FOLDER / "build_dashboard.py")
        dash = importlib.util.module_from_spec(spec)
        sys.modules["dash_five"] = dash
        spec.loader.exec_module(dash)
        g = {"scrub": dash.Scrubber([]), "tracked": [], "ignored": [], "texts": {}, "guestbook": "", "commits": [], "words": {},
             "raw_docs": {"docs/a.md": f"see token -> {self.V}"}}
        report = dash.leak_report(g, f"<a href='x'>token -&gt; {self.V}</a>", "")
        self.assertIn("something that looks like a credential", report)
        self.assertIn("docs/a.md", report)
        g["raw_docs"] = {"docs/b.md": f"see ?sig={self.V} here"}
        self.assertIn("docs/b.md", dash.leak_report(g, f'<a href="https://example.invalid/?sig={self.V}">x</a>', ""))
        self.assertIsNone(dash.leak_report(g, "<p>password: required</p><p>x</p>", ""))
        self.assertIsNone(dash.leak_report(g, '<script>x={"a":"password: required<\\/p>"}</script>', ""))

    def test_one_config_line_gives_one_note(self):
        target = self.workspace("fivenote")
        self.install(target)
        self.set_config(target, tagline="token: FaKeNoteEig8")
        output = self.build(target)
        self.assertEqual(output.count("looks like a credential"), 1)
        self.assertIn("dashboard_config.json: 1 line looks like a credential", output)
        self.assertNotIn("FaKeNoteEig8", self.page(target))

    def test_ordinary_phrases_stay_and_real_values_after_them_do_not(self):
        lines = ("Hall pass: Sunday", "Boarding pass: Tuesday", "bypass: route42", "cache key: user42", "Answer key: b2c3d4", "auth: oauth2", "session: sprint12", "password sha256 hashes")
        target, output = self.built("".join(f"- {line}\n" for line in lines))
        self.assertNotIn("withheld", output)
        for line in lines:
            self.assertIn(line, self.page(target))
        for line in ("cache key: V", "bypass: V", "Hall pass: V"):
            with self.subTest(line):
                target, output = self.built(f"- {line.replace('V', self.V)}\n")
                self.assertNotIn(self.V, self.page(target))

    def test_readme_names_what_stays_unmatched(self):
        readme = " ".join((KIT / "README.md").read_text(encoding="utf-8").split())
        for words in ("lookalike", "invisible characters", "HTML entities", "`pin: 1234`", "`Secret: door`", "`hall pass:`"):
            self.assertIn(words, readme)


if __name__ == "__main__":
    unittest.main(verbosity=1)
