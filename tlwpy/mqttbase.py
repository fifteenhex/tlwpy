import paho.mqtt.client as mqtt
import asyncio


class MqttBase:
    __slots__ = ['mqtt_client', 'event_loop', '__host', '__port', '__topics', '__connected', '__on_connected_futures']

    def __on_connect(self, client, userdata, flags, rc):
        for topic in self.__topics:
            self.mqtt_client.subscribe(topic)

        self.__connected = True
        for future in self.__on_connected_futures:
            self.__on_connected_futures.remove(future)
            self.event_loop.call_soon_threadsafe(future.set_result, True)

    def _on_sub(self, client, userdata, mid, granted_qos):
        self.__logger.debug("subbed")

    def __on_disconnect(self, client, userdata, rc):
        self.__connected = False

    def __init__(self, host: str = "localhost", port: int = None, topics: [] = []):
        # stash the mqtt parameters
        if port is None:
            port = 1883
        self.__host = host
        self.__port = port
        self.__topics = topics

        # create the connection state tracking stuf
        self.__connected = False
        self.__on_connected_futures = []

        # create and configure the mqtt client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.__on_connect
        self.mqtt_client.on_subscribe = self._on_sub
        self.mqtt_client.on_disconnect = self.__on_disconnect

        # get the event loop and start running the mqtt loop
        self.event_loop = asyncio.get_running_loop()
        self.event_loop.run_in_executor(None, self.__loop)

    def __loop(self):
        self.mqtt_client.connect(self.__host, self.__port)
        while self.event_loop.is_running():
            self.mqtt_client.loop(10)
            if not self.__connected:
                self.mqtt_client.reconnect()
        self.mqtt_client.disconnect()

    async def wait_for_connection(self):
        future = asyncio.get_running_loop().create_future()
        if self.__connected:
            self.event_loop.call_soon_threadsafe(future.set_result, True)
        else:
            self.__on_connected_futures.append(future)
        return await asyncio.wait_for(future, 10)
