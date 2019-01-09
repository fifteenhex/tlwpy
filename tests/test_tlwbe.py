import pytest
import tlwpy.tlwbe


@pytest.mark.asyncio
async def test_waitforconnection(mosquitto_process):
    tlwbe = tlwpy.tlwbe.Tlwbe(port=6666)
    await tlwbe.wait_for_connection()
