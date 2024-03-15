import os
import subprocess
import sys
from enum import Enum
from typing import Optional, Dict, Any, List, Callable

import requests
from pydantic import BaseModel
from autobotAI_integrations.integration_schema import IntegrationSchema
from autobotAI_integrations.utils import list_of_unique_elements


class AuthMethods(Enum):
    STEAMPIPE = 'steampipe'
    PYTHON_SDK = 'python_sdk'
    REST_API = 'rest_api'
    CLI = 'cli'


class SteampipeCreds(BaseModel):
    envs: dict
    connection_name: str
    plugin_name: str
    conf_path: Optional[str] = str
    tables: list = []


class RestAPICreds(BaseModel):
    api_url: str
    token: str
    headers: dict


class SDKCreds(BaseModel):
    clients: Dict[str, Any]
    library_names: List[str]
    package_names: List[str]
    creds: Optional[dict] = None
    envs: Optional[dict] = None


class CLICreds(BaseModel):
    envs: dict
    installer_check: str
    install_command: str


class BaseSchema(IntegrationSchema):
    name: str
    description: str
    logo: str
    authentication_methods: List[AuthMethods] = []
    creds: Optional[Any] = None


class BaseService:

    def __init__(self, ctx: dict, integration: dict):
        """
        Integration should have all the data regarding the integration
        """
        self.integration = integration
        self.ctx = ctx

    def get_forms(self):
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

    @staticmethod
    def get_schema() -> BaseSchema:
        raise NotImplementedError()

    @staticmethod
    def get_all_python_sdk_clients():
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

    @staticmethod
    def python_sdk_processor(code_exec: Callable[[Dict[str, Any], List[Dict[str, Any]]], List[Dict[str, Any]]],
                             resources: list, clients: list, creds: SDKCreds):
        # Setup Environment Variables
        for key, value in creds.envs.items():
            os.environ[key] = value

        # Install Packages
        for package_name in creds.package_names:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package_name])

        # Import Packages
        for library_name in creds.library_names:
            exec(f"import {library_name}")

        # Create Clients
        clients_to_run = {}
        for client in clients:
            clients_to_run[client] = eval(creds.clients[client]["code"])

        # Run the code and return Results
        results = code_exec(clients_to_run, resources)
        return results
