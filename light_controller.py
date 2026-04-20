import requests
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger("aura.core.iot.light_controller")

# Increase the timeout significantly to accommodate the 50% packet loss and high ping variance on the NodeMCU.
TIMEOUT = 10.0  

def get_esp_ip() -> str:
    # Always reload env in case it changed recently
    load_dotenv()
    return os.getenv("ESP32_IP", "192.168.1.100")

def turn_on_light() -> str:
    """Sends HTTP request to ESP32 to turn the relay ON."""
    ip = get_esp_ip()
    url = f"http://{ip}/ON"
    try:
        logger.info(f"IoT: Turning on light at {url}")
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            return "Turning on the light"
        else:
            return f"Light device connected, but returned error {response.status_code}"
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
        logger.error(f"IoT: Connection to ESP32 ({ip}) failed. Error: {e}")
        return "Light device not connected"

def turn_off_light() -> str:
    """Sends HTTP request to ESP32 to turn the relay OFF."""
    ip = get_esp_ip()
    url = f"http://{ip}/OFF"
    try:
        logger.info(f"IoT: Turning off light at {url}")
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            return "Turning off the light"
        else:
            return f"Light device connected, but returned error {response.status_code}"
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
        logger.error(f"IoT: Connection to ESP32 ({ip}) failed. Error: {e}")
        return "Light device not connected"