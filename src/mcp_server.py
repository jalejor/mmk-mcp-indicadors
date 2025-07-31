from fastapi_mcp import FastApiMCP


def start_mcp(app):
    mcp = FastApiMCP(app)
    mcp.setup_server()
    mcp.mount()
