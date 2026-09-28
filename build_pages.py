#!/usr/bin/env python3
"""Build the static GitHub Pages site for daily briefs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from weekly_brief import generate_brief, markdown_to_html
from youth_policies import find_candidates, markdown as youth_markdown, new_matches, notify_telegram, save_seen, today_seoul


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
            "title": f"Daily AI/Dev Brief - {brief_stamp(path)}",
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


def upgrade_existing_briefs(briefs_dir: Path) -> None:
    """Apply shared presentation to previously generated static briefs."""
    for path in briefs_dir.glob("*.html"):
        content = path.read_text(encoding="utf-8")
        updated = content
        if 'href="../brief-ui.css"' not in updated:
            updated = updated.replace("  <style>", '  <link rel="stylesheet" href="../brief-ui.css">\n  <style>', 1)
        if 'src="../brief-ui.js"' not in updated:
            updated = updated.replace("</body>", '  <script src="../brief-ui.js" defer></script>\n</body>', 1)
        if updated != content:
            path.write_text(updated, encoding="utf-8")


def build_site(public_dir: str = "public", keep: int = 28, generate: bool = True) -> dict[str, object]:
    root = Path(public_dir)
    briefs_dir = root / "briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)

    generated = None
    if generate:
        brief = generate_brief()
        html_path = briefs_dir / f"{brief.stamp}.html"
        html_body = brief.html
        api_key = os.getenv("YOUTHCENTER_API_KEY", "")
        birth = os.getenv("USER_BIRTH_DATE", "")
        if api_key and birth:
            try:
                candidates = find_candidates(api_key, birth, today_seoul())
                section = youth_markdown(candidates)
                if section:
                    html_body = html_body.replace("</article>", markdown_to_html(section) + "\n</article>", 1)
                state_path = root.parent / "data" / "youth_seen.json"
                fresh, seen = new_matches(candidates, state_path)
                if notify_telegram(fresh):
                    save_seen(state_path, seen)
                print(f"Youth policy candidates: {len(candidates)}, new: {len(fresh)}")
            except (OSError, ValueError, TypeError) as exc:
                print(f"Youth policy lookup unavailable: {type(exc).__name__}")
        html_path.write_text(html_body, encoding="utf-8")
        generated = {"stamp": brief.stamp, "items": brief.items_count, "html": str(html_path)}

    prune_briefs(briefs_dir, keep)
    upgrade_existing_briefs(briefs_dir)
    build_index(root, keep)
    return {"generated": generated, "briefs": [path.name for path in sorted(briefs_dir.glob("*.html"), reverse=True)]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build static GitHub Pages files.")
    parser.add_argument("--public-dir", default="public")
    parser.add_argument("--keep", type=int, default=28)
    parser.add_argument("--no-generate", action="store_true")
    args = parser.parse_args()

    result = build_site(public_dir=args.public_dir, keep=args.keep, generate=not args.no_generate)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
