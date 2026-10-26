"""Load the public Parquet tables into a DuckDB warehouse and create analysis views.

    python -m tdf.warehouse --data data/public --db data/warehouse.duckdb

The .duckdb file is a build artifact (not committed); it is rebuilt from the
Parquet tables in a few seconds. The SQL in sql/views.sql is the source of
truth for the views and is also used by the tests.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
SQL_DIR = HERE.parent.parent / "sql"


def build(data_dir: Path, db_path: Path) -> duckdb.DuckDBPyConnection:
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    for pq in sorted(data_dir.glob("*.parquet")):
        con.execute(f"CREATE OR REPLACE TABLE {pq.stem} AS SELECT * FROM read_parquet('{pq.as_posix()}')")
    con.execute((SQL_DIR / "views.sql").read_text(encoding="utf-8"))
    return con


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=Path("data/public"), type=Path)
    ap.add_argument("--db", default=Path("data/warehouse.duckdb"), type=Path)
    args = ap.parse_args(argv)
    con = build(args.data, args.db)
    rows = con.execute("SELECT table_name, table_type FROM information_schema.tables WHERE table_schema='main' ORDER BY table_type, table_name").fetchall()
    for name, kind in rows:
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"{kind:10s} {name:32s} {n:>8,}")
    con.close()


if __name__ == "__main__":
    main()
