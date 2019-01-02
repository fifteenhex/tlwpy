import logging
from tlwpy.mqttbase import MqttBase


class Gateway(MqttBase):
    __slots__ = ['__logger']

    def __on_heartbeat(self, client, userdata, msg):
        self.__logger.debug("saw gateway heartbeat")

    def __init__(self, host: str, gw_name: str):
        super().__init__(host)
        heartbeat_topic = 'gwctrl/%s/heartbeat' % gw_name
        self.__logger = logging.getLogger('gwctrl')
        self.mqtt_client.message_callback_add(heartbeat_topic, self.__on_heartbeat)
        self.mqtt_client.subscribe(heartbeat_topic)

    def reboot(self):
        pass
