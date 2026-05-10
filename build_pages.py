#!/usr/bin/env python3
"""Build the static GitHub Pages site for weekly briefs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from weekly_brief import generate_brief


def brief_stamp(path: Path) -> str:
    return path.stem


def prune_briefs(briefs_dir: Path, keep: int) -> None:
    html_files = sorted(briefs_dir.glob("*.html"), key=brief_stamp, reverse=True)
    for path in html_files[keep:]:
        path.unlink()


def build_index(public_dir: Path, keep: int) -> None:
    briefs_dir = public_dir / "briefs"
    html_files = sorted(briefs_dir.glob("*.html"), key=brief_stamp, reverse=True)[:keep]
    records = [
        {
            "stamp": brief_stamp(path),
            "title": f"Weekly AI/Dev Brief - {brief_stamp(path)}",
            "htmlUrl": f"briefs/{path.name}",
        }
        for path in html_files
    ]
    template_path = public_dir / "index.template.html"
    index_path = public_dir / "index.html"
    template = template_path.read_text(encoding="utf-8")
    index_path.write_text(
        template.replace("__BRIEFS_JSON__", json.dumps(records, ensure_ascii=False)),
        encoding="utf-8",
    )


def build_site(public_dir: str = "public", keep: int = 4, generate: bool = True) -> dict[str, object]:
    root = Path(public_dir)
    briefs_dir = root / "briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)

    generated = None
    if generate:
        brief = generate_brief()
        html_path = briefs_dir / f"{brief.stamp}.html"
        html_path.write_text(brief.html, encoding="utf-8")
        generated = {"stamp": brief.stamp, "items": brief.items_count, "html": str(html_path)}

    prune_briefs(briefs_dir, keep)
    build_index(root, keep)
    return {"generated": generated, "briefs": [path.name for path in sorted(briefs_dir.glob("*.html"), reverse=True)]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build static GitHub Pages files.")
    parser.add_argument("--public-dir", default="public")
    parser.add_argument("--keep", type=int, default=4)
    parser.add_argument("--no-generate", action="store_true")
    args = parser.parse_args()

    result = build_site(public_dir=args.public_dir, keep=args.keep, generate=not args.no_generate)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
