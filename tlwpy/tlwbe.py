import paho.mqtt.client as mqtt
from uuid import uuid4
import json
from asyncio import Queue
from asyncio import Future
import asyncio
import base64
import logging
import tlwpy.mqttbase
from tlwpy.mqttbase import MqttBase

ACTION_ADD = 'add'
ACTION_GET = 'get'
ACTION_UPDATE = 'update'
ACTION_DELETE = 'del'
ACTION_LIST = 'list'

TOPIC_DEV_ADD = 'tlwbe/control/dev/%s' % ACTION_ADD
TOPIC_DEV_GET = 'tlwbe/control/dev/%s' % ACTION_GET
TOPIC_DEV_UPDATE = 'tlwbe/control/dev/%s' % ACTION_UPDATE
TOPIC_DEV_DELETE = 'tlwbe/control/dev/%s' % ACTION_DELETE
TOPIC_DEV_LIST = 'tlwbe/control/dev/%s' % ACTION_LIST

TOPIC_APP_ADD = 'tlwbe/control/app/%s' % ACTION_ADD
TOPIC_APP_GET = 'tlwbe/control/app/%s' % ACTION_GET
TOPIC_APP_UPDATE = 'tlwbe/control/app/%s' % ACTION_UPDATE
TOPIC_APP_DELETE = 'tlwbe/control/app/%s' % ACTION_DELETE
TOPIC_APP_LIST = 'tlwbe/control/app/%s' % ACTION_LIST

TOPIC_CONTROL_RESULT = 'tlwbe/control/result/#'
TOPIC_DOWNLINK_RESULT = 'tlwbe/downlink/result/#'

TOPIC_UPLINK_QUERY = 'tlwbe/uplinks/query'
TOPIC_UPLINK_RESULT = 'tlwbe/uplinks/result/#'

RESULT_OK = 0


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


class App:
    __slots__ = ['name', 'eui']

    def __init__(self, json_app: dict):
        self.name = json_app['name']
        self.eui = json_app['eui']


class Dev:
    __slots__ = ['name', 'eui', 'app_eui', 'key', 'serial']

    def __init__(self, json_dev: dict):
        self.name = json_dev['name']
        self.eui = json_dev['eui']
        self.app_eui = json_dev['appeui']
        self.key = json_dev['key']
        self.serial = json_dev['serial']


class Result:
    __slots__ = ['token', 'result', 'code', 'eui_list', 'app', 'dev']

    def __init__(self, msg: mqtt.MQTTMessage):
        self.token = msg.topic.split("/")[-1]
        self.result = json.loads(msg.payload.decode('utf-8'))
        self.code = self.result['code']

        if 'eui_list' in self.result:
            self.eui_list = self.result['eui_list']
        elif 'app' in self.result:
            self.app = App(self.result['app'])
        elif 'dev' in self.result:
            self.dev = Dev(self.result['dev'])


