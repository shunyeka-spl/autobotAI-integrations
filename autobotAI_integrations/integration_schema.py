from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ConnectionTypes(Enum):
    DIRECT = "DIRECT"
    AGENT = "AGENT"


class IntegrationStates(Enum):
    ACTIVE = "ACTIVE"  # Accessible
    INACTIVE = "INACTIVE"  # In-Accessible
    AGENT_UPDATE_REQUIRED = "AGENT_UPDATE_REQUIRED"


class IntegrationSchema(BaseModel):
    userId: str  # The user creating the Integration
    accountId: str  # Unique ID for the integration, For AWS it is Account ID, Azure it is subscription id and GCP it is project id, if no unique id available we generate an unique id.
    integrationState: IntegrationStates = IntegrationStates.INACTIVE.value
    cspName: str   # AWS, AZURE, GCP, GITLAB etc.
    alias: str  # Name given by User
    connection_type: ConnectionTypes = ConnectionTypes.DIRECT.value  # Direct means we get the credentials, Agent means we don't have the creds, our agent is installed in the customer's environment.
    groups: list = []  # Tags/groups
    agent_ids: list = []  # If agent based, then agent ids are populated
    accessToken: str = ""  # Part of creds
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    indexFailures: int = 0
    isUnauthorized: bool = False
    lastUsed: Optional[str] = None
    resource_type: str = 'integration'
    activeRegions: Optional[list] = None

    @classmethod
    def encryption_exclusions(self):
        return ["agent_ids"]
