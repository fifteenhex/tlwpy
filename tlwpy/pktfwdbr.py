import paho.mqtt.client as mqtt
import logging
import base64
from tlwpy import lorawan
import json
import asyncio
from tlwpy.mqttbase import MqttBase


class PacketForwarder(MqttBase):
    __slots__ = ['uplinks', 'downlinks', '__logger', '__mqtt_client']

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
            self.uplinks.put_nowait(lorawan.Uplink(pkt_data))

    def __on_tx(self, client, userdata, msg: mqtt.MQTTMessage):
        payload_json = json.loads(msg.payload)
        pkt_data = base64.b64decode(payload_json["txpk"]['data'])
        pkt_type = lorawan.get_packet_type(pkt_data)
        if pkt_type == lorawan.MHDR_MTYPE_JOINACK:
            join_ack = lorawan.JoinAccept(pkt_data)
            self.__logger.debug('saw joinack')
        elif pkt_type == lorawan.MHDR_MTYPE_CNFDN or pkt_type == lorawan.MHDR_MTYPE_UNCNFDN:
            downlink = lorawan.Downlink(pkt_data)
            self.__logger.debug('saw downlink for %x, framecounter %d, port %d' % (
                downlink.devaddr, downlink.framecounter, downlink.port))
            self.downlinks.put_nowait(downlink)

    def __init__(self, host: str):
        super().__init__(host)
        self.uplinks = asyncio.Queue()
        self.downlinks = asyncio.Queue()
        rx_topic = 'pktfwdbr/+/rx/#'
        tx_topic = 'pktfwdbr/+/tx/#'
        self.__logger = logging.getLogger('pktfwdbr')
        self.mqtt_client.message_callback_add(rx_topic, self.__on_rx)
        self.mqtt_client.subscribe(rx_topic)
        self.mqtt_client.message_callback_add(tx_topic, self.__on_tx)
        self.mqtt_client.subscribe(tx_topic)

    def reset(self):
        pass
