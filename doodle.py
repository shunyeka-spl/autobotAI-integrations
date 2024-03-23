# import boto3
#
# aws_clients = [
#     {
#         "package": "boto3",
#         "name": "s3",
#         "is_regional": False,
#         "import": "boto3"
#     }
# ]
#
#
# def aws_client_generator(required_clients, regions):
#     clients = []
#     for client in required_clients:
#         if client.get("is_regional"):
#             clients.append(boto3.client(client["name"]))
#         else:
#             clients.append(boto3.client(client["name"], region_name="us-east-1"))
#
#
# azure_clients = [
#     {
#         "pkg": "azure-mgmt-network",
#         "module": "azure.mgmt.network",
#         "class": "NetworkManagementClient",
#         "name": "NetworkManagementClient",
#         "integration_type": "azure"
#     }
# ]
from typing import List, Optional, Any

from autobotAI_integrations import BaseSchema, BaseCreds
from autobotAI_integrations.integrations import integration_service_factory


class PayloadTask(BaseSchema):
    creds: BaseCreds
    auth_method: str
    executable: str
    params: Optional[Any] = None
    context: None

class Payload(BaseSchema):
    job_id: str
    job_type: str
    tasks: List[PayloadTask]


def generate_aws_payload():
    integration = {
    }
    aws_service = integration_service_factory.get_service("aws", {}, integration)
    print(aws_service)

# generate_aws_payload()


# def integration_details():
#     return integration_service_factory.get_service_details()
# import json
# print(json.dumps(integration_details()))


def get_steampipe_meta():
    integration_service = integration_service_factory.get_service_cls("gitlab")
    resource_types = []
    for rtype in integration_service.get_steampipe_tables():
        resource_types.append({"name": rtype["name"], "is_regional": False})
    return resource_types

print(get_steampipe_meta())
