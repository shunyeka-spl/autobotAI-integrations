# read the argument task_id
import json

from autobotAI_integrations import PayloadTask, ConnectionInterfaces, IntegrationSchema
from autobotAI_integrations.integrations import integration_service_factory

task_id = "xyz"
with open(f"/tmp/{task_id}.json") as task_file:
    task_details = task_file.read()
    task = PayloadTask.model_validate(task_details)
    # condition to check what is the connection interface.
    result = None
    if task.connection_interface == ConnectionInterfaces.PYTHON_SDK:
        integration = IntegrationSchema.model_validate(task.context.integration)
        service = integration_service_factory.get_service(None, integration)
        result = service.python_sdk_processor(task)
    elif task.connection_interface == ConnectionInterfaces.STEAMPIPE:
        pass

    with open(f"/tmp/{task_id}-output.json") as output:
        output.write(json.dumps(result, default=str))