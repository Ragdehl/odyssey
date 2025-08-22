from __future__ import annotations
from typing import Any, Dict, List

from aws_cdk import (
    Stack, CfnOutput
)
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_iam as iam
from constructs import Construct
from cdk_project.configs.config_manager import ConfigManager
from cdk_project.builders.policy_builder import apply_policies_to_role

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


def add_routes_from_dir(scope: Construct, api: apigwv2.WebSocketApi, lambdas: Dict[str, Any], config_mgr: ConfigManager, api_name: str) -> List[str]:
    """Add routes by scanning a folder of JSON files.

    Each file is a dict with at least:
      - route_key: "$connect" | "$disconnect" | "$default" | "<custom>"
      - integration: { "type": "lambda", "lambda_name": "<LambdaFleet name>", "timeout": 10 }

    The file name stem is used as default route_key when not present (e.g. sendMessage.json -> "sendMessage").

    Returns a list of route keys created.
    """
    created: List[str] = []
    
    # Use ConfigManager to find route files
    route_files = config_mgr.find_route_files(api_name)
    
    for route_file in route_files:
        rc = config_mgr.load_route_config(route_file)
        route_key = rc.get("route_key") or route_file.stem
        integ = rc.get("integration", {})
        if (integ.get("type") or "lambda").lower() != "lambda":
            raise ValueError(f"Only lambda integrations supported for now. File: {route_file}")

        lambda_name = integ.get("lambda_name")
        if not lambda_name or lambda_name not in lambdas:
            raise KeyError(f"lambda_name '{lambda_name}' not found in provided lambdas map. File: {route_file}")

        handler = lambdas[lambda_name]
        integration = lambda_integration(handler)

        api.add_route(route_key=route_key, integration=integration)
        created.append(route_key)
    return created


def grant_manage_connections(api: apigwv2.WebSocketApi, lambdas: Dict[str, Any], names: List[str], config_mgr: ConfigManager) -> None:
    """Grant execute-api:ManageConnections on this API to selected lambdas.

    Lambdas that reply to clients via the @connections endpoint need this.
    """
    for lambda_name in names or []:
        fn = lambdas.get(lambda_name)
        if not fn:
            raise KeyError(f"Lambda '{lambda_name}' not found to grant ManageConnections")

        # Use config manager to load the policy
        apply_policies_to_role(
            fn.role,
            "manage_connections.json"
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
            config_root="ws"                               # config type for WebSocket APIs
        )
        # Access endpoints: ws.endpoints["chat"] -> wss URL

    """
    def __init__(self,
                 scope: Construct,
                 construct_id: str,
                 *,
                 env_name: str,
                 lambdas: Dict[str, Any],
                 config_root: str = "ws") -> None:
        super().__init__(scope, construct_id)

        self.config_mgr = ConfigManager(Stack.of(self))
        self.apis: Dict[str, apigwv2.WebSocketApi] = {}
        self.stages: Dict[str, apigwv2.WebSocketStage] = {}
        self.endpoints: Dict[str, str] = {}

        # Use ConfigManager to find API directories
        api_dirs = self.config_mgr.find_api_directories()

        for api_dir in api_dirs:
            name = api_dir.name

            # Load API configuration using ConfigManager
            api_conf = self.config_mgr.load_api_config(api_dir)

            # 1) API
            api = build_websocket_api(self, name, api_conf)
            self.apis[name] = api

            # 2) Routes
            route_keys = add_routes_from_dir(self, api, lambdas, self.config_mgr, name)

            # 3) Stage
            stage = build_websocket_stage(self, api, api_conf)
            self.stages[name] = stage

            # 4) Optional: permissions to post to connections
            mc = api_conf.get("manage_connections_for", [])
            if mc:
                grant_manage_connections(api, lambdas, mc, self.config_mgr)

            # 5) Output endpoint
            stack = Stack.of(self)
            endpoint = f"wss://{api.api_id}.execute-api.{stack.region}.amazonaws.com/{stage.stage_name}"
            self.endpoints[name] = endpoint
            CfnOutput(self, f"WsEndpoint-{name}", value=endpoint)