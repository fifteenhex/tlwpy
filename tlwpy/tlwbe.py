import paho.mqtt.client as mqtt
from uuid import uuid4
import json
from asyncio import Queue
from asyncio import Future
import asyncio
import base64
import logging
from tlwpy.mqttbase import MqttBase

TOPIC_DEV_GET = 'tlwbe/control/dev/get'
TOPIC_APP_GET = 'tlwbe/control/app/get'


class Join:
    __slots__ = 'appeui', 'deveui', 'timestamp'

    def __init__(self, msg: mqtt.MQTTMessage):
        topic_parts = msg.topic.split('/')
        self.appeui = topic_parts[-2]
        self.deveui = topic_parts[-1]
        self.timestamp = json.loads(msg.payload)['timestamp']


class Uplink:
    __slots__ = ['timestamp', 'appeui', 'devui', 'port', 'payload', 'rfparams']

    def __init__(self, msg: mqtt.MQTTMessage):
        msg_json = json.loads(msg.payload)
        self.timestamp = msg_json.get('timestamp')
        self.appeui = msg_json.get('appeui')
        self.devui = msg_json.get('deveui')
        self.port = msg_json.get('port')
        b64_payload: str = msg_json.get('payload')
        self.payload = base64.decodebytes(b64_payload.encode("ascii"))
        self.rfparams = msg_json.get('rfparams')


class Result:
    __slots__ = ['token', 'payload']

    def __init__(self, msg: mqtt.MQTTMessage):
        self.token = msg.topic.split("/")[-1]
        self.payload = msg.payload


class Tlwbe(MqttBase):
    __slots__ = ['queue_joins', 'queue_uplinks', '__logger', '__control_results', '__downlink_results']

    def __dump_message(self, msg):
        self.__logger.debug('publish on %s' % msg.topic)

    def _on_sub(self, client, userdata, mid, granted_qos):
        self.__logger.debug("subbed")

    def __on_msg(self, client, userdata, msg):
        self.__dump_message(msg)
        self.__logger.warning('rogue publish')

    def __on_join(self, client, userdata, msg):
        self.__dump_message(msg)
        self.queue_joins.put_nowait(Join(msg))

    def __on_uplink(self, client, userdata, msg):
        self.__dump_message(msg)
        self.queue_uplinks.put_nowait(Uplink(msg))

    def __on_result(self, msg, results: dict):
        self.__dump_message(msg)
        result = Result(msg)
        self.__logger.debug('have result for %s' % result.token)
        if result.token in results:
            future: Future = results.pop(result.token)
            self.event_loop.call_soon_threadsafe(future.set_result, result)
        else:
            self.__logger.warning('rogue result')

    def __on_control_result(self, client, userdata, msg):
        self.__on_result(msg, self.__control_results)

    def __on_downlink_result(self, client, userdata, msg):
        self.__on_result(msg, self.__downlink_results)

    def __init__(self, host: str):
        super().__init__(host)
        self.queue_joins = Queue()
        self.queue_uplinks = Queue()
        self.__control_results = {}
        self.__downlink_results = {}

        self.mqtt_client.message_callback_add('tlwbe/join/+/+', self.__on_join)
        self.mqtt_client.message_callback_add('tlwbe/uplink/#', self.__on_uplink)
        self.mqtt_client.message_callback_add('tlwbe/control/result/#', self.__on_control_result)
        self.mqtt_client.message_callback_add('tlwbe/downlink/result/#', self.__on_downlink_result)
        self.mqtt_client.on_message = self.__on_msg
        self.mqtt_client.on_subscribe = self._on_sub
        self.mqtt_client.subscribe('tlwbe/control/result/#')
        self.mqtt_client.subscribe('tlwbe/downlink/result/#')

        self.__logger = logging.getLogger('tlwbe')

    async def __publish_and_wait_for_result(self, topic: str, payload: dict, results: dict):
        token = str(uuid4())
        future = asyncio.get_running_loop().create_future()
        results[token] = future
        self.mqtt_client.publish("%s/%s" % (topic, token), json.dumps(payload))
        result = await asyncio.wait_for(future, 10)
        return result

    async def __publish_and_wait_for_control_result(self, topic: str, payload: dict):
        return await self.__publish_and_wait_for_result(topic, payload, self.__control_results)

    async def __publish_and_wait_for_downlink_result(self, topic: str, payload: dict):
        return await self.__publish_and_wait_for_result(topic, payload, self.__downlink_results)

    def __sub_to_topic(self, topic: str):
        self.__logger.debug('subscribing to %s' % topic)
        self.mqtt_client.subscribe(topic)

    async def get_dev_by_name(self, name: str):
        payload = {'name': name}
        result = await self.__publish_and_wait_for_control_result(TOPIC_DEV_GET, payload)
        return result

    async def get_dev_by_eui(self, eui: str):
        payload = {'eui': eui}
        result = await self.__publish_and_wait_for_control_result(TOPIC_DEV_GET, payload)
        return result

    async def get_app_by_name(self, name: str):
        payload = {'name': name}
        result = await self.__publish_and_wait_for_control_result(TOPIC_APP_GET, payload)
        return result

    def get_app_by_eui(self, eui: str):
        payload = {'eui': eui}
        result = self.__publish_and_wait_for_control_result(TOPIC_APP_GET, payload)
        return result

    def listen_for_joins(self, appeui: str, deveui: str):
        self.__sub_to_topic('tlwbe/join/%s/%s' % (appeui, deveui))

    def listen_for_uplinks(self, appeui: str, deveui: str, port: int):
        self.__sub_to_topic('tlwbe/uplink/%s/%s/%d' % (appeui, deveui, port))

    async def send_downlink(self, app_eui, dev_eui, port, payload: bytes = None, confirm=False):
        msg_topic = 'tlwbe/downlink/schedule/%s/%s/%d' % (app_eui, dev_eui, port)
        msg_payload = {'confirm': confirm}
        if payload is not None:
            msg_payload['payload'] = base64.b64encode(payload).decode('ascii')
        return await self.__publish_and_wait_for_downlink_result(msg_topic, msg_payload)
