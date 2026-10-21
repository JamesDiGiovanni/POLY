## Paper market making for liquidity rewards: 4 sessions

$1,000 quoted per market on both sides at 0.5 x the max spread from the midpoint, re-quoted every `requote` seconds. Fills come from real taker prints (through our price, or at it once the queue ahead is gone). Markout = fill price against the midpoint later; negative = picked off.

Stale-quote loss: whenever the midpoint jumps past one of our quotes between re-quotes, the whole quote is assumed picked off at that gap, even with no print (an empty book only trades once someone quotes). Net if picked off subtracts it. Lasting jumps counts only jumps still past the quote 5 minutes later (news, not a thin book's quotes coming and going): the most realistic of the three.

| tier | requote | market-hours | rewards | trading P&L | net | net $/day per $1k | stale-quote loss | net if picked off $/day per $1k | lasting jumps loss | net, lasting jumps $/day per $1k | fills | markout 5m | markout 30m | markout 120m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| empty | 60s | 71 | $364.97 | $18.42 | $383.39 | $129.07 | $14,090.86 | $-4,614.52 | $9,960.59 | $-3,224.09 | 15 | $13.15 | $44.25 | $16.31 |
| empty | 10s | 35 | $172.72 | $31.64 | $204.36 | $140.18 | $22,382.69 | $-15,213.27 | $5,002.02 | $-3,290.96 | 14 | $-4.07 | $11.39 | $22.46 |
| medium | 60s | 71 | $350.01 | $-25.00 | $325.01 | $109.93 | $3,759.16 | $-1,161.53 | $3,426.13 | $-1,048.89 | 4 | $-20.89 | $10.29 | $8.60 |
| medium | 10s | 35 | $150.43 | $0.00 | $150.43 | $103.19 | $2,965.23 | $-1,930.83 | $1,245.74 | $-751.34 | 0 | $0.00 | $0.00 | $0.00 |
| crowded | 60s | 71 | $72.73 | $-3.43 | $69.30 | $23.29 | $110.46 | $-13.84 | $78.55 | $-3.11 | 4 | $4.48 | $5.53 | $-3.43 |
| crowded | 10s | 35 | $23.28 | $0.00 | $23.28 | $15.97 | $0.00 | $15.97 | $0.00 | $15.97 | 0 | $0.00 | $0.00 | $0.00 |

Check on the print data: 872 taker prints sat on the expected side of the midpoint (buys above, sells below), 346 did not.

Per market (latest first):

| session | tier | market | pool | hours | rewards | trading P&L | net | lasting jumps loss | fills | inventory | markout 30m |
|---|---|---|---|---|---|---|---|---|---|---|---|
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
| run-39533407188 | crowded | Will Iliana Iotova win the 2026 Bulgarian presiden | 161 | 5.0 | $7.68 | $0.00 | $7.68 | $53.19 | 0 | 0 | $0.00 |
| run-39533407188 | crowded | Will Anthropic IPO by December 15, 2026? | 300 | 5.0 | $7.38 | $0.00 | $7.38 | $0.00 | 0 | 0 | $0.00 |
| run-39533407188 | crowded | US x Iran ceasefire continues through November 30? | 200 | 5.0 | $3.49 | $0.00 | $3.49 | $0.00 | 0 | 0 | $0.00 |
| run-39533407188 | crowded | Will Lorne Doerkson be the next Premier of British | 150 | 5.0 | $2.82 | $0.00 | $2.82 | $0.00 | 0 | 0 | $0.00 |
| run-39533407188 | crowded | Will there be between 25 and 29 average daily tran | 117 | 5.0 | $1.56 | $0.00 | $1.56 | $0.00 | 0 | 0 | $0.00 |
| run-39533407188 | crowded | Will oil be at least $85 on November 2 and the Rep | 500 | 5.0 | $1.48 | $0.00 | $1.48 | $0.00 | 0 | 0 | $0.00 |
| run-39533407188 | empty | Next Fable Model (5.2+) released by October 26, 20 | 200 | 5.0 | $40.82 | $0.00 | $40.82 | $909.97 | 0 | 0 | $0.00 |
| run-39533407188 | empty | Next Fable Model (5.2+) released by October 27, 20 | 200 | 5.0 | $33.69 | $0.00 | $33.69 | $153.25 | 0 | 0 | $0.00 |
| run-39533407188 | empty | Next Fable Model (5.2+) released by October 28, 20 | 200 | 5.0 | $32.50 | $0.00 | $32.50 | $158.51 | 0 | 0 | $0.00 |
| run-39533407188 | empty | Will MrBeast's next video get between 113 and 115  | 153 | 5.0 | $30.81 | $-0.47 | $30.34 | $1444.75 | 3 | -66 | $0.49 |
| run-39533407188 | empty | Will MrBeast's next video get between 115 and 117  | 147 | 5.0 | $23.51 | $4.05 | $27.57 | $1053.73 | 7 | 39 | $-1.20 |
| run-39533407188 | empty | Will UK annual inflation be between 3.4% and 3.6%  | 118 | 5.0 | $20.41 | $0.00 | $20.41 | $657.11 | 0 | 0 | $0.00 |
| run-39533407188 | empty | Will NYC Mayor post 20-39 posts from October 16 to | 100 | 5.0 | $13.17 | $0.00 | $13.17 | $358.99 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Next Fable Model (5.2+) released by October 29, 20 | 200 | 5.0 | $33.32 | $0.00 | $33.32 | $10.64 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Will "Grand Theft Auto VI Launch Trailer" get betw | 526 | 5.0 | $33.30 | $0.00 | $33.30 | $11.52 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Next Fable Model (5.2+) released by October 23, 20 | 200 | 5.0 | $31.43 | $0.00 | $31.43 | $31.75 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Will "Grand Theft Auto VI Launch Trailer" get betw | 478 | 5.0 | $26.43 | $0.00 | $26.43 | $26.04 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Next Astra Model (6.1+) released by December 15, 2 | 200 | 5.0 | $22.37 | $0.00 | $22.37 | $68.42 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Marseille public gathering ban effectively lifted  | 202 | 5.0 | $20.14 | $0.00 | $20.14 | $15.96 | 0 | 0 | $0.00 |
| run-39533407188 | medium | Next Fable Model (5.2+) released by October 24, 20 | 100 | 5.0 | $14.54 | $0.00 | $14.54 | $84.43 | 0 | 0 | $0.00 |
| run-39563704774 | crowded | Will Anthropic IPO by December 15, 2026? | 300 | 5.0 | $5.58 | $0.00 | $5.58 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | crowded | US x Iran ceasefire continues through October 31? | 2000 | 5.0 | $4.09 | $0.00 | $4.09 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | crowded | Will Anthropic's market cap be between $1.75T and  | 185 | 5.0 | $3.45 | $0.00 | $3.45 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | crowded | Will Anthropic have the best AI model at the end o | 107 | 5.0 | $3.29 | $0.00 | $3.29 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | crowded | Will Aleksandar Vučić – United Serbia win the most | 613 | 5.0 | $3.06 | $0.00 | $3.06 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | crowded | US-Iran Hormuz Agreement by December 31? | 200 | 5.0 | $2.04 | $0.00 | $2.04 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | crowded | Will Lorne Doerkson be the next Premier of British | 94 | 5.0 | $1.77 | $0.00 | $1.77 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | empty | Will MrBeast's next video get between 113 and 115  | 165 | 5.0 | $34.05 | $31.64 | $65.70 | $3243.01 | 13 | -204 | $11.39 |
| run-39563704774 | empty | Next Fable Model (5.2+) released by October 28, 20 | 200 | 5.0 | $32.84 | $0.00 | $32.84 | $79.68 | 0 | 0 | $0.00 |
| run-39563704774 | empty | Next Fable Model (5.2+) released by October 26, 20 | 200 | 5.0 | $30.75 | $0.00 | $30.75 | $26.48 | 0 | 0 | $0.00 |
| run-39563704774 | empty | Next Fable Model (5.2+) released by October 29, 20 | 200 | 5.0 | $21.54 | $0.00 | $21.54 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | empty | Will the next Fable model (5.2+) be released on Oc | 136 | 5.0 | $20.97 | $0.00 | $20.97 | $158.55 | 0 | 0 | $0.00 |
| run-39563704774 | empty | Will OpenAI have the second highest OpenRouter mar | 115 | 5.0 | $17.05 | $0.00 | $17.05 | $343.84 | 0 | 0 | $0.00 |
| run-39563704774 | empty | Will gemini-4-argon-high be the best AI model on O | 100 | 5.0 | $15.52 | $0.00 | $15.52 | $1150.45 | 1 | -20 | $0.00 |
| run-39563704774 | medium | Will OpenAI have the best Image Edit AI at the end | 159 | 5.0 | $27.91 | $0.00 | $27.91 | $704.87 | 0 | 0 | $0.00 |
| run-39563704774 | medium | Will Anthropic have the best AI model on LiveBench | 147 | 5.0 | $27.47 | $0.00 | $27.47 | $530.24 | 0 | 0 | $0.00 |
| run-39563704774 | medium | Next Fable Model (5.2+) released by October 27, 20 | 200 | 5.0 | $26.99 | $0.00 | $26.99 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | medium | No change in Bank of Mexico’s interest rates after | 137 | 5.0 | $20.32 | $0.00 | $20.32 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | medium | Will Core PCE YoY be 3.1% in September? | 116 | 5.0 | $19.14 | $0.00 | $19.14 | $0.00 | 0 | 0 | $0.00 |
| run-39563704774 | medium | Next Astra Model (6.1+) released by December 15, 2 | 200 | 5.0 | $18.02 | $0.00 | $18.02 | $10.64 | 0 | 0 | $0.00 |
| run-39563704774 | medium | Will Iliana Iotova win the 2026 Bulgarian presiden | 268 | 5.0 | $10.57 | $0.00 | $10.57 | $0.00 | 0 | 0 | $0.00 |
