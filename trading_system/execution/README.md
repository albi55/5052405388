# Component 2 — Execution (DISABLED SCAFFOLD)

> ⚠️ **This build cannot place a live order.** That is by design, not by omission.

This directory contains the *architecture* of the execution component — how it
would consume a validated strategy, the risk-limit framework, logging, and a
demo-first path. **The actual order-placement function is stubbed and raises.**

## Why it is disabled

The execution logic for a trading bot is shaped by the *strategy it runs*. A
mean-reversion bot and a trend bot need different position sizing, different
halt conditions, different exit handling. **No strategy has yet survived honest
out-of-sample testing plus a multi-week demo run**, so there is nothing valid to
execute. An execution bot built and armed before a validated strategy exists is
not bot #2 of a system — it is a money shredder with a nice interface, because
the temptation is to point it at an untested (likely curve-fit) strategy.

So this build ships the structure, **incapable of trading**, until there is
something real to arm it with.

## The three independent locks

A live order requires changing **all three**. No single edit arms this.

1. **`order_gate.py`** — `place_order()` raises `ExecutionDisabledError` by
   default. This is the single, clearly-marked integration point where real
   broker logic will later be added.
2. **`config/settings.py: EXECUTION_ENABLED`** — `False`. The runner refuses to
   proceed while this is false, even if order logic were written.
3. **The validation gate** — the runner only accepts a `ValidationRecord` that
   is *eligible* (survived OOS **and** carries a multi-week demo stamp). None can
   exist until a strategy actually survives. Research **never** writes this
   record; only a human running `gate/promote.py` can.

## The manual gate (no auto-promotion)

Research (Component 1) **never** auto-promotes a strategy to execution. Promotion
is a deliberate, human-in-the-loop step (`gate/promote.py`) gated on real
evidence. There is no code path from "backtest looked good" to "place order."

## When you have a real edge

The day a strategy survives the research tool *and* a demo run, you:
1. run `gate/promote.py` to create the `ValidationRecord`,
2. implement the real broker logic at the single marked point in `order_gate.py`,
   shaped around that specific strategy,
3. flip `EXECUTION_ENABLED` only after demo-first validation of the execution
   path itself.

That is the two-bot system, armed in the only order that does not blow up an
account.
