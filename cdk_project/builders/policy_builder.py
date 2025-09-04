"""
IAM policy builders for Odyssey CDK project.

This module provides builders for creating and applying IAM policies to roles.
It supports both managed policies and inline policies with comprehensive validation
using the centralized error handler system.
"""

from __future__ import annotations
from typing import Any, Dict, List
from aws_cdk import aws_iam as iam
from constructs import Construct
from cdk_project.configs.config_manager import ConfigManager
from cdk_project.configs.error_handler import ErrorHandler

def _ensure_list(obj: Any) -> List[Any]:
    """
    Ensure obj is a list, wrapping it if it's a single item.
    
    Args:
        obj: Object to ensure is a list
        
    Returns:
        List containing the object or the object itself if already a list
    """
    if isinstance(obj, list):
        return obj
    return [obj]

def _attach_managed(
        role: iam.IRole, 
        policies: List[str]
    ) -> None:
    """
    Attach managed policies to a role.
    
    Args:
        role: IAM role to attach policies to
        policies: List of policy names or ARNs
    """
    for policy in policies:
        if policy.startswith("arn:"):
            role.add_managed_policy(
                iam.ManagedPolicy.from_managed_policy_arn(
                    role, 
                    f"Managed-{policy.split('/')[-1]}", 
                    policy
                )
            )
        else:
            role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name(policy)
            )

def _attach_inline(
        role: iam.IRole, 
        name: str, 
        statements: list[dict]
    ) -> None:
    """
    Attach inline policy to a role.
    
    Args:
        role: IAM role to attach policy to
        name: Name of the inline policy
        statements: List of IAM policy statements
    """
    doc = iam.PolicyDocument(
        statements=[iam.PolicyStatement.from_json(s) for s in statements]
    )
    iam.Policy(
        role, 
        f"Inline-{name}", 
        document=doc, 
        roles=[role]
    )

def _validate_config(raw: dict) -> None:
    """
    Validate policy configuration structure.
    
    Args:
        raw: Policy configuration dictionary
        
    Raises:
        ValueError: If configuration structure is invalid
    """
    ErrorHandler.validate_type(raw, dict, "policy config", "Policy")
    
    allowed = {"managed", "inline"}
    extra = set(raw.keys()) - allowed
    if extra:
        raise ValueError(f"Unknown keys in policy config: {', '.join(sorted(extra))}")
    
    if "managed" in raw:
        ErrorHandler.validate_type(
            raw["managed"], 
            (list, tuple), 
            "managed", 
            "Policy"
        )
    
    inline = raw.get("inline", {})
    ErrorHandler.validate_type(inline, dict, "inline", "Policy")
    
    for name, stmts in inline.items():
        ErrorHandler.validate_string_not_empty(
            name, 
            "inline policy name", 
            "Policy"
        )
        lst = _ensure_list(stmts)
        ErrorHandler.validate_list_not_empty(
            lst, 
            f"inline policy '{name}'", 
            "Policy"
        )
        
        for i, s in enumerate(lst):
            ErrorHandler.validate_type(
                s, 
                dict, 
                f"statement #{i} in '{name}'", 
                "Policy"
            )
            
            # Validate required fields for IAM statement
            required_fields = ["Effect", "Action"]
            ErrorHandler.validate_required_fields(
                s, 
                required_fields, 
                f"Statement #{i} in '{name}'"
            )
            
            # Check for Resource or NotResource
            if "Resource" not in s and "NotResource" not in s:
                raise ValueError(
                    f"Statement #{i} in '{name}' must include Resource or NotResource"
                )

def apply_policies_to_role(
        role: iam.IRole, 
        filename: str, 
        base_dir: str = None
    ) -> None:
    """
    Apply policies from a JSON file to a role.
    
    The JSON file should have this structure:
    {
      "managed": ["AmazonS3ReadOnlyAccess", "arn:aws:iam::...:policy/MyPolicy"],
      "inline": {
        "MyInlinePolicy": [
          {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::my-bucket/*"]
          }
        ]
      }
    }
    
    Args:
        role: IAM role to apply policies to
        filename: Policy config filename
        base_dir: Optional base directory (uses config manager if None)
        
    Raises:
        ValueError: If policy configuration is invalid
        FileNotFoundError: If policy file is not found
    """
    config_mgr = ConfigManager(role.stack)
    
    # Load policy configuration
    if base_dir:
        # Legacy support - load from specific directory
        import os
        file_path = os.path.join(base_dir, filename)
        ErrorHandler.validate_file_exists(file_path, "Policy file")
        with open(file_path, "r", encoding="utf-8") as f:
            import json
            raw = json.load(f)
        raw = config_mgr.expand_placeholders(raw)
    else:
        # Use ConfigManager to load policy
        raw = config_mgr.load_config("policies", filename)
    
    # Validate configuration
    _validate_config(raw)
    
    # Apply managed policies
    if "managed" in raw:
        _attach_managed(role, raw["managed"])
    
    # Apply inline policies
    for name, statements in raw.get("inline", {}).items():
        _attach_inline(
            role, 
            name, 
            _ensure_list(statements)
        )