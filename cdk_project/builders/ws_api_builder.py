"""
WebSocket API builders for Odyssey CDK project.

This module provides builders for creating AWS API Gateway WebSocket APIs,
stages, routes, and integrations. It includes support for Lambda integrations,
route management, and comprehensive validation using the centralized error handler.
"""

from __future__ import annotations
from typing import Any, Dict, List

from aws_cdk import (
    Stack, 
    CfnOutput
)
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_iam as iam
from constructs import Construct
from cdk_project.configs.config_manager import ConfigManager
from cdk_project.builders.policy_builder import apply_policies_to_role
from cdk_project.configs.error_handler import ErrorHandler, ValidationDecorators

# -----------------------------
# Core builders
# -----------------------------

@ValidationDecorators.validate_required_config_fields(
    ["name", "route_selection_expression"], 
    context="WebSocket API"
)
def build_websocket_api(
        scope: Construct, 
        logical_name: str, 
        conf: dict
    ) -> apigwv2.WebSocketApi:
    """
    Create a WebSocket API with a route selection expression.

    Args:
        scope: CDK construct scope
        logical_name: ID suffix used for CDK logical names
        conf: Parsed api.json dict with required keys:
            - name: string (API name in console)
            - route_selection_expression: string
            
    Returns:
        apigwv2.WebSocketApi instance
    """
    return apigwv2.WebSocketApi(
        scope, 
        f"WsApi-{logical_name}",
        api_name=conf["name"],
        route_selection_expression=conf["route_selection_expression"],
        connect_route_options=None,  # routes are added later from JSON files
    )


@ValidationDecorators.validate_required_config_fields(
    ["stage"], 
    context="WebSocket API"
)
def build_websocket_stage(
        scope: Construct, 
        api: apigwv2.WebSocketApi, 
        conf: dict
    ) -> apigwv2.WebSocketStage:
    """
    Create a WebSocket stage using config.stage.*

    api.json > stage:
      {
        "name": "dev",
        "auto_deploy": true
      }
      
    Args:
        scope: CDK construct scope
        api: WebSocket API to create stage for
        conf: API configuration dictionary
        
    Returns:
        WebSocket stage instance
    """
    ErrorHandler.validate_field_structure(
        conf, 
        "stage", 
        ["name", "auto_deploy"], 
        "WebSocket API configuration"
    )

    return apigwv2.WebSocketStage(
        scope, 
        f"WsStage-{api.node.id}",
        web_socket_api=api,
        stage_name=conf["stage"]["name"],
        auto_deploy=conf["stage"]["auto_deploy"],
    )


def lambda_integration(
        handler
    ) -> apigwv2_integrations.WebSocketLambdaIntegration:
    """
    Wrap a Lambda function in a WebSocket integration.
    
    Args:
        handler: Lambda function handler
        
    Returns:
        WebSocket Lambda integration
    """
    return apigwv2_integrations.WebSocketLambdaIntegration(
        f"WsLambdaInt-{handler.node.id}", 
        handler
    )


