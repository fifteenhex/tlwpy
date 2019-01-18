import tlwpy.mqttbase
from tlwpy.mqttbase import MqttBase
import json
import tlwpy.liblorawan
import tlwpy.pktfwdbr
import base64
import asyncio

PKTFWDBRROOT = 'pktfwdbr'
RX_TYPE_JOIN = 'join'


class Gateway(MqttBase):
    __slots__ = ['__gateway_id', '__pktfwdbr']

    def __init__(self, host: str = None, port: int = None, gateway_id: str = None):
        super(Gateway, self).__init__(host, port, id=tlwpy.mqttbase.create_client_id("gwsim"))
        if gateway_id is not None:
            self.__gateway_id = gateway_id
        else:
            self.__gateway_id = 'fakegw'

        self.__pktfwdbr = tlwpy.pktfwdbr.PacketForwarder(host=host, port=port)

    async def send_pktfwdbr_publish(self, topic, payload):
        await self.wait_for_connection()
        self.mqtt_client.publish(topic, json.dumps(payload))

    async def join(self, app_eui: str, dev_eui: str, dev_key: str):
        assert len(app_eui) is 16
        assert len(dev_eui) is 16
        topic = '%s/%s/rx/%s/%s/%s' % (PKTFWDBRROOT, self.__gateway_id, RX_TYPE_JOIN, app_eui, dev_eui)

        bin_dev_key = bytes.fromhex(dev_key)

        data = tlwpy.liblorawan.build_joinreq(bin_dev_key, bytes.fromhex(app_eui), bytes.fromhex(dev_eui),
                                              b'00')

        payload = {"tmst": 3889331076,
                   "chan": 1,
                   "rfch": 0,
                   "freq": 923.39999999999998,
                   "stat": 1,
                   "modu": "LORA",
                   "datr": "SF10BW125",
                   "codr": "4/5",
                   "lsnr": 12.0,
                   "rssi": -48,
                   "size": 23,
                   "data": base64.b64encode(data).decode('ascii')}

        await self.send_pktfwdbr_publish(topic, payload)

        encrypted_joinack = await asyncio.wait_for(self.__pktfwdbr.joinacks.get(), 10)
        joinack = encrypted_joinack.decrypt(bin_dev_key)
        return joinack

    async def send_uplink(self):
        pass

    async def send_txack(self):
        pass
