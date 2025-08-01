# Variables de Entorno

Este documento describe todas las variables de entorno disponibles para configurar la aplicación.

## 🔧 Configuración de la Aplicación

### Variables Principales

| Variable     | Descripción                    | Valor por Defecto | Requerida |
| ------------ | ------------------------------ | ----------------- | --------- |
| `DD_SERVICE` | Nombre del servicio            | `fastapi`         | No        |
| `DD_VERSION` | Versión del servicio           | `1.0.0`           | No        |
| `APP_ID`     | Identificador de la aplicación | `fastapi`         | No        |

### Variables de Entorno

| Variable     | Descripción                                | Valor por Defecto | Requerida |
| ------------ | ------------------------------------------ | ----------------- | --------- |
| `PY_ENV`     | Entorno de Python (development/production) | `development`     | No        |
| `PYTHON_ENV` | Alias para PY_ENV                          | `development`     | No        |
| `ASGI_ENV`   | Entorno ASGI (local/docker)                | `local`           | No        |

### Variables de Servidor

| Variable | Descripción         | Valor por Defecto | Requerida |
| -------- | ------------------- | ----------------- | --------- |
| `HOST`   | Host del servidor   | `0.0.0.0`         | No        |
| `PORT`   | Puerto del servidor | `8000`            | No        |

### Variables de Rutas

| Variable        | Descripción                 | Valor por Defecto | Requerida |
| --------------- | --------------------------- | ----------------- | --------- |
| `PREFIX_PATH`   | Prefijo base para rutas API | `/prefix`         | No        |
| `HEALTHY_PATH`  | Ruta para health checks     | `/healthy`        | No        |
| `LIVENESS_PATH` | Ruta para liveness probe    | `/liveness`       | No        |

### Variables de Umbrales de Indicadores

Los umbrales pueden definirse a nivel global o por símbolo.

| Variable | Descripción | Ejemplo | Valor por Defecto |
| -------- | ----------- | ------- | ----------------- |
| `RSI_OVERBOUGHT` | Nivel RSI para sobrecompra | `70` | 70 |
| `RSI_OVERSOLD` | Nivel RSI para sobreventa | `30` | 30 |
| `ADX_TREND` | Umbral ADX para considerar tendencia fuerte | `25` | 25 |
| `BBWP_HIGH` | BBWP alto (expansión volatilidad) | `4` | 4 |

Variables por símbolo: sustituir `/` por `_` y anteponer el símbolo, p.e.

```
BTC_USDT_RSI_OVERSOLD=28
ETH_USDT_RSI_OVERSOLD=25
```

Los umbrales por símbolo tienen prioridad sobre los globales.

### Variables de Logging

| Variable    | Descripción                                              | Valor por Defecto | Requerida |
| ----------- | -------------------------------------------------------- | ----------------- | --------- |
| `LOG_LEVEL` | Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO`            | No        |

## 📝 Ejemplos de Configuración

### Desarrollo Local

```bash
# .env
PY_ENV=development
PYTHON_ENV=development
ASGI_ENV=local
PORT=3000
HOST=localhost
DD_SERVICE=my-api
PREFIX_PATH=/api
LOG_LEVEL=DEBUG
```

### Producción

```bash
# .env
PY_ENV=production
PYTHON_ENV=production
ASGI_ENV=docker
PORT=8000
HOST=0.0.0.0
DD_SERVICE=production-api
DD_VERSION=1.2.0
LOG_LEVEL=INFO
```

### Docker

```bash
# docker-compose.yaml environment
PY_ENV=development
PYTHON_ENV=development
ASGI_ENV=docker
PORT=8000
HOST=0.0.0.0
LOG_LEVEL=INFO
```

> **⚠️ IMPORTANTE**: Nunca comitees archivos `.env` con información sensible al repositorio.

## 📋 Checklist de Configuración

- [ ] Crear archivo `.env` basado en `.env.example`
- [ ] Configurar `DD_SERVICE` con el nombre de tu servicio
- [ ] Configurar `DD_VERSION` con la versión correcta
- [ ] Ajustar `PREFIX_PATH` según tu arquitectura
- [ ] Verificar que las rutas de health checks sean correctas
- [ ] Configurar el nivel de logging apropiado
- [ ] Asegurar que `PY_ENV` y `PYTHON_ENV` estén sincronizados
- [ ] Configurar variables sensibles en un lugar seguro
