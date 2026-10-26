"""Filter the FMCSA Motor Carrier Census file down to a list of USDOT numbers.

The Census CSV (https://ai.fmcsa.dot.gov/SMS/Tools/Downloads.aspx, "Motor
Carrier Census File") is several hundred MB. This script keeps only the rows
whose DOT_NUMBER appears in a private list and writes a small CSV that can be
joined on the pseudonymous dot_key after hashing with the same key.

    python scripts/filter_fmcsa_census.py --census FMCSA_CENSUS1_2026Oct.txt \
        --dot-list my_dot_numbers.txt --out fmcsa_census_subset.csv

`my_dot_numbers.txt` is one USDOT number per line (never committed).
Works with either a comma- or pipe-delimited Census file.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", required=True, type=Path)
    ap.add_argument("--dot-list", required=True, type=Path)
    ap.add_argument("--out", default=Path("fmcsa_census_subset.csv"), type=Path)
    a = ap.parse_args(argv)

    wanted = {re.sub(r"\D", "", line) for line in a.dot_list.read_text().splitlines() if re.sub(r"\D", "", line)}
    with open(a.census, encoding="latin-1", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",|\t")
        reader = csv.DictReader(fh, dialect=dialect)
        dot_col = next(c for c in reader.fieldnames if c.strip().upper() in {"DOT_NUMBER", "USDOT_NUMBER", "DOT NUMBER"})
        kept = 0
        with open(a.out, "w", encoding="utf-8", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                if re.sub(r"\D", "", row[dot_col] or "") in wanted:
                    writer.writerow(row)
                    kept += 1
    print(f"kept {kept:,} of {len(wanted):,} requested USDOT numbers -> {a.out}")


if __name__ == "__main__":
    main()
