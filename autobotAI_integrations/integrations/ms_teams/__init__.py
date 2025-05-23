from typing import List, Optional, Type, Union

from autobotAI_integrations.models import BaseSchema, CLICreds, ConnectionInterfaces, IntegrationCategory, SDKClient, SDKCreds
import re

from autobotAI_integrations import BaseService, list_of_unique_elements, PayloadTask
import importlib


class MsTeamsIntegration(BaseSchema):
    webhook: str
    accountId: Optional[str] = None

    name: Optional[str] = "Microsoft Teams"
    category: Optional[str] = IntegrationCategory.NOTIFICATIONS_AND_COMMUNICATIONS.value
    description: Optional[str] = (
        "A collaboration platform from Microsoft, enabling communication, file sharing, and video conferencing within teams."
    )


class MsTeamsService(BaseService):
    def __init__(self, ctx: dict, integration: Union[MsTeamsIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, MsTeamsIntegration):
            integration = MsTeamsIntegration(**integration)
        super().__init__(ctx, integration)

    def _test_integration(self) -> dict:
        import pymsteams
        pattern = re.compile(
            "https:\\/\\/[\\w\\-\\.]+\\/webhookb2\\/[\\w\\d\\-\\@]+\\/IncomingWebhook\\/[\\w\\d\\-\\@]+\\/[\\w\\d\\-\\@]+")
        result = pattern.match(self.integration.webhook)
        if result is None:
            return {'success': False, "error": "Webhook is not valid MS Teams webhook URL"}
        try:
            client = pymsteams.connectorcard(self.integration.webhook)
            client.send()
            return {'success': True}
        except Exception as e:
            if str(e).startswith("Summary or Text is required"):
                return {"success": True}
        return {"success": False, "error": "Unable to send message to Webhook"}

    @staticmethod
    def get_forms():
        return {
            "label": "MS Teams",
            "type": "form",
            "children": [
                {
                    "name": "webhook",
                    "type": "text/url",
                    "label": "Webhook URL",
                    "placeholder": "Enter your Webhook URL",
                    "required": True,
                }
            ],
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return MsTeamsIntegration

    @classmethod
    def get_details(cls):
        return {
            "clients": list_of_unique_elements(cls.get_all_python_sdk_clients()),
            "supported_executor": "lambda",
            "approval_automation_details": {
                "title": "Send Approval Request to Teams",
                "name": "Send Approval Request to Teams",
                "clients": ["msteams_client"],
                "type": "communication",
                "approval_required": False,
                "batch_supported": False,
                "required_payload": [
                    {
                        "type": "string",
                        "name": "automation_title",
                        "values": "sample automation",
                        "description": "Title of the Automation being executed",
                    },
                    {
                        "type": "string",
                        "name": "admin_email",
                        "values": "admin@email.com",
                        "description": "Administrator's email",
                    },
                    {
                        "type": "list",
                        "name": "links",
                        "values": [{"name": "button1", "link": "some.link"}],
                        "description": "Links to show in the approval",
                    },
                    {
                        "type": "list",
                        "name": "approvers",
                        "values": ["email1@yopmail.com"],
                        "description": "List of approver emails",
                    },
                    {
                        "type": "json",
                        "name": "bot",
                        "values": {},
                        "description": "Bot details",
                    },
                ],
            },
            "supported_interfaces": cls.supported_connection_interfaces(),
            "python_code_sample": cls.get_code_sample(),
        }

    def build_python_exec_combinations_hook(self, payload_task: PayloadTask, client_definitions: List[SDKClient]) -> list:
        pymsteams = importlib.import_module(client_definitions[0].import_library_names[0], package=None)
        return [
            {
                "clients": {
                    "pymsteams": pymsteams.connectorcard(self.integration.webhook)
                },
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context
            }
        ]

    def generate_python_sdk_creds(self, requested_clients=None) -> SDKCreds:
        creds = self._temp_credentials()
        return SDKCreds(envs=creds)

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.PYTHON_SDK,
        ]

    def generate_cli_creds(self) -> CLICreds:
        raise NotImplementedError()

    def _temp_credentials(self):
        return {
            "WEBHOOK_URL": self.integration.webhook
        }
