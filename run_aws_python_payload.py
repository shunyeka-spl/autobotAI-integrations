import json

from autobotAI_integrations import IntegrationSchema
from autobotAI_integrations.integrations import integration_service_factory
from aws_payload import Payload, generate_aws_python_sdk_payload

payload = generate_aws_python_sdk_payload()

for task in payload.tasks:
    # Run with subprocess
    # Save the task details in a temp file with the taskId as the unique id.
    # Run the python script, let's call task executor pass the task id as an argument.
    # Save the output in the file named with the task id
    # Wait for the process to complete.
    # Read the file.
    integration = IntegrationSchema.model_validate(task.context.integration)
    service = integration_service_factory.get_service(None, integration)
    print(service.python_sdk_processor(task))