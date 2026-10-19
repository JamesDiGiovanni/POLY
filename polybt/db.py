"""DuckDB storage. All timestamps are unix seconds (UTC)."""
from __future__ import annotations

from pathlib import Path

import duckdb

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    wallet VARCHAR PRIMARY KEY,
    sources VARCHAR,
    discovered_at BIGINT
);

CREATE TABLE IF NOT EXISTS markets (
    condition_id VARCHAR PRIMARY KEY,
    question VARCHAR,
    slug VARCHAR,
    token_ids VARCHAR[],
    outcomes VARCHAR[],
    payouts DOUBLE[],           -- final outcome prices, aligned with token_ids
    category VARCHAR,
    volume DOUBLE,
    end_time BIGINT,            -- resolution / close time
    closed BOOLEAN,
    resolved BOOLEAN,
    resolved_outcome VARCHAR,   -- winning token id, NULL if unresolved or split
    fetched_at BIGINT,
    fee_rate DOUBLE,            -- taker fee parameters (see polybt.fees)
    fee_exponent DOUBLE,
    fee_source VARCHAR,         -- market (CLOB market info) | category (config fallback)
    fee_category VARCHAR
);

-- Every Data API activity row: TRADE, REDEEM, MERGE, SPLIT, ...
CREATE TABLE IF NOT EXISTS wallet_trades (
    wallet VARCHAR,
    tx_hash VARCHAR,
    type VARCHAR,
    token_id VARCHAR,
    condition_id VARCHAR,
    outcome_index INTEGER,
    side VARCHAR,
    price DOUBLE,
    size DOUBLE,
    usdc_size DOUBLE,
    timestamp BIGINT,
    PRIMARY KEY (wallet, tx_hash, type, token_id, side, size, price)
);

CREATE TABLE IF NOT EXISTS wallet_ingest_state (
    wallet VARCHAR PRIMARY KEY,
    start_ts BIGINT,            -- earliest timestamp requested
    synced_to BIGINT,           -- everything up to here has been pulled
    updated_at BIGINT,
    capped BOOLEAN              -- stopped at http.max_activity_rows: history incomplete, wallet rejected
);

CREATE TABLE IF NOT EXISTS price_history (
    token_id VARCHAR,
    timestamp BIGINT,
    price DOUBLE,
    PRIMARY KEY (token_id, timestamp)
);

CREATE TABLE IF NOT EXISTS price_fetches (
    token_id VARCHAR,
    start_ts BIGINT,
    end_ts BIGINT,
    PRIMARY KEY (token_id, start_ts)
);

CREATE TABLE IF NOT EXISTS wallet_scores (
    wallet VARCHAR PRIMARY KEY,
    resolved_trades INTEGER,
    span_days DOUBLE,
    days_since_last DOUBLE,
    roi DOUBLE,
    win_rate DOUBLE,
    avg_entry DOUBLE,
    edge_pts DOUBLE,
    top3_share DOUBLE,
    median_trade_usd DOUBLE,
    trades_per_day DOUBLE,
    wash_fraction DOUBLE,
    passed BOOLEAN,
    rejection_reason VARCHAR,
    scored_at BIGINT
);

-- One row per simulated lot (a copied buy) or skipped trade.
-- mode = 'copy' for the delayed copy, 'wallet' for the wallet's own fills (delay_s = 0).
CREATE TABLE IF NOT EXISTS sim_trades (
    wallet VARCHAR,
    mode VARCHAR,
    delay_s INTEGER,
    tx_hash VARCHAR,
    token_id VARCHAR,
    condition_id VARCHAR,
    category VARCHAR,
    side VARCHAR,
    ts BIGINT,
    wallet_price DOUBLE,
    market_price DOUBLE,
    copy_price DOUBLE,
    shares DOUBLE,
    stake DOUBLE,
    fees DOUBLE,
    proceeds DOUBLE,
    pnl DOUBLE,
    close_ts BIGINT,
    status VARCHAR,             -- closed | open | skipped
    skipped_reason VARCHAR,
    sizing VARCHAR,             -- flat | proportional | mirror
    exec_ts BIGINT
);

