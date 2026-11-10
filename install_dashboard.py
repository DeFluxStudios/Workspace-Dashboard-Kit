#!/usr/bin/env python3
"""Install the workspace dashboard into a workspace. Standard library only. Adding files is its only effect.

  python install_dashboard.py <target_workspace> [--dry-run] [--name "Title"] [--force]

It never changes an existing file unless --force is given, and --force only replaces the kit's own program
files (generator, theme, art, and launchers the kit wrote). Your config, words, guestbook, documents and any
launcher of your own are never replaced. Every path is checked before the first write, and a page or data file
that is not this kit's stops the install. Safe to re-run. Prints every file written or kept, then runs one build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
PAYLOAD = KIT / "payload"
STARTER = KIT / "starter"
FOLDER = "workspace_dashboard"
DEFAULT_DOCS = {"overview": "docs/Works_in_Development.md", "ledger": "docs/project-ledger.md", "decisions": "docs/decision-log.md"}
STARTER_DOCS = {"overview": "Works_in_Development.md", "ledger": "project-ledger.md", "decisions": "decision-log.md"}
SKIP_NAMES = {"__pycache__"}
GITIGNORE = b"/Workspace_Dashboard.html\n/Workspace_Dashboard_data.js\n__pycache__/\n"
PAGE_REL = f"{FOLDER}/Workspace_Dashboard.html"
DATA_REL = f"{FOLDER}/Workspace_Dashboard_data.js"
PAGE_MARK, DATA_MARK = b'<body data-stamp="', b"window.onDashData("
LAUNCHER_MARK = b"Builds this workspace's dashboard"
LAUNCHERS = ("Open_Dashboard.cmd", "Open_Dashboard.sh")

LAUNCHER_CMD = f"""@echo off
rem Builds this workspace's dashboard, starts its updater and opens the page.
rem pushd also copes with a network path, which cd cannot.
pushd "%~dp0"
set "DASH_PY=py -3"
where py >nul 2>nul || set "DASH_PY=python"
%DASH_PY% {FOLDER}\\build_dashboard.py
if errorlevel 1 pause
start "Dashboard updater" /min %DASH_PY% "%~dp0{FOLDER}\\build_dashboard.py" --watch
start "" "{FOLDER}\\Workspace_Dashboard.html"
""".replace("\n", "\r\n").encode("ascii")

LAUNCHER_SH = f"""#!/bin/sh
# Builds this workspace's dashboard, starts its updater and opens the page.
cd "$(dirname "$0")" || exit 1
python3 {FOLDER}/build_dashboard.py || exit 1
nohup python3 "$PWD/{FOLDER}/build_dashboard.py" --watch >/dev/null 2>&1 &
if command -v open >/dev/null 2>&1; then open "{FOLDER}/Workspace_Dashboard.html"
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "{FOLDER}/Workspace_Dashboard.html"
else echo "Open {FOLDER}/Workspace_Dashboard.html in a browser."; fi
""".encode("ascii")


def payload_files():
    for path in sorted(PAYLOAD.rglob("*")):
        if path.is_file() and not SKIP_NAMES.intersection(path.parts) and path.suffix != ".pyc":
            yield path.relative_to(PAYLOAD).as_posix(), path.read_bytes()


def starter_config(title):
    text = (STARTER / "dashboard_config.json").read_text(encoding="utf-8")
    config = json.loads(text)
    config["title"] = title
    return (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def starter_hashes():
    """Lets the generator tell a starter document nobody has edited from real work, so it is not counted as work."""
    hashes = [hashlib.sha256((STARTER / name).read_bytes()).hexdigest() for name in STARTER_DOCS.values()]
    return (json.dumps(sorted(hashes), indent=1) + "\n").encode("ascii")


def existing_config(target):
    """The workspace's own config as an object, or {} if there is none the installer can use. The build reports why."""
    path = target / "dashboard_config.json"
    if not path.is_file():
        return {}
    try:
        raw = path.read_bytes()
        # The same decoding as the generator's read_text, so both read a config the same way.
        loaded = json.loads(raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", "replace"))
    except (ValueError, OSError, RecursionError):
        loaded = None
    if not isinstance(loaded, dict):
        print("  note     dashboard_config.json could not be read, so the default document paths are assumed.")
        return {}
    return loaded


def doc_paths(config):
    """Where the documents go: an existing config decides, so a workspace's own files can be mapped first."""
    return {key: config[key] if isinstance(config.get(key), str) else rel for key, rel in DEFAULT_DOCS.items()}


def launcher_is_foreign(target, name):
    path = target / name
    return path.is_file() and LAUNCHER_MARK not in path.read_bytes()


def plan(target, title, config):
    """Every file the kit could add, as (workspace path, bytes, whether it is the kit's own program file)."""
    version = (KIT / "VERSION").read_bytes()
    files = [(f"{FOLDER}/{rel}", data, True) for rel, data in payload_files()]
    files += [(f"{FOLDER}/VERSION", version, True),
              (f"{FOLDER}/psychology_checklist.md", (KIT / "psychology_checklist.md").read_bytes(), True),
              (f"{FOLDER}/HOW_TO_FILL.md", (STARTER / "HOW_TO_FILL.md").read_bytes(), True),
              (f"{FOLDER}/starter_docs.json", starter_hashes(), True),
              (f"{FOLDER}/.gitignore", GITIGNORE, True)]
    for name, data in zip(LAUNCHERS, (LAUNCHER_CMD, LAUNCHER_SH)):
        files.append((name, data, not launcher_is_foreign(target, name)))
    files += [("dashboard_config.json", starter_config(title), False),
              (f"{FOLDER}/words.json", (STARTER / "words.json").read_bytes(), False),
              (f"{FOLDER}/Guestbook.md", (STARTER / "Guestbook.md").read_bytes(), False)]
    resolved_target = target.resolve()
    for key, rel in doc_paths(config).items():
        data = (STARTER / STARTER_DOCS[key]).read_bytes()
        try:
            destination = (target / rel).resolve()
        except (ValueError, OSError):
            files.append((rel, data, False))  # reported by first_blocker, before anything is written
            continue
        if resolved_target not in destination.parents:
            print(f"  note     config path for '{key}' leaves the workspace, so no starter was written: {rel}")
            continue
        files.append((destination.relative_to(resolved_target).as_posix(), data, False))
    return files


def first_blocker(target, files, config):
    """Why the install cannot go ahead, or None. Checked before the first write, so a bad path leaves nothing half done."""
    folders = {parent.as_posix().casefold() for rel, _, _ in files for parent in Path(rel).parents}
    for rel, _, _ in files:
        if rel.casefold() in folders:
            return f"{rel} is a folder the kit needs, so it cannot also be a document. Change it in dashboard_config.json."
        if any(len(part) > 255 for part in Path(rel).parts) or len(str(target / rel)) >= (32000 if os.name == "nt" else 4096):
            return f"{rel[:60]}... is too long for a file path. Change it in dashboard_config.json."
        if "\0" in rel or (os.name == "nt" and re.search(r'[<>:"|?*]', rel)):
            return f"{rel!r} cannot be a file name here. Change it in dashboard_config.json."
        path = target / rel
        if path.is_dir():
            return f"{rel} is a folder, and the kit needs a file there."
        for parent in path.relative_to(target).parents:
            if (target / parent).exists() and not (target / parent).is_dir():
                return f"{parent.as_posix()} is a file, and the kit needs a folder there."
    if config.get("output") in (None, PAGE_REL):
        for rel, mark in ((PAGE_REL, PAGE_MARK), (DATA_REL, DATA_MARK)):
            path = target / rel
            if path.exists() and (not path.is_file() or mark not in path.read_bytes()):
                return f"{rel} already exists and is not this kit's. Move it, or set 'output' in dashboard_config.json."
    return None


def install(target, files, dry_run, force):
    written = kept = 0
    before = "would write" if dry_run else "write"
    for rel, data, own in files:
        path = target / rel
        if path.exists():
            same = path.read_bytes() == data
            if same or not own or not force:
                detail = "same as the kit" if same else "yours, left alone" if not own else "differs from the kit, --force replaces it"
                print(f"  keep     {rel} ({detail})")
                kept += 1
                continue
            print(f"  {'would replace' if dry_run else 'replace'}  {rel}")
        else:
            print(f"  {before}    {rel}")
        if not dry_run:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                if rel.endswith(".sh"):
                    os.chmod(path, 0o755)
            except OSError as error:
                raise SystemExit(f"Stopped: could not write {rel} ({error.strerror or error}). The {written} files listed above were written; "
                                 "nothing that already existed was changed. Fix that and run this again.") from None
        written += 1
    return written, kept


def run_build(target):
    """One build. Says 'generated' only for a page the build reports and that carries the kit's stamp."""
    builder = target / FOLDER / "build_dashboard.py"
    if builder.read_bytes() != (PAYLOAD / "build_dashboard.py").read_bytes():
        print(f"Not built: {FOLDER}/build_dashboard.py differs from this kit's, so it was not run. "
              "Run it yourself if it is yours, or use --force to replace it with the kit's.")
        return 2
    result = subprocess.run([sys.executable, "-B", str(builder)], cwd=target, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        print(f"The build stopped with exit code {result.returncode}. The page was not written, and no existing file was changed.")
        return result.returncode
    built = re.search(r"^Built (.+?): ", result.stdout, re.M)
    page = target / built.group(1) if built else None
    if page is None or not page.is_file() or PAGE_MARK not in page.read_bytes():
        print("The build ran, but no page with the kit's stamp was found. Run build_dashboard.py --doctor to see why.")
        return 2
    print(f"  generated {built.group(1)}")
    print(f"  generated {Path(built.group(1)).with_name(page.stem + '_data.js').as_posix()}")
    return 0


def closing_line(target):
    name = LAUNCHERS[0] if os.name == "nt" else LAUNCHERS[1]
    follow = f"Next: read {FOLDER}/HOW_TO_FILL.md, or run {FOLDER}/build_dashboard.py --doctor."
    if launcher_is_foreign(target, name):
        return (f"{name} in this workspace is not the kit's, so it was left alone. To rebuild: python {FOLDER}/build_dashboard.py. "
                f"For live updates add --watch. The page is {PAGE_REL}. {follow}")
    launcher = name if os.name == "nt" else f"sh {name}"
    return f"Open it with {launcher}. {follow}"


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", help="the workspace folder to add the dashboard to")
    parser.add_argument("--dry-run", action="store_true", help="print what would happen and change nothing")
    parser.add_argument("--name", help="page title, used only when dashboard_config.json is created")
    parser.add_argument("--force", action="store_true", help="replace the kit's own program files; never your config, words, documents or own launcher")
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    if target == KIT or KIT in target.parents:
        print(f"Refused: {target} is inside the kit. Give the workspace you want the dashboard in.")
        return 2
    if not target.is_dir():
        print(f"Refused: {target} is not an existing folder.")
        return 2
    if (target / "install_dashboard.py").exists() and (target / "payload").is_dir():
        print(f"Refused: {target} looks like a copy of the kit, not a workspace.")
        return 2

    title = (args.name or f"{target.name} Workspace").strip()
    if args.name and (target / "dashboard_config.json").exists():
        print("  note     dashboard_config.json already exists, so --name was not applied. Change its title there.")
    print(f"{'Dry run for' if args.dry_run else 'Installing into'} {target}")
    config = existing_config(target)
    files = plan(target, title, config)
    blocker = first_blocker(target, files, config)
    if blocker:
        print(f"Refused: {blocker} Nothing was changed.")
        return 2
    written, kept = install(target, files, args.dry_run, args.force)
    if args.dry_run:
        print(f"Dry run: {written} would be written, {kept} kept. Nothing was changed and no build was run.")
        return 0
    print(f"{written} written, {kept} kept. Running one build.")
    status = run_build(target)
    if status == 0:
        print(closing_line(target))
    return status


if __name__ == "__main__":
    sys.exit(main())
