"""Consistent SQLite online backup, including WAL contents."""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.settings import DATA

parser = argparse.ArgumentParser()
parser.add_argument("destination", type=Path)
args = parser.parse_args()
source = DATA / "simforge.sqlite3"
if not source.exists():
    parser.error("Database does not exist yet")
if args.destination.exists():
    parser.error("Choose a new backup filename; existing backups are not overwritten")
args.destination.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(args.destination)) as dst:
    src.backup(dst)
print(f"Backup created: {args.destination.resolve()}")
