import logging
logging.basicConfig(level=logging.INFO)
from core.iot.light_controller import turn_on_light
print("Result:", turn_on_light())
