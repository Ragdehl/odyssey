from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from aws_cdk import Duration, Stack, Tags
from aws_cdk import aws_lambda as _lambda
from constructs import Construct
from cdk_project.configs.config_manager import ConfigManager
from cdk_project.builders.policy_builder import apply_policies_to_role

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
        
        self.config_mgr = ConfigManager(Stack.of(self))
        self.functions: Dict[str, _lambda.Function] = {}

        for folder in self.config_mgr.find_lambda_dirs(code_root):
            conf = self.config_mgr.load_lambda_config_from_folder(folder, extra_vars={"EnvName": env_name})
            logical_name = conf["name"]

            fn = build_lambda_function(self, logical_name, conf)

            # Attach inline/managed policies if requested
            policy_file = conf.get("policy_file")
            if policy_file:
                apply_policies_to_role(fn.role, policy_file)

            # Dynamo grants (optional)
            grant_table_access(fn, conf.get("dynamodb_access", []), tables)

            self.functions[logical_name] = fn
