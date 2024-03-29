# read the argument task_id
import json
import argparse

from autobotAI_integrations import IntegrationSchema
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.models import ConnectionInterfaces
from autobotAI_integrations.payload_schema import PayloadTask

parser = argparse.ArgumentParser(description="Task Executer File For Given Task Id")
parser.add_argument(
    "--task_id", "-tid", required=True, help="Provide unique taskId as an argument"
)

args = parser.parse_args()

task_id = str(args.task_id)


with open(f"temp/{task_id}.json") as task_file:
    task = PayloadTask.model_validate_json(task_file.read(), strict=False)
    
    integration = IntegrationSchema.model_validate(task.context.integration)
    service = integration_service_factory.get_service(None, integration)
    
    result = None
    if task.connection_interface == ConnectionInterfaces.PYTHON_SDK:
        result = service.python_sdk_processor(task)
    elif task.connection_interface == ConnectionInterfaces.STEAMPIPE:
        result = service.execute_steampipe_task(task)
    else:
        print("Method is not implemented yet.")

    with open(f"temp/{task_id}-output.json", "w") as output:
        output.write(json.dumps(result, default=str))
