## Paper market making for liquidity rewards: 2 sessions

$1,000 quoted per market on both sides at 0.5 x the max spread from the midpoint, re-quoted every minute. Fills come from real taker prints (through our price, or at it once the queue ahead is gone). Markout = fill price against the midpoint later; negative = picked off.

Stale-quote loss: whenever the midpoint jumps past one of our quotes between re-quotes, the whole quote is assumed picked off at that gap, even with no print (an empty book only trades once someone quotes). Net if picked off subtracts it; the truth is between the two nets.

| tier | market-hours | rewards | trading P&L | net | net $/day per $1k | stale-quote loss | net if picked off $/day per $1k | fills | markout 5m | markout 30m | markout 120m |
|---|---|---|---|---|---|---|---|---|---|---|---|
| empty | 36 | $170.06 | $14.83 | $184.89 | $121.91 | $5,224.29 | $-3,322.67 | 5 | $11.53 | $44.96 | $24.27 |
| medium | 36 | $168.48 | $-25.00 | $143.48 | $95.48 | $3,177.37 | $-2,018.89 | 4 | $-20.89 | $10.29 | $8.60 |
| crowded | 37 | $27.65 | $0.00 | $27.65 | $18.18 | $15.26 | $8.15 | 0 | $0.00 | $0.00 | $0.00 |

Check on the print data: 247 taker prints sat on the expected side of the midpoint (buys above, sells below), 65 did not.

Per market (latest first):

