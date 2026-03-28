#!/usr/bin/env python3
"""
Extract `docs/REBUILD_SINGLE_FILE.md` (or any path) into a real directory tree.

Portable: always pass --md and --dest (good for USB / two-file carry).

  python3 scripts/extract_kit.py --md docs/REBUILD_SINGLE_FILE.md --dest ./out
  python3 scripts/extract_kit.py --md docs/REBUILD_SINGLE_FILE.md --dest . --dry-run

See also: `scripts/extract_rebuild_kit.py` (defaults to repo layout).
Guide: `docs/RECREATE_FROM_NOTHING.md`
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def extract(md_path: Path, dest_root: Path, dry_run: bool) -> None:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    i, n, written = 0, len(lines), 0
    while i < n:
        m = re.match(r"^## File: `([^`]+)`\s*$", lines[i].rstrip("\n"))
        if not m:
            i += 1
            continue
        rel, i = m.group(1), i + 1
        while i < n and lines[i].strip() == "":
            i += 1
        if i >= n or not lines[i].lstrip().startswith("```"):
            print(f"skip (no fence): {rel}", file=sys.stderr)
            continue
        i += 1
        buf: list[str] = []
        while i < n:
            line = lines[i]
            if line.rstrip("\n").strip() == "```" and not buf:
                i += 1
                break
            if line.rstrip("\n").strip() == "```":
                i += 1
                break
            buf.append(line)
            i += 1
        out = dest_root / rel
        content = "".join(buf)
        if content and not content.endswith("\n"):
            content += "\n"
        if dry_run:
            print(f"would write {out}")
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding="utf-8")
            if rel.endswith(".sh"):
                try:
                    out.chmod(out.stat().st_mode | 0o111)
                except OSError:
                    pass
            print(f"wrote {rel}")
        written += 1
    print(f"Done. {written} file(s).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract REBUILD_SINGLE_FILE.md to disk.")
    ap.add_argument("--md", type=Path, required=True, help="Path to REBUILD_SINGLE_FILE.md")
    ap.add_argument("--dest", type=Path, required=True, help="Output root directory")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.md.is_file():
        print(f"Not found: {a.md}", file=sys.stderr)
        return 1
    extract(a.md, a.dest, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
