from typing import List, Optional, Any, Union

from pydantic import BaseModel

from autobotAI_integrations import BaseCreds, SteampipeCreds, SDKCreds, \
    RestAPICreds, CLICreds


class PayloadTask(BaseModel):
    taskId: Optional[str]
    creds: Union[
        BaseCreds,
        SteampipeCreds,
        RestAPICreds,
        CLICreds,
        SDKCreds
    ]
    connection_type: str
    executable: str
    params: Optional[Any] = None
    context: Optional[dict] = None
    interation_specific_details: Optional[dict] = None


class Payload(BaseModel):
    job_id: str
    tasks: List[PayloadTask]