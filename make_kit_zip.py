#!/usr/bin/env python3
"""Rebuild the kit's zip, for moving it to another PC. Standard library only.

  python make_kit_zip.py [--out some/where.zip]

Default output: workspace_dashboard_kit_<VERSION>.zip beside the kit folder. __pycache__ is left out.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parent


def kit_files():
    for path in sorted(KIT.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", help="where to write the zip")
    args = parser.parse_args()
    version = (KIT / "VERSION").read_text(encoding="utf-8").strip()
    out = Path(args.out) if args.out else KIT.parent / f"{KIT.name}_{version}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(out.name + ".tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        count = 0
        for path in kit_files():
            archive.write(path, f"{KIT.name}/{path.relative_to(KIT).as_posix()}")
            count += 1
    temporary.replace(out)
    print(f"{out}: {count} files, {out.stat().st_size // 1024} KB")
    older = sorted(p.name for p in out.parent.glob(f"{KIT.name}_*.zip") if p != out)
    if older:
        print(f"Warning: older zips of this kit are beside it: {', '.join(older)}. Use only {out.name}. They may hold fixed problems, and this script does not delete them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
