import paho.mqtt.client as mqtt
import asyncio


class MqttBase:
    __slots__ = ['mqtt_client', 'event_loop']

    def __init__(self, host: str):
        self.event_loop = asyncio.get_running_loop()
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(host)

    def loop(self):
        while self.event_loop.is_running():
            self.mqtt_client.loop()
        self.mqtt_client.disconnect()
        self.mqtt_client.loop()
