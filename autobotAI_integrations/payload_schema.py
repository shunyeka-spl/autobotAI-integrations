from typing import List, Optional, Any

from pydantic import BaseModel, SerializeAsAny

from autobotAI_integrations import IntegrationSchema
from autobotAI_integrations.models import BaseCreds


class Caller(BaseModel):
    user_id: str
    root_user_id: str


class ExecutionDetails(BaseModel):
    execution_id: str
    bot_id: str
    bot_name: str
    node_name: str
    caller: Caller


class PayloadTaskContext(BaseModel):
    integration: SerializeAsAny[IntegrationSchema]
    global_variables: dict  # Global Variables defined by User, this will be store in secret manager
    integration_variables: dict  # Secret manager variables stored for the specific Integration.
    integration_group_vars: dict  # Secret manager variables stored for the specific Integration Group.
    execute_details: ExecutionDetails
    node_steps: dict


class PayloadTask(BaseModel):
    task_id: Optional[str]
    creds: SerializeAsAny[BaseCreds]
    connection_interface: str
    executable: str
    clients: Optional[List[str]] = None
    params: Optional[Any] = None
    node_details: Optional[Any] = None
    context: PayloadTaskContext
    resources: Optional[List] = None


class Payload(BaseModel):
    job_id: str
    tasks: List[PayloadTask]
