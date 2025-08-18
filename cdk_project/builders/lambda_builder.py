from __future__ import annotations
import json, os, re
from pathlib import Path
from typing import Any, Mapping, Dict, List, Optional
from aws_cdk import Duration, Stack, Tags
from aws_cdk import aws_lambda as _lambda
from constructs import Construct
from cdk_project.configs.odyssey_cfg import get_cfg
from cdk_project.builders.policy_builder import apply_policies_to_role

_VAR = re.compile(r"\$\{([A-Za-z0-9_]+)\}")

# -----------------------------
# Generic helpers
# -----------------------------

def expand_placeholders(obj: Any, vars: Mapping[str, str]) -> Any:
    if isinstance(obj, str):  return _VAR.sub(lambda m: str(vars.get(m.group(1), m.group(0))), obj)
    if isinstance(obj, list): return [expand_placeholders(x, vars) for x in obj]
    if isinstance(obj, dict): return {k: expand_placeholders(v, vars) for k, v in obj.items()}
    return obj

def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# -----------------------------
# Config loading (multi JSON per lambda folder)
# -----------------------------

def find_lambda_dirs(root: Path) -> List[Path]:
    if not root.is_dir():
        raise FileNotFoundError(f"Lambda root not found: {root}")
    out: List[Path] = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if (d / "app.py").is_file():
            out.append(d)
    return out

def load_lambda_config_from_folder(folder: Path, vars: Mapping[str, str]) -> dict:
    """
    Merge all JSON files that match config*.json in lexicographic order.
    Later files override earlier keys. Placeholders ${...} are expanded.
    Minimum defaults are applied if no JSON provides them.
    """
    # Gather config JSONs
    config_files = sorted(folder.glob("config*.json"))
    conf: dict = {}

    # Merge in order
    for cf in config_files:
        data = load_json(cf)
        conf.update(data)

    # Defaults
    conf.setdefault("name", folder.name)
    conf.setdefault("runtime", "python3.12")
    conf.setdefault("memory", 256)
    conf.setdefault("timeout", 10)
    conf.setdefault("handler", "app.handler")

    # Add code path and expand placeholders
    conf["code_path"] = str(folder.resolve())
    conf = expand_placeholders(conf, vars)

    return conf

# -----------------------------
# Lambda creators & grants
# -----------------------------

def runtime_from(s: str) -> _lambda.Runtime:
    s = (s or "python3.12").lower()
    m = {
        "python3.12": _lambda.Runtime.PYTHON_3_12,
        "python3.11": _lambda.Runtime.PYTHON_3_11,
        "python3.10": _lambda.Runtime.PYTHON_3_10,
        "nodejs18.x": _lambda.Runtime.NODEJS_18_X,
        "nodejs20.x": _lambda.Runtime.NODEJS_20_X,
    }
    if s not in m:
        raise ValueError(f"Unsupported runtime: {s}")
    return m[s]

def build_lambda_function(scope: Construct, logical_name: str, conf: dict) -> _lambda.Function:
    fn = _lambda.Function(
        scope, f"Fn-{logical_name}",
        function_name=conf.get("function_name"),
        runtime=runtime_from(conf.get("runtime")),
        handler=conf.get("handler", "app.handler"),
        code=_lambda.Code.from_asset(conf["code_path"]),
        memory_size=int(conf.get("memory", 256)),
        timeout=Duration.seconds(int(conf.get("timeout", 10))),
        environment={k: str(v) for k, v in (conf.get("env") or {}).items()},
        description=conf.get("description"),
    )

    for k, v in (conf.get("tags") or {}).items():
        Tags.of(fn).add(k, v)

    return fn

def grant_table_access(fn: _lambda.Function, grants: List[dict], tables: Dict[str, Any]) -> None:
    for g in grants or []:
        tname = g["table"]
        access = (g.get("access") or "readWrite").lower()
        table = tables.get(tname)
        if not table:
            raise KeyError(f"Table logical name '{tname}' not found for grants.")
        if access == "read":
            table.grant_read_data(fn)
        elif access == "write":
            table.grant_write_data(fn)
        else:
            table.grant_read_write_data(fn)


def resolve_policy_file(policy_file: Optional[str], folder: Path) -> Optional[str]:
    if not policy_file:
        return None
    p = Path(policy_file)
    if not p.is_absolute():
        # try folder local first
        local = (folder / policy_file)
        if local.is_file():
            return str(local)
        # else allow relative to configs dir for backwards compat
        alt = Path("cdk_project/configs") / policy_file
        if alt.is_file():
            return str(alt)
    return str(p)

# -----------------------------
# Fleet construct (single way: per-folder configs)
# -----------------------------

class LambdaFleet(Construct):
    """
    Discovers lambda folders under `code_root` and builds each function using
    multi-JSON config files inside each folder (config*.json). Example:

      lambda_src/chat_handler/app.py
      lambda_src/chat_handler/config.base.json
      lambda_src/chat_handler/config.env.dev.json

    Merge order is lexicographic; later files override earlier ones.
    """
    def __init__(self, scope: Construct, construct_id: str, *, env_name: str, tables: Dict[str, Any], code_root: str = "lambda_src") -> None:
        super().__init__(scope, construct_id)
        stack = Stack.of(self)
        cfg = get_cfg(stack)
        vars = cfg.vars(stack, extra={"EnvName": env_name})

        root = Path(code_root)
        self.functions: Dict[str, _lambda.Function] = {}

        for folder in find_lambda_dirs(root):
            conf = load_lambda_config_from_folder(folder, vars)
            logical_name = conf["name"]

            fn = build_lambda_function(self, logical_name, conf)

            # Attach inline/managed policies if requested
            policy_file = resolve_policy_file(conf.get("policy_file"), folder)
            if policy_file:
                # Use the filename only; the builder expects file relative name & base_dir
                apply_policies_to_role(fn.role, os.path.basename(policy_file), base_dir=str(Path(policy_file).parent))

            # Dynamo grants (optional)
            grant_table_access(fn, conf.get("dynamodb_access", []), tables)

            self.functions[logical_name] = fn

# -----------------------------
# Example stack usage
# -----------------------------
# from cdk_project.builders.dynamodb_builder import DynamoTables
# from cdk_project.builders.lambda_per_folder import LambdaFleet
#
# dyn = DynamoTables(self, "Dynamo", env_name=env_name, config_dir="cdk_project/configs/tables", defaults_file="cdk_project/configs/dynamodb.defaults.json")
# lambdas = LambdaFleet(self, "Lambdas", env_name=env_name, tables=dyn.tables, code_root="lambda_src").functions
#
# # Example: access a function by folder/name
# chat_fn = lambdas["chat"]
#
# # If you prefer to inject some env vars at stack-time:
# # chat_fn.add_environment("TABLE_NAME", dyn.tables["messages"].table_name)
