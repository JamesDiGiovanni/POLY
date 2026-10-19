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
| Ingest | `python -m polybt ingest` | Discover candidates (leaderboards + most active wallets in top markets + `seed_wallets`), pull their activity and market metadata |
| Filter | `python -m polybt filter` | Score every candidate on pre-cutoff data; log a rejection reason for each failure |
| Prices | `python -m polybt prices` | Pull 1-minute price history around every test-period trade of wallets that passed |
| Simulate | `python -m polybt simulate` | Copy each test-period trade at every delay |
| Report | `python -m polybt report` | Metrics, bootstrap intervals, go/no-go, `output/report.html` + CSVs |

Useful options: `ingest --wallet 0x…` (skip discovery), `ingest --no-discovery` (re-sync known candidates),
`prices --all`, `simulate --wallet 0x…`, `-v` for debug logging, `--config my.yaml` (merged over `config.yaml`).

**Phase 2 hand check:** `python -m polybt inspect 0x…` prints a wallet's stored trade count, volume, cash P&L
and latest fills next to its profile URL, to compare against polymarket.com by hand.

## Outputs (`output/`)

- `report.html` — verdict, ranked wallet table, per-category table, an edge-decay chart per wallet, filter funnel
- `results.csv` — one row per wallet × delay × category (`all`, `short_term_crypto`, `other`)
- `trades.csv` — every simulated copy (and skip) with prices, delay and P&L, for spot checks
- `wallet_scores.csv` — every candidate's filter metrics and rejection reason

## How the simulation works

- **Split.** Wallets are scored on `[cutoff − 365d, cutoff)` and tested only on trades after the cutoff
  (default: 60 days ago). In the selection window, only positions that closed before the cutoff count.
- **Unit of account.** Each copied buy is a *lot* staked at a flat `$10`. When the wallet sells a fraction of
  its position, every open copy lot in that token sells the same fraction at the same delay. Whatever is
  still held settles at the market's final payout (1, 0, or 0.5 on a split). Lots in unresolved markets are
  reported as open and left out of ROI.
- **Market price at delay.** The latest 1-minute print after the wallet's fill and at or before
  `fill + delay`. If there is none (all sub-minute delays, and gaps), interpolate linearly from the wallet's
  own fill price to the next print.
- **Fill.** Buys: `max(wallet_price, market_price) + spread`; sells: `min(wallet_price, market_price) − spread`.
  Spread is 1¢, or 2¢ in markets under $50k volume. Skipped when the copy price is above 97¢, the market
  resolved before the delayed entry, or there is no price history. A sell whose delayed time is after
  resolution is not copied; the copy rides to the payout.
- **Fees.** `simulate.fees` is a taker fee as a fraction of notional per category, charged on entry and exit.
  It defaults to 0 — **set it from Polymarket's current schedule before trusting results.**
- **Wallet ROI** uses the same lot engine on the wallet's real fills and real cost (`usdcSize`, which includes
  fees), on the same period, so it sits directly beside copy ROI. Edge decay = copy ROI ÷ wallet ROI.
- **Confidence.** 90% percentile bootstrap over lots (2,000 resamples, fixed seed).
- **Go/no-go.** At least 3 wallets with copy ROI > 0 at 60 s, the interval's lower bound above 0,
  ≥ 100 copyable trades, and positive P&L in ≥ 2 of the last three 30-day periods.

## Judgement calls against the spec

- **Wash filter tolerance.** The spec reads as zero tolerance for buying both sides within an hour. The default
  `max_wash_fraction` is 5% so a rare flip doesn't reject a real trader; set it to 0 for the strict rule.
- **Trades per day** is measured per *active* day, so a wallet that trades in bursts is judged on its bursts.
- **Price history is pulled only around trades** (±1 h plus the longest delay, in 24 h chunks), not the full
  life of every market. That is all the simulation reads and it is far fewer requests. Closed chunks are
  recorded in `price_fetches` and never pulled again; every HTTP response is also cached under `data/cache/`.
- **Exits by merge.** Wallets that exit by merging YES+NO back to USDC have no SELL fill; those copies ride to
  resolution. The wash filter usually removes such wallets first.
- **"Last 3 months" vs a 60-day test window.** With the default cutoff, the oldest of the three 30-day periods
  is before the cutoff and has no copy trades, so a wallet must be positive in *both* of the other two. Move
  the cutoff back (≥ 90 days) if you want the rule to mean 2 of 3.

## Open questions (from the spec)

- [ ] Current Polymarket taker fees by category → `simulate.fees`
- [ ] Data API / CLOB rate limits → `http.requests_per_second` (default 4/s per host; 429s back off and retry)
- [ ] Cutoff date → `split.cutoff_date` / `cutoff_days_ago` (default 60 days)
- [ ] Sizing-mirrored results — not in this version; flat $10 only

The leaderboard path (`/v1/leaderboard`) and its query values are configurable in `discovery.leaderboard`
in case the Data API's shape differs from what's assumed here; a failing board is logged and skipped.