CREATE TABLE IF NOT EXISTS sim_results (
    wallet VARCHAR,
    delay_s INTEGER,
    category VARCHAR,
    trades INTEGER,
    skipped INTEGER,
    skipped_reasons VARCHAR,
    open_positions INTEGER,
    staked DOUBLE,
    pnl DOUBLE,
    copy_roi DOUBLE,
    wallet_roi DOUBLE,
    edge_decay DOUBLE,
    win_rate DOUBLE,
    avg_entry DOUBLE,
    ci_low DOUBLE,
    ci_high DOUBLE,
    drawdown DOUBLE,
    sizing VARCHAR
);

-- Paper / live trading. One session = one continuous run of the shared engine.
CREATE TABLE IF NOT EXISTS live_sessions (
    session VARCHAR PRIMARY KEY,
    mode VARCHAR,               -- paper | live | replay
    start_ts BIGINT,
    wallets VARCHAR[],
    config VARCHAR,
    created_at BIGINT
);

-- Every order decision, filled or not. The key makes execution idempotent: on restart the engine is
-- rebuilt by replaying fills, and anything already in this journal is never sent again.
CREATE TABLE IF NOT EXISTS live_orders (
    session VARCHAR,
    wallet VARCHAR,
    tx_hash VARCHAR,
    token_id VARCHAR,
    side VARCHAR,
    signal_ts BIGINT,           -- the wallet's fill
    seen_ts BIGINT,             -- when we detected it
    exec_ts BIGINT,
    status VARCHAR,             -- filled | skipped
    reason VARCHAR,
    wallet_price DOUBLE,
    price DOUBLE,               -- our average fill price before fees
    shares DOUBLE,
    usdc DOUBLE,
    fee DOUBLE,
    ref_price DOUBLE,           -- mid / reference price at execution
    model_price DOUBLE,         -- what the backtest spread model would have charged
    meta VARCHAR,
    PRIMARY KEY (session, wallet, tx_hash, token_id, side)
);

-- Current portfolio snapshot per session, same shape as sim_trades for reporting.
CREATE TABLE IF NOT EXISTS live_lots (
    session VARCHAR,
    wallet VARCHAR,
    tx_hash VARCHAR,
    token_id VARCHAR,
    condition_id VARCHAR,
    category VARCHAR,
    ts BIGINT,
    exec_ts BIGINT,
    wallet_price DOUBLE,
    entry_price DOUBLE,
    shares DOUBLE,
    open_shares DOUBLE,
    stake DOUBLE,
    fees DOUBLE,
    proceeds DOUBLE,
    pnl DOUBLE,
    close_ts BIGINT,
    status VARCHAR
);
"""

# Columns added after the first release; ALTER keeps existing database files usable.
MIGRATIONS = [
    "ALTER TABLE markets ADD COLUMN IF NOT EXISTS fee_rate DOUBLE",
    "ALTER TABLE markets ADD COLUMN IF NOT EXISTS fee_exponent DOUBLE",
    "ALTER TABLE markets ADD COLUMN IF NOT EXISTS fee_source VARCHAR",
    "ALTER TABLE markets ADD COLUMN IF NOT EXISTS fee_category VARCHAR",
    "ALTER TABLE sim_trades ADD COLUMN IF NOT EXISTS sizing VARCHAR",
    "ALTER TABLE sim_trades ADD COLUMN IF NOT EXISTS exec_ts BIGINT",
    "ALTER TABLE sim_results ADD COLUMN IF NOT EXISTS sizing VARCHAR",
    "ALTER TABLE wallet_ingest_state ADD COLUMN IF NOT EXISTS capped BOOLEAN",
]


def connect(path: str | Path) -> duckdb.DuckDBPyConnection:
    path = str(path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(path)
    con.execute(SCHEMA)
    for m in MIGRATIONS:
        con.execute(m)
    return con


def insert_many(con, table: str, rows, verb: str = "INSERT OR IGNORE", chunk: int = 500) -> None:
    """Bulk insert. DuckDB's executemany runs one statement per row, which is far too slow here."""
    rows = list(rows)
    if not rows:
        return
    width = len(rows[0])
    tuple_sql = "(" + ",".join("?" * width) + ")"
    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        con.execute(f"{verb} INTO {table} VALUES " + ",".join([tuple_sql] * len(part)),
                    [v for row in part for v in row])
