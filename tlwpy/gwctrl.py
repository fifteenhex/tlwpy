import logging
import tlwpy.mqttbase
from tlwpy.mqttbase import MqttBase


class Gateway(MqttBase):
    __slots__ = ['__logger']

    def __on_heartbeat(self, client, userdata, msg):
        self.__logger.debug("saw gateway heartbeat")

    def __init__(self, host: str, gw_name: str):
        heartbeat_topic = 'gwctrl/%s/heartbeat' % gw_name
        super().__init__(host, id=tlwpy.mqttbase.create_client_id('gwctrl'), topics=[heartbeat_topic])
        self.__logger = logging.getLogger('gwctrl')
        self.mqtt_client.message_callback_add(heartbeat_topic, self.__on_heartbeat)

    def reboot(self):
        pass
