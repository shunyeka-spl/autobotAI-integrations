import json

from autobotAI_integrations import IntegrationSchema
from autobotAI_integrations.integrations import integration_service_factory
from aws_payload import Payload, generate_aws_python_sdk_payload

payload = generate_aws_python_sdk_payload()

for task in payload.tasks:
    integration = IntegrationSchema.model_validate(task.context.integration)
    service = integration_service_factory.get_service(None, integration)
    print(service.python_sdk_processor(task))