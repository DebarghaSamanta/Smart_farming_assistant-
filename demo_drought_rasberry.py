import os
from unittest.mock import patch, MagicMock

import demo_drought as demo


def test_demo_sensor_data():
    data = demo.get_demo_sensor_data()

    assert data["crop"] == "rice"
    assert data["state"] == "West Bengal"
    assert data["season"] == "AMAN"
    assert len(data["node_trends"]) == 4
    assert data["air_temp_c"] > 0
    assert 0 <= data["humidity_pct"] <= 100


def test_sms_message_for_high_risk():
    result = {
        "risk_level": "HIGH",
        "trajectory": "WORSENING",
        "crop_context": {
            "growth_stage": "FLOWERING"
        }
    }

    message = demo.build_alert_message(result)

    assert message is not None
    assert "HIGH" in message
    assert "FLOWERING" in message
    assert "drought-like conditions" in message


def test_sms_message_for_medium_risk():
    result = {
        "risk_level": "MEDIUM",
        "trajectory": "STABLE",
        "crop_context": {
            "growth_stage": "TILLERING"
        }
    }

    message = demo.build_alert_message(result)

    assert message is not None
    assert "MEDIUM" in message
    assert "TILLERING" in message


def test_no_sms_for_none_risk():
    result = {
        "risk_level": "NONE",
        "trajectory": "STABLE",
        "crop_context": {
            "growth_stage": "VEGETATIVE"
        }
    }

    assert demo.build_alert_message(result) is None


@patch("raspberry_drought_demo.Client")
def test_sms_function(mock_client):
    demo.TWILIO_ACCOUNT_SID = "test_sid"
    demo.TWILIO_AUTH_TOKEN = "test_token"
    demo.TWILIO_FROM_NUMBER = "+10000000000"
    demo.MOBILE_NUMBER = "+919999999999"

    mock_messages = MagicMock()
    mock_client.return_value.messages = mock_messages

    result = demo.send_sms("Test drought alert")

    assert result is True
    mock_messages.create.assert_called_once()


print("All Raspberry Pi SMS demonstration tests passed.")
