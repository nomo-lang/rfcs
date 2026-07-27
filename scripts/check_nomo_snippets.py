#!/usr/bin/env python3
"""Compile explicitly marked canonical Nomo snippets from Markdown."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNIPPET = re.compile(
    r"<!--\s*nomo-check:\s*package=(?P<package>[a-z0-9-]+)\s*-->\s*"
    r"```nomo\s*\n(?P<source>.*?)\n```",
    re.DOTALL,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nomo", type=Path, required=True)
    args = parser.parse_args()
    binary = args.nomo.resolve()
    if not binary.is_file():
        raise SystemExit(f"nomo binary does not exist: {binary}")

    snippets: list[tuple[Path, str, str]] = []
    for path in sorted(ROOT.rglob("*.md")):
        if "archive" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for match in SNIPPET.finditer(text):
            snippets.append((path, match.group("package"), match.group("source")))

    if not snippets:
        raise SystemExit("no <!-- nomo-check: package=... --> snippets found")

    with tempfile.TemporaryDirectory(prefix="nomo-rfc-snippets-") as temporary:
        temporary_root = Path(temporary)
        for index, (document, package, source) in enumerate(snippets):
            project = temporary_root / f"snippet-{index}"
            source_dir = project / "src"
            source_dir.mkdir(parents=True)
            (project / "nomo.toml").write_text(
                f'[package]\nname = "{package}"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )
            (source_dir / "main.nomo").write_text(source + "\n", encoding="utf-8")
            completed = subprocess.run(
                [str(binary), "check", str(project)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if completed.returncode != 0:
                relative = document.relative_to(ROOT)
                raise SystemExit(
                    f"{relative}: marked Nomo snippet failed\n"
                    f"stdout:\n{completed.stdout}\n"
                    f"stderr:\n{completed.stderr}"
                )

    print(f"compiled {len(snippets)} marked Nomo Markdown snippet(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
