# DevOps FastAPI MCP Template

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README.md) [![Español](https://img.shields.io/badge/lang-Español-red.svg)](README_ES.md)

A complete template for creating FastAPI APIs integrated with MCP (Model Context Protocol), designed to facilitate the development of scalable applications with DevOps best practices.

## 🚀 Features

- **FastAPI**: Modern and fast web framework for Python
- **MCP Integration**: Native integration with Model Context Protocol using `fastapi-mcp`
- **Modular Structure**: Clear organization with controllers, routes, and services
- **Docker Ready**: Complete container configuration
- **Development Tools**: Hot reload, debugging, and logging configured
- **Health Checks**: Health and liveness endpoints
- **CORS**: CORS configuration for development
- **PDM**: Modern dependency management

## 📁 Project Structure

```
src/
├── controllers/          # Business logic
│   ├── codes/           # Example controller
│   └── healthy_controller.py
├── routes/              # Route definitions
│   ├── healthy.py       # Health checks
│   └── v1/              # API versioning
│       └── code_routing.py
├── main.py              # Main entry point
├── web_server.py        # FastAPI configuration
├── mcp_server.py        # MCP configuration
└── log_conf.yaml        # Logging configuration
```

## 🛠️ Installation

### Prerequisites

- Python 3.10+
- PDM (Python Dependency Manager)
- Docker and Docker Compose (optional)

### Local Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd devops-fastapi-mcp-template
   ```

2. **Install dependencies**
   ```bash
   pdm install
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env  # If exists
   # Edit .env with your configuration
   ```

4. **Run in development mode**
   ```bash
   pdm run dev
   ```

The application will be available at `http://localhost:3000`

## 🐳 Docker

### Development with Docker

```bash
docker-compose up --build
```

The application will be available at `http://localhost:8000`

### Debugging with Docker

The template includes configuration for remote debugging on port `5678`.

## 📡 API Endpoints

### Health Checks

- `GET /prefix/healthy` - Basic health check
- `GET /prefix/liveness` - Liveness probe

### API v1

- `GET /prefix/v1/codes/get/{code}` - Example endpoint

### Documentation

- `GET /prefix/docs` - Swagger UI
- `GET /prefix/openapi.json` - OpenAPI schema

## ⚙️ Configuration

### Environment Variables

See [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md) for complete documentation of all available environment variables.

### Logging

Logging uses the Python standard library `logging` with a structured JSON formatter (see `src/web_server.py`); base config in `src/log_conf.yaml`.

## 🔧 Development

### Available PDM Commands

```bash
# Development with hot reload
pdm run dev

# Update dependencies
pdm run update-all

# Export requirements.txt
pdm run export
```

### Controller and Route Structure

```python
# controllers/example/example_controller.py
async def your_function(param: str):
    # Your business logic here
    return {"result": "success"}
```

```python
# routes/v1/example_routing.py
from fastapi import APIRouter
from middlewares import has_errors
from controllers.example.example_controller import your_function

example_router = APIRouter()

@example_router.get('/example/{param}', tags=['example'])
@has_errors
async def example_endpoint(param: str):
    return your_function(param)
```

### Adding New Routes

1. Create controller in `controllers/`
2. Define routes in `routes/v1/`
3. Import in `routes/__init__.py`

## 🧪 MCP Integration

This template includes integration with MCP (Model Context Protocol) through `fastapi-mcp`:

```python
# src/mcp_server.py
from fastapi_mcp import FastApiMCP

def start_mcp(app):
    mcp = FastApiMCP(app)
    mcp.setup_server()
    mcp.mount()
```

> **⚠️ Important note about fastapi-mcp**: 
> 
> The original [fastapi_mcp](https://github.com/tadata-org/fastapi_mcp) library has a known bug related to handling FastAPI's `root_path` parameter ([PR #163](https://github.com/tadata-org/fastapi_mcp/pull/163)). This bug causes routes to not work correctly when using a `root_path` different from `/` (like `/prefix` in this template).
> 
> **Solution**: This template uses the fork from [@am1ter](https://github.com/am1ter) available at [am1ter/fastapi_mcp](https://github.com/am1ter/fastapi_mcp/tree/main) which includes the fix for this problem.

### Configuration for AI Code Editors

To use this MCP server with editors like **Cursor**, you need to have [mcp-proxy](https://pypi.org/project/mcp-proxy/) installed on your system.

#### Prerequisites:

1. **Install mcp-proxy** from PyPI:
   ```bash
   pip install mcp-proxy
   ```
   
   > **Requirements**: Python >=3.10
   
   > **Note**: mcp-proxy is a tool that allows switching between MCP server transports, facilitating communication between AI code editors and remote MCP servers.

#### Configuration:

Add the following configuration to your `mcp.json` file:

```json
{
  "mcpServers": {
    "mcp-server-1": {
      "command": "/path/to/your/mcp-proxy",
      "args": ["http://localhost:8000/prefix/mcp"],
      "cwd": "/path/to/devops-fastapi-mcp-template",
      "env": {
        "PYTHONPATH": "/path/to/your/mcp"
      }
    }
  }
}
```

#### Step-by-step configuration:

1. **Verify mcp-proxy installation**:
   ```bash
   mcp-proxy --version
   ```

2. **Locate your mcp.json file**:
   - **Cursor**: `~/.cursor/mcp.json`
   - **Other editors**: Check specific documentation

3. **Adjust paths**:
   - `command`: Path to your mcp-proxy installation
   - `cwd`: Your project working directory
   - `env.PYTHONPATH`: Path to your MCP environment (if applicable)

4. **Verify endpoint**:
   - MCP server will be available at: `http://localhost:8000/prefix/mcp`
   - Make sure your application is running

5. **Restart your editor** to load the new configuration

## 📋 Main Dependencies

- **FastAPI**: Main web framework
- **uvicorn**: ASGI server
- **fastapi-mcp**: MCP integration
- **ccxt**: Exchange market data
- **pandas / pandas-ta**: Indicator computation
- **slowapi**: Rate limiting
- **PyYAML**: YAML file handling

  
**Note**: This is a base template. Customize according to your project's specific needs.