class Tlwbe(MqttBase):
    __slots__ = ['queue_joins',
                 'queue_uplinks',
                 '__id',
                 '__logger',
                 '__control_results',
                 '__uplink_results',
                 '__downlink_results']

    def __dump_message(self, msg):
        self.__logger.debug('publish on %s' % msg.topic)

    def __on_msg(self, client, userdata, msg):
        self.__dump_message(msg)
        self.__logger.warning('rogue publish')

    def __on_join(self, client, userdata, msg):
        self.__dump_message(msg)
        self.event_loop.call_soon_threadsafe(self.queue_joins.put_nowait, Join(msg))

    def __on_uplink(self, client, userdata, msg):
        self.__dump_message(msg)
        self.event_loop.call_soon_threadsafe(self.queue_uplinks.put_nowait, Uplink(msg))

    def __on_result(self, msg, results: dict):
        self.__dump_message(msg)
        result = Result(msg)
        self.__logger.debug('have result for %s' % result.token)
        if result.token.startswith(self.__id):
            if result.token in results:
                future: Future = results.pop(result.token)
                self.event_loop.call_soon_threadsafe(future.set_result, result)
            else:
                self.__logger.warning('rogue result')
        else:
            self.__logger.debug('ignoring result, probably not for us')

    def __on_control_result(self, client, userdata, msg):
        self.__on_result(msg, self.__control_results)

    def __on_uplink_result(self, client, userdata, msg):
        self.__on_result(msg, self.__uplink_results)

    def __on_downlink_result(self, client, userdata, msg):
        self.__on_result(msg, self.__downlink_results)

    def __init__(self, host: str = 'localhost', port: int = None):
        self.__id = tlwpy.mqttbase.create_client_id('tlwbe')
        super().__init__(host, port=port, id=self.__id,
                         topics=[TOPIC_CONTROL_RESULT, TOPIC_UPLINK_RESULT, TOPIC_DOWNLINK_RESULT])
        self.queue_joins = Queue()
        self.queue_uplinks = Queue()
        self.__control_results = {}
        self.__downlink_results = {}

        self.mqtt_client.message_callback_add('tlwbe/join/+/+', self.__on_join)
        self.mqtt_client.message_callback_add('tlwbe/uplink/#', self.__on_uplink)
        self.mqtt_client.message_callback_add(TOPIC_CONTROL_RESULT, self.__on_control_result)
        self.mqtt_client.message_callback_add(TOPIC_UPLINK_RESULT, self.__on_uplink_result)
        self.mqtt_client.message_callback_add(TOPIC_DOWNLINK_RESULT, self.__on_downlink_result)
        self.mqtt_client.on_message = self.__on_msg

        self.__logger = logging.getLogger('tlwbe')

    async def __publish_and_wait_for_result(self, topic: str, payload: dict, results: dict):
        token = "%s_%s" % (self.__id, str(uuid4()))
        future = asyncio.get_running_loop().create_future()
        results[token] = future
        await self.wait_for_connection()
        msginfo = self.mqtt_client.publish("%s/%s" % (topic, token), json.dumps(payload))
        assert msginfo.rc == mqtt.MQTT_ERR_SUCCESS, 'rc was %d' % msginfo.rc
        result = await asyncio.wait_for(future, 10)
        return result

    async def __publish_and_wait_for_control_result(self, topic: str, payload: dict):
        return await self.__publish_and_wait_for_result(topic, payload, self.__control_results)

    async def __publish_and_wait_for_uplink_result(self, topic: str, payload: dict):
        return await self.__publish_and_wait_for_result(topic, payload, self.__uplink_results)

    async def __publish_and_wait_for_downlink_result(self, topic: str, payload: dict):
        return await self.__publish_and_wait_for_result(topic, payload, self.__downlink_results)

    def __sub_to_topic(self, topic: str):
        self.__logger.debug('subscribing to %s' % topic)
        self.mqtt_client.subscribe(topic)

    async def add_dev(self, name: str, app_eui: str, eui: str = None, key: str = None):
        assert name is not None and app_eui is not None
        payload = {'name': name, 'appeui': app_eui}
        if eui is not None:
            payload['eui'] = eui
        if key is not None:
            payload['key'] = key
        result = await self.__publish_and_wait_for_control_result(TOPIC_DEV_ADD, payload)
        return result

    async def get_dev_by_name(self, name: str):
        payload = {'name': name}
        result = await self.__publish_and_wait_for_control_result(TOPIC_DEV_GET, payload)
        return result

    async def get_dev_by_eui(self, eui: str):
        payload = {'eui': eui}
        result = await self.__publish_and_wait_for_control_result(TOPIC_DEV_GET, payload)
        return result

    async def update_dev(self, name: str, eui: str):
        payload = {'name': name, 'eui': eui}
        result = await self.__publish_and_wait_for_control_result(TOPIC_DEV_UPDATE, payload)
        return result

    async def delete_dev(self, eui: str):
        payload = {'eui': eui}
        result = await self.__publish_and_wait_for_control_result(TOPIC_DEV_DELETE, payload)
        return result

    async def list_devs(self):
        payload = {}
        result = await self.__publish_and_wait_for_control_result(TOPIC_DEV_LIST, payload)
        return result

    async def add_app(self, name: str, eui: str = None):
        payload = {'name': name}
        if eui is not None:
            payload['eui'] = eui
        result = await self.__publish_and_wait_for_control_result(TOPIC_APP_ADD, payload)
        return result

    async def get_app_by_name(self, name: str):
        payload = {'name': name}
        result = await self.__publish_and_wait_for_control_result(TOPIC_APP_GET, payload)
        return result

    async def get_app_by_eui(self, eui: str):
        payload = {'eui': eui}
        result = await self.__publish_and_wait_for_control_result(TOPIC_APP_GET, payload)
        return result

    async def update_app(self, name: str, eui: str):
        payload = {'name': name, 'eui': eui}
        result = await self.__publish_and_wait_for_control_result(TOPIC_APP_UPDATE, payload)
        return result

    async def delete_app(self, eui: str):
        payload = {'eui': eui}
        result = await self.__publish_and_wait_for_control_result(TOPIC_APP_DELETE, payload)
        return result

    async def list_apps(self):
        payload = {}
        result = await self.__publish_and_wait_for_control_result(TOPIC_APP_LIST, payload)
        return result

    async def list_uplinks(self, dev_eui: str, app_eui: str):
        payload = {'deveui': dev_eui}
        result = await self.__publish_and_wait_for_uplink_result(TOPIC_UPLINK_QUERY, payload)
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
