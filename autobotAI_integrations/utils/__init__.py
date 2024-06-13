import asyncio
from datetime import datetime
import importlib.machinery
import importlib.util
import traceback
import uuid
from pathlib import Path
import json

from autobotAI_integrations.payload_schema import PayloadTask


def fromisoformat(strdate):
    try:
        return datetime.strptime(strdate, "%Y-%m-%dT%H:%M:%S.%f")
    except:
        return datetime.strptime(strdate, "%Y-%m-%dT%H:%M:%S")


def load_mod_from_string(code_string):
    try:
        Path("/tmp/mods/").mkdir(parents=True, exist_ok=True)
        file_path = "/tmp/mods/" + str(uuid.uuid4()) + ".py"
        f = open(file_path, "w")
        f.write(code_string)
        f.close()
        loader = importlib.machinery.SourceFileLoader("fetcher", file_path)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        return mod
    except:
        traceback.print_exc()
        raise Exception("Unable to load function.")


def run_mod_func(fn, **kwargs):
    if not asyncio.iscoroutinefunction(fn):
        return fn(**kwargs)
    else:
        return asyncio.run(fn(**kwargs))


def list_of_unique_elements(list_to_verify: list) -> list:
    my_set = set()
    unique_list = list()

    for item in list_to_verify:
        my_set.add(json.dumps(item, sort_keys=True))

    for string_json in my_set:
        unique_list.append(json.loads(string_json))

    return unique_list

# Inventory Utils

def change_keys(obj, convert=lambda key: key.replace('.', '_').replace('$', '-')):
    """
    Recursively goes through the dictionary obj and replaces keys with the convert function.
    """
    if isinstance(obj, (str, int, float)):
        return obj
    if isinstance(obj, dict):
        new = obj.__class__()
        for k, v in obj.items():
            new[convert(k)] = change_keys(v, convert)
    elif isinstance(obj, (list, set, tuple)):
        new = obj.__class__(change_keys(v, convert) for v in obj)
    else:
        return obj
    return new

def transform_inventory_resources(stdout: dict, payload_task: PayloadTask):
    results = []
    stdout = stdout["rows"]
    for row in stdout:
        row["id"] = row.get("id", (row.get("akas") or [str(uuid.uuid4().hex)])[0])
        row["name"] = row.get("name", (row.get("akas") or [str(uuid.uuid4().hex)])[0])
        row["integration_id"] = payload_task.context.integration.accountId
        row["integration_type"] = payload_task.context.integration.cspName
        row["user_id"] = payload_task.context.execution_details.caller.user_id
        row["root_user_id"] = (
            payload_task.context.execution_details.caller.root_user_id
        )
        if payload_task.context.integration.agent_ids:
            row["agent_id"] = payload_task.context.integration.agent_ids
        results.append(change_keys(row))
    return results


# transform steampipe compliance data

def transform_steampipe_compliance_resources(data):
    result = []
    if not data:
        return result
    if isinstance(data, list):
        for subData in data:
            result.extend(transform_steampipe_compliance_resources(subData))
    elif isinstance(data, dict):
        subGroups = []
        if "resources" in data and "group_id" not in data:
            data = data["resources"]
        if "groups" in data:
            subGroups = data.pop("groups")
        result.append(data)
        for subgroup in subGroups:
            result.extend(transform_steampipe_compliance_resources(subgroup))
    else:
        raise Exception(f"data is of type {type(data)}")
    return result


def transform_steampipe_results(results, integration_type, integration_id=None):
    new_results = []

    for result in results:
        new_result = result.copy()

        if result.get("dimensions"):
            dimensions = {dim["key"]: dim["value"] for dim in result["dimensions"]}
            new_result.update(dimensions)
            del new_result["dimensions"]

        transformed_result = {
            "uid": new_result["resource"],
            "details": new_result["reason"],
            "criticality": new_result["status"],
        }
        if integration_type == "aws":
            transformed_result["account_uid"] = (
                new_result.get("account_id") if new_result.get("account_id") else None
            )
            transformed_result["region"] = (
                new_result.get("region") if new_result.get("region") else None
            )
        elif integration_type == "azure":
            transformed_result["account_uid"] = (
                new_result.get("subscription")
                if new_result.get("subscription")
                else None
            )
        elif integration_type == "gcp":
            transformed_result["account_uid"] = (
                new_result.get("project") if new_result.get("project") else None
            )
        elif integration_type == "kubernetes":
            transformed_result["account_uid"] = (
                integration_id if integration_id else None,
            )
            transformed_result["namespace"] = (
                new_result.get("namespace") if new_result.get("namespace") else None
            )
        else:
            raise ValueError(
                "Invalid integration_type. Supported types: 'aws', 'azure', 'gcp', 'kubernetes'."
            )

        new_results.append(transformed_result)

    return new_results


def oscf_based_steampipe_json(data, integration_type, integration_id, query):
    result = []
    for compData in data:
        if compData["controls"]:
            for control in compData["controls"]:
                temp = {
                    "uid": compData["group_id"] + "_" + control["control_id"],
                    "activity_source": "steampipe",
                    "activity_id": compData["group_id"],
                    "activity_name": compData["title"],
                    "category_name": (
                        [compData["tags"]["category"]]
                        if compData.get("tags") and compData["tags"].get("category")
                        else None
                    ),
                    "compliances": {
                        "service": (
                            compData["tags"]["service"]
                            if compData.get("tags") and compData["tags"].get("service")
                            else None
                        ),
                        "type": (
                            compData["tags"]["type"]
                            if compData.get("tags") and compData["tags"].get("type")
                            else None
                        ),
                        "benchmark": query,
                    },
                    "end_time": datetime.now(),
                    "findings": {
                        "id": control["control_id"],
                        "title": control["title"],
                        "description": control["description"],
                        "severity": (
                            control["severity"] if control.get("severity") else None
                        ),
                        "service": (
                            control["tags"]["service"]
                            if control.get("tags") and control["tags"].get("service")
                            else None
                        ),
                        "summary": (
                            control["summary"] if control.get("summary") else None
                        ),
                    },
                    "run_error": (
                        control["run_error"] if control.get("run_error") else None
                    ),
                }
                temp["resources"] = (
                    transform_steampipe_results(
                        control["results"], integration_type, integration_id
                    )
                    if control.get("results")
                    else None
                )
                temp["integration_id"] = integration_id
                temp["integration_type"] = (integration_type,)
                temp["detected_on"] = datetime.now()
                result.append(temp)
        else:
            result.append(
                {
                    "uid": compData["group_id"],
                    "activity_source": "steampipe",
                    "activity_id": compData["group_id"],
                    "activity_name": compData["title"],
                    "category_name": (
                        compData["tags"]["category"] if compData.get("tags") else None
                    ),
                    "compliances": {
                        "service": (
                            compData["tags"]["service"]
                            if compData.get("tags") and compData["tags"].get("service")
                            else None
                        ),
                        "type": (
                            compData["tags"]["type"]
                            if compData.get("tags") and compData["tags"].get("type")
                            else None
                        ),
                        "benchmark": query,
                    },
                    "end_time": datetime.now(),
                    "integration_type": integration_type,
                    "integration_id": integration_id,
                    "detected_on": datetime.now(),
                }
            )
    return result
