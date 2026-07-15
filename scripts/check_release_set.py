#!/usr/bin/env python3
"""Validate the versions and revisions of a sibling Nomo release set."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Callable


SNAPSHOT = re.compile(r"^0\.0\.0-\d{14}$")
STABLE = re.compile(r"^[1-9]\d*\.\d+\.\d+$")


def toml_value(path: Path, table: str, key: str) -> str:
    source = path.read_text(encoding="utf-8")
    section = re.search(
        rf"^\[{re.escape(table)}\]\s*$([\s\S]*?)(?=^\[|\Z)",
        source,
        re.MULTILINE,
    )
    if not section:
        raise ValueError(f"{path}: cannot find [{table}]")
    value = re.search(
        rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"\s*$',
        section.group(1),
        re.MULTILINE,
    )
    if not value:
        raise ValueError(f"{path}: cannot find {table}.{key}")
    return value.group(1)


def json_value(path: Path, *keys: str) -> str:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    for key in keys:
        if not isinstance(value, dict):
            raise ValueError(f"{path}: cannot read {'.'.join(keys)}")
        value = value[key]
    if not isinstance(value, str):
        raise ValueError(f"{path}: {'.'.join(keys)} is not a string")
    return value


def regex_value(path: Path, pattern: str, label: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise ValueError(f"{path}: cannot find {label}")
    return match.group(1)


def cargo_lock_version(path: Path, package: str) -> str:
    return regex_value(
        path,
        rf'^\[\[package\]\]\s*\nname\s*=\s*"{re.escape(package)}"\s*\nversion\s*=\s*"([^"]+)"',
        f"Cargo.lock package {package}",
    )


def git_state(root: Path) -> dict[str, object]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.splitlines()
    return {"revision": revision, "clean": not status, "changed_paths": len(status)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="directory containing the sibling Nomo repositories",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace.resolve()

    readers: dict[str, tuple[str, Callable[[], str]]] = {
        "nomo": (
            "nomo",
            lambda: toml_value(workspace / "nomo" / "Cargo.toml", "workspace.package", "version"),
        ),
        "nomo-std-manifest": (
            "nomo",
            lambda: toml_value(workspace / "nomo" / "std" / "nomo.toml", "package", "version"),
        ),
        "nomo-lock": (
            "nomo",
            lambda: cargo_lock_version(workspace / "nomo" / "Cargo.lock", "nomo"),
        ),
        "nomo-lsp": (
            "nomo-lsp",
            lambda: toml_value(workspace / "nomo-lsp" / "Cargo.toml", "package", "version"),
        ),
        "nomo-lsp-lock": (
            "nomo-lsp",
            lambda: cargo_lock_version(
                workspace / "nomo-lsp" / "Cargo.lock", "nomo-lsp"
            ),
        ),
        "setup-nomo": (
            "setup-nomo",
            lambda: json_value(workspace / "setup-nomo" / "package.json", "version"),
        ),
        "setup-nomo-lock": (
            "setup-nomo",
            lambda: json_value(workspace / "setup-nomo" / "package-lock.json", "version"),
        ),
        "tree-sitter-nomo": (
            "tree-sitter-nomo",
            lambda: json_value(workspace / "tree-sitter-nomo" / "package.json", "version"),
        ),
        "tree-sitter-metadata": (
            "tree-sitter-nomo",
            lambda: json_value(workspace / "tree-sitter-nomo" / "tree-sitter.json", "metadata", "version"),
        ),
        "tree-sitter-lock": (
            "tree-sitter-nomo",
            lambda: json_value(
                workspace / "tree-sitter-nomo" / "package-lock.json", "version"
            ),
        ),
        "vscode-nomo": (
            "vscode-nomo",
            lambda: json_value(workspace / "vscode-nomo" / "package.json", "version"),
        ),
        "vscode-nomo-lock": (
            "vscode-nomo",
            lambda: json_value(workspace / "vscode-nomo" / "package-lock.json", "version"),
        ),
        "zed-nomo-crate": (
            "zed-nomo",
            lambda: toml_value(workspace / "zed-nomo" / "Cargo.toml", "package", "version"),
        ),
        "zed-nomo-extension": (
            "zed-nomo",
            lambda: regex_value(
                workspace / "zed-nomo" / "extension.toml",
                r'^version\s*=\s*"([^"]+)"',
                "extension version",
            ),
        ),
        "zed-nomo-lock": (
            "zed-nomo",
            lambda: cargo_lock_version(
                workspace / "zed-nomo" / "Cargo.lock", "zed-nomo"
            ),
        ),
        "intellij-nomo": (
            "intellij-nomo",
            lambda: regex_value(
                workspace / "intellij-nomo" / "build.gradle.kts",
                r'^version\s*=\s*"([^"]+)"',
                "Gradle version",
            ),
        ),
    }
    components = {
        name: {"repository": repository, "version": reader()}
        for name, (repository, reader) in readers.items()
    }
    versions = {component["version"] for component in components.values()}
    if len(versions) != 1:
        details = ", ".join(
            f"{name}={component['version']}" for name, component in components.items()
        )
        raise RuntimeError(f"coordinated release versions differ: {details}")
    version = versions.pop()
    if not (SNAPSHOT.fullmatch(version) or STABLE.fullmatch(version)):
        raise RuntimeError(
            f"release version {version!r} is neither 0.0.0-YYYYMMDDHHMMSS nor stable SemVer"
        )

    repositories = {
        repository: git_state(workspace / repository)
        for repository in sorted({item[0] for item in readers.values()})
    }
    if args.require_clean:
        dirty = [name for name, state in repositories.items() if not state["clean"]]
        if dirty:
            raise RuntimeError(f"release repositories are dirty: {', '.join(dirty)}")

    result = {
        "schema": 1,
        "version": version,
        "kind": "snapshot" if SNAPSHOT.fullmatch(version) else "stable",
        "components": components,
        "repositories": repositories,
    }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
