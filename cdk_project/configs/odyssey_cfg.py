"""
Project configuration management for Odyssey CDK project.

This module provides configuration classes and utilities for managing project-wide
settings, environment configurations, and context variables. It handles loading
configuration from cdk.json and provides type-safe access to configuration values.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Union
from aws_cdk import App, Stack
from functools import lru_cache
from cdk_project.configs.error_handler import ErrorHandler

@dataclass(frozen=True)
class GithubCfg:
    """
    GitHub configuration settings.
    
    Attributes:
        owner: GitHub repository owner
        repo: GitHub repository name
    """
    owner: str
    repo: str

@dataclass(frozen=True)
class EnvCfg:
    """
    Environment configuration settings.
    
    Attributes:
        name: Environment name
        account_id: AWS account ID
        region: AWS region
        branch: Git branch name
        connection_id: Optional CodeStar connection ID
        connection_arn: Optional CodeStar connection ARN
    """
    name: str
    account_id: str
    region: str
    branch: str
    connection_id: Optional[str] = None
    connection_arn: Optional[str] = None

    @property
    def resolved_connection_arn(self) -> Optional[str]:
        """
        Get the resolved connection ARN.
        
        Returns:
            Connection ARN if available, None otherwise
        """
        if self.connection_arn:
            return self.connection_arn
        if self.connection_id:
            return f"arn:aws:codestar-connections:{self.region}:{self.account_id}:connection/{self.connection_id}"
        return None

@dataclass(frozen=True)
class OdysseyCfg:
    """
    Main project configuration container.
    
    Attributes:
        env: Environment configuration
        github: GitHub configuration
    """
    env: EnvCfg
    github: GithubCfg

    def vars(
            self, 
            stack: Stack, 
            extra: dict[str, str] | None = None
        ) -> dict[str, str]:
        """
        Generate placeholder variables for JSON configuration expansion.
        
        Args:
            stack: CDK stack instance
            extra: Additional variables to include
            
        Returns:
            Dictionary of variable name to value mappings
        """
        base = {
            "EnvName": self.env.name,
            "AccountId": stack.account or self.env.account_id,
            "Region": stack.region or self.env.region,
            "Partition": stack.partition,          # arn:aws / arn:aws-cn / ...
            "GithubOwner": self.github.owner,
            "GithubRepo": self.github.repo,
            "Branch": self.env.branch,
        }
        if self.env.connection_id:
            base["ConnectionId"] = self.env.connection_id
        if self.env.resolved_connection_arn:
            base["ConnectionArn"] = self.env.resolved_connection_arn
        if extra:
            base.update({k: str(v) for k, v in extra.items()})

        return base

def _node(obj: Union[App, Stack]):
    """
    Get the CDK node from an App or Stack.
    
    Args:
        obj: CDK App or Stack instance
        
    Returns:
        CDK node instance
    """
    return (obj if isinstance(obj, App) else Stack.of(obj)).node

@lru_cache(maxsize=1)
def get_cfg(obj: Union[App, Stack]) -> OdysseyCfg:
    """
    Load project configuration from cdk.json context.
    
    Reads cdk.json once, applies overrides (-c odyssey.env=...), and validates.
    
    Args:
        obj: CDK App or Stack instance
        
    Returns:
        Validated project configuration
        
    Raises:
        ValueError: If required context keys are missing
    """
    node = _node(obj)
    ctx = node.try_get_context("odyssey") or {}
    env_name = (node.try_get_context("odyssey.env") or ctx.get("env") or "dev").lower()
    region = ctx.get("region", "eu-west-1")

    env_ctx = ctx.get(env_name) or {}
    account_id = env_ctx.get("account_id")
    branch = env_ctx.get("branch", env_name)
    conn_id = env_ctx.get("connection_id")
    conn_arn = env_ctx.get("connection_arn")

    gh = ctx.get("github") or {}
    owner = gh.get("owner")
    repo = gh.get("repo")

    # Validate required configuration
    missing = []
    if not account_id: 
        missing.append(f"{env_name}.account_id")
    if not owner:      
        missing.append("github.owner")
    if not repo:       
        missing.append("github.repo")
    
    ErrorHandler.validate_context_keys(missing, "cdk.json")

    return OdysseyCfg(
        env=EnvCfg(
            name=env_name, 
            account_id=account_id, 
            region=region, 
            branch=branch,
            connection_id=conn_id, 
            connection_arn=conn_arn
        ),
        github=GithubCfg(owner=owner, repo=repo),
    )