#!/usr/bin/env python3
"""Preflight COPY LEDGER blocks before expensive slide generation."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


LEDGER_RE = re.compile(r"COPY LEDGER\s*\n(?P<body>.*?)(?:\n```|\Z)", re.DOTALL)


def parse_ledger(block: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def assess(index: int, ledger: dict[str, str]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    failures: list[str] = []
    title = ledger.get("title", "")
    conclusion = ledger.get("conclusion", "")
    strings = [value for value in ledger.values() if value]

    if not title:
        failures.append("missing title")
    if not conclusion:
        failures.append("missing conclusion")
    if len(title) > 42:
        failures.append(f"title too long ({len(title)} chars; max 42)")
    elif len(title) > 32:
        warnings.append(f"long title ({len(title)} chars); deterministic header normalization likely")
    if len(conclusion) > 60:
        failures.append(f"conclusion too long ({len(conclusion)} chars; max 60)")
    elif len(conclusion) > 44:
        warnings.append(f"long conclusion ({len(conclusion)} chars)")

    body_values = [value for key, value in ledger.items() if key.startswith("body_")]
    for body_index, value in enumerate(body_values, start=1):
        if len(value) > 40:
            failures.append(f"body_{body_index} too long ({len(value)} chars; max 40)")
        elif len(value) > 26:
            warnings.append(f"body_{body_index} is dense ({len(value)} chars)")
    if len(strings) > 10:
        failures.append(f"too many visible strings ({len(strings)}; max 10)")
    elif len(strings) > 8:
        warnings.append(f"many visible strings ({len(strings)}); remove decorative labels")
    if sum(map(len, strings)) > 220:
        failures.append("total visible copy exceeds 220 characters")
    elif sum(map(len, strings)) > 160:
        warnings.append("total visible copy exceeds 160 characters")

    duplicates = sorted({value for value in strings if strings.count(value) > 1})
    if duplicates:
        warnings.append(f"duplicate ledger values: {duplicates}")
    return warnings, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt_set", type=Path)
    parser.add_argument("--strict", action="store_true", help="Treat density warnings as failures")
    args = parser.parse_args()

    if not args.prompt_set.is_file():
        print(f"ERROR prompt set not found: {args.prompt_set}", file=sys.stderr)
        return 2
    text = args.prompt_set.read_text(encoding="utf-8")
    ledgers = [parse_ledger(match.group("body")) for match in LEDGER_RE.finditer(text)]
    if not ledgers:
        print("ERROR no COPY LEDGER blocks found", file=sys.stderr)
        return 2

    all_warnings: list[str] = []
    all_failures: list[str] = []
    for index, ledger in enumerate(ledgers, start=1):
        warnings, failures = assess(index, ledger)
        all_warnings.extend(f"ledger {index}: {message}" for message in warnings)
        all_failures.extend(f"ledger {index}: {message}" for message in failures)

    if "Text silence:" not in text:
        all_warnings.append("prompt set does not contain the required 'Text silence:' constraint")

    for message in all_warnings:
        print(f"WARN {message}")
    for message in all_failures:
        print(f"FAIL {message}")
    if all_failures or (args.strict and all_warnings):
        return 1
    print(f"PASS ledgers={len(ledgers)} warnings={len(all_warnings)} prompt_set={args.prompt_set}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
