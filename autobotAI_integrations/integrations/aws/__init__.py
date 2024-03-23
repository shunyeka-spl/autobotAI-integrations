import traceback
from typing import Type, List, Optional

from botocore.exceptions import ClientError

from autobotAI_integrations import BaseSchema, BaseService, list_of_unique_elements, SteampipeCreds, RestAPICreds, \
    SDKCreds, CLICreds, ConnectionTypes
from autobotAI_integrations.utils import boto3_helper
from autobotAI_integrations.utils.boto3_helper import Boto3Helper

import inspect
import platform
import os

class Forms:
    pass


class AWSIntegration(BaseSchema):
    # TODO: Add validation for role_arn and access keys
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    session_token: Optional[str] = None
    account_id: str = None
    role_arn: Optional[str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.account_id = kwargs["accountId"]


class AWSService(BaseService):

    def __init__(self, ctx: dict, integration: AWSIntegration):
        """
        Integration should have all the data regarding the integration
        """
        super().__init__(ctx, integration)


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

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return AWSIntegration


    @staticmethod
    def get_all_python_sdk_clients():
        return [
            {
                "name": "accessanalyzer",
                "is_regional": True
            },
            {
                "name": "account",
                "is_regional": False
            },
            {
                "name": "acm",
                "is_regional": True
            },
            {
                "name": "acm-pca",
                "is_regional": True
            },
            {
                "name": "alexaforbusiness",
                "is_regional": True
            },
            {
                "name": "amp",
                "is_regional": True
            },
            {
                "name": "amplify",
                "is_regional": True
            },
            {
                "name": "amplifybackend",
                "is_regional": True
            },
            {
                "name": "amplifyuibuilder",
                "is_regional": True
            },
            {
                "name": "apigateway",
                "is_regional": True
            },
            {
                "name": "apigatewaymanagementapi",
                "is_regional": False
            },
            {
                "name": "apigatewayv2",
                "is_regional": True
            },
            {
                "name": "appconfig",
                "is_regional": True
            },
            {
                "name": "appconfigdata",
                "is_regional": True
            },
            {
                "name": "appflow",
                "is_regional": True
            },
            {
                "name": "appintegrations",
                "is_regional": True
            },
            {
                "name": "application-autoscaling",
                "is_regional": True
            },
            {
                "name": "application-insights",
                "is_regional": True
            },
            {
                "name": "applicationcostprofiler",
                "is_regional": False
            },
            {
                "name": "appmesh",
                "is_regional": True
            },
            {
                "name": "apprunner",
                "is_regional": True
            },
            {
                "name": "appstream",
                "is_regional": True
            },
            {
                "name": "appsync",
                "is_regional": True
            },
            {
                "name": "athena",
                "is_regional": True
            },
            {
                "name": "auditmanager",
                "is_regional": True
            },
            {
                "name": "autoscaling",
                "is_regional": True
            },
            {
                "name": "autoscaling-plans",
                "is_regional": True
            },
            {
                "name": "backup",
                "is_regional": True
            },
            {
                "name": "backup-gateway",
                "is_regional": True
            },
            {
                "name": "backupstorage",
                "is_regional": True
            },
            {
                "name": "batch",
                "is_regional": True
            },
            {
                "name": "billingconductor",
                "is_regional": False
            },
            {
                "name": "braket",
                "is_regional": True
            },
            {
                "name": "budgets",
                "is_regional": False
            },
            {
                "name": "ce",
                "is_regional": False
            },
            {
                "name": "chime",
                "is_regional": False
            },
            {
                "name": "chime-sdk-identity",
                "is_regional": True
            },
            {
                "name": "chime-sdk-media-pipelines",
                "is_regional": True
            },
            {
                "name": "chime-sdk-meetings",
                "is_regional": True
            },
            {
                "name": "chime-sdk-messaging",
                "is_regional": True
            },
            {
                "name": "cloud9",
                "is_regional": True
            },
            {
                "name": "cloudcontrol",
                "is_regional": True
            },
            {
                "name": "clouddirectory",
                "is_regional": True
            },
            {
                "name": "cloudformation",
                "is_regional": True
            },
            {
                "name": "cloudfront",
                "is_regional": False
            },
            {
                "name": "cloudhsm",
                "is_regional": True
            },
            {
                "name": "cloudhsmv2",
                "is_regional": True
            },
            {
                "name": "cloudsearch",
                "is_regional": True
            },
            {
                "name": "cloudsearchdomain",
                "is_regional": False
            },
            {
                "name": "cloudtrail",
                "is_regional": True
            },
            {
                "name": "cloudwatch",
                "is_regional": True
            },
            {
                "name": "codeartifact",
                "is_regional": True
            },
            {
                "name": "codebuild",
                "is_regional": True
            },
            {
                "name": "codecommit",
                "is_regional": True
            },
            {
                "name": "codedeploy",
                "is_regional": True
            },
            {
                "name": "codeguru-reviewer",
                "is_regional": True
            },
            {
                "name": "codeguruprofiler",
                "is_regional": False
            },
            {
                "name": "codepipeline",
                "is_regional": True
            },
            {
                "name": "codestar",
                "is_regional": True
            },
            {
                "name": "codestar-connections",
                "is_regional": True
            },
            {
                "name": "codestar-notifications",
                "is_regional": False
            },
            {
                "name": "cognito-identity",
                "is_regional": True
            },
            {
                "name": "cognito-idp",
                "is_regional": True
            },
            {
                "name": "cognito-sync",
                "is_regional": True
            },
            {
                "name": "comprehend",
                "is_regional": True
            },
            {
                "name": "comprehendmedical",
                "is_regional": True
            },
            {
                "name": "compute-optimizer",
                "is_regional": True
            },
            {
                "name": "config",
                "is_regional": True
            },
            {
                "name": "connect",
                "is_regional": True
            },
            {
                "name": "connect-contact-lens",
                "is_regional": True
            },
            {
                "name": "connectcampaigns",
                "is_regional": True
            },
            {
                "name": "connectparticipant",
                "is_regional": False
            },
            {
                "name": "controltower",
                "is_regional": True
            },
            {
                "name": "cur",
                "is_regional": True
            },
            {
                "name": "customer-profiles",
                "is_regional": True
            },
            {
                "name": "databrew",
                "is_regional": True
            },
            {
                "name": "dataexchange",
                "is_regional": True
            },
            {
                "name": "datapipeline",
                "is_regional": True
            },
            {
                "name": "datasync",
                "is_regional": True
            },
            {
                "name": "dax",
                "is_regional": True
            },
            {
                "name": "detective",
                "is_regional": True
            },
            {
                "name": "devicefarm",
                "is_regional": True
            },
            {
                "name": "devops-guru",
                "is_regional": True
            },
            {
                "name": "directconnect",
                "is_regional": True
            },
            {
                "name": "discovery",
                "is_regional": True
            },
            {
                "name": "dlm",
                "is_regional": True
            },
            {
                "name": "dms",
                "is_regional": True
            },
            {
                "name": "docdb",
                "is_regional": True
            },
            {
                "name": "drs",
                "is_regional": True
            },
            {
                "name": "ds",
                "is_regional": True
            },
            {
                "name": "dynamodb",
                "is_regional": True
            },
            {
                "name": "dynamodbstreams",
                "is_regional": True
            },
            {
                "name": "ebs",
                "is_regional": True
            },
            {
                "name": "ec2",
                "is_regional": True
            },
            {
                "name": "ec2-instance-connect",
                "is_regional": False
            },
            {
                "name": "ecr",
                "is_regional": True
            },
            {
                "name": "ecr-public",
                "is_regional": False
            },
            {
                "name": "ecs",
                "is_regional": True
            },
            {
                "name": "efs",
                "is_regional": True
            },
            {
                "name": "eks",
                "is_regional": True
            },
            {
                "name": "elastic-inference",
                "is_regional": True
            },
            {
                "name": "elasticache",
                "is_regional": True
            },
            {
                "name": "elasticbeanstalk",
                "is_regional": True
            },
            {
                "name": "elastictranscoder",
                "is_regional": True
            },
            {
                "name": "elb",
                "is_regional": True
            },
            {
                "name": "elbv2",
                "is_regional": True
            },
            {
                "name": "emr",
                "is_regional": True
            },
            {
                "name": "emr-containers",
                "is_regional": True
            },
            {
                "name": "emr-serverless",
                "is_regional": True
            },
            {
                "name": "es",
                "is_regional": True
            },
            {
                "name": "events",
                "is_regional": True
            },
            {
                "name": "evidently",
                "is_regional": True
            },
            {
                "name": "finspace",
                "is_regional": True
            },
            {
                "name": "finspace-data",
                "is_regional": True
            },
            {
                "name": "firehose",
                "is_regional": True
            },
            {
                "name": "fis",
                "is_regional": False
            },
            {
                "name": "fms",
                "is_regional": True
            },
            {
                "name": "forecast",
                "is_regional": True
            },
            {
                "name": "forecastquery",
                "is_regional": True
            },
            {
                "name": "frauddetector",
                "is_regional": True
            },
            {
                "name": "fsx",
                "is_regional": True
            },
            {
                "name": "gamelift",
                "is_regional": True
            },
            {
                "name": "gamesparks",
                "is_regional": True
            },
            {
                "name": "glacier",
                "is_regional": True
            },
            {
                "name": "globalaccelerator",
                "is_regional": False
            },
            {
                "name": "glue",
                "is_regional": True
            },
            {
                "name": "grafana",
                "is_regional": True
            },
            {
                "name": "greengrass",
                "is_regional": True
            },
            {
                "name": "greengrassv2",
                "is_regional": True
            },
            {
                "name": "groundstation",
                "is_regional": True
            },
            {
                "name": "guardduty",
                "is_regional": True
            },
            {
                "name": "health",
                "is_regional": True
            },
            {
                "name": "healthlake",
                "is_regional": True
            },
            {
                "name": "honeycode",
                "is_regional": True
            },
            {
                "name": "iam",
                "is_regional": False
            },
            {
                "name": "identitystore",
                "is_regional": True
            },
            {
                "name": "imagebuilder",
                "is_regional": False
            },
            {
                "name": "importexport",
                "is_regional": False
            },
            {
                "name": "inspector",
                "is_regional": True
            },
            {
                "name": "inspector2",
                "is_regional": True
            },
            {
                "name": "iot",
                "is_regional": True
            },
            {
                "name": "iot-data",
                "is_regional": True
            },
            {
                "name": "iot-jobs-data",
                "is_regional": True
            },
            {
                "name": "iot1click-devices",
                "is_regional": False
            },
            {
                "name": "iot1click-projects",
                "is_regional": True
            },
            {
                "name": "iotanalytics",
                "is_regional": True
            },
            {
                "name": "iotdeviceadvisor",
                "is_regional": True
            },
            {
                "name": "iotevents",
                "is_regional": True
            },
            {
                "name": "iotevents-data",
                "is_regional": False
            },
            {
                "name": "iotfleethub",
                "is_regional": True
            },
            {
                "name": "iotsecuretunneling",
                "is_regional": True
            },
            {
                "name": "iotsitewise",
                "is_regional": True
            },
            {
                "name": "iotthingsgraph",
                "is_regional": True
            },
            {
                "name": "iottwinmaker",
                "is_regional": True
            },
            {
                "name": "iotwireless",
                "is_regional": True
            },
            {
                "name": "ivs",
                "is_regional": True
            },
            {
                "name": "ivschat",
                "is_regional": True
            },
            {
                "name": "kafka",
                "is_regional": True
            },
            {
                "name": "kafkaconnect",
                "is_regional": True
            },
            {
                "name": "kendra",
                "is_regional": True
            },
            {
                "name": "keyspaces",
                "is_regional": True
            },
            {
                "name": "kinesis",
                "is_regional": True
            },
            {
                "name": "kinesis-video-archived-media",
                "is_regional": True
            },
            {
                "name": "kinesis-video-media",
                "is_regional": True
            },
            {
                "name": "kinesis-video-signaling",
                "is_regional": True
            },
            {
                "name": "kinesisanalytics",
                "is_regional": True
            },
            {
                "name": "kinesisanalyticsv2",
                "is_regional": True
            },
            {
                "name": "kinesisvideo",
                "is_regional": True
            },
            {
                "name": "kms",
                "is_regional": True
            },
            {
                "name": "lakeformation",
                "is_regional": True
            },
            {
                "name": "lambda",
                "is_regional": True
            },
            {
                "name": "lex-models",
                "is_regional": True
            },
            {
                "name": "lex-runtime",
                "is_regional": True
            },
            {
                "name": "lexv2-models",
                "is_regional": True
            },
            {
                "name": "lexv2-runtime",
                "is_regional": True
            },
            {
                "name": "license-manager",
                "is_regional": True
            },
            {
                "name": "license-manager-user-subscriptions",
                "is_regional": True
            },
            {
                "name": "lightsail",
                "is_regional": True
            },
            {
                "name": "location",
                "is_regional": True
            },
            {
                "name": "logs",
                "is_regional": True
            },
            {
                "name": "lookoutequipment",
                "is_regional": True
            },
            {
                "name": "lookoutmetrics",
                "is_regional": True
            },
            {
                "name": "lookoutvision",
                "is_regional": True
            },
            {
                "name": "m2",
                "is_regional": True
            },
            {
                "name": "machinelearning",
                "is_regional": True
            },
            {
                "name": "macie",
                "is_regional": True
            },
            {
                "name": "macie2",
                "is_regional": True
            },
            {
                "name": "managedblockchain",
                "is_regional": True
            },
            {
                "name": "marketplace-catalog",
                "is_regional": True
            },
            {
                "name": "marketplace-entitlement",
                "is_regional": True
            },
            {
                "name": "marketplacecommerceanalytics",
                "is_regional": True
            },
            {
                "name": "mediaconnect",
                "is_regional": True
            },
            {
                "name": "mediaconvert",
                "is_regional": True
            },
            {
                "name": "medialive",
                "is_regional": True
            },
            {
                "name": "mediapackage",
                "is_regional": True
            },
            {
                "name": "mediapackage-vod",
                "is_regional": True
            },
            {
                "name": "mediastore",
                "is_regional": True
            },
            {
                "name": "mediastore-data",
                "is_regional": True
            },
            {
                "name": "mediatailor",
                "is_regional": True
            },
            {
                "name": "memorydb",
                "is_regional": True
            },
            {
                "name": "meteringmarketplace",
                "is_regional": True
            },
            {
                "name": "mgh",
                "is_regional": True
            },
            {
                "name": "mgn",
                "is_regional": True
            },
            {
                "name": "migration-hub-refactor-spaces",
                "is_regional": False
            },
            {
                "name": "migrationhub-config",
                "is_regional": False
            },
            {
                "name": "migrationhubstrategy",
                "is_regional": True
            },
            {
                "name": "mobile",
                "is_regional": False
            },
            {
                "name": "mq",
                "is_regional": True
            },
            {
                "name": "mturk",
                "is_regional": True
            },
            {
                "name": "mwaa",
                "is_regional": True
            },
            {
                "name": "neptune",
                "is_regional": True
            },
            {
                "name": "network-firewall",
                "is_regional": True
            },
            {
                "name": "networkmanager",
                "is_regional": False
            },
            {
                "name": "nimble",
                "is_regional": True
            },
            {
                "name": "opensearch",
                "is_regional": True
            },
            {
                "name": "opsworks",
                "is_regional": True
            },
            {
                "name": "opsworkscm",
                "is_regional": True
            },
            {
                "name": "organizations",
                "is_regional": False
            },
            {
                "name": "outposts",
                "is_regional": True
            },
            {
                "name": "panorama",
                "is_regional": False
            },
            {
                "name": "personalize",
                "is_regional": True
            },
            {
                "name": "personalize-events",
                "is_regional": False
            },
            {
                "name": "personalize-runtime",
                "is_regional": False
            },
            {
                "name": "pi",
                "is_regional": True
            },
            {
                "name": "pinpoint",
                "is_regional": True
            },
            {
                "name": "pinpoint-email",
                "is_regional": True
            },
            {
                "name": "pinpoint-sms-voice",
                "is_regional": False
            },
            {
                "name": "pinpoint-sms-voice-v2",
                "is_regional": True
            },
            {
                "name": "polly",
                "is_regional": True
            },
            {
                "name": "pricing",
                "is_regional": True
            },
            {
                "name": "privatenetworks",
                "is_regional": False
            },
            {
                "name": "proton",
                "is_regional": True
            },
            {
                "name": "qldb",
                "is_regional": True
            },
            {
                "name": "qldb-session",
                "is_regional": True
            },
            {
                "name": "quicksight",
                "is_regional": True
            },
            {
                "name": "ram",
                "is_regional": True
            },
            {
                "name": "rbin",
                "is_regional": True
            },
            {
                "name": "rds",
                "is_regional": True
            },
            {
                "name": "rds-data",
                "is_regional": True
            },
            {
                "name": "redshift",
                "is_regional": True
            },
            {
                "name": "redshift-data",
                "is_regional": False
            },
            {
                "name": "redshift-serverless",
                "is_regional": True
            },
            {
                "name": "rekognition",
                "is_regional": True
            },
            {
                "name": "resiliencehub",
                "is_regional": True
            },
            {
                "name": "resource-groups",
                "is_regional": True
            },
            {
                "name": "resourcegroupstaggingapi",
                "is_regional": True
            },
            {
                "name": "robomaker",
                "is_regional": True
            },
            {
                "name": "rolesanywhere",
                "is_regional": True
            },
            {
                "name": "route53",
                "is_regional": False
            },
            {
                "name": "route53-recovery-cluster",
                "is_regional": False
            },
            {
                "name": "route53-recovery-control-config",
                "is_regional": False
            },
            {
                "name": "route53-recovery-readiness",
                "is_regional": False
            },
            {
                "name": "route53domains",
                "is_regional": True
            },
            {
                "name": "route53resolver",
                "is_regional": True
            },
            {
                "name": "rum",
                "is_regional": True
            },
            {
                "name": "s3",
                "is_regional": True
            },
            {
                "name": "s3control",
                "is_regional": True
            },
            {
                "name": "s3outposts",
                "is_regional": True
            },
            {
                "name": "sagemaker",
                "is_regional": True
            },
            {
                "name": "sagemaker-a2i-runtime",
                "is_regional": False
            },
            {
                "name": "sagemaker-edge",
                "is_regional": True
            },
            {
                "name": "sagemaker-featurestore-runtime",
                "is_regional": False
            },
            {
                "name": "sagemaker-runtime",
                "is_regional": True
            },
            {
                "name": "savingsplans",
                "is_regional": False
            },
            {
                "name": "schemas",
                "is_regional": True
            },
            {
                "name": "sdb",
                "is_regional": True
            },
            {
                "name": "secretsmanager",
                "is_regional": True
            },
            {
                "name": "securityhub",
                "is_regional": True
            },
            {
                "name": "serverlessrepo",
                "is_regional": True
            },
            {
                "name": "service-quotas",
                "is_regional": True
            },
            {
                "name": "servicecatalog",
                "is_regional": True
            },
            {
                "name": "servicecatalog-appregistry",
                "is_regional": True
            },
            {
                "name": "servicediscovery",
                "is_regional": True
            },
            {
                "name": "ses",
                "is_regional": True
            },
            {
                "name": "sesv2",
                "is_regional": True
            },
            {
                "name": "shield",
                "is_regional": False
            },
            {
                "name": "signer",
                "is_regional": False
            },
            {
                "name": "sms",
                "is_regional": True
            },
            {
                "name": "sms-voice",
                "is_regional": False
            },
            {
                "name": "snow-device-management",
                "is_regional": False
            },
            {
                "name": "snowball",
                "is_regional": True
            },
            {
                "name": "sns",
                "is_regional": True
            },
            {
                "name": "sqs",
                "is_regional": True
            },
            {
                "name": "ssm",
                "is_regional": True
            },
            {
                "name": "ssm-contacts",
                "is_regional": False
            },
            {
                "name": "ssm-incidents",
                "is_regional": True
            },
            {
                "name": "sso",
                "is_regional": True
            },
            {
                "name": "sso-admin",
                "is_regional": True
            },
            {
                "name": "sso-oidc",
                "is_regional": True
            },
            {
                "name": "stepfunctions",
                "is_regional": True
            },
            {
                "name": "storagegateway",
                "is_regional": True
            },
            {
                "name": "sts",
                "is_regional": True
            },
            {
                "name": "support",
                "is_regional": False
            },
            {
                "name": "support-app",
                "is_regional": True
            },
            {
                "name": "swf",
                "is_regional": True
            },
            {
                "name": "synthetics",
                "is_regional": True
            },
            {
                "name": "textract",
                "is_regional": True
            },
            {
                "name": "timestream-query",
                "is_regional": False
            },
            {
                "name": "timestream-write",
                "is_regional": False
            },
            {
                "name": "transcribe",
                "is_regional": True
            },
            {
                "name": "transfer",
                "is_regional": True
            },
            {
                "name": "translate",
                "is_regional": True
            },
            {
                "name": "voice-id",
                "is_regional": True
            },
            {
                "name": "waf",
                "is_regional": False
            },
            {
                "name": "waf-regional",
                "is_regional": True
            },
            {
                "name": "wafv2",
                "is_regional": True
            },
            {
                "name": "wellarchitected",
                "is_regional": True
            },
            {
                "name": "wisdom",
                "is_regional": True
            },
            {
                "name": "workdocs",
                "is_regional": True
            },
            {
                "name": "worklink",
                "is_regional": False
            },
            {
                "name": "workmail",
                "is_regional": True
            },
            {
                "name": "workmailmessageflow",
                "is_regional": False
            },
            {
                "name": "workspaces",
                "is_regional": True
            },
            {
                "name": "workspaces-web",
                "is_regional": True
            },
            {
                "name": "xray",
                "is_regional": True
            }
        ]

    @classmethod
    def get_details(cls):
        return {
            "automation_code": "",
            "fetcher_code": "",
            "automation_supported": ["communication", 'mutation'],
            "clients": list_of_unique_elements(cls.get_all_python_sdk_clients()),
            "supported_executor": "ecs",
            "compliance_supported": False
        }

    def generate_steampipe_creds(self) -> SteampipeCreds:
        creds = self._temp_credentials()
        conf_path = "~/.steampipe/config/aws.spc"
        return SteampipeCreds(envs=creds, plugin_name="aws", connection_name="aws",
                              conf_path=conf_path)

    def generate_python_sdk_clients(self, required_clients: list, regions: list):
        all_clients = self.get_all_python_sdk_clients()
        filtered_clients = []
        for client in required_clients:
            filtered_clients.append(next(item for item in all_clients if item["name"] == client["name"]))
        cat_clients = {
            "global": {},
            "regional": {}
        }
        for client in filtered_clients:
            if client["is_regional"]:
                for region in regions:
                    cat_clients["regional"].setdefault(region, {})
                    cat_clients["regional"][region][
                        client["name"]] = self.ctx.integration_context.boto3_helper.get_client(client["name"], region)
            else:
                cat_clients["global"][client["name"]] = self.ctx.integration_context.boto3_helper.get_client(
                    client["name"])
        return cat_clients

    def generate_python_sdk_creds(self, requested_clients=None) -> SDKCreds:
        creds = self._temp_credentials()
        clients = self.get_all_python_sdk_clients()
        package_names = None
        return SDKCreds(library_names=[], clients=[], envs=creds, package_names=package_names)

    @staticmethod
    def supported_connection_types():
        return [ConnectionTypes.REST_API, ConnectionTypes.CLI, ConnectionTypes.PYTHON_SDK, ConnectionTypes.STEAMPIPE]

    def generate_cli_creds(self) -> CLICreds:
        raise NotImplementedError()

    def _temp_credentials(self):
        if self.integration.role_arn:
            return {
                "AWS_ACCESS_KEY_ID": self.ctx.integration_context.boto3_helper.get_access_key(),
                "AWS_SECRET_ACCESS_KEY": self.ctx.integration_context.boto3_helper.get_secret_key(),
                "AWS_SESSION_TOKEN": self.ctx.integration_context.boto3_helper.get_session_token(),
            }
        else:
            return {
                "AWS_ACCESS_KEY_ID": self.integration.access_key,
                "AWS_SECRET_ACCESS_KEY": self.integration.secret_key,
                "AWS_SESSION_TOKEN": self.integration.session_token,
            }
