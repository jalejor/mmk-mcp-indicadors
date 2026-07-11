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
| **Binance** | Spot symbols | `GET api.binance.com/api/v3/exchangeInfo` | 3635 pares (HTTP 200 desde local CO) |
| **Binance** | USDT-M futures | `GET fapi.binance.com/fapi/v1/exchangeInfo` | 832 símbolos (HTTP 200 desde local CO) |
| **Binance** | Tickers perp | `GET fapi.binance.com/fapi/v1/ticker/24hr?symbol=...` | identificación + liquidez |
| **Binance** | OHLCV spot/perp | `GET api.binance.com/api/v3/klines` · `GET fapi.binance.com/fapi/v1/klines` | ✅ velas devueltas |
| **Binance** | Geo-block probe | `GET api.binance.com/api/v3/ping` · `GET fapi.binance.com/fapi/v1/ping` | HTTP 200 desde local CO (ver caveat) |
| **Binance** | P2P USDT/COP | `POST p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search` (no oficial) | 292 anuncios, ~3243 COP/USDT |

---

## ⚠️ Trampas de símbolo detectadas (identificación por precio de ticker)

| Símbolo | Parece | ES en realidad | Evidencia |
|---|---|---|---|
| `SPXUSDT` (Bitget, Bitunix, **Binance**) | S&P 500 | **Memecoin SPX6900** | last=$0.375 en los 3 (el índice ≈ 7,000) |
| `COPUSDT` (Bitget) | Peso colombiano | **Acción ConocoPhillips** (página Bitget: "COPSTOCKUSDT Perpetual") | last=$109.41 (USD/COP ≈ 3,200–4,000) |
| `COPPERUSDT` (Bitunix) | — | **Cobre** (commodity) | last=$6.31 |
| `SPYBUSDT` (Binance spot) | SPY? | token distinto (no es el ETF SPY) — NO usar | aparece en spot exchangeInfo |

**Familia S&P 500 — tres símbolos distintos que trackean el MISMO subyacente (S&P 500), NO confundir:**
- `SPYUSDT` = ETF SPDR SPY (precio ~$757, share del ETF) — el más líquido.
- `VOOUSDT` = ETF Vanguard VOO (precio ~$691, share del ETF) — **existe solo en Bitget, el MENOS líquido**.
- `SP500USDT` = índice directo (precio ~7,579 = puntos del índice) — solo Bitget.

**USD/COP NO existe como par spot/perp en ningún broker; lo más cercano es el mercado P2P USDT/COP de Binance (ver Pista A).**

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

## Matriz BINANCE (ccxt ✅ · ⚠️ geo-block desde cloud US)

> **Gran hallazgo 2026**: Binance ya lista **TradFi perpetuals** (`contractType: TRADIFI_PERPETUAL`) para oro, plata, petróleo y S&P 500 — con liquidez muy superior a los RWA de Bitget. Esto supera el estado histórico (los stock tokens de 2021 fueron delistados; hoy son perps sintéticos nuevos). Todos verificados vivos (`status: TRADING`) e identificados por precio de ticker.

| Activo | Spot | USDT-perp (contractType) | Ticker (11-jul) | Vol 24h perp | Notas |
|---|---|---|---|---|---|
| BTC | `BTCUSDT` ✅ | `BTCUSDT` (PERPETUAL) | $64,325 | — | Lev máx 125x (docs) |
| ETH | `ETHUSDT` ✅ | `ETHUSDT` (PERPETUAL) | — | — | Lev máx 125x |
| SOL | `SOLUSDT` ✅ | `SOLUSDT` (PERPETUAL) | — | — | Lev máx ~100x |
| Oro | `PAXGUSDT` ✅ ($4,103, vol $1.7M) · `XAUTUSDT` ✅ | `PAXGUSDT` (PERPETUAL, $4,101, vol $12M) · **`XAUUSDT` (TRADIFI_PERPETUAL, $4,115, vol $145M)** | $4,115 | **XAU TradFi = el oro más líquido de los 3 brokers** |
| Plata | ❌ | **`XAGUSDT` (TRADIFI_PERPETUAL)** | $59.86 | **$20.4M** | Sin spot; perp muy líquido |
| SP500 | ❌ (`SPYBUSDT` es otro token) | **`SPYUSDT` (TRADIFI_PERPETUAL)** | $757.32 | **$14.3M** | Trackea SPDR S&P 500 ETF. No hay VOO en Binance |
| USD/COP | ❌ par spot; ✅ **mercado P2P USDT/COP** (ver Pista A) | ❌ | ~3,243 COP/USDT (P2P) | — | Señales-only (P2P/TRM) |
| Petróleo | ❌ | **`CLUSDT` (TRADIFI_PERPETUAL)** | $71.92 | **$67.4M** | WTI; el más líquido de los brokers |

