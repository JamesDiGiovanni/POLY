# Polymarket copy-trade backtester

Answers one question before any money is risked: **does a top Polymarket wallet's edge survive being copied
late, at worse prices, after fees?** Read-only: it never connects a wallet or places an order.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest            # offline; no network needed
```

## Running

```bash
python -m polybt run                      # every step, in order
```

Or step by step. Each step reads and writes the one DuckDB file (`data/polybt.duckdb`), so any step can be
re-run alone without repeating the earlier ones:

| Step | Command | Does |
| --- | --- | --- |
| Ingest | `python -m polybt ingest` | Discover candidates (most active wallets in top markets that closed before the cutoff, plus `seed_wallets`), pull their activity and market metadata |
| Filter | `python -m polybt filter` | Score every candidate on pre-cutoff data; log a rejection reason for each failure |
| Prices | `python -m polybt prices` | Pull 1-minute price history around every test-period trade of wallets that passed |
| Simulate | `python -m polybt simulate` | Copy each test-period trade at every delay |
| Report | `python -m polybt report` | Metrics, bootstrap intervals, go/no-go, `output/report.html` + CSVs |

`python -m polybt fees` shows where each market's fee came from and checks the fee formula against real fills.

Useful options: `ingest --wallet 0x…` (skip discovery), `ingest --no-discovery` (re-sync known candidates),
`prices --all`, `simulate --wallet 0x…`, `-v` for debug logging, `--config my.yaml` (merged over `config.yaml`).

**Phase 2 hand check:** `python -m polybt inspect 0x…` prints a wallet's stored trade count, volume, cash P&L
and latest fills next to its profile URL, to compare against polymarket.com by hand.

## Outputs (`output/`)

- `report.html` — verdict, ranked wallet table, per-category table, an edge-decay chart per wallet, filter funnel
- `results.csv` — one row per wallet × delay × category (`all`, `short_term_crypto`, `other`)
- `trades.csv` — every simulated copy (and skip) with prices, delay and P&L, for spot checks
- `wallet_scores.csv` — every candidate's filter metrics and rejection reason
- `session_<name>.csv`, `session_<name>_orders.csv`, `session_<name>_lots.csv` — paper/live session results

## How the simulation works

- **Split.** Wallets are scored on `[cutoff − 365d, cutoff)` and tested only on trades after the cutoff
  (default: 90 days ago). In the selection window, only positions that closed before the cutoff count.
- **Unit of account.** Each copied buy is a *lot* staked at a flat `$10` (and, in a second pass, sized in
  proportion to the wallet's own bet: `$10 × their buy ÷ their median buy`, capped at 5×). When the wallet sells a fraction of
  its position, every open copy lot in that token sells the same fraction at the same delay. Whatever is
  still held settles at the market's final payout (1, 0, or 0.5 on a split). Lots in unresolved markets are
  reported as open and left out of ROI.
- **Market price at delay.** The latest 1-minute print after the wallet's fill and at or before
  `fill + delay`. If there is none (all sub-minute delays, and gaps), interpolate linearly from the wallet's
  own fill price to the next print.
- **Fill.** Buys: `max(wallet_price, market_price) + spread`; sells: `min(wallet_price, market_price) − spread`.
  Spread is 1¢, or 2¢ in markets under $50k volume. Skipped when the copy price is above 97¢, the market
  resolved before the delayed entry, or there is no price history. A sell whose delayed time is after
  resolution is not copied; the copy rides to the payout. A wallet that exits by merging YES+NO back into
  USDC is copied as a sell of whichever side the copy holds, at the market price.
- **Fees.** See [Fees](#fees). Every copy pays taker fees on entry and exit, using each market's own fee
  parameters.
- **Wallet ROI** uses the same lot engine on the wallet's real fills and real cost (`usdcSize`, which includes
  fees), on the same period, so it sits directly beside copy ROI. Edge decay = copy ROI ÷ wallet ROI.
- **Confidence.** 90% percentile bootstrap (2,000 resamples, fixed seed) that resamples whole **markets**,
  not fills: a wallet's 100 fills in one market are one bet. The go rule also needs 30+ distinct markets.
- **Category specialists** (`filters.specialist`, the workflow's `specialist` profile). Candidates are
  drawn evenly across Polymarket's categories, each wallet is scored separately within every category,
  and a wallet that passes in one is copied **only in that category**, the bets where it showed skill.
- **No lookahead in discovery.** Candidates come only from markets that closed before the cutoff.
  Polymarket's leaderboards (even all-time) rank wallets partly on test-period profit, so they're off by
  default (`discovery.leaderboard.enabled`). A run that used monthly boards produced 6 "GO" wallets, 5 of
  which earned most of their profit in exactly the month they were picked on.
- **Go/no-go.** At least 3 wallets with copy ROI > 0 at 60 s, the interval's lower bound above 0,
  ≥ 100 copyable trades, and positive P&L in ≥ 2 of the last three 30-day periods.

## Judgement calls against the spec

- **Wash filter tolerance.** The spec reads as zero tolerance for buying both sides within an hour. The default
  `max_wash_fraction` is 5% so a rare flip doesn't reject a real trader; set it to 0 for the strict rule.
- **Trades per day** is measured per *active* day, so a wallet that trades in bursts is judged on its bursts.
- **Price history is pulled only around trades** (±1 h plus the longest delay, in 24 h chunks), not the full
  life of every market. That is all the simulation reads and it is far fewer requests. Closed chunks are
  recorded in `price_fetches` and never pulled again; every HTTP response is also cached under `data/cache/`.
- **Minimum order and staleness** apply in every mode: a copy under $1 (Polymarket's minimum marketable order)
  is skipped, and an exit that small rides to resolution. Fills older than 30 minutes are never acted on.

## Fees

Polymarket charges **takers only**. The fee is computed in USDC, rounded to 4 decimals, and taken **in shares
on buys and in USDC on sells**. The current documented formula is

    fee = shares × rate × p × (1 − p)

with rates set per market under Fee Structure V2 (since March 30 2026; revised July 2026): crypto 0.07;
sports, economics, culture, weather and other 0.05; politics, finance, tech and mentions 0.04; geopolitics 0.
Some sports markets listed before July keep 0.03.

- **Per-market parameters win.** Ingest reads each market's fee details from the CLOB
  (`GET /clob-markets/{condition_id}` → `fd: {r, e, to}`) and stores them on the market. The category table in
  `config.yaml` is only the fallback for markets the CLOB doesn't describe.
- **Formula check.** Sources disagree on whether an older formula, `shares × p × rate × (p(1−p))^exponent`,
  still applies. `python -m polybt fees` tests both against the wallets' real fills (the gap between `usdcSize`
  and `price × size`) and tells you if `fees.formula` should be `v1`. Run it after your first real ingest.
- **History.** Before March 30 2026 only crypto and some sports markets charged fees. The test window
  (the last 90 days) is entirely under the current schedule, and wallet ROI uses real `usdcSize`, so this
  doesn't affect results.

## Paper and live trading

Paper and production run **the same code**: the same runner, engine, policy, risk limits, fee model, journal
and reports. The only thing that differs is the executor that turns an order into a fill:

| Mode | Executor | What it does |
| --- | --- | --- |
| backtest | `BacktestExecutor` | historical price at the delay, plus the modelled spread |
| paper | `PaperExecutor` | walks the **live order book** exactly as a fill-or-kill market order would, and sends nothing |
| live | `LiveExecutor` | sends that fill-or-kill order through `py-clob-client-v2` |

```bash
python -m polybt paper                              # GO wallets from the report, or live.wallets / --wallet
python -m polybt session                            # paper vs backtest: ROI, latency, slippage vs the model
python -m polybt paper --replay --delay 60          # offline: the same runner over stored history
python -m polybt live --confirm-live --session live-1   # real orders; see below first
```

- **Polling.** Each cycle (5 s) pulls new activity for every tracked wallet, acts on new fills, and every
  5 minutes checks open positions' markets for resolution.
- **Restart-safe.** Every decision is written to `live_orders` keyed by session, wallet, fill, token and side.
  On restart the engines are rebuilt by replaying stored fills, and anything already journalled returns its
  recorded result instead of executing again, so a restart never double-orders. Reusing a session name
  resumes it.
- **What paper measures.** For each buy, `live_orders` records detection latency (`seen_ts − signal_ts`),
  our book-walked price, and the price the backtest's spread model would have charged at the same mid.
  `python -m polybt session` sets these against the backtest at the nearest delay. This is where the
  spread-penalty guess gets measured.
- **Parity is tested.** `tests/test_live.py` runs the live runner over stored history and checks it
  reproduces the backtest's lots exactly, including partial exits and fees. It also checks a mid-session restart
  sends nothing twice, and that paper and live executors build identical portfolios from the same book.

**Running it continuously.** It needs a machine that can reach the Polymarket APIs and stays up, such as a small VPS:

```bash
docker compose run --rm backtest          # ingest → filter → prices → simulate → report
docker compose up -d paper                # paper trade, restarting automatically
docker compose run --rm backtest session  # how paper compares with the backtest
```

Edit `config.local.yaml` (merged over `config.yaml`) for the wallet shortlist and session name.

**Going live** (only after paper results justify it): put `POLYBT_PRIVATE_KEY` (and `POLYBT_FUNDER` for a
Polymarket proxy wallet) in `.env`, set `risk.max_open_usd` / `risk.max_market_usd`, and
`docker compose --profile live up -d live`. The `ClobOrderClient` adapter in `polybt/live.py` is the only code
that signs anything. It follows the py-clob-client-v2 README but has never sent a real order, so check it
against the installed SDK with one small manual order first. Polymarket blocks trading from some
jurisdictions, including the US on the international exchange.

## Settled open questions

- [x] **Taker fees** → per-market CLOB fee details, category fallback, formula check (see [Fees](#fees))
- [x] **Rate limits** → from Polymarket's docs: Data API 1,000 req/10 s (200 on `/trades`), CLOB 9,000/10 s
  (1,000 on `/prices-history`, 1,500 on `/book`), over sliding windows and throttled rather than rejected.
  Defaults stay well under these (`http.requests_per_second`), with 8 parallel workers (`http.workers`).
- [x] **Cutoff** → 90 days, so "positive in 2 of the last 3 months" has three test months to look at
- [x] **Sizing-mirrored results** → second pass alongside flat (`simulate.sizing`), shown in the report

Not yet checked against the live API (blocked from the build environment): the `/v1/leaderboard` path and
parameters (configurable in `discovery.leaderboard`; a failing board is logged and skipped) and the
`/clob-markets` response shape (a missing `fd` falls back to the category table).
