"""
Static site stack for Odyssey CDK project.

This stack creates the static website infrastructure using the StaticWebsite builder.
It provides a simple interface for deploying the frontend application to AWS.
"""

from __future__ import annotations

from aws_cdk import Stack
from constructs import Construct

from cdk_project.builders.static_site_builder import StaticWebsite


class StaticSiteStack(Stack):
    """
    Stack for deploying the static website.

    This stack uses the StaticWebsite builder to create all necessary
    infrastructure for hosting the Odyssey frontend application.
    """

    def __init__(self, scope: Construct, construct_id: str, *, env_name: str, **kwargs) -> None:
        """
        Initialize the static site stack.

        Args:
            scope: CDK construct scope
            construct_id: Construct ID
            env_name: Environment name
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)
        # Use the builder to create the static website
        self.site = StaticWebsite(self, "Site", env_name=env_name)
