class HealthyController:
    def __init__(self, app_id: str, environment: str):
        self._app_status = {
            "message": f"{app_id} OK",
            "environment": environment,
        }

    def root(self):
        return self._app_status

    def healthy(self):
        return self._app_status

    def liveness(self):
        return self._app_status
