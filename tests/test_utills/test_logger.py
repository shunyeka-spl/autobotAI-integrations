import pytest
import logging
from autobotAI_integrations.utils.logging_config import logger


class TestLogCalls:
    @pytest.mark.parametrize(
        "sensitive_data, expected_masked",
        [
            ("a", "*"),
            ("ab", "**"),
            ("abc", "***"),
            ("abcd", "a**d"),
            ("abcde", "a***e"),
            ("password123", "pa*******23"),
            ("token123", "to****23"),
            ("key123", "k****3"),
            ("secret123", "se*****23"),
            (True, "*"),
            (
                {
                    "password": "ThisIsPassword",
                    "token": {"key": "key123", "secret": ["secret123"]},
                },
                {
                    "password": "Th**********rd",
                    "token": {"key": "k****3", "secret": ["se*****23"]},
                },
            ),
        ],
    )
    def test_logger_output(self, caplog, sensitive_data, expected_masked):
        """
        Test if the logger outputs the correct message with filename and level.
        """
        test_message = "Masked Sensitive Data: "

        with caplog.at_level(logging.INFO):
            logger.info(test_message, sensitive_data=sensitive_data)

        assert len(caplog.records) == 1 
        log_record = caplog.records[0]
        assert log_record.levelname == "INFO"
        assert test_message in log_record.message

        masked_data = log_record.message.split("Masked Sensitive Data: ")[1]
        try:
            masked_data = eval(masked_data)
        except:
            pass
        assert masked_data == expected_masked 