- **Todos los TradFi perps (XAU/XAG/CL/SPY) son ejecutables por API** (a diferencia de Bitunix, que los marca `isApiSupported: false`). Con la salvedad geográfica de abajo, Binance es hoy el broker con mejor liquidez y mayor cobertura API-tradeable de commodities/índices.
- Leverage: `GET /fapi/v1/leverageBracket` requiere firma (HTTP 401 sin key) → no expuesto público. Majors 125x por docs; los TradFi perps tienen tope menor (docs), pero **≥10x sobra para los 3 perfiles** (Ancient 0x / Pro 5x / Snipper 10x).
- OHLCV: público sin key, spot (`/api/v3/klines`) y perp (`/fapi/v1/klines`), hasta 1500 velas/llamada + `startTime/endTime` para histórico profundo. Verificado.
- **ccxt**: soportado (trivial) — `python/ccxt/binance.py` presente en master (HTTP 200). Cubre spot, USDT-M y COIN-M.

### ⚠️ CAVEAT GEO-BLOCK (crítico para F2/F3)

- **Desde local (Colombia)**: `api.binance.com` y `fapi.binance.com` responden **HTTP 200** — toda la data de esta sección se obtuvo así.
- **Desde nuestra infra cloud (Cloud Run `us-west1`, IP US)**: Binance responde **HTTP 451** (Unavailable For Legal Reasons) — **NO alcanzable**. El watcher/executor mmk que corre en `suideaweb-two/us-west1` **no puede llamar a Binance**.
- Mitigación posible (mismo costo $0): correr el Cloud Run Job del executor en **región no-US** (`southamerica-east1` São Paulo o `southamerica-west1` Santiago). Cambia solo la región del Job, no el precio. ⚠️ **Sin verificar**: que Binance derivatives no bloquee también esas jurisdicciones — hay que probar la IP real de esa región antes de comprometerse. Alternativa robusta: proxy de salida, pero eso sí puede costar → avisar antes.

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

## Pistas del owner — resueltas

### Pista A — "COP USDT existe"

**Qué es exactamente:** NO hay par **spot** `COPUSDT` en Binance (ni en Bitget/Bitunix como peso). El `COPUSDT` de Bitget es la acción **ConocoPhillips** (trampa ya documentada). Lo que el owner ve es el **mercado P2P USDT/COP de Binance** (fiat colombiano):
- Verificado vivo: `POST p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search` con `{"asset":"USDT","fiat":"COP","tradeType":"BUY"}` → **292 anuncios**, precio ~**3,243–3,245 COP/USDT**.
- Endpoint **no oficial** (interno del sitio P2P, sin documentar, sin garantía de estabilidad ni SLA), pero público y sin firma.
- `Binance Convert` (`/sapi/v1/convert/exchangeInfo`) responde 200 pero cotizar requiere key → no sirve como fuente pública.

**¿Sirve para señales USD/COP?** Parcialmente:
- Da un **precio spot de mercado** de USDT≈USD contra COP, pero **NO entrega OHLCV/velas** — es un order-book de anuncios P2P. Para una serie habría que **pollear y construir las velas nosotros** (y el precio carga una **prima P2P** + varía por método de pago/monto, diverge de la tasa interbancaria).
- **Recomendación**: para la señal canónica de USD/COP usar **TRM oficial** (`datos.gov.co` Socrata, dataset TRM `32sa-8pi3`, diaria, sin key, con histórico) como fuente OHLCV; usar el **P2P de Binance como cross-check spot en vivo** (útil para ver la prima cripto vs TRM), no como serie histórica.
- Sigue siendo **señales-only** (sin ejecución) y solo **TF 1d** confiable.

### Pista B — "El de SP500 es Vanguard como commodity"

**Confirmado: el owner tiene razón.** Existe `VOOUSDT` = **Vanguard S&P 500 ETF (VOO)** como perp en **Bitget** (`base: VOO`, listado en el productType usdt-futures / categoría "commodities" del broker):
- Verificado: `GET api.bitget.com/api/v2/mix/market/contracts?productType=usdt-futures` → `VOOUSDT`, lev **20x**, funding 8h, `symbolStatus: normal`, last $691.42.
- **PERO es el proxy S&P 500 MENOS líquido**: vol 24h = **$18.8k** (ilíquido). No existe en Bitunix ni Binance.

**Comparativa de los 3 proxies S&P 500 (todos trackean el mismo índice):**

| Símbolo | Qué trackea | Broker | Lev | Vol 24h | Precio |
|---|---|---|---|---|---|
| `VOOUSDT` | ETF Vanguard VOO | Bitget | 20x | **$18.8k** ⚠️ ilíquido | $691 |
| `SP500USDT` | índice directo | Bitget | 50x | $127k | 7,579 |
| `SPYUSDT` | ETF SPDR SPY | Bitget | 50x | $622k | $758 |
| **`SPYUSDT`** | ETF SPDR SPY | **Binance** (TradFi) | ≥10x | **$14.3M** 🏆 | $757 |

