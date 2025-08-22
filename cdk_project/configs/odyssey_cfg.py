from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Union
from aws_cdk import App, Stack
from cdk_project.configs.error_handler import ErrorHandler

@dataclass(frozen=True)
class GithubCfg:
    owner: str
    repo: str

@dataclass(frozen=True)
class EnvCfg:
    name: str                 # "dev" | "main"
    account_id: str
    region: str
    branch: str
    connection_id: Optional[str] = None
    connection_arn: Optional[str] = None

    @property
    def resolved_connection_arn(self) -> Optional[str]:
        if self.connection_arn:
            return self.connection_arn
        if self.connection_id:
            return f"arn:aws:codestar-connections:{self.region}:{self.account_id}:connection/{self.connection_id}"
        return None

@dataclass(frozen=True)
class OdysseyCfg:
    env: EnvCfg
    github: GithubCfg

    def vars(self, stack: Stack, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Placeholders para JSONs de políticas, etc."""
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
    return (obj if isinstance(obj, App) else Stack.of(obj)).node

@lru_cache(maxsize=1)
def get_cfg(obj: Union[App, Stack]) -> OdysseyCfg:
    """Lee cdk.json una vez, aplica overrides (-c odyssey.env=...), y valida."""
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

    # Validación mínima
    missing = []
    if not account_id: missing.append(f"{env_name}.account_id")
    if not owner:      missing.append("github.owner")
    if not repo:       missing.append("github.repo")
    
    ErrorHandler.validate_context_keys(missing, "cdk.json")

    return OdysseyCfg(
        env=EnvCfg(
            name=env_name, account_id=account_id, region=region, branch=branch,
            connection_id=conn_id, connection_arn=conn_arn
        ),
        github=GithubCfg(owner=owner, repo=repo),
    )
