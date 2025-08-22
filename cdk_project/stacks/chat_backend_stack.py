from __future__ import annotations
from aws_cdk import (
    Stack, CfnOutput
)
from constructs import Construct

# Builders you already have in canvas
from cdk_project.builders.dynamodb_builder import DynamoTables
from cdk_project.builders.lambda_builder import LambdaFleet
from cdk_project.builders.ws_api_builder import WebSocketApis

class ChatBackendStack(Stack):
    """
    WebSocket-based backend stack for Odyssey.

    What this stack does:
      1) Builds multiple DynamoDB tables from per-table JSON files.
      2) Builds a fleet of Lambdas from per-folder multi-JSON configs (config*.json).
      3) Builds one or more WebSocket APIs from JSON-only configs (api.json + routes/*.json).
      4) Exposes the wss endpoint(s) as CloudFormation outputs.

    ManageConnections policy:
      - The WebSocketApis builder can grant execute-api:ManageConnections automatically to lambdas
        listed in api.json > manage_connections_for.
      - If you want to harden/override, this stack also shows how to attach the policy explicitly
        after the API has been created (see the optional section below).

    Per-route timeouts:
      - API Gateway WebSocket integrations do not support per-route timeouts from CDK L2.
      - Set the timeout at the Lambda level in each folder's JSON (e.g., config.base.json -> "timeout": 10).
    """

    def __init__(self, scope: Construct, construct_id: str, *, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1) DynamoDB tables from directory (file-per-table)
        dyn = DynamoTables(
            self, "Dynamo",
            env_name=env_name,
            config_files=["messages.json"],
        )
        tables = dyn.tables  # e.g. {"messages": Table, "sessions": Table}

        # 2) Lambda fleet from folders (per-folder, multi JSON)
        lambdas = LambdaFleet(
            self, "Lambdas",
            env_name=env_name,
            tables=tables,
            code_root="lambda_src",
        ).functions

        # Example: inject table name at deploy time (safer than hardcoding)
        if "chat" in lambdas and "messages" in tables:
            lambdas["chat"].add_environment("TABLE_NAME", tables["messages"].table_name)

        # 3) WebSocket APIs from JSON-only configs
        ws = WebSocketApis(
            self, "WsApis",
            env_name=env_name,
            lambdas=lambdas,
            config_root="ws",
        )

        # --- Optional: explicitly enforce ManageConnections policy for a lambda on a given API ---
        # If you also want to grant manage connections here (in addition to builder's grant), uncomment:
        #
        # api = ws.apis["chat"]  # the API folder name under configs/apis/ws/
        # region = self.region
        # account = self.account
        # arn = f"arn:aws:execute-api:{region}:{account}:{api.api_id}/*/@connections/*"
        # lambdas["chat"].add_to_role_policy(
        #     iam.PolicyStatement(actions=["execute-api:ManageConnections"], resources=[arn])
        # )

        # 4) Outputs
        if "chat" in ws.endpoints:
            CfnOutput(self, "WsChatEndpoint", value=ws.endpoints["chat"])  # wss://.../<stage>
        if "messages" in tables:
            CfnOutput(self, "MessagesTableName", value=tables["messages"].table_name)
