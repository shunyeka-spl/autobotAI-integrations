import subprocess
import os
import json
import tempfile
from autobotAI_integrations.payload_schema import Payload

temp_dir = "temp"

os.makedirs(temp_dir, exist_ok=True)

# custom comments
# [Working on it]
# python liberry to create temp file [Named temp file]
# check all four integrations is working
# check with differnt set of credentials of aws either if it is isolated


def handle(payload: Payload):
    for task in payload.tasks:
        with open(f"temp/{task.task_id}.json", "w") as task_file:
            task_file.write(task.model_dump_json())

        subprocess.run(
            ["python", "task_handler.py", "--task_id", task.task_id],
            check=True,
            capture_output=True,
            text=True
        )

        with open(f"temp/{task.task_id}-output.json") as ouput_file:
            print(json.loads(ouput_file.read()))

# run_env = os.environ.get('RUN_ENV', app_env)
# run_env = os.environ.get('RUN_ENV', "non-local")
# If run_env = app_env
# run it here
# else do not execute defined source

from run_aws_steampipe import generate_aws_python_payload, generate_aws_steampipe_payload
python_payload = generate_aws_python_payload()
handle(payload=python_payload)
