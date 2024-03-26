from enum import Enum
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, ConfigDict, Extra

from autobotAI_integrations import IntegrationSchema


class ConnectionInterfaces(Enum):
    # TODO: Change Name to connection interface
    STEAMPIPE = 'steampipe'
    PYTHON_SDK = 'python_sdk'
    REST_API = 'rest_api'
    CLI = 'cli'


class BaseCreds(BaseModel):
    pass


class SteampipeCreds(BaseCreds):
    envs: dict
    connection_name: str
    plugin_name: str
    conf_path: Optional[str] = str
    config: Optional[str] = None
    tables: list = []


class RestAPICreds(BaseCreds):
    api_url: str
    token: str
    headers: dict


class Client(BaseModel):
    name: str


class SDKClient(Client):
    model_config = ConfigDict(extra=Extra.allow)
    pip_package_names: Optional[List[str]] = None
    import_library_names: Optional[List[str]] = None


class SDKCreds(BaseCreds):
    creds: Optional[dict] = None
    envs: Optional[dict] = None


class CLICreds(BaseCreds):
    envs: dict
    installer_check: str
    install_command: str


# Setting default to None
class BaseSchema(IntegrationSchema):
    name: str = None
    description: str = None
    logo: str = None