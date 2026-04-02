#!/usr/bin/env python3
"""Group-by aggregation on a CSV file (standard library only)."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Group CSV rows and sum a numeric column per group.",
    )
    p.add_argument("--input", required=True, help="Input CSV path")
    p.add_argument("--group-by", required=True, help="Column name to group by")
    p.add_argument("--sum", required=True, dest="sum_col", help="Column to sum")
    p.add_argument("--output", required=True, help="Output CSV path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    inp = Path(args.input)
    if not inp.is_file():
        print(f"Input not found: {inp}", file=sys.stderr)
        return 1

    group_col = args.group_by
    sum_col = args.sum_col
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    counts: dict[str, int] = defaultdict(int)

    with inp.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print("CSV has no header row.", file=sys.stderr)
            return 1
        if group_col not in reader.fieldnames:
            print(f"Missing group column {group_col!r}.", file=sys.stderr)
            return 1
        if sum_col not in reader.fieldnames:
            print(f"Missing sum column {sum_col!r}.", file=sys.stderr)
            return 1

        for row in reader:
            key = (row.get(group_col) or "").strip()
            raw = (row.get(sum_col) or "").strip()
            try:
                val = Decimal(raw) if raw else Decimal("0")
            except InvalidOperation:
                print(f"Non-numeric value in {sum_col!r}: {raw!r}", file=sys.stderr)
                return 1
            totals[key] += val
            counts[key] += 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    sum_header = f"total_{sum_col}"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([group_col, sum_header, "row_count"])
        for key in sorted(totals.keys()):
            w.writerow([key, str(totals[key]), counts[key]])

    print(f"Wrote {out} ({len(totals)} groups).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
