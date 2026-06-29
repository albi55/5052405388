# Two-Component Algorithmic Trading System

A research tool that hunts for trading edges with **honest** validation, plus a
**deliberately disabled** execution scaffold that cannot place a live order until
a strategy has actually survived that validation.

The design principle, learned the hard way: a backtest's job is not to make a
strategy look good — it's to tell you the truth. Most strategies that look good
are curve-fit noise. This system is built to catch that before it costs money.

## Two components, one manual gate

```
COMPONENT 1: RESEARCH (live, read-only)        COMPONENT 2: EXECUTION (disabled scaffold)
  data → strategy → backtest → HONESTY → verdict      risk limits · runner · order gate (LOCKED)
                                   │                              ▲
                                   └──────── gate/promote.py ─────┘
                                       (human-in-the-loop; never automatic)
```

- **Component 1** is fully functional and never touches your account — it only
  reads historical/demo data via MetaTrader5.
- **Component 2** has real structure (risk framework, runner, logging) but its
  order function **raises** — this build is structurally incapable of trading.
- Between them is a **manual gate**: a strategy becomes eligible for execution
  only after (a) surviving out-of-sample testing and (b) a multi-week demo run,
  and only when a human runs `gate/promote.py`. Research never auto-promotes.

See [execution/README.md](execution/README.md) for the three independent locks.

## The honesty layer (the core)

Every result is a `Verdict`, and a verdict can only be produced by a pipeline
that:
1. **diagnoses the regime** (warns if the instrument is a random walk),
2. enforces a **time-ordered out-of-sample split** with the OOS data
   *structurally locked* until parameters are frozen,
3. **optimizes only in-sample**, tracking the winner per sub-slice,
4. **freezes**, then runs **once, blind, out-of-sample**,
5. applies a **cost floor** (spread can never be zero), reports **drawdown and
   risk first-class**, and runs **overfit/curve-fit detection** (parameter
   instability, in-sample/out-of-sample degradation, knife-edge dependence),
6. **deflates** the result for the number of parameter combinations tried,
7. warns loudly on **small samples**.

There is no API that returns a bare equity curve. That is on purpose.

## Quick start

```bash
pip install -r requirements.txt          # numpy + MetaTrader5
# MT5 desktop terminal must be open and logged in for live data.

# Run the built-in dip-buy example (with a parameter sweep):
python -m trading_system.apps.research_cli --example

# Run your own strategy spec:
python -m trading_system.apps.research_cli --spec my_strategy.json

# Review past runs (never retest a dead idea):
python -m trading_system.apps.research_cli --history

# Inspect the (disabled) execution component:
python -m trading_system.apps.execution_cli --status
python -m trading_system.apps.execution_cli --attempt   # refused, by design

# Run the guard tests:
python -m unittest discover -s trading_system/tests -v
```

## Live vs disabled map

| Area | Status |
|---|---|
| `data/ strategy/ backtest/ honesty/ records/` | **LIVE** (Component 1) |
| `apps/research_cli.py` | **LIVE** |
| `execution/order_gate.py` | **🔒 LOCKED** — `place_order()` raises |
| `execution/` (rest) | **SCAFFOLD** — real structure, cannot reach a broker |
| `gate/promote.py` | **LIVE but gated** — promotes nothing until a strategy survives |
| `apps/execution_cli.py` | **LIVE, inert** — reports disabled status |

## Extending

- New indicator/signal/exit → add to `strategy/` and the vocabulary in
  `core/strategy_spec.py`. Strategies are **data, not code** — there is no user
  code execution, which is also the security posture for the future product.
- New data source (e.g. rate differentials for carry) → implement
  `data/source_base.DataSource`.
- Swap SQLite for Supabase/Postgres → implement `records/store.RecordStore`;
  callers are unchanged.
