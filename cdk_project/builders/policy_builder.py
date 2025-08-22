from __future__ import annotations
from typing import Any, Iterable
from aws_cdk import Stack
from aws_cdk import aws_iam as iam
from cdk_project.configs.config_manager import ConfigManager

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

def apply_policies_to_role(role: iam.IRole, filename: str, base_dir: str = None) -> None:
    """
    Load policy config file and apply managed/inline policies to the role.
    
    Args:
        role: IAM role to attach policies to
        filename: Policy config filename (e.g., "pipeline.json")
        base_dir: Optional base directory (uses config manager if None)
    
    Policy config format:
    {
      "managed": ["AWSLambdaBasicExecutionRole", "arn:aws:iam::aws:policy/SomePolicy"],
      "inline": {
        "CustomPolicy": [
          {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::${BucketName}/*"]
          }
        ]
      }
    }
    """
    stack = Stack.of(role)
    config_mgr = ConfigManager(stack)

    raw = config_mgr.load_config("policies", filename, expand_vars=True)

    _validate_config(raw)

    # Attach managed policies
    _attach_managed(role, raw.get("managed", []))

    # Attach inline policies
    for name, stmts in (raw.get("inline") or {}).items():
        stmts_expanded = _ensure_list(stmts)
        _attach_inline(role, name, stmts_expanded)
