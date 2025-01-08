import logging
import logging.config
import os

from pydantic import BaseModel

DEBUG = os.getenv("DEBUG", None)


# Custom LoggerAdapter for Masking Sensitive Data
class MaskSensitiveDataLoggerAdapter(logging.LoggerAdapter):
    @staticmethod
    def mask_value(value):
        if isinstance(value, (str, int, float)):
            value = str(value)
            if value.lower() in ["true", "false"]:
                return "*"
            unmasked_length = min(len(value) // 4, 2)
            return (
                value[:unmasked_length]
                + "*" * min(len(value) - 2 * unmasked_length, 10)
                + value[len(value) - unmasked_length:]
            )
        if isinstance(value, dict):
            return {
                k: MaskSensitiveDataLoggerAdapter.mask_value(v)
                for k, v in value.items()
            }
        elif isinstance(value, (list, set, tuple)):
            return value.__class__(
                MaskSensitiveDataLoggerAdapter.mask_value(v) for v in value
            )
        elif isinstance(value, BaseModel):
            return MaskSensitiveDataLoggerAdapter.mask_value(value.model_dump())
        return value # Return Value for unsupported type

    def process(self, msg, kwargs):
        # Mask sensitive data if 'data' is passed in kwargs
        sensitive_data = kwargs.pop("sensitive_data", None)
        if sensitive_data:
            masked_data = self.mask_value(sensitive_data)
            msg = f"{msg}{masked_data}"
        return msg, kwargs


def setup_logging():
    if DEBUG:
        # Configure logging for development
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
            ],
        )
    else:
        # Configure logging for production
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
            ],
        )
    logger = logging.getLogger(__name__)
    return MaskSensitiveDataLoggerAdapter(logger, {})


# Call setup_logging when this module is imported
logger = setup_logging()
