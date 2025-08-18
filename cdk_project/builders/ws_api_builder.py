from __future__ import annotations
import json, os, re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from aws_cdk import (
    Stack, CfnOutput
)
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_iam as iam
from constructs import Construct
from cdk_project.configs.odyssey_cfg import get_cfg
from cdk_project.builders.policy_builder import apply_policies_to_role

_VAR = re.compile(r"\$\{([A-Za-z0-9_]+)\}")

# -----------------------------
# Helpers
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
# Core builders
# -----------------------------

def build_websocket_api(scope: Construct, logical_name: str, conf: dict) -> apigwv2.WebSocketApi:
    """Create a WebSocket API with a route selection expression.

    Args:
        scope: CDK construct scope
        logical_name: ID suffix used for CDK logical names
        conf: Parsed api.json dict. Supports keys:
            - name: string (API name in console)
            - route_selection_expression: string (default: "$request.body.action")
    Returns:
        apigwv2.WebSocketApi instance
    """
    return apigwv2.WebSocketApi(
        scope, f"WsApi-{logical_name}",
        api_name=conf.get("name", f"odyssey-ws-{logical_name}"),
        route_selection_expression=conf.get("route_selection_expression", "$request.body.action"),
        connect_route_options=None,  # routes are added later from JSON files
    )


def build_websocket_stage(scope: Construct, api: apigwv2.WebSocketApi, conf: dict) -> apigwv2.WebSocketStage:
    """Create a WebSocket stage using config.stage.*

    api.json > stage:
      {
        "name": "dev",
        "auto_deploy": true
      }
    """
    stage_conf = conf.get("stage", {})
    stage_name = stage_conf.get("name", "$default")
    auto_deploy = bool(stage_conf.get("auto_deploy", True))

    return apigwv2.WebSocketStage(
        scope, f"WsStage-{api.node.id}",
        web_socket_api=api,
        stage_name=stage_name,
        auto_deploy=auto_deploy,
    )


def lambda_integration(handler) -> apigwv2_integrations.WebSocketLambdaIntegration:
    """Wrap a Lambda function in a WebSocket integration."""
    return apigwv2_integrations.WebSocketLambdaIntegration(
        f"WsLambdaInt-{handler.node.id}", handler
    )


def add_routes_from_dir(scope: Construct, api: apigwv2.WebSocketApi, lambdas: Dict[str, Any], routes_dir: Path) -> List[str]:
    """Add routes by scanning a folder of JSON files.

    Each file is a dict with at least:
      - route_key: "$connect" | "$disconnect" | "$default" | "<custom>"
      - integration: { "type": "lambda", "lambda_name": "<LambdaFleet name>", "timeout": 10 }

    The file name stem is used as default route_key when not present (e.g. sendMessage.json -> "sendMessage").

    Returns a list of route keys created.
    """
    created: List[str] = []
    for f in sorted(routes_dir.glob("**/*.json")):
        rc = load_json(f)
        route_key = rc.get("route_key") or f.stem
        integ = rc.get("integration", {})
        if (integ.get("type") or "lambda").lower() != "lambda":
            raise ValueError(f"Only lambda integrations supported for now. File: {f}")

        lambda_name = integ.get("lambda_name")
        if not lambda_name or lambda_name not in lambdas:
            raise KeyError(f"lambda_name '{lambda_name}' not found in provided lambdas map. File: {f}")

        handler = lambdas[lambda_name]
        integration = lambda_integration(handler)

        api.add_route(route_key=route_key, integration=integration)
        created.append(route_key)
    return created


def grant_manage_connections(api: apigwv2.WebSocketApi, lambdas: Dict[str, Any], names: List[str], *, region: str, account: str) -> None:
    """Grant execute-api:ManageConnections on this API to selected lambdas.

    Lambdas that reply to clients via the @connections endpoint need this.
    """
    for lambda_name in names or []:
        fn = lambdas.get(lambda_name)
        if not fn:
            raise KeyError(f"Lambda '{lambda_name}' not found to grant ManageConnections")

        # Note: we pass the ApiId at runtime using extra_vars
        apply_policies_to_role(
            fn.role,
            "manage_connections.json",
            base_dir="cdk_project/configs/iam/policies",
        )

# -----------------------------
# High-level construct
# -----------------------------

class WebSocketApis(Construct):
    """Build multiple WebSocket APIs from JSON folders.

    Directory layout per API (under config_root):
      <api_dir>/api.json                   # metadata (name, stage, route selection expression,...)
      <api_dir>/routes/*.json              # one route per file

    Example usage in a stack:

        ws = WebSocketApis(
            self, "WsApis",
            env_name=env_name,
            lambdas=lambdas,                                # dict[str, _lambda.Function] from LambdaFleet
            config_root="cdk_project/configs/apis/ws"      # root folder with one subfolder per API
        )
        # Access endpoints: ws.endpoints["chat"] -> wss URL

    """
    def __init__(self,
                 scope: Construct,
                 construct_id: str,
                 *,
                 env_name: str,
                 lambdas: Dict[str, Any],
                 config_root: str = "cdk_project/configs/apis/ws") -> None:
        super().__init__(scope, construct_id)

        stack = Stack.of(self)
        cfg = get_cfg(stack)
        vars = cfg.vars(stack)

        root = Path(config_root)
        if not root.is_dir():
            raise FileNotFoundError(f"WebSocket config root not found: {config_root}")

        self.apis: Dict[str, apigwv2.WebSocketApi] = {}
        self.stages: Dict[str, apigwv2.WebSocketStage] = {}
        self.endpoints: Dict[str, str] = {}

        for api_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            name = api_dir.name
            api_json = api_dir / "api.json"
            routes_dir = api_dir / "routes"
            if not api_json.is_file():
                raise FileNotFoundError(f"Missing api.json in {api_dir}")
            if not routes_dir.is_dir():
                raise FileNotFoundError(f"Missing routes/ directory in {api_dir}")

            # Load and expand api.json
            api_conf = expand_placeholders(load_json(api_json), vars)

            # 1) API
            api = build_websocket_api(self, name, api_conf)
            self.apis[name] = api

            # 2) Routes
            route_keys = add_routes_from_dir(self, api, lambdas, routes_dir)

            # 3) Stage
            stage = build_websocket_stage(self, api, api_conf)
            self.stages[name] = stage

            # 4) Optional: permissions to post to connections
            mc = api_conf.get("manage_connections_for", [])
            if mc:
                grant_manage_connections(api, lambdas, mc, region=stack.region, account=stack.account)

            # 5) Output endpoint
            endpoint = f"wss://{api.api_id}.execute-api.{stack.region}.amazonaws.com/{stage.stage_name}"
            self.endpoints[name] = endpoint
            CfnOutput(self, f"WsEndpoint-{name}", value=endpoint)