**Recomendación SP500**: usar **`SPYUSDT`** como instrumento — no VOO. Para ejecución desde cloud US, `SPYUSDT` de **Bitget** (más líquido de su familia, alcanzable, en ccxt). Si se resuelve el geo-block, `SPYUSDT` de **Binance** es 20x más profundo. **VOOUSDT queda descartado** por liquidez (18.8k/d = slippage alto, riesgo de no poder salir). Datos de señal puros si se quiere: yfinance `^GSPC`/`SPY`, stooq `^spx` (diario, gratis).

---

## Tabla resumen final (3 brokers)

| Activo | Ancient 0x (spot) | Pro 5x / Snipper 10x (perp) | Broker recomendado (ejecución) | Mejor liquidez |
|---|---|---|---|---|
| BTC | `BTCUSDT` (los 3) | `BTCUSDT` perp (Bitget 150x / Binance 125x / Bitunix 200x) | **Bitget** (alcanzable cloud) o Binance (si no-US) | Binance |
| ETH | `ETHUSDT` (los 3) | `ETHUSDT` perp (150/125/200x) | Bitget o Binance | Binance |
| SOL | `SOLUSDT` (los 3) | `SOLUSDT` perp (100x) | Bitget o Binance | Binance |
| Oro | `PAXGUSDT`/`XAUTUSDT` spot | `XAUUSDT` perp (Bitget 100x / Binance TradFi) | Bitget (o Binance XAU si no-US, $145M vol) | **Binance XAU** |
| Plata | ⚠️ sin spot líquido | `XAGUSDT` perp (Bitget 100x / Binance TradFi $20M) | Bitget (Binance si no-US) | Binance |
| SP500 | ⚠️ sin spot líquido (VOO/SPYON ilíquidos) | `SPYUSDT` perp (Bitget 50x $622k / Binance TradFi $14M) — **NO VOO** | Bitget SPY (Binance SPY si no-US) | Binance |
| Petróleo | sin spot | `CLUSDT` perp (Bitget 100x / Binance TradFi $67M) | Bitget (Binance si no-US) | Binance |
| USD/COP | **señales-only** (TRM datos.gov.co + cross-check P2P Binance) | señales-only | — | — |

**Recomendaciones cerradas (actualizadas con Binance):**

1. **F2 (paper) sigue siendo Bitget-first, pero por una razón nueva: el geo-block.** Binance tiene mejor liquidez en todo y **testnet oficial** para paper (`testnet.binance.vision` / `testnet.binancefuture.com`, gratis), lo que lo haría el candidato ideal. **Pero desde Cloud Run us-west1 (IP US) Binance da 451.** Opciones:
   - **(a) Bitget-only en us-west1** (statu quo): cero fricción, alcanzable, en ccxt, cubre los 7 activos API-tradeables. **Recomendado para arrancar F2.**
   - **(b) Binance desde Cloud Run región no-US** (`southamerica-east1`/`-west1`): mismo costo $0, desbloquea testnet + liquidez superior + XAU/XAG/CL/SPY TradFi ejecutables. **Requiere verificar primero** que la IP de esa región no esté también bloqueada por Binance derivatives (probar `fapi.binance.com/fapi/v1/ping` desde un Job en esa región antes de comprometerse). Si funciona, es upgrade claro para F3.
   - Como F2 son fills SIMULADOS (no toca dinero), la data de velas puede venir de Bitget aunque se modele el broker Binance — el geo-block solo muerde en F3 (ejecución real). **Decisión operativa: F2 con velas Bitget; evaluar región no-US para Binance en el gate F2→F3.**
2. Perfil Ancient estricto (spot puro): BTC, ETH, SOL, oro (PAXG/XAUT en cualquiera de los 3). Plata/SP500/petróleo no tienen spot líquido → perp 1x (ojo funding c/4h como carry) o señales-only en Ancient.
3. Pro (5x) y Snipper (10x): los 7 activos por perp; leverage sobra en los 3 brokers.
4. **Señales-only definitivo: USD/COP** — TRM oficial (datos.gov.co) como serie; P2P Binance como cross-check spot de la prima cripto. Solo TF 1d.
5. **SP500 = `SPYUSDT`, NO `VOOUSDT`** (VOO existe en Bitget pero vol $18.8k/d = descartado por liquidez).
6. Anti-gotcha `watchlist`/`constants.ts` — **prohibir**: `SPXUSDT` (memecoin SPX6900, en los 3 brokers), `COPUSDT` Bitget (ConocoPhillips), `VOOUSDT` (ilíquido), `SPYBUSDT` Binance (token distinto). Los válidos de índice: `SPYUSDT`.
7. **Bitunix**: sin ccxt y con RWA no API-tradeables → sigue diferido (solo aporta majors). Prioridad de contraparte futura: **Binance no-US > Bitunix**.
