import logging
import mqttbase
from mqttbase import MqttBase
from asyncio import Queue
import asyncio
import json

TOPICROOT = 'gwctrl'
HEARTBEAT = 'heartbeat'
CTRL_REBOOT = 'reboot'


class Gateway(MqttBase):
    __slots__ = ['gwid', '__logger', '__last_uptime', '__reboot_queue']

    def __on_heartbeat(self, client, userdata, msg):
        self.__logger.debug("saw gateway heartbeat")
        heartbeat_json = json.loads(msg.payload)

        uptime = heartbeat_json['sysinfo']['uptime']
        if uptime < self.__last_uptime:
            self.__logger.debug('gateway uptime went backwards, probably rebooted')
            self.event_loop.call_soon_threadsafe(self.__reboot_queue.put_nowait, True)
        self.__last_uptime = uptime

    def __init__(self, host: str, gwid: str):
        self.__last_uptime = -1
        self.__reboot_queue = Queue()
        self.gwid = gwid
        heartbeat_topic = '%s/%s/%s' % (TOPICROOT, gwid, HEARTBEAT)
        super().__init__(host, id=mqttbase.create_client_id('gwctrl'), topics=[heartbeat_topic])
        self.__logger = logging.getLogger('gwctrl')
        self.mqtt_client.message_callback_add(heartbeat_topic, self.__on_heartbeat)

    async def reboot(self):
        self.__logger.debug('triggering gateway reboot')
        self.mqtt_client.publish('%s/%s/ctrl/%s' % (TOPICROOT, self.gwid, CTRL_REBOOT))
        return await asyncio.wait_for(self.__reboot_queue.get(), 5 * 60)
