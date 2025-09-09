#!/usr/bin/env python3
import argparse
import json
import sys

from jsonschema import Draft202012Validator


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


ap = argparse.ArgumentParser()
ap.add_argument("--schema", required=True)
ap.add_argument("files", nargs="+")
args = ap.parse_args()

schema = load(args.schema)
validator = Draft202012Validator(schema)

bad = False
for f in args.files:
    try:
        data = load(f)
    except Exception as e:
        print(f"[✗] {f}: unreadable JSON ({e})")
        bad = True
        continue
    errs = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errs:
        bad = True
        print(f"[✗] {f}: {len(errs)} error(s)")
        for e in errs:
            p = "/".join(map(str, e.path)) or "(root)"
            print(f"  • {p}: {e.message}")
    else:
        print(f"[✓] {f}: OK")
sys.exit(1 if bad else 0)
