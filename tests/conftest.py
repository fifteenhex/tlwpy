import pytest
from subprocess import Popen
import time

MQTT_PORT = 6666


def pytest_addoption(parser):
    parser.addoption("--mosquitto_path", action="store")


@pytest.fixture(scope="session")
def mosquitto_path(request):
    path = request.config.getoption("--mosquitto_path")
    if path is None:
        path = "mosquitto"
    return path


@pytest.fixture(scope="session")
def mosquitto_process(mosquitto_path):
    process = Popen([mosquitto_path, '-v', '-p', str(MQTT_PORT)])
    time.sleep(2)
    yield process
    process.terminate()
    process.wait()
