import os
import traceback
from typing import Any, Dict, List, Optional, Type, Union

import json
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError
from pydantic import Field, model_validator
from pathlib import Path

from autobotAI_integrations import (
    AIBaseService,
    list_of_unique_elements,
    PayloadTask,
    Param,
)
from autobotAI_integrations.models import (
    CLICreds,
    ConnectionInterfaces,
    IntegrationCategory,
    BaseSchema,
    SDKClient,
    SDKCreds,
)
from autobotAI_integrations.utils.aws_region import resolve_aws_sub_integration_region
from autobotAI_integrations.utils.boto3_helper import Boto3Helper
from autobotAI_integrations.utils.logging_config import logger


def _boto3():
    import boto3

    return boto3


class AWSBedrockIntegration(BaseSchema):
    region: Optional[str] = None
    access_key: Optional[str] = Field(default=None, exclude=True)
    secret_key: Optional[str] = Field(default=None, exclude=True)
    session_token: Optional[str] = Field(default=None, exclude=True)
    account_id: Optional[str] = None
    roleArn: Optional[str] = None
    externalId: Optional[str] = None

    name: Optional[str] = "AWS Bedrock"
    category: Optional[str] = IntegrationCategory.AI.value
    description: Optional[str] = (
        "AWS Bedrock is a service that lets you use powerful AI models from various companies for your applications, all through one place."
    )

    @model_validator(mode="before")
    @classmethod
    def ensure_region(cls, values: Any) -> Any:
        if isinstance(values, dict) and not values.get("region"):
            values["region"] = resolve_aws_sub_integration_region()
        return values

    def __init__(self, **kwargs):
        if kwargs.get("region"):
            kwargs["activeRegions"] = [kwargs["region"]]
        super().__init__(**kwargs)

    def use_dependency(self, dependency: dict):
        self.roleArn = dependency.get("roleArn")
        self.access_key = dependency.get("access_key")
        self.secret_key = dependency.get("secret_key")
        self.session_token = dependency.get("session_token")
        self.externalId = dependency.get("externalId")
        self.account_id = dependency.get("account_id")
        self.dependent_integration_id = dependency.get("accountId")


