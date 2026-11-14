#!/usr/bin/env python3
"""Validate a plain YouTube chapter list."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


LINE = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+\S)$")


def seconds(timestamp: str) -> int:
    parts = [int(part) for part in timestamp.split(":")]
    if len(parts) == 2:
        minute, second = parts
        if second >= 60:
            raise ValueError("seconds must be below 60")
        return minute * 60 + second
    hour, minute, second = parts
    if minute >= 60 or second >= 60:
        raise ValueError("minutes and seconds must be below 60")
    return hour * 3600 + minute * 60 + second


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("chapters", type=Path)
    parser.add_argument("--duration", type=float)
    args = parser.parse_args()

    entries: list[tuple[int, str, int]] = []
    errors: list[str] = []
    for number, raw in enumerate(args.chapters.read_text().splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        match = LINE.match(line)
        if not match:
            errors.append(f"line {number}: expected 'MM:SS title'")
            continue
        try:
            start = seconds(match.group(1))
        except ValueError as exc:
            errors.append(f"line {number}: {exc}")
            continue
        entries.append((start, match.group(2), number))

    if len(entries) < 3:
        errors.append("YouTube chapters require at least three timestamps")
    if entries and entries[0][0] != 0:
        errors.append("first chapter must start at 00:00")

    for current, following in zip(entries, entries[1:]):
        if following[0] <= current[0]:
            errors.append(f"line {following[2]}: timestamps must strictly increase")
        elif following[0] - current[0] < 10:
            errors.append(
                f"line {current[2]}: chapter is only {following[0] - current[0]} seconds"
            )

    if args.duration is not None and entries:
        final_length = args.duration - entries[-1][0]
        if final_length < 10:
            errors.append(f"final chapter is only {final_length:.2f} seconds")
        if entries[-1][0] >= args.duration:
            errors.append("final timestamp is outside the media duration")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {len(entries)} chapters satisfy the timestamp rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
