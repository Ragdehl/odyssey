"""
DynamoDB table builders for Odyssey CDK project.

This module provides builders for creating DynamoDB tables from JSON configurations.
It includes support for single table creation, multi-table management, KMS encryption,
Global Secondary Indexes, and comprehensive validation using the centralized error handler.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from aws_cdk import (
    Stack, 
    RemovalPolicy, 
    Duration, 
    Tags
)
from aws_cdk import aws_kms as kms
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct
from cdk_project.configs.config_manager import ConfigManager
from cdk_project.configs.error_handler import ErrorHandler, ValidationDecorators
from pathlib import Path

# -----------------------------
# Type mappers
# -----------------------------

def to_attr_type(s: str) -> dynamodb.AttributeType:
    """
    Convert string to DynamoDB attribute type.
    
    Args:
        s: String representation of attribute type
        
    Returns:
        DynamoDB attribute type enum
        
    Raises:
        KeyError: If string is not a valid attribute type
    """
    s = (s or "").upper()
    return {
        "STRING": dynamodb.AttributeType.STRING,
        "NUMBER": dynamodb.AttributeType.NUMBER,
        "BINARY": dynamodb.AttributeType.BINARY,
    }[s]

def to_stream_type(s: str | None) -> dynamodb.StreamViewType | None:
    """
    Convert string to DynamoDB stream view type.
    
    Args:
        s: String representation of stream view type
        
    Returns:
        DynamoDB stream view type enum or None
    """
    if not s: 
        return None
    m = {
        "NEW_IMAGE": dynamodb.StreamViewType.NEW_IMAGE,
        "OLD_IMAGE": dynamodb.StreamViewType.OLD_IMAGE,
        "NEW_AND_OLD_IMAGES": dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        "KEYS_ONLY": dynamodb.StreamViewType.KEYS_ONLY,
    }
    return m[s.upper()]

# -----------------------------
# KMS & GSIs
# -----------------------------

def ensure_kms_key(
        scope: Construct, 
        *, 
        alias: str, 
        env_name: str
    ) -> kms.Key:
    """
    Ensure a KMS key exists for DynamoDB encryption.
    
    Args:
        scope: CDK construct scope
        alias: KMS key alias
        env_name: Environment name for removal policy
        
    Returns:
        KMS key instance
    """
    return kms.Key(
        scope, 
        f"KmsKey-{alias.replace('/', '-')}",
        alias=alias,
        enable_key_rotation=True,
        removal_policy=RemovalPolicy.RETAIN if env_name == "main" else RemovalPolicy.DESTROY,
    )

def add_gsis(
        table: dynamodb.Table, 
        gsis: list[dict]
    ) -> None:
    """
    Add Global Secondary Indexes to a DynamoDB table.
    
    Args:
        table: DynamoDB table to add GSIs to
        gsis: List of GSI configuration dictionaries
        
    Raises:
        ValueError: If GSI configuration is invalid
    """
    for i, g in enumerate(gsis or []):
        # Validate required fields
        ErrorHandler.validate_required_fields(
            g, 
            ["index_name", "partition_key", "projection"], 
            f"GSI #{i}"
        )
        
        pk = g["partition_key"]
        ErrorHandler.validate_field_structure(
            g, 
            "partition_key", 
            ["name", "type"], 
            f"GSI #{i}"
        )
        
        sk = g.get("sort_key")
        if sk:
            ErrorHandler.validate_field_structure(
                g, 
                "sort_key", 
                ["name", "type"], 
                f"GSI #{i}"
            )
        
        table.add_global_secondary_index(
            index_name=g["index_name"],
            partition_key=dynamodb.Attribute(
                name=pk["name"], 
                type=to_attr_type(pk["type"])
            ),
            sort_key=dynamodb.Attribute(
                name=sk["name"], 
                type=to_attr_type(sk["type"])
            ) if sk else None,
            projection_type=getattr(dynamodb.ProjectionType, g["projection"].upper()),
            read_capacity=g.get("rcu"),   # only used if PROVISIONED; ignored for PAY_PER_REQUEST
            write_capacity=g.get("wcu"),  # idem
        )

# -----------------------------
# Single table builder
# -----------------------------

@ValidationDecorators.validate_required_config_fields(
    ["table_name", "partition_key", "billing_mode", "pitr", "kms_alias"], 
    context="Table"
)
def build_table(
        scope: Construct, 
        name: str, 
        conf: dict, 
        *, 
        env_name: str
    ) -> dynamodb.Table:
    """
    Build a DynamoDB table from configuration.
    
    Args:
        scope: CDK construct scope
        name: Logical name for the table
        conf: Table configuration dictionary
        env_name: Environment name for removal policy
        
    Returns:
        DynamoDB table instance
        
    Raises:
        ValueError: If configuration is invalid
    """
    # Validate partition_key structure
    ErrorHandler.validate_field_structure(
        conf, 
        "partition_key", 
        ["name", "type"], 
        f"Table configuration for {name}"
    )
    
    # Validate sort_key structure if present
    sk = conf.get("sort_key")
    if sk:
        ErrorHandler.validate_field_structure(
            conf, 
            "sort_key", 
            ["name", "type"], 
            f"Table configuration for {name}"
        )
    
    billing = conf["billing_mode"].upper()
    pitr = conf["pitr"]
    ttl_attr = conf.get("ttl_attribute")
    stream = to_stream_type(conf.get("stream"))
    kms_alias = conf["kms_alias"]
    removal = RemovalPolicy.RETAIN if env_name == "main" else RemovalPolicy.DESTROY

    # Create KMS key for encryption
    key = ensure_kms_key(
        scope, 
        alias=kms_alias, 
        env_name=env_name
    )

    table = dynamodb.Table(
        scope, 
        f"Table-{name}",
        table_name=conf["table_name"],
        partition_key=dynamodb.Attribute(
            name=conf["partition_key"]["name"], 
            type=to_attr_type(conf["partition_key"]["type"])
        ),
        sort_key=dynamodb.Attribute(
            name=sk["name"], 
            type=to_attr_type(sk["type"])
        ) if sk else None,
        billing_mode=dynamodb.BillingMode.PROVISIONED if billing == "PROVISIONED" else dynamodb.BillingMode.PAY_PER_REQUEST,
        read_capacity=conf.get("rcu") if billing == "PROVISIONED" else None,
        write_capacity=conf.get("wcu") if billing == "PROVISIONED" else None,
        time_to_live_attribute=ttl_attr,
        point_in_time_recovery=pitr,
        encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
        encryption_key=key,
        stream=stream,
        removal_policy=removal,
    )

    # Add GSIs if configured
    add_gsis(table, conf.get("global_secondary_indexes", []))

    # Add tags if configured
    for k, v in (conf.get("tags") or {}).items():
        Tags.of(table).add(k, v)

    return table

# -----------------------------
# Multi-table builder (file-per-table)
# -----------------------------

class DynamoTables(Construct):
    """
    Build multiple DynamoDB tables from multiple JSON files.

    Usage:
      DynamoTables(..., env_name=env, config_files=["messages.json","sessions.json"])

      Each table JSON must have:
      {
        "name": "messages",                   # optional; falls back to filename stem
        "table_name": "odyssey-chat-messages-${EnvName}",
        "partition_key": {"name":"pk","type":"STRING"},
        "billing_mode": "PAY_PER_REQUEST",
        "pitr": true,
        "kms_alias": "alias/odyssey-chat-${EnvName}",
        
        # Optional fields:
        "sort_key": {"name":"sk","type":"NUMBER"},
        "ttl_attribute": "ttl",
        "stream": "NEW_AND_OLD_IMAGES",
        "global_secondary_indexes": [ ... ],
        "tags": {"service":"odyssey"}
      }
    """    
    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            *,
            env_name: str,
            config_files: Optional[List[str]] = None,
        ) -> None:
        """
        Initialize the DynamoDB tables construct.
        
        Args:
            scope: CDK construct scope
            construct_id: Construct ID
            env_name: Environment name
            config_files: List of configuration file names
            
        Raises:
            ValueError: If no config files provided or no configurations found
        """
        super().__init__(scope, construct_id)
        
        self.config_mgr = ConfigManager(Stack.of(self))

        # Load specific files
        table_configs = []

        ErrorHandler.validate_config_files_provided(config_files, "DynamoTables")

        for filename in config_files:
            config = self.config_mgr.load_config("dynamodb", filename)
            table_configs.append((filename, config))
        
        ErrorHandler.validate_configs_found(table_configs, "table")

        # Build tables
        self.tables: Dict[str, dynamodb.Table] = {}
        for filepath, conf in table_configs:
            logical_name = conf.get("name") or Path(filepath).stem if filepath else "table"
            table = build_table(
                self, 
                logical_name, 
                conf, 
                env_name=env_name
            )
            self.tables[logical_name] = table