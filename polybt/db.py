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
    fetched_at BIGINT
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
    updated_at BIGINT
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
    skipped_reason VARCHAR
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
    drawdown DOUBLE
);
"""


def connect(path: str | Path) -> duckdb.DuckDBPyConnection:
    path = str(path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(path)
    con.execute(SCHEMA)
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
