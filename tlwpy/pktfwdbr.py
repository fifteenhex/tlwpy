import paho.mqtt.client as mqtt
import logging
import base64
from tlwpy import lorawan
import json
import asyncio
import tlwpy.mqttbase
from tlwpy.mqttbase import MqttBase


class PacketForwarder(MqttBase):
    __slots__ = ['joinacks', 'uplinks', 'downlinks', '__logger', '__mqtt_client']

    def __on_rx(self, client, userdata, msg: mqtt.MQTTMessage):
        payload_json = json.loads(msg.payload)
        pkt_data = base64.b64decode(payload_json['data'])
        pkt_type = lorawan.get_packet_type(pkt_data)
        if pkt_type == lorawan.MHDR_MTYPE_JOINREQ:
            join_reg = lorawan.JoinReq(pkt_data)
            self.__logger.debug('saw joinreq for %x' % join_reg.deveui)
        elif pkt_type == lorawan.MHDR_MTYPE_CNFUP or pkt_type == lorawan.MHDR_MTYPE_UNCNFUP:
            uplink = lorawan.Uplink(pkt_data)
            self.__logger.debug(
                'saw uplink for %x, framecounter %d, port %d' % (uplink.devaddr, uplink.framecounter, uplink.port))
            self.event_loop.call_soon_threadsafe(self.uplinks.put_nowait, lorawan.Uplink(pkt_data))

    def __on_tx(self, client, userdata, msg: mqtt.MQTTMessage):
        payload_json = json.loads(msg.payload)
        pkt_data = base64.b64decode(payload_json["txpk"]['data'])
        pkt_type = lorawan.get_packet_type(pkt_data)
        if pkt_type == lorawan.MHDR_MTYPE_JOINACK:
            join_ack = lorawan.EncryptedJoinAccept(pkt_data)
            self.__logger.debug('saw joinack')
            self.event_loop.call_soon_threadsafe(self.joinacks.put_nowait, join_ack)
        elif pkt_type == lorawan.MHDR_MTYPE_CNFDN or pkt_type == lorawan.MHDR_MTYPE_UNCNFDN:
            downlink = lorawan.Downlink(pkt_data)
            self.__logger.debug('saw downlink for %x, framecounter %d, port %d' % (
                downlink.devaddr, downlink.framecounter, downlink.port))
            self.event_loop.call_soon_threadsafe(self.downlinks.put_nowait, downlink)
        else:
            self.__logger.debug('saw an unknown downlink packet')

    def __on_txack(self, client, userdata, msg: mqtt.MQTTMessage):
        self.__logger.debug('saw a txack')

    def __init__(self, host: str, port: int = None):
        rx_topic = 'pktfwdbr/+/rx/#'
        tx_topic = 'pktfwdbr/+/tx/#'
        txack_topic = 'pktfwdbr/+/txack/#'
        super().__init__(host, port=port, id=tlwpy.mqttbase.create_client_id('pktfwdbr'),
                         topics=[rx_topic, tx_topic, txack_topic])
        self.joinacks = asyncio.Queue()
        self.uplinks = asyncio.Queue()
        self.downlinks = asyncio.Queue()
        self.__logger = logging.getLogger('pktfwdbr')
        self.mqtt_client.message_callback_add(rx_topic, self.__on_rx)
        self.mqtt_client.message_callback_add(tx_topic, self.__on_tx)
        self.mqtt_client.message_callback_add(txack_topic, self.__on_txack)
