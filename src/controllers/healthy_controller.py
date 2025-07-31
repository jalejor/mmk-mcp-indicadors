class HealthyController(object):
    def __init__(self, getenv):
        _SVC = getenv("APP_ID", "fastapi")
        _ENV = getenv("PYTHON_ENV", "development")

        self._app_status = {
            "message": f"{_SVC} OK 👽",
            "environment": _ENV,
        }

    def root(self):
        return self._app_status

    def healthy(self):
        return self._app_status

    def liveness(self):
        return self._app_status
