# MMK — Matriz Broker × Activo (Bitget / Bitunix)

> Verificada contra APIs públicas en vivo el **11-jul-2026 ~21:55 UTC**. Cada símbolo citado apareció en la respuesta real del endpoint indicado (no de docs). Precios de ticker usados para identificar el activo real detrás del símbolo.

## Endpoints consultados (evidencia)

| Broker | Qué | Endpoint | Resultado |
|---|---|---|---|
| Bitget | Spot symbols | `GET api.bitget.com/api/v2/spot/public/symbols` | 1175 pares |
| Bitget | USDT-perps | `GET api.bitget.com/api/v2/mix/market/contracts?productType=usdt-futures` | 697 contratos |
| Bitget | Margin | `GET api.bitget.com/api/v2/margin/currencies` | 570 pares |
| Bitget | Tickers perp | `GET api.bitget.com/api/v2/mix/market/tickers?productType=usdt-futures` | identificación por precio |
| Bitget | OHLCV perp | `GET api.bitget.com/api/v2/mix/market/candles?symbol=XAUUSDT&productType=usdt-futures&granularity=1H` | ✅ velas devueltas |
| Bitget | OHLCV spot | `GET api.bitget.com/api/v2/spot/market/candles?symbol=PAXGUSDT&granularity=1h` | ✅ velas devueltas |
| Bitunix | Futures pairs | `GET fapi.bitunix.com/api/v1/futures/market/trading_pairs` | 664 contratos |
| Bitunix | Spot pairs | `GET openapi.bitunix.com/api/spot/v1/common/coin_pair/list` | 840 pares |
| Bitunix | Tickers futures | `GET fapi.bitunix.com/api/v1/futures/market/tickers?symbols=...` | identificación por precio |
| Bitunix | OHLCV futures | `GET fapi.bitunix.com/api/v1/futures/market/kline?symbol=BTCUSDT&interval=1h` | ✅ velas devueltas |
| Bitunix | OHLCV spot | `GET openapi.bitunix.com/api/spot/v1/market/kline?symbol=btcusdt&interval=60` | ✅ velas devueltas |

---

## ⚠️ Tres trampas de símbolo detectadas (identificación por precio de ticker)

| Símbolo | Parece | ES en realidad | Evidencia |
|---|---|---|---|
| `SPXUSDT` (ambos brokers) | S&P 500 | **Memecoin SPX6900** | last=$0.375 (el índice ≈ 7,000) |
| `COPUSDT` (Bitget) | Peso colombiano | **Acción ConocoPhillips** (página Bitget: "COPSTOCKUSDT Perpetual") | last=$109.41 (USD/COP ≈ 4,000) |
| `COPPERUSDT` (Bitunix) | — | **Cobre** (commodity) | last=$6.31 |

**USD/COP NO existe en ningún broker cripto de los dos. SP500 SÍ tiene proxy real: `SPYUSDT` (perp RWA del SPDR S&P 500 ETF, last=$757.9 ≈ SPY real).**

---

## Matriz BITGET (broker vivo hoy — ccxt ✅)

| Activo | Spot | Margin | USDT-perp | Lev. máx perp | Ticker (11-jul) | Vol 24h perp | Notas |
|---|---|---|---|---|---|---|---|
| BTC | `BTCUSDT` ✅ | cross 5x / iso 10x | `BTCUSDT` ✅ | **150x** | $64,312 | $846M | |
| ETH | `ETHUSDT` ✅ | cross 5x / iso 10x | `ETHUSDT` ✅ | **150x** | — | — | |
| SOL | `SOLUSDT` ✅ | cross 5x / iso 10x | `SOLUSDT` ✅ | **100x** | — | — | |
| Oro | `XAUTUSDT` / `PAXGUSDT` ✅ (oro tokenizado) | XAUT/PAXG 5x | `XAUUSDT` ✅ (RWA index) | **100x** | $4,114.98 | $9.6M | Perps alternos: XAUT 75x, PAXG 50x. Funding c/4h |
| Plata | `SLVONUSDT` (ETF SLV tokenizado Ondo) ⚠️ vol24h **$2.7k** — ilíquido | — | `XAGUSDT` ✅ (RWA index) | **100x** | $59.87 | $2.0M | No hay XAG spot. Funding c/4h |
| SP500 | `SPYONUSDT` (SPY tokenizado Ondo, 1:1 custodiado) ⚠️ vol24h **$5.9k** — ilíquido | — | `SPYUSDT` ✅ (RWA, trackea SPDR S&P 500 ETF) | **50x** | $757.91 | $628k | Funding c/8h. También QQQON/IVVON spot |
| USD/COP | ❌ | ❌ | ❌ (COPUSDT = ConocoPhillips, NO confundir) | — | — | — | **Señales-only** |
| Petróleo | ❌ | ❌ | `CLUSDT` ✅ (WTI, RWA index) | **100x** | $71.74 | **$42.8M** | El RWA más líquido. Funding c/4h |

