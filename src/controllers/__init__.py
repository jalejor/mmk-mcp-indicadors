from os import getenv
from .healthy_controller import HealthyController

healthy_controller = HealthyController(getenv)
