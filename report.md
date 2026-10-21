## Paper market making for liquidity rewards: 3 sessions

$1,000 quoted per market on both sides at 0.5 x the max spread from the midpoint, re-quoted every minute. Fills come from real taker prints (through our price, or at it once the queue ahead is gone). Markout = fill price against the midpoint later; negative = picked off.

Stale-quote loss: whenever the midpoint jumps past one of our quotes between re-quotes, the whole quote is assumed picked off at that gap, even with no print (an empty book only trades once someone quotes). Net if picked off subtracts it. Lasting jumps counts only jumps still past the quote 5 minutes later (news, not a thin book's quotes coming and going): the most realistic of the three.

| tier | market-hours | rewards | trading P&L | net | net $/day per $1k | stale-quote loss | net if picked off $/day per $1k | lasting jumps loss | net, lasting jumps $/day per $1k | fills | markout 5m | markout 30m | markout 120m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| empty | 71 | $364.97 | $18.42 | $383.39 | $129.07 | $14,090.86 | $-4,614.52 | $9,960.59 | $-3,224.09 | 15 | $13.15 | $44.25 | $16.31 |
| medium | 71 | $350.01 | $-25.00 | $325.01 | $109.93 | $3,759.16 | $-1,161.53 | $3,426.13 | $-1,048.89 | 4 | $-20.89 | $10.29 | $8.60 |
| crowded | 71 | $72.73 | $-3.43 | $69.30 | $23.29 | $110.46 | $-13.84 | $78.55 | $-3.11 | 4 | $4.48 | $5.53 | $-3.43 |

Check on the print data: 654 taker prints sat on the expected side of the midpoint (buys above, sells below), 254 did not.

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
| run-39533407188 | crowded | US x Iran ceasefire continues through October 31? | 2000 | 5.0 | $20.66 | $-3.43 | $17.23 | $10.10 | 4 | -1106 | $5.53 |
| run-39533407188 | crowded | Will Iliana Iotova win the 2026 Bulgarian presiden | 161 | 5.0 | $7.68 | $0.00 | $7.68 | $85.11 | 0 | 0 | $0.00 |
| run-39533407188 | crowded | Will Anthropic IPO by December 15, 2026? | 300 | 5.0 | $7.38 | $0.00 | $7.38 | $0.00 | 0 | 0 | $0.00 |
| run-39533407188 | crowded | US x Iran ceasefire continues through November 30? | 200 | 5.0 | $3.49 | $0.00 | $3.49 | $0.00 | 0 | 0 | $0.00 |
| run-39533407188 | crowded | Will Lorne Doerkson be the next Premier of British | 150 | 5.0 | $2.82 | $0.00 | $2.82 | $0.00 | 0 | 0 | $0.00 |
| run-39533407188 | crowded | Will there be between 25 and 29 average daily tran | 117 | 5.0 | $1.56 | $0.00 | $1.56 | $0.00 | 0 | 0 | $0.00 |
| run-39533407188 | crowded | Will oil be at least $85 on November 2 and the Rep | 500 | 5.0 | $1.48 | $0.00 | $1.48 | $0.00 | 0 | 0 | $0.00 |
| run-39533407188 | empty | Next Fable Model (5.2+) released by October 26, 20 | 200 | 5.0 | $40.82 | $0.00 | $40.82 | $1973.01 | 0 | 0 | $0.00 |
| run-39533407188 | empty | Next Fable Model (5.2+) released by October 27, 20 | 200 | 5.0 | $33.69 | $0.00 | $33.69 | $227.32 | 0 | 0 | $0.00 |
| run-39533407188 | empty | Next Fable Model (5.2+) released by October 28, 20 | 200 | 5.0 | $32.50 | $0.00 | $32.50 | $501.90 | 0 | 0 | $0.00 |
| run-39533407188 | empty | Will MrBeast's next video get between 113 and 115  | 153 | 5.0 | $30.81 | $-0.47 | $30.34 | $1527.81 | 3 | -66 | $0.49 |
| run-39533407188 | empty | Will MrBeast's next video get between 115 and 117  | 147 | 5.0 | $23.51 | $4.05 | $27.57 | $2224.91 | 7 | 39 | $-1.20 |
| run-39533407188 | empty | Will UK annual inflation be between 3.4% and 3.6%  | 118 | 5.0 | $20.41 | $0.00 | $20.41 | $2030.12 | 0 | 0 | $0.00 |
| run-39533407188 | empty | Will NYC Mayor post 20-39 posts from October 16 to | 100 | 5.0 | $13.17 | $0.00 | $13.17 | $381.48 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Next Fable Model (5.2+) released by October 29, 20 | 200 | 5.0 | $33.32 | $0.00 | $33.32 | $15.96 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Will "Grand Theft Auto VI Launch Trailer" get betw | 526 | 5.0 | $33.30 | $0.00 | $33.30 | $11.52 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Next Fable Model (5.2+) released by October 23, 20 | 200 | 5.0 | $31.43 | $0.00 | $31.43 | $42.27 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Will "Grand Theft Auto VI Launch Trailer" get betw | 478 | 5.0 | $26.43 | $0.00 | $26.43 | $26.04 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Next Astra Model (6.1+) released by December 15, 2 | 200 | 5.0 | $22.37 | $0.00 | $22.37 | $105.26 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Marseille public gathering ban effectively lifted  | 202 | 5.0 | $20.14 | $0.00 | $20.14 | $15.96 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Next Fable Model (5.2+) released by October 24, 20 | 100 | 5.0 | $14.54 | $0.00 | $14.54 | $364.78 | 0 | 0 | $0.00 |
