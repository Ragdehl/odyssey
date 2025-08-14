from __future__ import annotations
import json, os, re
from typing import Any, Iterable, Mapping
from aws_cdk import Stack
from aws_cdk import aws_iam as iam
from cdk_project.configs.odyssey_cfg import get_cfg

_VAR = re.compile(r"\$\{([A-Za-z0-9_]+)\}")

def _expand(obj: Any, vars: Mapping[str, str]) -> Any:
    if isinstance(obj, str):
        return _VAR.sub(lambda m: str(vars.get(m.group(1), m.group(0))), obj)
    if isinstance(obj, list):
        return [_expand(x, vars) for x in obj]
    if isinstance(obj, dict):
        return {k: _expand(v, vars) for k, v in obj.items()}
    return obj

def _ensure_list(x: Any) -> list:
    if x is None: return []
    return x if isinstance(x, list) else [x]

def _attach_managed(role: iam.IRole, managed: Iterable[str]) -> None:
    scope = Stack.of(role)
    for p in managed or []:
        arn = p if ":" in p else f"arn:aws:iam::aws:policy/{p}"
        role.add_managed_policy(iam.ManagedPolicy.from_managed_policy_arn(scope, f"MP-{abs(hash(arn))}", arn))

def _attach_inline(role: iam.IRole, name: str, statements: list[dict]) -> None:
    scope = Stack.of(role)
    doc = iam.PolicyDocument.from_json({"Version": "2012-10-17", "Statement": statements})
    iam.Policy(scope, f"Inline-{name}", document=doc, roles=[role])

def _validate_config(raw: dict) -> None:
    if not isinstance(raw, dict):
        raise ValueError("Policy config must be a JSON object.")
    allowed = {"managed", "inline"}
    extra = set(raw.keys()) - allowed
    if extra:
        raise ValueError(f"Unknown keys in policy config: {', '.join(sorted(extra))}")
    if "managed" in raw and not isinstance(raw["managed"], (list, tuple)):
        raise ValueError("'managed' must be a list of policy names/ARNs.")
    inline = raw.get("inline", {})
    if not isinstance(inline, dict):
        raise ValueError("'inline' must be an object mapping policyName -> statements.")
    for name, stmts in inline.items():
        if not isinstance(name, str) or not name:
            raise ValueError("Inline policy names must be non-empty strings.")
        lst = _ensure_list(stmts)
        if not lst:
            raise ValueError(f"Inline policy '{name}' must contain at least one statement.")
        for i, s in enumerate(lst):
            if not isinstance(s, dict):
                raise ValueError(f"Statement #{i} in '{name}' must be a JSON object.")
            # Comprobación mínima de campos
            if "Effect" not in s or "Action" not in s or ("Resource" not in s and "NotResource" not in s):
                raise ValueError(f"Statement #{i} in '{name}' must include Effect, Action and Resource/NotResource.")

def apply_policies_to_role(role: iam.IRole, file: str, base_dir: str = "configs") -> None:
    """
    Carga {base_dir}/{file}, expande placeholders con odyssey_cfg y adjunta:
      - 'managed': lista de políticas gestionadas (nombre corto o ARN completo)
      - 'inline':  mapa { nombre -> [statements] }  (sin 'Version'/'Statement', el builder lo añade)
    Placeholders disponibles: ${EnvName}, ${AccountId}, ${Region}, ${Partition}, ${Branch}, ${ConnectionArn}
    """
    stack = Stack.of(role)
    cfg = get_cfg(stack)
    vars = cfg.vars(stack)

    path = os.path.join(base_dir, file)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Policy config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    _validate_config(raw)

    _attach_managed(role, raw.get("managed", []))

    for name, stmts in (raw.get("inline") or {}).items():
        stmts_expanded = _expand(_ensure_list(stmts), vars)
        _attach_inline(role, name, stmts_expanded)