class AWSBedrockService(AIBaseService):
    def __init__(self, ctx: dict, integration: Union[AWSBedrockIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, AWSBedrockIntegration):
            integration = AWSBedrockIntegration(**integration)
        super().__init__(ctx, integration)
        self._boto3_helper = None
        self._clients = {}

    def _get_aws_client(
        self,
        aws_client_name: str,
        region_name: Optional[str] = None,
        botocore_config: Optional[BotocoreConfig] = None,
    ):
        target_region = region_name or self.integration.region
        cache_key = f"{aws_client_name}:{target_region}:{id(botocore_config) if botocore_config else 'default'}"
        if cache_key in self._clients:
            return self._clients[cache_key]

        if self.integration.roleArn not in ["None", None]:
            if not self._boto3_helper:
                self._boto3_helper = Boto3Helper(
                    self.ctx, integration=self.integration.dump_all_data()
                )
            client = self._boto3_helper.get_client(
                aws_client_name, region_name=target_region, config=botocore_config
            )
        else:
            client = _boto3().client(
                aws_client_name,
                aws_access_key_id=str(self.integration.access_key),
                aws_secret_access_key=str(self.integration.secret_key),
                aws_session_token=(
                    str(self.integration.session_token)
                    if self.integration.session_token not in [None, "None"]
                    else None
                ),
                region_name=target_region,
                config=botocore_config,
            )
        self._clients[cache_key] = client
        return client

    def _test_integration(self) -> dict:
        try:
            # 1. Retrieve and set AWS Account ID via STS
            sts_client = self._get_aws_client("sts")
            identity_data = sts_client.get_caller_identity()
            account_id = str(identity_data["Account"])
            self.integration.account_id = account_id

            # 2. Primary check: Live inference call to Nova 2 Lite (global inference profile)
            nova_model = "global.amazon.nova-2-lite-v1:0"
            bedrock_runtime = self._get_aws_client("bedrock-runtime")
            nova_error_msg = None

            try:
                response = bedrock_runtime.converse(
                    modelId=nova_model,
                    messages=[{"role": "user", "content": [{"text": "ping"}]}],
                    inferenceConfig={"maxTokens": 1, "temperature": 0.0},
                )
                logger.info(
                    f"AWS Bedrock Nova 2 Lite live response: output={response.get('output')} "
                    f"usage={response.get('usage')} metrics={response.get('metrics')} "
                    f"status_code={response.get('ResponseMetadata', {}).get('HTTPStatusCode')}"
                )
                return {
                    "success": True,
                    "message": "AWS Bedrock integration active (verified via Nova 2 Lite live invocation).",
                }
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "ClientError")
                msg = e.response.get("Error", {}).get("Message", str(e))
                nova_error_msg = f"{code}: {msg}"
                logger.warning(
                    f"AWS Bedrock live model test failed for '{nova_model}' ({code}): {msg}. Attempting fallback..."
                )
            except Exception as e:
                nova_error_msg = str(e)
                logger.warning(
                    f"AWS Bedrock live model test failed for '{nova_model}': {e}. Attempting fallback..."
                )

            # 3. Fallback check: List foundation models to verify control-plane access
            bedrock_client = self._get_aws_client("bedrock")
            bedrock_client.list_foundation_models()

            return {
                "success": True,
                "warning_title": "Bedrock Model Warning",
                "warning": (
                    f"Live model test for '{nova_model}' failed ({nova_error_msg}). "
                    "Integration is active via fallback verification (ListFoundationModels). "
                    "The model may be deprecated, updated, or missing Model Access in your AWS Bedrock console."
                ),
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "ClientError")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"AWS Bedrock integration test failed ({error_code}): {error_msg}")
            return {"success": False, "error": f"{error_code}: {error_msg}"}
        except Exception as e:
            logger.error(str(e))
            logger.error(traceback.format_exc())
            return {"success": False, "error": f"Integration Test Failed: {str(e)}"}

    def test_model(self, model: str) -> dict:
        """Lightweight live verification of a specific model on AWS Bedrock."""
        import time
        try:
            target_region = self.integration.region or "ap-south-1"
            if model.startswith("us.") and not (target_region or "").startswith("us-"):
                target_region = "us-east-1"
            elif model.startswith("eu.") and not (target_region or "").startswith("eu-"):
                target_region = "eu-central-1"
            elif model.startswith("apac.") or model.startswith("in."):
                target_region = "ap-south-1"

            fast_config = BotocoreConfig(
                connect_timeout=6,
                read_timeout=15,
                retries={"max_attempts": 1},
            )
            bedrock_runtime = self._get_aws_client(
                "bedrock-runtime",
                region_name=target_region,
                botocore_config=fast_config,
            )
            start_t = time.time()
            response = bedrock_runtime.converse(
                modelId=model,
                messages=[{"role": "user", "content": [{"text": "ping"}]}],
                inferenceConfig={"maxTokens": 16},
            )
            latency_ms = response.get("metrics", {}).get("latencyMs") or int(
                (time.time() - start_t) * 1000
            )
            return {
                "success": True,
                "model": model,
                "latency_ms": latency_ms,
            }
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "ClientError")
            msg = e.response.get("Error", {}).get("Message", str(e))
            return {"success": False, "model": model, "error": f"{code}: {msg}"}
        except Exception as e:
            return {"success": False, "model": model, "error": str(e)}

    def get_integration_specific_details(self) -> dict:
        try:
            bedrock = self._get_aws_client("bedrock")
            prefix = (
                "apac."
                if (self.integration.region or "").startswith("ap-")
                else ("eu." if (self.integration.region or "").startswith("eu-") else "us.")
            )

            models = []
            # 1. Dynamically fetch system inference profiles available for this region
            try:
                profiles_res = bedrock.list_inference_profiles(typeEquals="SYSTEM_DEFINED")
                for p in profiles_res.get("inferenceProfileSummaries", []):
                    pid = p.get("inferenceProfileId")
                    if pid and not any(
                        x in pid.lower()
                        for x in [
                            "fable",
                            "claude-3-5-haiku",
                            "claude-3-haiku-20240307",
                            "claude-3-sonnet-20240229",
                            "claude-3-opus-20240229",
                            "claude-v2",
                            "claude-instant",
                            "embed",
                            "upscale",
                            "inpaint",
                            "outpaint",
                            "canvas",
                            "reel",
                            "style",
                            "erase",
                            "search-replace",
                            "sonic",
                            "pegasus",
                            "marengo",
                            "video",
                        ]
                    ):
                        models.append(pid)
            except Exception as e:
                logger.warn(
                    f"Error listing inference profiles in {self.integration.region}: {e}"
                )

            # Priority ranking: latest generation models (Sonnet 3.7, 3.5, Haiku 4.5, Nova Pro/Lite/Micro, Sonnet 5/4.6, Opus 4.6)
            priority_rank = {
                f"{prefix}anthropic.claude-3-7-sonnet-20250219-v1:0": 1,
                f"{prefix}anthropic.claude-3-5-sonnet-20241022-v2:0": 2,
                "global.anthropic.claude-haiku-4-5-20251001-v1:0": 3,
                f"{prefix}amazon.nova-pro-v1:0": 4,
                f"{prefix}amazon.nova-lite-v1:0": 5,
                f"{prefix}amazon.nova-micro-v1:0": 6,
                "global.anthropic.claude-sonnet-5": 7,
                "global.anthropic.claude-sonnet-4-6": 8,
                "global.anthropic.claude-opus-4-6-v1": 9,
                "global.amazon.nova-2-lite-v1:0": 10,
            }

            default_top_models = [
                f"{prefix}anthropic.claude-3-7-sonnet-20250219-v1:0",
                f"{prefix}anthropic.claude-3-5-sonnet-20241022-v2:0",
                "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                f"{prefix}amazon.nova-pro-v1:0",
                f"{prefix}amazon.nova-lite-v1:0",
                f"{prefix}amazon.nova-micro-v1:0",
                "global.anthropic.claude-sonnet-5",
                "global.anthropic.claude-sonnet-4-6",
                "global.anthropic.claude-opus-4-6-v1",
                "global.amazon.nova-2-lite-v1:0",
            ]

            # Filter out any fable, legacy Claude 3 models, or unavailable claude-3-5-haiku
            filtered_models = [
                m for m in models
                if "fable" not in m.lower()
                and "claude-3-5-haiku" not in m.lower()
                and "claude-3-haiku-20240307" not in m.lower()
                and "claude-3-sonnet-20240229" not in m.lower()
                and "claude-3-opus-20240229" not in m.lower()
                and "claude-v2" not in m.lower()
            ]
            if filtered_models:
                filtered_models.sort(key=lambda m: priority_rank.get(m, 99))
                # Ensure top defaults are represented if discovered set is partial
                seen = set(filtered_models)
                for fallback_m in default_top_models:
                    if fallback_m not in seen:
                        filtered_models.append(fallback_m)
                        seen.add(fallback_m)
                filtered_models.sort(key=lambda m: priority_rank.get(m, 99))
                available_models = filtered_models
            else:
                available_models = default_top_models

            try:
                from autobotAI_integrations.utils.boto3_helper import regions as standard_aws_regions
                regions = [r["id"] for r in standard_aws_regions] if standard_aws_regions else []
            except Exception:
                regions = []

            if not regions:
                regions = [
                    "us-east-1", "us-west-2", "ap-south-1", "ap-southeast-1", "ap-northeast-1", "eu-central-1", "eu-west-1"
                ]

            if self.integration.region and self.integration.region not in regions:
                regions.append(self.integration.region)

            return {
                "integration_id": self.integration.accountId,
                "models": available_models,
                "available_regions": regions,
                "embedding_models": [
                    "cohere.embed-english-v3",
                    "amazon.titan-embed-text-v2:0",
                    "cohere.embed-multilingual-v3",
                ],
            }

        except Exception as e:
            logger.warn(f"Error fetching integration details: {e}")
            return {"error": "Details cannot be fetched"}

    @staticmethod
    def get_forms():
        return {
            "label": "AWS Bedrock",
            "type": "form",
            "children": [
                {
                    "name": "roleArn",
                    "type": "text",
                    "label": "IAM Role ARN",
                    "placeholder": "Enter IAM role ARN",
                    "required": True,
                },
                {
                    "name": "region",
                    "type": "select",
                    "label": "Region",
                    "placeholder": "Select Region (defaults to parent AWS region or us-east-1)",
                    "required": False,
                },
            ],
        }

    @staticmethod
    def ai_prompt_python_template():
        current_directory = Path(__file__).resolve().parent
        with open(os.path.join(current_directory, "ai_evaluator_code.py")) as f:
            return {
                "integration_type": "aws_bedrock",
                "ai_client": "Agent",
                "param_definitions": [
                    {
                        "name": "prompt",
                        "type": "handlebars-text",
                        "description": "The prompt to use for the AI model",
                        "required": True,
                    },
                    {
                        "name": "model",
                        "type": "str",
                        "description": "The model to use for the AI model",
                        "required": True,
                    },
                    {
                        "name": "resources",
                        "type": "list",
                        "description": "The resources to use for the AI model",
                        "required": True,
                    },
                    {
                        "name": "output_token",
                        "type": "int",
                        "description": "Output Token controls the maximum length of the AI model response. Higher values support larger outputs.",
                        "required": False,
                    }
                ],
                "code": f.read(),
            }

    @staticmethod
    def get_schema(ctx=None) -> Type[BaseSchema]:
        return AWSBedrockIntegration

    @classmethod
    def get_details(cls):
        return {
            "clients": list_of_unique_elements(cls.get_all_python_sdk_clients()),
            "supported_executor": "ecs",
            "compliance_supported": False,
            "supported_interfaces": cls.supported_connection_interfaces(),
            "python_code_sample": cls.get_code_sample(),
            "preview": True,
        }

    def build_python_exec_combinations_hook(
        self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        def model_agent(model_string: str, system_prompt: str = "", tools: Optional[list] = None, **agent_kwargs):
            creds = payload_task.creds.envs if payload_task.creds else {}
            return self.get_pydantic_agent(
                model=model_string,
                tools=tools or [],
                system_prompt=system_prompt,
                options=agent_kwargs,
                credentials=creds,
            )

        return [
            {
                "metadata": {"region": self.integration.region},
                "clients": {
                    "bedrock": _boto3().client(
                        "bedrock", region_name=self.integration.region
                    ),
                    "bedrock-runtime": _boto3().client(
                        "bedrock-runtime", region_name=self.integration.region
                    ),
                    "bedrock-agent": _boto3().client(
                        "bedrock-agent", region_name=self.integration.region
                    ),
                    "bedrock-agent-runtime": _boto3().client(
                        "bedrock-agent-runtime", region_name=self.integration.region
                    ),
                    "Agent": model_agent,
                },
                "params": self.prepare_params(
                    self.filer_combo_params(
                        payload_task.params, self.integration.region
                    )
                ),
                "context": payload_task.context,
            }
        ]

    def filer_combo_params(self, params: List[Param], region):
        filtered_params = []
        for param in params:
            if not param.filter_relevant_resources or not param.values:
                filtered_params.append(param)
            else:
                filtered_values = []
                for value in param.values:
                    if isinstance(value, dict):
                        if value.get("region") == region:
                            filtered_values.append(value)
                    else:
                        filtered_values.append(value)
                filtered_params.append({"name": param.name, "values": filtered_values})
        return filtered_params

    def generate_python_sdk_creds(self, requested_clients=None) -> SDKCreds:
        creds = self._temp_credentials()
        return SDKCreds(envs=creds)

    @staticmethod
    def supported_connection_interfaces():
        return [ConnectionInterfaces.PYTHON_SDK]

    def generate_cli_creds(self) -> CLICreds:
        raise NotImplementedError()

    def _temp_credentials(self):
        if self.integration.roleArn not in ["None", None]:
            boto3_helper = Boto3Helper(
                self.ctx, integration=self.integration.model_dump()
            )
            return {
                "AWS_ACCESS_KEY_ID": boto3_helper.get_access_key(),
                "AWS_SECRET_ACCESS_KEY": boto3_helper.get_secret_key(),
                "AWS_SESSION_TOKEN": boto3_helper.get_session_token(),
            }
        else:
            creds = {
                "AWS_ACCESS_KEY_ID": str(self.integration.access_key),
                "AWS_SECRET_ACCESS_KEY": str(self.integration.secret_key),
            }
            if self.integration.session_token not in [None, "None"]:
                creds["AWS_SESSION_TOKEN"] = str(self.integration.session_token)
            return creds

    def get_pydantic_agent(
        self, model: str, tools, system_prompt: str, options: dict = {}, credentials: Optional[dict] = None
    ):
        from pydantic_ai import Agent
        from autobotAI_integrations.utils.model_helpers import bedrock_model_rejects_temperature

        options = options.copy() if options else {}

        if not credentials:
            credentials = self._temp_credentials()

        model_instance = self.get_pydantic_model(model,credentials=credentials)

        provider_settings = (options.pop("model_settings", {}) or {}).copy()

        t = provider_settings.get("temperature")
        if t is not None and bedrock_model_rejects_temperature(model):
            provider_settings.pop("temperature", None)

        enable_caching = provider_settings.pop("enable_prompt_caching", True)
        if enable_caching:
            try:
                from pydantic_ai.models.bedrock import BedrockModelSettings
                provider_settings.update(BedrockModelSettings(
                    bedrock_cache_instructions='5m',
                    bedrock_cache_tool_definitions='5m'
                ))
            except ImportError:
                pass

        if provider_settings:
            options["model_settings"] = provider_settings

        return Agent(
            model_instance, system_prompt=system_prompt, tools=tools, **options
        )

    def get_pydantic_model(self, model_name: str, credentials: Optional[dict] = None):
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        if not credentials:
            credentials = self._temp_credentials()
  
        model = BedrockConverseModel(
            model_name=model_name,
            provider=BedrockProvider(
                aws_access_key_id=credentials.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=credentials.get("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=credentials.get("AWS_SESSION_TOKEN"),  # None if no role assumption
                region_name=self.integration.region,
            ),
        )
        return model

    @staticmethod
    def build_model_from_credentials(model_name: str, credentials: dict):
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        return BedrockConverseModel(
            model_name=model_name,
            provider=BedrockProvider(
                aws_access_key_id=credentials.get("access_key"),
                aws_secret_access_key=credentials.get("secret_key"),
                aws_session_token=credentials.get("session_token"),
                region_name=credentials.get("region") or "us-east-1",
            ),
        )

    def load_llama_index_embedding_model(
        self, model_name: Optional[str] = None, **kwargs
    ):
        """
        Returns Langchaain Embedding model object and model dimensions as tuple
        """
        if not model_name:
            model_name = "amazon.titan-embed-text-v2:0"
        from llama_index.embeddings.bedrock import BedrockEmbedding

        credentials = self._temp_credentials()
        embed_model = BedrockEmbedding(
            model_name=model_name,
            aws_access_key_id=credentials["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=credentials["AWS_SECRET_ACCESS_KEY"],
            aws_session_token=credentials["AWS_SESSION_TOKEN"],
            region_name=self.integration.region,
            **kwargs,
        )
        # embeddings = embed_model.get_text_embedding(
        #     "Bedrock new Embeddings models is great."
        # )

        # dimensions = len(embeddings)

        # return embed_model, dimensions
        return embed_model

    def load_llama_index_llm(self, model, **kwargs):
        from autobotAI_integrations.patches.llama_index_llms_bedrock_converse import (
            BedrockConverse,
        )

        credentials = self._temp_credentials()
        llm = BedrockConverse(
            model=model,
            aws_access_key_id=credentials["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=credentials["AWS_SECRET_ACCESS_KEY"],
            aws_session_token=credentials["AWS_SESSION_TOKEN"],
            region_name=self.integration.region,
            **kwargs,
        )
        return llm
    
    def generate_llm_credentials(self):
        credentials = self._temp_credentials()
        return {
            "access_key": credentials["AWS_ACCESS_KEY_ID"],
            "secret_key": credentials["AWS_SECRET_ACCESS_KEY"],
            "session_token": credentials["AWS_SESSION_TOKEN"],
            "region": self.integration.region
        }
