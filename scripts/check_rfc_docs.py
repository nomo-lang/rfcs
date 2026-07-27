#!/usr/bin/env python3
"""Validate bilingual RFC inventory, metadata, indexes, and local links."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "zh-CN")
RFC_FILE = re.compile(r"^(?P<number>\d{4})-[a-z0-9-]+\.md$")
INDEX_LINK = re.compile(r"\[(?P<number>\d{4})\]\(\./rfcs/(?P<file>[^)]+\.md)\)")
MARKDOWN_LINK = re.compile(r"\]\((?P<target>[^)]+)\)")


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def rfc_inventory(locale: str, errors: list[str]) -> dict[str, Path]:
    directory = ROOT / locale / "rfcs"
    inventory: dict[str, Path] = {}
    for path in sorted(directory.glob("*.md")):
        match = RFC_FILE.fullmatch(path.name)
        if match is None:
            fail(f"{path.relative_to(ROOT)}: invalid RFC filename", errors)
            continue
        number = match.group("number")
        if number in inventory:
            fail(f"{locale}: duplicate RFC number {number}", errors)
        inventory[number] = path
    return inventory


def index_inventory(locale: str, errors: list[str]) -> dict[str, str]:
    path = ROOT / locale / "README.md"
    entries: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = INDEX_LINK.search(line)
        if match is None:
            continue
        number = match.group("number")
        filename = match.group("file")
        if number in entries:
            fail(f"{path.relative_to(ROOT)}:{line_number}: duplicate index {number}", errors)
        entries[number] = filename
    return entries


def metadata_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        match = re.search(rf"^\| {re.escape(label)} \| (?P<value>.+) \|$", text, re.MULTILINE)
        if match is not None:
            return match.group("value").strip()
    return None


def check_metadata(locale: str, inventory: dict[str, Path], errors: list[str]) -> None:
    decision_labels = ("Decision Status", "Status") if locale == "en" else ("决策状态", "状态")
    implementation_label = "Implementation Status" if locale == "en" else "实现状态"

    for number, path in inventory.items():
        text = path.read_text(encoding="utf-8")
        decision = metadata_value(text, decision_labels)
        implementation = metadata_value(text, (implementation_label,))
        if decision is None:
            fail(f"{path.relative_to(ROOT)}: missing decision/status metadata", errors)
        if metadata_value(text, (decision_labels[0],)) is not None and implementation is None:
            fail(
                f"{path.relative_to(ROOT)}: decision status requires implementation status",
                errors,
            )
        if number in {"0021", "0041"}:
            if decision is None or not decision.startswith("Proposed"):
                fail(f"{path.relative_to(ROOT)}: must initially remain Proposed", errors)
            if implementation is None or not implementation.startswith("Not implemented"):
                fail(
                    f"{path.relative_to(ROOT)}: must initially remain Not implemented",
                    errors,
                )


def check_local_links(errors: list[str]) -> None:
    for path in sorted(ROOT.rglob("*.md")):
        if path.name == "0000-template.md":
            continue
        text = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            raw_target = match.group("target").strip()
            target = raw_target.split("#", 1)[0].strip("<>")
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                continue
            resolved = (path.parent / unquote(target)).resolve()
            if not resolved.exists():
                fail(
                    f"{path.relative_to(ROOT)}: missing relative link target {raw_target}",
                    errors,
                )


def main() -> int:
    errors: list[str] = []
    inventories = {locale: rfc_inventory(locale, errors) for locale in LOCALES}

    en_names = {number: path.name for number, path in inventories["en"].items()}
    zh_names = {number: path.name for number, path in inventories["zh-CN"].items()}
    if en_names != zh_names:
        fail("en/rfcs and zh-CN/rfcs inventories must match exactly", errors)

    for locale in LOCALES:
        index = index_inventory(locale, errors)
        actual = {number: path.name for number, path in inventories[locale].items()}
        if index != actual:
            missing = sorted(set(actual) - set(index))
            extra = sorted(set(index) - set(actual))
            mismatched = sorted(
                number
                for number in set(actual) & set(index)
                if actual[number] != index[number]
            )
            fail(
                f"{locale}/README.md index mismatch: "
                f"missing={missing}, extra={extra}, wrong_file={mismatched}",
                errors,
            )
        check_metadata(locale, inventories[locale], errors)

    check_local_links(errors)

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        "RFC documentation validation passed: "
        f"{len(inventories['en'])} bilingual RFC pairs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
