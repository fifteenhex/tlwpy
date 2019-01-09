import pytest
import tlwpy.mqttbase


@pytest.mark.asyncio
async def test_waitforconnection(mosquitto_process):
    mqttbase = tlwpy.mqttbase.MqttBase(port=6666)
    await mqttbase.wait_for_connection()
