"""Mounts the MCP transport on the FastAPI app, protected by the API key.

The MCP tools run the exact same ccxt/indicator compute as the protected
`/v1/*` HTTP endpoints, so the MCP transport MUST enforce the same
`X-API-Key` auth. We pass `api_key_dependency` through fastapi-mcp's
`AuthConfig.dependencies`; the fork applies it to BOTH MCP endpoints
(the SSE GET handshake at `<mount_path>` and the POST at
`<mount_path>/messages/`). When `API_KEYS` is unset the dependency is a
no-op (development mode), matching the HTTP routes.
"""

from fastapi import Depends
from fastapi_mcp import AuthConfig, FastApiMCP

from security import api_key_dependency


def start_mcp(app):
    mcp = FastApiMCP(
        app,
        auth_config=AuthConfig(
            dependencies=[Depends(api_key_dependency)],
        ),
    )
    mcp.setup_server()
    mcp.mount()
