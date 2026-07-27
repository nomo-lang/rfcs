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
INDEX_ROW = re.compile(
    r"^\| \[(?P<number>\d{4})\]\(\./rfcs/(?P<file>[^)]+\.md)\)"
    r" \| .*? \| (?P<decision>[^|]+) \| (?P<implementation>[^|]+) \|"
)
MARKDOWN_LINK = re.compile(r"\]\((?P<target>[^)]+)\)")
LEGACY_MAIN_PACKAGE = re.compile(
    r"\bpackage\s+[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\.main\b"
)
DECLARATION_VOID = re.compile(
    r"\b(?:pub\s+)?(?:suspend\s+)?fn\s+[A-Za-z_][A-Za-z0-9_.]*"
    r"(?:<[^>\n]+>)?\([^)\n]*\)\s*->\s*void\b"
)
DECISION_VALUES = {"Draft", "Proposed", "Accepted", "Rejected", "Deferred"}
IMPLEMENTATION_VALUES = {"Not implemented", "Partially implemented", "Implemented"}


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


def index_inventory(
    locale: str, errors: list[str]
) -> dict[str, tuple[str, str, str]]:
    path = ROOT / locale / "README.md"
    entries: dict[str, tuple[str, str, str]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = INDEX_ROW.match(line)
        if match is None:
            continue
        number = match.group("number")
        if number in entries:
            fail(f"{path.relative_to(ROOT)}:{line_number}: duplicate index {number}", errors)
        entries[number] = (
            match.group("file"),
            match.group("decision").strip(),
            match.group("implementation").strip(),
        )
    return entries


def metadata_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        match = re.search(rf"^\| {re.escape(label)} \| (?P<value>.+) \|$", text, re.MULTILINE)
        if match is not None:
            return match.group("value").strip()
    return None


def normalized_status(value: str) -> str:
    return value.split("（", 1)[0].strip()


def check_metadata(
    locale: str, inventory: dict[str, Path], errors: list[str]
) -> dict[str, tuple[str, str]]:
    decision_label = "Decision Status" if locale == "en" else "决策状态"
    implementation_label = "Implementation Status" if locale == "en" else "实现状态"
    evidence_label = "Implementation Evidence" if locale == "en" else "实现证据"
    statuses: dict[str, tuple[str, str]] = {}

    for number, path in inventory.items():
        text = path.read_text(encoding="utf-8")
        decision = metadata_value(text, (decision_label,))
        implementation = metadata_value(text, (implementation_label,))
        if decision is None:
            fail(f"{path.relative_to(ROOT)}: missing {decision_label}", errors)
            continue
        if implementation is None:
            fail(f"{path.relative_to(ROOT)}: missing {implementation_label}", errors)
            continue
        normalized_decision = normalized_status(decision)
        normalized_implementation = normalized_status(implementation)
        if normalized_decision not in DECISION_VALUES:
            fail(
                f"{path.relative_to(ROOT)}: invalid decision status {decision}",
                errors,
            )
        if normalized_implementation not in IMPLEMENTATION_VALUES:
            fail(
                f"{path.relative_to(ROOT)}: invalid implementation status {implementation}",
                errors,
            )
        if (
            int(number) >= 26
            and normalized_implementation != "Not implemented"
            and metadata_value(text, (evidence_label,)) is None
        ):
            fail(
                f"{path.relative_to(ROOT)}: implemented RFC 0026+ requires "
                f"{evidence_label}",
                errors,
            )
        statuses[number] = (decision, implementation)
    return statuses


def check_canonical_current_docs(errors: list[str]) -> None:
    for locale in LOCALES:
        for path in sorted((ROOT / locale).rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            relative = path.relative_to(ROOT)
            if path.name != "0021-manifest-derived-module-roots.md":
                match = LEGACY_MAIN_PACKAGE.search(text)
                if match is not None:
                    fail(
                        f"{relative}: non-migration docs use legacy module root "
                        f"{match.group(0)}",
                        errors,
                    )
            if path.name != "0041-canonical-implicit-void-return-declarations.md":
                match = DECLARATION_VOID.search(text)
                if match is not None:
                    fail(
                        f"{relative}: non-compatibility docs use declaration void "
                        f"{match.group(0)}",
                        errors,
                    )


def check_documented_commands(errors: list[str]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for command, script in (
        ("python3 scripts/check_rfc_docs.py", ROOT / "scripts/check_rfc_docs.py"),
        (
            "python3 scripts/check_nomo_snippets.py",
            ROOT / "scripts/check_nomo_snippets.py",
        ),
        ("python3 scripts/check_release_set.py", ROOT / "scripts/check_release_set.py"),
    ):
        if command not in readme:
            fail(f"README.md: missing documented validation command {command}", errors)
        if not script.is_file():
            fail(f"README.md: documented script does not exist: {script.name}", errors)


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

    metadata: dict[str, dict[str, tuple[str, str]]] = {}
    for locale in LOCALES:
        index = index_inventory(locale, errors)
        actual_files = {number: path.name for number, path in inventories[locale].items()}
        index_files = {number: value[0] for number, value in index.items()}
        if index_files != actual_files:
            missing = sorted(set(actual_files) - set(index_files))
            extra = sorted(set(index_files) - set(actual_files))
            mismatched = sorted(
                number
                for number in set(actual_files) & set(index_files)
                if actual_files[number] != index_files[number]
            )
            fail(
                f"{locale}/README.md index mismatch: "
                f"missing={missing}, extra={extra}, wrong_file={mismatched}",
                errors,
            )
        metadata[locale] = check_metadata(locale, inventories[locale], errors)
        for number in sorted(set(index) & set(metadata[locale])):
            indexed_status = index[number][1:]
            if indexed_status != metadata[locale][number]:
                fail(
                    f"{locale}/README.md: RFC {number} index status "
                    f"{indexed_status} != metadata {metadata[locale][number]}",
                    errors,
                )

    check_canonical_current_docs(errors)
    check_documented_commands(errors)
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
