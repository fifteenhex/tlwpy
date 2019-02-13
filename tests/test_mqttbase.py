import pytest
from mqttbase import MqttBase


@pytest.mark.asyncio
async def test_waitforconnection(mosquitto_process):
    mqttbase = MqttBase(port=6666)
    await mqttbase.wait_for_connection()