| session | tier | market | pool | hours | rewards | trading P&L | net | stale-quote loss | fills | inventory | markout 30m |
|---|---|---|---|---|---|---|---|---|---|---|---|
| run-39495687078 | crowded | Will "Grand Theft Auto VI Launch Trailer" get betw | 500 | 0.2 | $1.12 | $0.00 | $1.12 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | crowded | US x Iran ceasefire continues through October 31? | 1000 | 0.2 | $0.40 | $0.00 | $0.40 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | crowded | Will Anthropic announce bankruptcy by December 31, | 330 | 0.2 | $0.24 | $0.00 | $0.24 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | crowded | US x Iran ceasefire continues through October 24? | 1000 | 0.2 | $0.21 | $0.00 | $0.21 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | crowded | US x Iran ceasefire continues through October 28? | 1000 | 0.2 | $0.20 | $0.00 | $0.20 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | crowded | Will Anthropic IPO by December 15, 2026? | 300 | 0.2 | $0.20 | $0.00 | $0.20 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | crowded | US-Iran Hormuz Agreement by December 31? | 200 | 0.2 | $0.15 | $0.00 | $0.15 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | empty | WTI Crude Oil (WTI) Up or Down on October 20? | 200 | 0.2 | $1.94 | $0.00 | $1.94 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | empty | Marseille public gathering ban effectively lifted  | 200 | 0.2 | $1.94 | $0.00 | $1.94 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | empty | Marseille public gathering ban effectively lifted  | 200 | 0.2 | $1.70 | $0.00 | $1.70 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | empty | Will Anthropic have the best AI model on LiveBench | 152 | 0.2 | $1.48 | $0.00 | $1.48 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | empty | Will OpenAI have the third highest OpenRouter mark | 111 | 0.2 | $1.08 | $0.00 | $1.08 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | empty | S&P 500 (SPX) Opens Up or Down on October 21? | 100 | 0.2 | $0.97 | $0.00 | $0.97 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | empty | S&P 500 (SPX) Up or Down on October 21? | 100 | 0.2 | $0.97 | $0.00 | $0.97 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | medium | Paris curfew effectively lifted by October 24? | 200 | 0.2 | $1.60 | $0.00 | $1.60 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | medium | Lyon curfew effectively lifted by October 24? | 200 | 0.2 | $1.34 | $0.00 | $1.34 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | medium | Will MrBeast's next video get less than 150 millio | 188 | 0.2 | $1.28 | $0.00 | $1.28 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | medium | Paris curfew effectively lifted by October 31? | 200 | 0.2 | $1.23 | $0.00 | $1.23 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | medium | Will Trump say "Ass" during his Midterm Rally in N | 150 | 0.2 | $1.03 | $0.00 | $1.03 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | medium | Will Trump say "Hell" 15+ times during his Midterm | 150 | 0.2 | $0.87 | $0.00 | $0.87 | $0.00 | 0 | 0 | $0.00 |
| run-39495687078 | medium | Will Trump say "Fentanyl" or "Deport" or "Deported | 100 | 0.2 | $0.82 | $0.00 | $0.82 | $0.00 | 0 | 0 | $0.00 |
| run-39499059959 | crowded | US x Iran ceasefire continues through October 31? | 1000 | 5.0 | $8.36 | $0.00 | $8.36 | $10.10 | 0 | 0 | $0.00 |
| run-39499059959 | crowded | US x Iran ceasefire continues through October 28? | 1000 | 5.0 | $4.04 | $0.00 | $4.04 | $0.00 | 0 | 0 | $0.00 |
| run-39499059959 | crowded | US x Iran ceasefire continues through October 24? | 1000 | 5.0 | $3.52 | $0.00 | $3.52 | $0.00 | 0 | 0 | $0.00 |
| run-39499059959 | crowded | Will Anthropic announce bankruptcy by December 31, | 330 | 5.0 | $2.58 | $0.00 | $2.58 | $5.15 | 0 | 0 | $0.00 |
| run-39499059959 | crowded | US x Iran ceasefire continues through December 31? | 200 | 5.0 | $2.50 | $0.00 | $2.50 | $0.00 | 0 | 0 | $0.00 |
| run-39499059959 | crowded | US-Iran ceasefire continues through the midterms? | 1000 | 5.0 | $2.14 | $0.00 | $2.14 | $0.00 | 0 | 0 | $0.00 |
| run-39499059959 | crowded | Alexandre de Moraes out as Brazil Supreme Court Ju | 103 | 5.0 | $2.00 | $0.00 | $2.00 | $0.00 | 0 | 0 | $0.00 |
| run-39499059959 | empty | Marseille public gathering ban effectively lifted  | 202 | 5.0 | $40.01 | $28.61 | $68.62 | $344.44 | 3 | 137 | $41.02 |
| run-39499059959 | empty | Paris curfew effectively lifted by October 31? | 200 | 5.0 | $33.83 | $0.00 | $33.83 | $0.00 | 0 | 0 | $0.00 |
| run-39499059959 | empty | Will Anthropic have the best AI model on LiveBench | 152 | 5.0 | $24.79 | $0.00 | $24.79 | $3923.12 | 0 | 0 | $0.00 |
| run-39499059959 | empty | Marseille public gathering ban effectively lifted  | 200 | 5.0 | $28.17 | $-6.33 | $21.84 | $21.90 | 1 | -87 | $0.22 |
| run-39499059959 | empty | Will Trump say "Transgender" 7+ times during his M | 150 | 5.0 | $13.77 | $0.00 | $13.77 | $271.05 | 0 | 0 | $0.00 |
| run-39499059959 | empty | Will Trump say "Hell" 15+ times during his Midterm | 150 | 5.0 | $13.84 | $-7.44 | $6.40 | $528.95 | 1 | 93 | $3.72 |
| run-39499059959 | empty | WTI Crude Oil (WTI) Up or Down on October 20? | 200 | 4.9 | $5.56 | $0.00 | $5.56 | $134.83 | 0 | 0 | $0.00 |
| run-39499059959 | medium | SPY (SPY) Up or Down on October 21? | 200 | 5.0 | $32.30 | $0.00 | $32.30 | $590.69 | 0 | 0 | $0.00 |
| run-39499059959 | medium | Lyon curfew effectively lifted by October 24? | 200 | 5.0 | $24.51 | $0.00 | $24.51 | $47.87 | 0 | 0 | $0.00 |
| run-39499059959 | medium | Paris curfew effectively lifted by October 24? | 200 | 5.0 | $24.42 | $0.00 | $24.42 | $37.23 | 0 | 0 | $0.00 |
| run-39499059959 | medium | Will Trump say "Biden" or "Kamala" or "Obama" 15+  | 150 | 5.0 | $17.02 | $1.58 | $18.59 | $154.09 | 1 | -7 | $0.42 |
| run-39499059959 | medium | Will Trump say "Hormuz" or "Blockade" during his M | 150 | 5.0 | $11.46 | $4.62 | $16.08 | $538.69 | 2 | 231 | $3.47 |
| run-39499059959 | medium | Will Trump say "Ass" during his Midterm Rally in N | 150 | 4.5 | $10.96 | $0.00 | $10.96 | $95.74 | 0 | 0 | $0.00 |
| run-39499059959 | medium | WTI Crude Oil (WTI) Up or Down on October 21? | 200 | 5.0 | $39.65 | $-31.20 | $8.45 | $1713.05 | 1 | -160 | $6.40 |
