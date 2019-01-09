from tlwpy.mqttbase import MqttBase
import json
import tlwpy.liblorawan
import base64

PKTFWDBRROOT = 'pktfwdbr'
RX_TYPE_JOIN = 'join'


class Gateway(MqttBase):
    __slots__ = ['__gateway_id']

    def __init__(self, host: str = None, port: int = None, gateway_id: str = None):
        super(Gateway, self).__init__(host, port, id="gwsim")
        if gateway_id is not None:
            self.__gateway_id = gateway_id
        else:
            self.__gateway_id = 'fakegw'

    async def send_pktfwdbr_publish(self, topic, payload):
        await self.wait_for_connection()
        self.mqtt_client.publish(topic, json.dumps(payload))

    async def join(self, app_eui: str, dev_eui: str):
        assert len(app_eui) is 16
        assert len(dev_eui) is 16
        topic = '%s/%s/rx/%s/%s/%s' % (PKTFWDBRROOT, self.__gateway_id, RX_TYPE_JOIN, app_eui, dev_eui)

        data = tlwpy.liblorawan.builder_joinreq(b'0000000000000000', bytes.fromhex(app_eui), bytes.fromhex(dev_eui),
                                                b'00')

        payload = {"tmst": 3889331076, "chan": 1, "rfch": 0, "freq": 923.39999999999998, "stat": 1, "modu": "LORA",
                   "datr": "SF10BW125", "codr": "4/5", "lsnr": 12.0, "rssi": -48, "size": 23,
                   "data": base64.b64encode(data).decode('ascii')}

        await self.send_pktfwdbr_publish(topic, payload)

    async def send_uplink(self):
        pass

    async def send_txack(self):
        pass