- Los 3 símbolos que ya usa el dashboard (`CL/USDT:USDT`, `XAU/USDT:USDT`, `XAG/USDT:USDT` en notación ccxt = `CLUSDT`/`XAUUSDT`/`XAGUSDT`) **siguen vivos**: `symbolStatus: normal`, `offTime: -1`, ticker y velas respondiendo.
- Fees perps RWA: maker 0.02% / taker 0.06%, `minTradeUSDT: 5`.
- OHLCV: sí, público, sin key — spot y mix candles (hasta 1000 velas/llamada; histórico más viejo vía `/api/v2/mix/market/history-candles`).

## Matriz BITUNIX (ccxt ❌ — ver sección ccxt)

| Activo | Spot | USDT-perp | Lev. máx | **API-tradeable** (`isApiSupported`) | Ticker (11-jul) | Notas |
|---|---|---|---|---|---|---|
| BTC | `btcusdt` ✅ | `BTCUSDT` ✅ | **200x** | ✅ true | $64,321 | También BTCUSD 125x, BTCUSDC 125x |
| ETH | `ethusdt` ✅ | `ETHUSDT` ✅ | **200x** | ✅ true | — | |
| SOL | `solusdt` ✅ | `SOLUSDT` ✅ | **100x** | ✅ true | — | |
| Oro | `xautusdt`, `paxgusdt` ✅ | `XAUUSDT` 200x ❌ API / **`PAXGUSDT` 200x ✅ API** | 200x | XAU: **false** · PAXG: **true** | XAU $4,115 | Oro ejecutable por API SOLO vía PAXG perp |
| Plata | ❌ | `XAGUSDT` | 200x | ❌ **false** | $59.84 | Solo UI manual, no bot |
| SP500 | ❌ | `SPYUSDT` | 50x | ❌ **false** | $757.54 | Solo UI manual. `spxusdt` spot = memecoin |
| USD/COP | ❌ | ❌ | — | — | — | **Señales-only** |
| Petróleo | ❌ | `CLUSDT` | 100x | ❌ **false** | $71.72 | vol $5.2M pero solo UI manual |

- **Hallazgo crítico**: los perps RWA de Bitunix (XAU, XAG, CL, SPY, COPPER) tienen `isApiSupported: false` → **un bot NO puede operarlos**. Para commodities/índices por API, **Bitget es el único broker ejecutable**.
- Margin: Bitunix no documenta producto margin en su OpenAPI (solo spot + futures).
- OHLCV: sí, público — futures kline (`fapi.bitunix.com/api/v1/futures/market/kline`) y spot kline verificados.

---

## ccxt — Bitunix

