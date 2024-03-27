import json
import subprocess
import os
from autobotAI_integrations import IntegrationSchema
from autobotAI_integrations.integrations import integration_service_factory

from autobotAI_integrations.payload_schema import Payload

temp_dir = "temp"

os.makedirs(temp_dir, exist_ok=True)

# payload url
# payload json is on s3 bucket
# presigned download and upload url for 1 hour validation
# output_url


def handle(payload: Payload):
    for task in payload.tasks:
        with open(f"temp/{task.task_id}.json", "w") as task_file:
            task_file.write(json.dumps(task, default=str))

        subprocess.run(
            ["python", "task_handler.py", "--task_id", task.task_id],
        )

        with open(f"temp/{task.task_id}-output.json") as ouput_file:
            print(ouput_file.read())


from run_aws_steampipe import generate_aws_python_payload
python_payload = generate_aws_python_payload()
handle(payload=python_payload)
