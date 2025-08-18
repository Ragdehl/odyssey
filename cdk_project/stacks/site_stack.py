from aws_cdk import Stack
from constructs import Construct
from cdk_project.builders.static_site_builder import StaticWebsite

class StaticSiteStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # just “use the builder”
        self.site = StaticWebsite(self, "Site", env_name=env_name)
