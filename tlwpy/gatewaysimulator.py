import tlwpy.mqttbase
from tlwpy.mqttbase import MqttBase
import json
import tlwpy.liblorawan
import tlwpy.pktfwdbr
import base64
import asyncio
from tlwpy.lorawan import PacketType, JoinAccept, SessionKeys

PKTFWDBRROOT = 'pktfwdbr'
RX_TYPE_JOIN = 'join'
RX_TYPE_UNCONFIRMED = 'unconfirmed'


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

    def __create_tx_json(self, data: bytes):
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
        return payload

    async def join(self, app_eui: str, dev_eui: str, dev_key: str):
        assert len(app_eui) is 16
        assert len(dev_eui) is 16
        topic = '%s/%s/rx/%s/%s/%s' % (PKTFWDBRROOT, self.__gateway_id, RX_TYPE_JOIN, app_eui, dev_eui)

        bin_dev_key = bytes.fromhex(dev_key)

        dev_nonce = 0

        data = tlwpy.liblorawan.build_joinreq(bin_dev_key, bytes.fromhex(app_eui), bytes.fromhex(dev_eui), dev_nonce)

        payload = self.__create_tx_json(data)

        await self.send_pktfwdbr_publish(topic, payload)

        encrypted_joinack = await asyncio.wait_for(self.__pktfwdbr.joinacks.get(), 10)
        joinack: JoinAccept = encrypted_joinack.decrypt(bin_dev_key)

        session_keys = SessionKeys(bin_dev_key, joinack.appnonce, joinack.netid, dev_nonce)

        return joinack.devaddr, session_keys.network_key, session_keys.app_key

    async def send_uplink(self, dev_addr: int, framecounter: int, port: int,
                          network_key: bytes, application_key: bytes, confirmed=False, payload: bytes = None):

        packet_type = PacketType.CONFIRMED_UP if confirmed else PacketType.UNCONFIRMED_UP

        topic = '%s/%s/rx/%s' % (PKTFWDBRROOT, self.__gateway_id, RX_TYPE_UNCONFIRMED)
        data = tlwpy.liblorawan.build_data(int(packet_type), dev_addr, framecounter, port, payload, network_key,
                                           application_key)
        payload = self.__create_tx_json(data)
        await self.send_pktfwdbr_publish(topic, payload)

    async def send_txack(self):
        pass


class Node:
    __slots__ = ['app_eui', 'dev_eui', 'key', '__gateway', '__dev_addr', '__frame_counter', '__network_key',
                 '__app_key']

    def __init__(self, gateway: Gateway, app_eui: str, dev_eui: str, key: str):
        self.__gateway = gateway
        self.__dev_addr = None
        self.__frame_counter = 0
        self.__network_key = None
        self.__app_key = None
        self.app_eui = app_eui
        self.dev_eui = dev_eui
        self.key = key

    async def join(self):
        dev_addr, network_key, app_key = await self.__gateway.join(self.app_eui, self.dev_eui, self.key)
        assert 0 <= dev_addr <= 0xffffffff
        assert len(network_key) is 16
        assert len(app_key) is 16
        self.__dev_addr = dev_addr
        self.__network_key = network_key
        self.__app_key = app_key

    async def send_uplink(self, port: int, confirmed=False, payload: bytes = None):
        await self.__gateway.send_uplink(self.__dev_addr, self.__frame_counter, port, self.__network_key,
                                         self.__app_key, confirmed=confirmed, payload=payload)
        self.__frame_counter += 1
