from __future__ import annotations
import json, os, re
from pathlib import Path
from typing import Any, Mapping, Dict, List, Optional
from aws_cdk import (
    Stack, RemovalPolicy, Duration, Tags
)
from aws_cdk import aws_kms as kms
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct
from cdk_project.configs.odyssey_cfg import get_cfg

_VAR = re.compile(r"\$\{([A-Za-z0-9_]+)\}")

# -----------------------------
# Generic helpers
# -----------------------------

def expand_placeholders(obj: Any, vars: Mapping[str, str]) -> Any:
    if isinstance(obj, str):  return _VAR.sub(lambda m: str(vars.get(m.group(1), m.group(0))), obj)
    if isinstance(obj, list): return [expand_placeholders(x, vars) for x in obj]
    if isinstance(obj, dict): return {k: expand_placeholders(v, vars) for k, v in obj.items()}
    return obj

def load_json_config(path: str, vars: Mapping[str, str]) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return expand_placeholders(raw, vars)

# New helpers for file-per-table mode

def list_json_files(config_dir: str, exclude: Optional[set[str]] = None) -> List[str]:
    p = Path(config_dir)
    if not p.is_dir():
        raise FileNotFoundError(f"Config directory not found: {config_dir}")
    files = sorted(str(fp) for fp in p.glob("*.json"))
    if exclude:
        files = [f for f in files if Path(f).name not in exclude]
    return files

# -----------------------------
# Type mappers
# -----------------------------

def to_attr_type(s: str) -> dynamodb.AttributeType:
    s = (s or "").upper()
    return {
        "STRING": dynamodb.AttributeType.STRING,
        "NUMBER": dynamodb.AttributeType.NUMBER,
        "BINARY": dynamodb.AttributeType.BINARY,
    }[s]

def to_stream_type(s: str | None) -> dynamodb.StreamViewType | None:
    if not s: return None
    m = {
        "NEW_IMAGE": dynamodb.StreamViewType.NEW_IMAGE,
        "OLD_IMAGE": dynamodb.StreamViewType.OLD_IMAGE,
        "NEW_AND_OLD_IMAGES": dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        "KEYS_ONLY": dynamodb.StreamViewType.KEYS_ONLY,
    }
    return m[s.upper()]

# -----------------------------
# KMS & GSIs
# -----------------------------

def ensure_kms_key(scope: Construct, *, alias: str, env_name: str) -> kms.Key:
    return kms.Key(
        scope, f"KmsKey-{alias.replace('/', '-')}",
        alias=alias,
        enable_key_rotation=True,
        removal_policy=RemovalPolicy.RETAIN if env_name == "main" else RemovalPolicy.DESTROY,
    )

def add_gsis(table: dynamodb.Table, gsis: list[dict]) -> None:
    for i, g in enumerate(gsis or []):
        pk = g["partition_key"]
        sk = g.get("sort_key")
        table.add_global_secondary_index(
            index_name=g["index_name"],
            partition_key=dynamodb.Attribute(name=pk["name"], type=to_attr_type(pk["type"])),
            sort_key=dynamodb.Attribute(name=sk["name"], type=to_attr_type(sk["type"])) if sk else None,
            projection_type=getattr(dynamodb.ProjectionType, (g.get("projection", "ALL")).upper()),
            read_capacity=g.get("rcu"),   # only used if PROVISIONED; ignored for PAY_PER_REQUEST
            write_capacity=g.get("wcu"),  # idem
        )

# -----------------------------
# Single table builder
# -----------------------------

def build_table(scope: Construct, name: str, conf: dict, *, env_name: str) -> dynamodb.Table:
    pk = conf["partition_key"]
    sk = conf.get("sort_key")
    billing = (conf.get("billing_mode") or "PAY_PER_REQUEST").upper()
    pitr = bool(conf.get("pitr", True))
    ttl_attr = conf.get("ttl_attribute")
    stream = to_stream_type(conf.get("stream"))
    kms_alias = conf.get("kms_alias", f"alias/{conf['table_name']}")
    removal = RemovalPolicy.RETAIN if env_name == "main" else RemovalPolicy.DESTROY

    key = ensure_kms_key(scope, alias=kms_alias, env_name=env_name)

    table = dynamodb.Table(
        scope, f"Table-{name}",
        table_name=conf["table_name"],
        partition_key=dynamodb.Attribute(name=pk["name"], type=to_attr_type(pk["type"])),
        sort_key=dynamodb.Attribute(name=sk["name"], type=to_attr_type(sk["type"])) if sk else None,
        billing_mode=dynamodb.BillingMode.PROVISIONED if billing == "PROVISIONED" else dynamodb.BillingMode.PAY_PER_REQUEST,
        read_capacity=conf.get("rcu") if billing == "PROVISIONED" else None,
        write_capacity=conf.get("wcu") if billing == "PROVISIONED" else None,
        time_to_live_attribute=ttl_attr,
        point_in_time_recovery=pitr,
        encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
        encryption_key=key,
        stream=stream,
        removal_policy=removal,
    )

    # GSIs (optional)
    add_gsis(table, conf.get("global_secondary_indexes", []))

    # Tags (optional)
    for k, v in (conf.get("tags") or {}).items():
        Tags.of(table).add(k, v)

    return table

# -----------------------------
# Multi-table builder (file-per-table)
# -----------------------------

class DynamoTables(Construct):
    """
    Build multiple DynamoDB tables from multiple JSON files.

    Usage options:
      1) Provide a directory with one JSON per table:
         DynamoTables(..., env_name=env, config_dir="cdk_project/configs/tables", defaults_file="cdk_project/configs/dynamodb.defaults.json")

         Each table JSON looks like:
         {
           "name": "messages",                   # optional; falls back to filename stem
           "table_name": "odyssey-chat-messages-${EnvName}",
           "partition_key": {"name":"pk","type":"STRING"},
           "sort_key": {"name":"sk","type":"NUMBER"},
           "ttl_attribute": "ttl",
           "pitr": true,
           "billing_mode": "PAY_PER_REQUEST",
           "kms_alias": "alias/odyssey-chat-${EnvName}",
           "stream": "NEW_AND_OLD_IMAGES",
           "global_secondary_indexes": [ ... ],
           "tags": {"service":"odyssey"}
         }

         The optional defaults_file contains a JSON object with default keys merged into each table config.

      2) Provide explicit list of files:
         DynamoTables(..., env_name=env, config_files=["configs/tables/messages.json","configs/tables/sessions.json"]) 
    """
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        config_files: Optional[List[str]] = None,
        config_dir: Optional[str] = None,
        defaults_file: Optional[str] = None,
    ) -> None:
        super().__init__(scope, construct_id)
        stack = Stack.of(self)
        cfg = get_cfg(stack)
        vars = cfg.vars(stack)

        # Load defaults (if provided). Format: a flat dict of default keys/values.
        defaults: dict = {}
        if defaults_file:
            defaults = load_json_config(defaults_file, vars) or {}

        # Gather table config files
        files: List[str] = []
        if config_files:
            files.extend(config_files)
        if config_dir:
            exclude = {Path(defaults_file).name} if defaults_file else set()
            files.extend(list_json_files(config_dir, exclude=exclude))
        if not files:
            raise ValueError("You must provide either 'config_files' or 'config_dir' with at least one table config JSON.")

        # Build tables
        self.tables: Dict[str, dynamodb.Table] = {}
        for path in files:
            conf = load_json_config(path, vars)
            merged = {**defaults, **conf}
            logical_name = merged.get("name") or Path(path).stem
            table = build_table(self, logical_name, merged, env_name=env_name)
            self.tables[logical_name] = table