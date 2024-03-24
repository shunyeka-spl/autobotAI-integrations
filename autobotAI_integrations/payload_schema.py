from typing import List, Optional, Any

from pydantic import BaseModel, SerializeAsAny

from autobotAI_integrations import IntegrationSchema
from autobotAI_integrations.models import BaseCreds


class PayloadTaskContext(BaseModel):
    integration: SerializeAsAny[IntegrationSchema]


class PayloadTask(BaseModel):
    taskId: Optional[str]
    creds: SerializeAsAny[BaseCreds]
    connection_type: str
    executable: str
    clients: Optional[List[str]] = None
    params: Optional[Any] = None
    node_details: Optional[Any] = None
    context: PayloadTaskContext
    resources: Optional[List] = None


class Payload(BaseModel):
    job_id: str
    tasks: List[PayloadTask]