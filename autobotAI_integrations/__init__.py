import os
import subprocess
import sys
import inspect
import platform
import json
from copy import deepcopy
from enum import Enum
from os import path
from typing import Optional, Dict, Any, List, Callable

import requests
import yaml
from pydantic import BaseModel
from autobotAI_integrations.integration_schema import IntegrationSchema
from autobotAI_integrations.models import *
from autobotAI_integrations.payload_schema import PayloadTask
from autobotAI_integrations.utils import list_of_unique_elements, load_mod_from_string, run_mod_func


class BaseService:

    def __init__(self, ctx: dict, integration: BaseSchema):
        """
        Integration should have all the data regarding the integration
        """
        self.integration = integration
        self.ctx = ctx

    @staticmethod
    def supported_connection_types():
        return [ConnectionTypes.REST_API]

    def get_forms(self):
        """
        Returns a list of Forms Represented in JSON format for UI
        - success: bool
        - error: str
        """
        raise NotImplementedError()

    def _test_integration(self, integration: dict) -> dict:
        """
        Returns a dictionary with the following keys:
        - success: bool
        - error: str
        """
        raise NotImplementedError()

    def is_active(self, integration):
        result = self._test_integration(integration)
        if not result["success"]:
            self.on_test_integration_failure(integration)
        return result

    def on_test_integration_failure(self, integration):
        pass

    @classmethod
    def get_integration_type(cls):
        system_os = platform.system()
        if system_os == "Windows":
            sep = "\\"
        else:
            sep = "/"
        integration_type = os.path.dirname(inspect.getfile(cls)).split(sep)[-1]
        return integration_type

    @classmethod
    def get_steampipe_tables(cls) -> List[dict]:
        base_path = os.path.dirname(inspect.getfile(cls))
        integration_type = cls.get_integration_type()
        with open(path.join(base_path, ".", 'inventory.json')) as f:
            clients_data = f.read()
            data = json.loads(clients_data)
        return data[integration_type]

    @classmethod
    def get_all_python_sdk_clients(cls):
        base_path = os.path.dirname(inspect.getfile(cls))
        with open(path.join(base_path, ".", 'python_sdk_clients.yml')) as f:
            return yaml.safe_load(f)

    @staticmethod
    def get_schema() -> BaseSchema:
        raise NotImplementedError()

    @classmethod
    def get_details(cls):
        return {
            "automation_code": "",
            "fetcher_code": "",
            "fetcher_supported": ["code", "no_code"],
            "listener_supported": False,
            "automation_supported": ["communication", 'mutation'],
            "clients": list_of_unique_elements(cls.get_all_python_sdk_clients()),
            "supported_executor": "ecs",
            "compliance_supported": False
        }

    @staticmethod
    def generic_rest_api_call(api_creds: RestAPICreds, method: str, endpoint: str, data=None):
        url = api_creds.api_url + endpoint
        headers = api_creds.headers.copy()
        headers["Authorization"] = f"Bearer {api_creds.token}"

        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError("Invalid HTTP method specified.")

            response.raise_for_status()  # Raise exception for non-2xx responses

            return response.json()

        except requests.RequestException as e:
            print(f"Error occurred during {method} request to {url}: {e}")
            return None

    def get_integration_specific_details(self):
        return {
            "regions": self.integration.activeRegions
        }

    def get_credentials(self):
        raise NotImplementedError("To be implemented")

    def generate_steampipe_creds(self) -> SteampipeCreds:
        raise NotImplementedError()

    def generate_rest_api_creds(self) -> RestAPICreds:
        raise NotImplementedError()

    def generate_python_sdk_creds(self) -> SDKCreds:
        raise NotImplementedError()

    def generate_cli_creds(self) -> CLICreds:
        raise NotImplementedError()

    """
    Callable in python_sdk_processor means this ->

    @staticmethod
    def exec(clients: Dict[str, Any], resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pass

    """

    def build_python_exec_combinations_hook(self, payload_task: PayloadTask, client_definitions: List[SDKClient]) -> list:
        raise NotImplementedError()

    def build_python_exec_combinations(self, payload_task: PayloadTask):
        client_definitions = self.find_client_definitions(payload_task.clients)
        for client in client_definitions:
            if client.pip_package_names:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', " ".join(client.pip_package_names)])
            if client.import_library_names:
                for library in client.import_library_names:
                    try:
                        __import__(library)
                    except ImportError:
                        print(f"Failed to import library: {library}")

        return self.build_python_exec_combinations_hook(payload_task, client_definitions)

    def find_client_definitions(self, client_name_list) -> List[SDKClient]:
        all_clients = self.get_all_python_sdk_clients()
        client_details = []
        for client in client_name_list:
            client_def = next(item for item in all_clients if item["name"] == client)
            client_details.append(SDKClient(**client_def))
        return client_details

    def python_sdk_processor(self, payload_task: PayloadTask):

        if payload_task.creds and payload_task.creds.envs:
            for key, value in payload_task.creds.envs.items():
                os.environ[key] = value

        results = []
        combinations = self.build_python_exec_combinations(payload_task)
        for combo in combinations:
            results.extend(self.execute_python_sdk_code(combo, payload_task))

        return results

    def execute_python_sdk_code(self, combination, payload_task: PayloadTask):
        mod = load_mod_from_string(payload_task.executable)
        context = {**payload_task.context.model_dump(), **combination}
        result = run_mod_func(mod.execute, context=context)
        resources = []
        if result:
            for r in result:
                resources.append({**r, **combination["metadata"]})
        return resources

    def execute_steampipe_task(task):
        pass
