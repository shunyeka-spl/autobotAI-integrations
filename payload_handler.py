import json
import subprocess

from autobotAI_integrations.payload_schema import Payload


def handle(payload: Payload):
    for task in payload.tasks:
        # Run with subprocess
        # Save the task details in a temp file with the taskId as the unique id.
        # Run the python script, let's call task executor pass the task id as an argument.
        # Save the output in the file named with the task id
        # Wait for the process to complete.
        # Read the file.
        #print(service.python_sdk_processor(task))
        with open(f"/tmp/{task.task_id}.json") as task_file:
            task_file.write(json.dumps(task, default=str))
        task_executor_result = subprocess.run(["python task_handler.py", "--task_id", task.task_id],
                                         cwd=".", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
