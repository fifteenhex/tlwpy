import paho.mqtt.client as mqtt
import asyncio
import logging


class MqttBase:
    __slots__ = ['mqtt_client', 'event_loop',
                 '__host', '__port', '__topics', '__connected',
                 '__logger']

    def __on_connect(self, client, userdata, flags, rc):
        self.__logger.debug('Connected')
        for topic in self.__topics:
            self.__logger.debug('Subbing to %s' % topic)
            assert self.mqtt_client.subscribe(topic) == mqtt.MQTT_ERR_SUCCESS
        self.event_loop.call_soon_threadsafe(self.__connected.set())

    def __on_sub(self, client, userdata, mid, granted_qos):
        self.__logger.debug('Subbed')

    def __on_disconnect(self, client, userdata, rc):
        self.__logger.debug('Disconnected')
        self.event_loop.call_soon_threadsafe(self.__connected.clear())

    def __init__(self, host: str = "localhost", port: int = None, id: str = None, topics: [] = []):
        self.__logger = logging.getLogger('mqttbase')

        # stash the mqtt parameters
        if port is None:
            port = 1883
        self.__host = host
        self.__port = port
        self.__topics = topics

        # create the connection state tracking stuff
        self.__connected = asyncio.Event()

        # create and configure the mqtt client
        self.mqtt_client = mqtt.Client(client_id=id)
        self.mqtt_client.max_inflight_messages_set(0)
        self.mqtt_client.max_queued_messages_set(0)
        self.mqtt_client.on_connect = self.__on_connect
        self.mqtt_client.on_subscribe = self.__on_sub
        self.mqtt_client.on_disconnect = self.__on_disconnect

        # get the event loop and start running the mqtt loop
        self.event_loop = asyncio.get_running_loop()
        self.event_loop.run_in_executor(None, self.__loop)

    def __loop(self):
        self.mqtt_client.connect(self.__host, self.__port)
        while self.event_loop.is_running():
            rc = self.mqtt_client.loop(1)
            if rc != mqtt.MQTT_ERR_SUCCESS:
                self.__logger.warning('might have gotten disconnected, %s' % mqtt.error_string(rc))
                try:
                    self.mqtt_client.reconnect()
                except ConnectionRefusedError:
                    self.__logger.warning('connection was refused')
        self.mqtt_client.disconnect()

    async def wait_for_connection(self):
        await asyncio.wait_for(self.__connected.wait(), 30)
