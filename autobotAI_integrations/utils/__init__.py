import asyncio
from datetime import datetime
import importlib.machinery
import importlib.util
import traceback
import uuid
from pathlib import Path
import json


def fromisoformat(strdate):
    try:
        return datetime.strptime(strdate, "%Y-%m-%dT%H:%M:%S.%f")
    except:
        return datetime.strptime(strdate, "%Y-%m-%dT%H:%M:%S")


def load_mod_from_string(code_string):
    try:
        Path("/tmp/mods/").mkdir(parents=True, exist_ok=True)
        file_path = '/tmp/mods/' + str(uuid.uuid4()) + '.py'
        f = open(file_path, "w")
        f.write(code_string)
        f.close()
        loader = importlib.machinery.SourceFileLoader('fetcher', file_path)
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

# TODO: Added to reduce duplicate code, Will make it dynamic in near future
aws_common_regions = [
    {
        "label": "US East (N. Virginia)",
        "value": "us-east-1"
    },
    {
        "label": "Asia Pacific (Mumbai)",
        "value": "ap-south-1"
    },
    {
        "label": "US West (N. California)",
        "value": "us-west-1"
    },
    {
        "label": "US East (Ohio)",
        "value": "us-east-2"
    },
    {
        "label": "US West (Oregon)",
        "value": "us-west-2"
    },
    {
        "label": "Africa (Cape Town)",
        "value": "af-south-1"
    },
    {
        "label": "Asia Pacific (Hong Kong)",
        "value": "ap-east-1"
    },
    {
        "label": "Asia Pacific (Jakarta)",
        "value": "ap-southeast-3"
    },
    {
        "label": "Asia Pacific (Osaka)",
        "value": "ap-northeast-3"
    },
    {
        "label": "Asia Pacific (Seoul)",
        "value": "ap-northeast-2"
    },
    {
        "label": "Asia Pacific (Singapore)",
        "value": "ap-southeast-1"
    },
    {
        "label": "Asia Pacific (Sydney)",
        "value": "ap-southeast-2"
    },
    {
        "label": "Asia Pacific (Tokyo)",
        "value": "ap-northeast-1"
    },
    {
        "label": "Canada (Central)",
        "value": "ca-central-1"
    },
    {
        "label": "Europe (Frankfurt)",
        "value": "eu-central-1"
    },
    {
        "label": "Europe (Ireland)",
        "value": "eu-west-1"
    },
    {
        "label": "Europe (London)",
        "value": "eu-west-2"
    },
    {
        "label": "Europe (Milan)",
        "value": "eu-south-1"
    },
    {
        "label": "Europe (Paris)",
        "value": "eu-west-3"
    },
    {
        "label": "Europe (Spain)",
        "value": "eu-south-2"
    },
    {
        "label": "Europe (Stockholm)",
        "value": "eu-north-1"
    },
    {
        "label": "Europe (Zurich)",
        "value": "eu-central-2"
    },
    {
        "label": "Middle East (Bahrain)",
        "value": "me-south-1"
    },
    {
        "label": "Middle East (UAE)",
        "value": "me-central-1"
    },
    {
        "label": "South America (São Paulo)",
        "value": "sa-east-1"
    },
]