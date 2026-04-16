import logging

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


def main():
    from web_server import start_fastapi, launch_asgi_server
    from mcp_server import start_mcp
    app = start_fastapi()
    start_mcp(app)
    launch_asgi_server(app)
    return app


if __name__ == '__main__':
    _LOGGER.debug("Starting FastAPI")
    main()
