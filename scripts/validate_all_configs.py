#!/usr/bin/env python3
"""
Comprehensive JSON schema validation for all Odyssey project configuration files.

This script validates all JSON configuration files against their corresponding schemas.
It's designed to be used as a pre-commit hook to ensure all configurations are valid.
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

# Schema to config file mappings
SCHEMA_MAPPINGS = {
    "schema/api.schema.json": ["cdk_project/configs/apis/ws/chat/api.json"],
    "schema/route.schema.json": [
        "cdk_project/configs/apis/ws/routes/connect.json",
        "cdk_project/configs/apis/ws/routes/default.json",
        "cdk_project/configs/apis/ws/routes/disconnect.json",
        "cdk_project/configs/apis/ws/routes/sendMessage.json",
    ],
    "schema/policy.schema.json": [
        "cdk_project/configs/iam/policies/manage_connections.json",
        "cdk_project/configs/iam/policies/pipeline.json",
    ],
    "schema/table.schema.json": ["cdk_project/configs/tables/messages.json"],
    "schema/dynamodb.defaults.schema.json": ["cdk_project/configs/tables/dynamodb.defaults.json"],
}


def load_json(path: Path) -> dict:
    """Load and parse a JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise Exception(f"Failed to load {path}: {e}")


def validate_files_against_schema(schema_path: Path, config_files: list[Path]) -> bool:
    """Validate a list of config files against a schema."""
    try:
        schema = load_json(schema_path)
        validator = Draft202012Validator(schema)
    except Exception as e:
        print(f"[X] Schema {schema_path}: {e}")
        return False

    all_valid = True
    for config_file in config_files:
        if not config_file.exists():
            print(f"[X] {config_file}: File not found")
            all_valid = False
            continue

        try:
            data = load_json(config_file)
        except Exception as e:
            print(f"[X] {config_file}: {e}")
            all_valid = False
            continue

        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            all_valid = False
            print(f"[X] {config_file}: {len(errors)} error(s)")
            for error in errors:
                path = "/".join(map(str, error.path)) or "(root)"
                print(f"  - {path}: {error.message}")
        else:
            print(f"[OK] {config_file}: OK")

    return all_valid


def main():
    """Main validation function."""
    project_root = Path(__file__).parent.parent
    all_valid = True

    print("Validating JSON configuration files against schemas...")
    print()

    for schema_file, config_files in SCHEMA_MAPPINGS.items():
        schema_path = project_root / schema_file
        config_paths = [project_root / f for f in config_files]

        print(f"Validating against {schema_file}:")
        if not validate_files_against_schema(schema_path, config_paths):
            all_valid = False
        print()

    if all_valid:
        print("All configuration files are valid! [OK]")
        sys.exit(0)
    else:
        print("Some configuration files have validation errors! [X]")
        sys.exit(1)


if __name__ == "__main__":
    main()
