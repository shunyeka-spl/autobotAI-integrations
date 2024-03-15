import traceback

from botocore.exceptions import ClientError

from autobotAI_integrations import BaseSchema, BaseService
from autobotAI_integrations.utils.boto3_helper import Boto3Helper


class Forms:
    pass


class AWSIntegration(BaseSchema):
    access_key: str
    secret_key: str
    session_token: str
    account_id: str

    def __init__(self, **kwargs):
        kwargs["accountId"] = self.account_id
        super().__init__(**kwargs)


class AWSService(BaseService):

    def _test_integration(self, integration: dict) -> dict:
        try:
            boto3_helper = Boto3Helper(self.ctx, integration=integration)
            boto3_helper.get_client("ec2")
            return {'success': True}
        except ClientError as e:
            print(traceback.format_exc())
            return {'success': False, 'error': traceback.format_exc()}

    def get_forms(self):
        return {
            "access_secret_form": {
                "fields": [
                    {
                        "name": "access_key",
                        "type": "text",
                        "label": "Access Key",
                        "placeholder": "Enter your AWS access key",
                        "required": True
                    },
                    {
                        "name": "secret_key",
                        "type": "password",
                        "label": "Secret Key",
                        "placeholder": "Enter your AWS secret key",
                        "required": True
                    }
                ],
                "submit_label": "Submit"
            },
            "iam_role_form": {
                "fields": [
                    {
                        "name": "roleArn",
                        "type": "text",
                        "label": "IAM Role ARN",
                        "placeholder": "Enter IAM role ARN",
                        "required": True
                    }
                ],
                "submit_label": "Submit"
            }
        }
