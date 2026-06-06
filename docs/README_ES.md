# DevOps FastAPI MCP Template

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README.md) [![Español](https://img.shields.io/badge/lang-Español-red.svg)](README_ES.md)

Un template completo para crear APIs FastAPI integradas con MCP (Model Context Protocol), diseñado para facilitar el desarrollo de aplicaciones escalables con buenas prácticas de DevOps.

## 🚀 Características

- **FastAPI**: Framework web moderno y rápido para Python
- **MCP Integration**: Integración nativa con Model Context Protocol usando `fastapi-mcp`
- **Estructura Modular**: Organización clara con controladores, rutas y servicios
- **Docker Ready**: Configuración completa para contenedores
- **Development Tools**: Hot reload, debugging y logging configurado
- **Health Checks**: Endpoints de salud y liveness
- **CORS**: Configuración de CORS para desarrollo
- **PDM**: Gestión moderna de dependencias

## 📁 Estructura del Proyecto

```
src/
├── controllers/          # Lógica de negocio
│   ├── codes/           # Ejemplo de controlador
│   └── healthy_controller.py
├── routes/              # Definición de rutas
│   ├── healthy.py       # Health checks
│   └── v1/              # API versioning
│       └── code_routing.py
├── main.py              # Punto de entrada principal
├── web_server.py        # Configuración de FastAPI
├── mcp_server.py        # Configuración de MCP
└── log_conf.yaml        # Configuración de logging
```

## 🛠️ Instalación

### Prerrequisitos

- Python 3.10+
- PDM (Python Dependency Manager)
- Docker y Docker Compose (opcional)

### Configuración Local

1. **Clonar el repositorio**
   ```bash
   git clone <your-repo-url>
   cd devops-fastapi-mcp-template
   ```

2. **Instalar dependencias**
   ```bash
   pdm install
   ```

3. **Configurar variables de entorno**
   ```bash
   cp .env.example .env  # Si existe
   # Editar .env con tu configuración
   ```

4. **Ejecutar en modo desarrollo**
   ```bash
   pdm run dev
   ```

La aplicación estará disponible en `http://localhost:3000`

## 🐳 Docker

### Desarrollo con Docker

```bash
docker-compose up --build
```

La aplicación estará disponible en `http://localhost:8000`

### Debugging con Docker

El template incluye configuración para debugging remoto en el puerto `5678`.

## 📡 API Endpoints

### Health Checks

- `GET /prefix/healthy` - Health check básico
- `GET /prefix/liveness` - Liveness probe

### API v1

- `GET /prefix/v1/codes/get/{code}` - Ejemplo de endpoint
- `GET /prefix/v1/metrics/get?symbol=BTC/USDT&exchange=binance&timeframe=1h&limit=500` - Métricas e indicadores técnicos

### Documentación

- `GET /prefix/docs` - Swagger UI
- `GET /prefix/openapi.json` - OpenAPI schema

## ⚙️ Configuración

### Variables de Entorno

Ver [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md) para la documentación completa de todas las variables de entorno disponibles.

### Logging

El logging usa la librería estándar `logging` de Python con un formatter JSON estructurado (ver `src/web_server.py`); config base en `src/log_conf.yaml`.

## 🔧 Desarrollo

### Comandos PDM Disponibles

```bash
# Desarrollo con hot reload
pdm run dev

# Actualizar dependencias
pdm run update-all

# Exportar requirements.txt
pdm run export
```

### Estructura de Controladores y Rutas

```python
# controllers/example/example_controller.py
async def your_function(param: str):
    # Tu lógica de negocio aquí
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

### Agregar Nuevas Rutas

1. Crear controlador en `controllers/`
2. Definir rutas en `routes/v1/`
3. Importar en `routes/__init__.py`

## 🧪 MCP Integration

Este template incluye integración con MCP (Model Context Protocol) a través de `fastapi-mcp`:

```python
# src/mcp_server.py
from fastapi_mcp import FastApiMCP

def start_mcp(app):
    mcp = FastApiMCP(app)
    mcp.setup_server()
    mcp.mount()
```

> **⚠️ Nota importante sobre fastapi-mcp**: 
> 
> La librería original de [fastapi_mcp](https://github.com/tadata-org/fastapi_mcp) tiene un bug conocido relacionado con el manejo del parámetro `root_path` de FastAPI ([PR #163](https://github.com/tadata-org/fastapi_mcp/pull/163)). Este bug causa que las rutas no funcionen correctamente cuando se usa un `root_path` diferente de `/` (como `/prefix` en este template).
> 
> **Solución**: Este template utiliza el fork de [@am1ter](https://github.com/am1ter) disponible en [am1ter/fastapi_mcp](https://github.com/am1ter/fastapi_mcp/tree/main) que incluye la corrección para este problema.

### Configuración para Editores de Código con IA

Para usar este servidor MCP con editores como **Cursor**, necesitas tener instalado [mcp-proxy](https://pypi.org/project/mcp-proxy/) en tu sistema.

#### Prerrequisitos:

1. **Instalar mcp-proxy** desde PyPI:
   ```bash
   pip install mcp-proxy
   ```
   
   > **Requisitos**: Python >=3.10
   
   > **Nota**: mcp-proxy es una herramienta que permite cambiar entre transportes de servidor MCP, facilitando la comunicación entre editores de código con IA y servidores MCP remotos.

#### Configuración:

Agrega la siguiente configuración a tu archivo `mcp.json`:

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

#### Configuración paso a paso:

1. **Verificar instalación de mcp-proxy**:
   ```bash
   mcp-proxy --version
   ```

2. **Ubicar tu archivo mcp.json**:
   - **Cursor**: `~/.cursor/mcp.json`
   - **Otros editores**: Consulta la documentación específica

3. **Ajustar las rutas**:
   - `command`: Ruta a tu instalación de mcp-proxy
   - `cwd`: Directorio de trabajo de tu proyecto
   - `env.PYTHONPATH`: Ruta a tu entorno MCP (si aplica)

4. **Verificar el endpoint**:
   - El servidor MCP estará disponible en: `http://localhost:8000/prefix/mcp`
   - Asegúrate de que tu aplicación esté ejecutándose

5. **Reiniciar tu editor** para que tome la nueva configuración

## 🧾 Esquema de Salida `/v1/metrics/get`

```jsonc
{
  "exchange": "binance",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "timestamp": "2025-07-31T12:34:56.789Z",
  "indicators": {
    "rsi14": 45.3,
    "adx14": 28.0,
    "bbwp": 2.5,
    "bbwp_ma4": 2.1,
    "ao": 1234.5,
    "sma50": 64000.2,
    "ema50": 63980.4,
    "sma200": 61000.8,
    "ema200": 61234.1,
    "konkorde_value": 120000.0,
    "konkorde_signal": "bullish"
  },
  "signals": {
    "signal": "entry",
    "reason": "RSI sobrevendido + tendencia + volumen comprador"
  }
}
```

## 📋 Dependencias Principales

- **FastAPI**: Framework web principal
- **uvicorn**: Servidor ASGI
- **fastapi-mcp**: Integración MCP
- **ccxt**: Datos de mercado de exchanges
- **pandas / pandas-ta**: Cálculo de indicadores
- **slowapi**: Rate limiting
- **PyYAML**: Manejo de archivos YAML

---

**Nota**: Este es un template base. Personaliza según las necesidades específicas de tu proyecto. 