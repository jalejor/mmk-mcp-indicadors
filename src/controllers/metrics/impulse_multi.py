"""Round 7 (docs/PREREG_IMPULSOS_v2_r7.md): multi-asset replication statistics.

Pure functions over closed ledger trades (`impulse_backtest.LedgerTrade`, duck-typed:
`r_net`, `cluster = "<symbol>|<YYYY-MM>"`, `block`, `pnl_net_usdt`, `entry_time`).
Nothing here produces a trade: it only scores pooled cells across assets and
corrects the GO decision for the number of cells looked at.

* `p_positive`: one-sided cluster-bootstrap p-value for "mean net R > 0" — the share
  of resampled means <= 0, same resampling scheme (clusters = symbol x month, 10 000
  resamples, seed 42) as `fep_cont_backtest.cluster_bootstrap_ci`.
* `holm`: step-down Holm-Bonferroni (family-wise alpha) for the PRIMARY family.
* `benjamini_hochberg`: BH step-up (false discovery rate q) for the per-asset family.
* `pooled_drawdown`: max drawdown of the cumulative net USDT of a pooled cell as a %
  of the POOLED start (one book per asset).
* `per_symbol_breakdown` / `leave_one_out`: which assets add to / subtract from a
  pooled cell (descriptive).
* `verdict_r7`: the round-4 mechanical gate AND the corrected p-value.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 42
PRIMARY_ALPHA = 0.05  # Holm, pooled primary family
ASSET_Q = 0.10  # Benjamini-Hochberg, per-asset family


def symbol_of(trade: Any) -> str:
    return str(trade.cluster).split("|", 1)[0]


def cluster_bootstrap_means(trades: Sequence[Any], *, resamples: int = BOOTSTRAP_RESAMPLES,
                            seed: int = BOOTSTRAP_SEED) -> np.ndarray:
    """Resampled means of net R, drawing (symbol, month) clusters with replacement."""
    rs = np.array([float(t.r_net) for t in trades], dtype=float)
    idx: Dict[str, List[int]] = {}
    for i, t in enumerate(trades):
        idx.setdefault(str(t.cluster), []).append(i)
    keys = sorted(idx)
    sums = np.array([rs[idx[k]].sum() for k in keys])
    counts = np.array([len(idx[k]) for k in keys])
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(keys), size=(resamples, len(keys)))
    return sums[picks].sum(axis=1) / np.maximum(counts[picks].sum(axis=1), 1)


def p_positive(trades: Sequence[Any], *, resamples: int = BOOTSTRAP_RESAMPLES,
               seed: int = BOOTSTRAP_SEED) -> Optional[float]:
    """One-sided p for H1 "mean net R > 0": share of bootstrap means <= 0 (floored at 1/resamples).
    None when fewer than 2 clusters (the resampling is degenerate)."""
    if len({str(t.cluster) for t in trades}) < 2:
        return None
    boot = cluster_bootstrap_means(trades, resamples=resamples, seed=seed)
    return float(max((boot <= 0.0).mean(), 1.0 / resamples))


def _ordered(pvals: Mapping[str, Optional[float]]) -> List[str]:
    """Keys sorted by p ascending; untestable cells (None) count as p = 1 so they stay in m."""
    return sorted(pvals, key=lambda k: (1.0 if pvals[k] is None else pvals[k], k))


def holm(pvals: Mapping[str, Optional[float]], alpha: float = PRIMARY_ALPHA) -> Dict[str, Dict[str, Any]]:
    """Holm step-down: p_(i) adjusted = max_{j<=i} min(1, (m - j + 1) p_(j)); reject iff adjusted < alpha.
    m = number of cells in the family (None p = untestable, counted in m, never rejected)."""
    keys = _ordered(pvals)
    m = len(keys)
    out: Dict[str, Dict[str, Any]] = {}
    running = 0.0
    for i, k in enumerate(keys):
        p = pvals[k]
        raw = 1.0 if p is None else p
        running = max(running, min(1.0, (m - i) * raw))
        out[k] = {"p": p, "p_adj": None if p is None else round(running, 6), "m": m, "method": "holm",
                  "reject": p is not None and running < alpha}
    return out


def benjamini_hochberg(pvals: Mapping[str, Optional[float]], q: float = ASSET_Q) -> Dict[str, Dict[str, Any]]:
    """BH step-up: q_(i) = min_{j>=i} min(1, m p_(j) / j); discovery iff q-value < q.
    m counts every cell of the family (None p = untestable, counted, never a discovery)."""
    keys = _ordered(pvals)
    m = len(keys)
    adj = [0.0] * m
    running = 1.0
    for i in range(m - 1, -1, -1):
        p = pvals[keys[i]]
        raw = 1.0 if p is None else p
        running = min(running, min(1.0, m * raw / (i + 1)))
        adj[i] = running
    return {k: {"p": pvals[k], "q_value": None if pvals[k] is None else round(adj[i], 6), "m": m, "method": "bh",
                "reject": pvals[k] is not None and adj[i] < q} for i, k in enumerate(keys)}


def pooled_drawdown(trades: Sequence[Any], start_total: float) -> Dict[str, float]:
    """Max drawdown of the cumulative NET USDT of the pooled trades, % of the pooled start."""
    eq = peak = dd = 0.0
    for t in sorted(trades, key=lambda t: str(t.entry_time)):
        eq += float(t.pnl_net_usdt)
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return {"max_drawdown_usdt": round(dd, 2), "max_drawdown_pct_initial": round(dd / start_total * 100.0, 2) if start_total else 0.0,
            "pnl_net_usdt": round(eq, 2), "start_total_usdt": round(start_total, 2)}


def _mean(xs: Iterable[float]) -> Optional[float]:
    xs = list(xs)
    return round(sum(xs) / len(xs), 4) if xs else None


def per_symbol_breakdown(trades: Sequence[Any], oos_block: str) -> Dict[str, Dict[str, Any]]:
    """n, sum R, expectancy (all / OOS) and net USDT per asset inside a pooled cell."""
    out: Dict[str, Dict[str, Any]] = {}
    for sym in sorted({symbol_of(t) for t in trades}):
        st = [t for t in trades if symbol_of(t) == sym]
        oos = [t for t in st if t.block == oos_block]
        out[sym] = {"n": len(st), "n_oos": len(oos), "sum_r": round(sum(float(t.r_net) for t in st), 3),
                    "exp_r": _mean(float(t.r_net) for t in st), "exp_oos": _mean(float(t.r_net) for t in oos),
                    "pnl_net_usdt": round(sum(float(t.pnl_net_usdt) for t in st), 2)}
    return out


def leave_one_out(trades: Sequence[Any], oos_block: str) -> Dict[str, Dict[str, Any]]:
    """Pooled expectancy (all / OOS) WITHOUT each asset, and the asset's sign of contribution:
    `adds` iff removing it lowers the pooled expectancy (its own mean R is above the pool's)."""
    pooled = _mean(float(t.r_net) for t in trades)
    out: Dict[str, Dict[str, Any]] = {}
    for sym in sorted({symbol_of(t) for t in trades}):
        rest = [t for t in trades if symbol_of(t) != sym]
        exp_wo = _mean(float(t.r_net) for t in rest)
        out[sym] = {"n_without": len(rest), "exp_without": exp_wo,
                    "exp_oos_without": _mean(float(t.r_net) for t in rest if t.block == oos_block),
                    "adds": None if exp_wo is None or pooled is None else exp_wo < pooled}
    return out


def verdict_r7(verdict_r4: Mapping[str, Any], corrected: Optional[Mapping[str, Any]], *, label: str) -> Dict[str, Any]:
    """GO iff the round-4 mechanical gate is GO AND the corrected p rejects (Holm alpha or BH q).
    INCONCLUSIVE stays INCONCLUSIVE; GO without a rejection = NO-GO (multiple comparisons)."""
    base = verdict_r4["verdict"]
    if base != "GO":
        return {"verdict": base, "failed": list(verdict_r4.get("failed", [])), "family": label}
    if corrected is None:
        return {"verdict": "NO-GO", "failed": ["not in a corrected family"], "family": label}
    if corrected.get("reject"):
        return {"verdict": "GO", "failed": [], "family": label}
    key = "p_adj" if corrected.get("method") == "holm" else "q_value"
    return {"verdict": "NO-GO", "failed": [f"{key}={corrected.get(key)} (multiple comparisons, m={corrected.get('m')})"], "family": label}


__all__ = [
    "ASSET_Q", "BOOTSTRAP_RESAMPLES", "BOOTSTRAP_SEED", "PRIMARY_ALPHA", "benjamini_hochberg", "cluster_bootstrap_means",
    "holm", "leave_one_out", "p_positive", "per_symbol_breakdown", "pooled_drawdown", "symbol_of", "verdict_r7",
]
