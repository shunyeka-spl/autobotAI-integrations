# Use right credentials
# to run the aws payload in realtime
# create function which runs the payload tasks
from aws_payload import generate_aws_payload
import os
from dotenv import load_dotenv
import subprocess

load_dotenv()

access_key = os.getenv("access_key")
secret_key = os.getenv("secret_key")
aws_json = {
    "userId": "amit@shunyeka.com*",
    "accountId": "175c0fa813244bc5a1aa6264e7ba20cc",
    "integrationState": "INACTIVE",
    "cspName": "aws*",
    "access_key": access_key,
    "secret_key": secret_key,
    "session_token": "",
    "alias": "test-aws-integrationsv2",
    "connection_type": "DIRECT",
    "groups": ["aws", "shunyeka", "integrations-v2"],
    "agent_ids": [],
    "accessToken": "",
    "createdAt": "2024-02-26T13:38:59.978056",
    "updatedAt": "2024-02-26T13:38:59.978056",
    "indexFailures": 0,
    "isUnauthorized": False,
    "lastUsed": None,
    "resource_type": "integration",
    "activeRegions": [],
}


def run_payload(aws_json):
    payload = generate_aws_payload(aws_json)
    for task in payload.tasks:
        query = task.executable
        creds = task.creds
        envs = creds.envs
        print(creds, envs)
        with open("steampipe_output.json", "w") as jsonfile:
            process = subprocess.Popen(["steampipe", "query", query, "--output", "json"], stdout=jsonfile)
            process.communicate()

run_payload(aws_json)
# Main Task: Create a function in BaseService to execute steampipe task
# def execute_steampipe_task(payload: Payload) -> None:
#     pass
