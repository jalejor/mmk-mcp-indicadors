from os import getenv
from .healthy_controller import HealthyController

healthy_controller = HealthyController(
    app_id=getenv("APP_ID", "mmk-mcp-indicadors"),
    environment=getenv("PYTHON_ENV", "development"),
)