def add_routes_from_dir(
        scope: Construct, 
        api: apigwv2.WebSocketApi, 
        lambdas: Dict[str, Any], 
        config_mgr: ConfigManager, 
        api_name: str
    ) -> List[str]:
    """
    Add routes by scanning a folder of JSON files.

    Each file is a dict with required fields:
      - route_key: "$connect" | "$disconnect" | "$default" | "<custom>"
      - integration: { "type": "lambda", "lambda_name": "<LambdaFleet name>" }

    Args:
        scope: CDK construct scope
        api: WebSocket API to add routes to
        lambdas: Dictionary of Lambda functions
        config_mgr: Configuration manager instance
        api_name: Name of the API
        
    Returns:
        List of route keys created
    """
    created: List[str] = []
    
    # Use ConfigManager to find route files
    route_files = config_mgr.find_route_files(api_name)
    
    for route_file in route_files:
        # Load route config using unified method
        rc = config_mgr.load_config("ws_routes", route_file.name)
        
        # Validate required fields
        ErrorHandler.validate_required_fields(
            rc, 
            ["route_key", "integration"], 
            f"Route configuration in {route_file}"
        )
        
        route_key = rc["route_key"]
        integ = rc["integration"]
        
        # Validate integration structure
        ErrorHandler.validate_field_structure(
            rc, 
            "integration", 
            ["type", "lambda_name"], 
            f"Route configuration in {route_file}"
        )
        
        # Validate integration type
        ErrorHandler.validate_enum_value(
            integ["type"], 
            ["lambda"], 
            "type", 
            f"Route integration in {route_file}"
        )

        # Validate lambda name
        lambda_name = integ["lambda_name"]
        ErrorHandler.validate_lambda_exists(
            lambda_name, 
            lambdas, 
            f"Route configuration in {route_file}"
        )

        handler = lambdas[lambda_name]
        integration = lambda_integration(handler)

        api.add_route(
            route_key=route_key, 
            integration=integration
        )
        created.append(route_key)
    return created


def grant_manage_connections(
        api: apigwv2.WebSocketApi, 
        lambdas: Dict[str, Any], 
        names: List[str], 
        config_mgr: ConfigManager
    ) -> None:
    """
    Grant execute-api:ManageConnections on this API to selected lambdas.

    Lambdas that reply to clients via the @connections endpoint need this.
    
    Args:
        api: WebSocket API to grant permissions on
        lambdas: Dictionary of Lambda functions
        names: List of Lambda function names to grant permissions to
        config_mgr: Configuration manager instance
    """
    for lambda_name in names or []:
        ErrorHandler.validate_lambda_exists(
            lambda_name, 
            lambdas, 
            "ManageConnections grant"
        )

        # Use config manager to load the policy
        apply_policies_to_role(
            lambdas[lambda_name].role,
            "manage_connections.json"
        )

# -----------------------------
# High-level construct
# -----------------------------

class WebSocketApis(Construct):
    """
    Build multiple WebSocket APIs from JSON folders.

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
    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            *,
            env_name: str,
            lambdas: Dict[str, Any],
            config_root: str = "ws"
        ) -> None:
        """
        Initialize the WebSocket APIs construct.
        
        Args:
            scope: CDK construct scope
            construct_id: Construct ID
            env_name: Environment name
            lambdas: Dictionary of Lambda functions
            config_root: Configuration root type
        """
        super().__init__(scope, construct_id)

        self.config_mgr = ConfigManager(Stack.of(self))
        self.apis: Dict[str, apigwv2.WebSocketApi] = {}
        self.stages: Dict[str, apigwv2.WebSocketStage] = {}
        self.endpoints: Dict[str, str] = {}

        # Use ConfigManager to find API directories
        api_dirs = self.config_mgr.find_api_dirs("ws_apis")

        for api_dir in api_dirs:
            name = api_dir.name

            # Load API configuration using unified method
            api_conf = self.config_mgr.load_config("ws_apis", "api.json")

            # 1) Create API
            api = build_websocket_api(
                self, 
                name, 
                api_conf
            )
            self.apis[name] = api

            # 2) Add routes
            route_keys = add_routes_from_dir(
                self, 
                api, 
                lambdas, 
                self.config_mgr, 
                name
            )
            self.route_keys = route_keys

            # 3) Create stage
            stage = build_websocket_stage(
                self, 
                api, 
                api_conf
            )
            self.stages[name] = stage

            # 4) Optional: permissions to post to connections
            mc = api_conf.get("manage_connections_for", [])
            if mc:
                grant_manage_connections(
                    api, 
                    lambdas, 
                    mc, 
                    self.config_mgr
                )

            # 5) Output endpoint
            stack = Stack.of(self)
            endpoint = f"wss://{api.api_id}.execute-api.{stack.region}.amazonaws.com/{stage.stage_name}"
            self.endpoints[name] = endpoint
            CfnOutput(
                self, 
                f"WsEndpoint-{name}", 
                value=endpoint
            )