**NO soportado** a hoy (11-jul-2026):
- No existe `python/ccxt/bitunix.py` en `ccxt/ccxt` master (verificado: GitHub contents API → 404).
- Requests abiertos y marcados duplicados sin implementar: issues [#24729](https://github.com/ccxt/ccxt/issues/24729), [#26493](https://github.com/ccxt/ccxt/issues/26493), [#27215](https://github.com/ccxt/ccxt/issues/27215), [#28131](https://github.com/ccxt/ccxt/issues/28131).
- Bitget sí está en ccxt (ya en uso por mmk-mcp-indicadors).

### Spec del adapter propio Bitunix (para mmk-brokers, Go) — si se decide integrarlo

- **Base URL futures**: `https://fapi.bitunix.com` (público sin firma: `trading_pairs`, `tickers`, `kline`, `depth`, `funding_rate`).
- **Headers firmados**: `api-key`, `nonce` (random 32-bit string), `timestamp` (ms UTC), `sign`, `Content-Type: application/json`.
- **Firma (doble SHA-256)**:
  1. `digest = SHA256(nonce + timestamp + api-key + queryParamsOrdenadosASCII + bodyJSONsinEspacios)`
  2. `sign = SHA256(digest + secretKey)`
- **Endpoints REST a firmar** (docs `bitunix.com/api-docs/futures/`):
  - `POST /api/v1/futures/trade/place_order` — body: `symbol`, `side` (BUY/SELL), `qty` (base coin, string), `price` (LIMIT), `orderType` (LIMIT/MARKET), **`clientId`** ← soporta el clientOrderId determinista del diseño mmk ✅
  - `POST /api/v1/futures/trade/cancel_orders`
  - `GET /api/v1/futures/position/get_pending_positions`
  - `GET /api/v1/futures/account` (balance)
- Rate limit público: 10 req/s/IP (trading_pairs).
- **Costo/beneficio**: dado que sus RWA no son API-tradeables, el adapter solo aportaría majors (BTC/ETH/SOL/PAXG) con leverage 200x — irrelevante para perfiles de 5x/10x. **Recomendación: diferir el adapter Bitunix; F2 arranca Bitget-only.**

---

## SP500 y USD/COP — resolución

| Activo | Veredicto | Ejecución | Datos para señales (gratis) |
|---|---|---|---|
| **SP500** | SÍ ejecutable vía proxy | `SPYUSDT` perp Bitget 50x (RWA del SPDR S&P 500 ETF, vol $628k/d, 24/7); spot `SPYONUSDT` existe pero ilíquido ($5.9k/d) | El propio perp Bitget da OHLCV 24/7 por la misma API que el resto → **cero código extra**. Índice puro si se quiere: yfinance `^GSPC` / `SPY`, stooq `^spx` (diario, gratis) |
| **USD/COP** | NO existe en ningún broker → **señales-only** | — | 1) **TRM oficial**: `datos.gov.co` Socrata API (dataset TRM `32sa-8pi3`), diaria, sin API key, oficial Colombia. 2) yfinance `COP=X` (diario sólido; intradía 1h limitado a ~2 años). 3) stooq `usdcop` CSV diario gratis. Límite común: es par forex → **solo TF 1d confiable** (sin 1h/4h de calidad gratis; mercado cerrado fines de semana) → solo perfil Ancient |

---

## Tabla resumen final

| Activo | Ancient 0x (spot) | Pro 5x (perp) | Snipper 10x (perp) | Broker ejecutor |
|---|---|---|---|---|
| BTC | `BTCUSDT` spot | `BTCUSDT` perp (150x disp.) | ídem | Bitget (Bitunix opcional) |
| ETH | `ETHUSDT` spot | `ETHUSDT` perp (150x) | ídem | Bitget (Bitunix opcional) |
| SOL | `SOLUSDT` spot | `SOLUSDT` perp (100x) | ídem | Bitget (Bitunix opcional) |
| Oro | `XAUTUSDT` o `PAXGUSDT` spot | `XAUUSDT` perp (100x) | ídem | Bitget |
| Plata | ⚠️ sin spot líquido → perp 1x o señales-only en Ancient | `XAGUSDT` perp (100x) | ídem | Bitget |
| SP500 | ⚠️ `SPYONUSDT` ilíquido → perp 1x o señales-only en Ancient | `SPYUSDT` perp (50x) | ídem | Bitget |
| Petróleo | sin spot → perp 1x o señales-only en Ancient | `CLUSDT` perp (100x) | ídem | Bitget |
| USD/COP | **señales-only** (TRM datos.gov.co / yfinance `COP=X`) | señales-only | señales-only | — |

**Recomendaciones cerradas:**
1. **Bitget = broker ejecutor único para F2**: cubre los 7 activos ejecutables por API con leverage ≥10x, ya está en ccxt y ya lo usa la plataforma. Bitunix queda como diversificación futura de contraparte para majors (adapter propio requerido, RWA no operables por API) — **diferir**.
2. Perfil Ancient estricto (spot puro): BTC, ETH, SOL, oro (XAUT/PAXG). Plata/SP500/petróleo no tienen spot líquido → o se aceptan como **perp 1x** (ojo: funding c/4h ≈ costo de carry que el spot no tiene) o quedan señales-only para ese perfil.
3. Pro (5x) y Snipper (10x): los 7 activos vía perps Bitget — todos con leverage máximo ≥50x, sobra margen.
4. **Señales-only definitivo: USD/COP** (solo TF 1d, fuente TRM oficial gratis).
5. Anti-gotcha para `watchlist`/`constants.ts`: **prohibir `SPXUSDT` y `COPUSDT`** como proxies de índice/forex (memecoin y acción ConocoPhillips respectivamente).
