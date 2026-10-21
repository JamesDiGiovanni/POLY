## Paper market making for liquidity rewards: 5 sessions

$1,000 quoted per market on both sides at 0.5 x the max spread from the midpoint, re-quoted every `requote` seconds. Fills come from real taker prints (through our price, or at it once the queue ahead is gone). Markout = fill price against the midpoint later; negative = picked off.

Stale-quote loss: whenever the midpoint jumps past one of our quotes between re-quotes, the whole quote is assumed picked off at that gap, even with no print (an empty book only trades once someone quotes). Net if picked off subtracts it. Lasting jumps counts only jumps still past the quote 5 minutes later (news, not a thin book's quotes coming and going): the most realistic of the three.

| tier | requote | market-hours | rewards | trading P&L | net | net $/day per $1k | stale-quote loss | net if picked off $/day per $1k | lasting jumps loss | net, lasting jumps $/day per $1k | fills | markout 5m | markout 30m | markout 120m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| empty | 60s | 71 | $364.97 | $18.42 | $383.39 | $129.07 | $14,090.86 | $-4,614.52 | $9,960.59 | $-3,224.09 | 15 | $13.15 | $44.25 | $16.31 |
| empty | 10s | 68 | $262.51 | $11.66 | $274.18 | $96.20 | $30,971.52 | $-10,770.66 | $7,098.74 | $-2,394.51 | 24 | $-2.69 | $-13.29 | $5.46 |
| medium | 60s | 71 | $350.01 | $-25.00 | $325.01 | $109.93 | $3,759.16 | $-1,161.53 | $3,426.13 | $-1,048.89 | 4 | $-20.89 | $10.29 | $8.60 |
| medium | 10s | 70 | $319.36 | $-1.60 | $317.76 | $109.00 | $7,929.23 | $-2,610.84 | $3,436.44 | $-1,069.75 | 1 | $-3.20 | $-1.60 | $-1.60 |
| crowded | 60s | 71 | $72.73 | $-3.43 | $69.30 | $23.29 | $110.46 | $-13.84 | $78.55 | $-3.11 | 4 | $4.48 | $5.53 | $-3.43 |
| crowded | 10s | 70 | $48.13 | $0.00 | $48.13 | $16.51 | $0.00 | $16.51 | $0.00 | $16.51 | 0 | $0.00 | $0.00 | $0.00 |

Check on the print data: 1332 taker prints sat on the expected side of the midpoint (buys above, sells below), 575 did not.

Per market (latest first):

| session | tier | market | pool | hours | rewards | trading P&L | net | lasting jumps loss | fills | inventory | markout 30m |
|---|---|---|---|---|---|---|---|---|---|---|---|
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
| run-39611059138 | crowded | Will Anthropic IPO by December 15, 2026? | 300 | 5.0 | $7.49 | $0.00 | $7.49 | $0.00 | 0 | 0 | $0.00 |
| run-39611059138 | crowded | Will Anthropic IPO by November 30, 2026? | 100 | 5.0 | $4.01 | $0.00 | $4.01 | $0.00 | 0 | 0 | $0.00 |
| run-39611059138 | crowded | Will Delcy Rodríguez be the leader of Venezuela en | 131 | 5.0 | $3.32 | $0.00 | $3.32 | $0.00 | 0 | 0 | $0.00 |
| run-39611059138 | crowded | Will Anthropic's valuation hit (HIGH) $2.0T by Dec | 500 | 5.0 | $2.98 | $0.00 | $2.98 | $0.00 | 0 | 0 | $0.00 |
| run-39611059138 | crowded | Will Flávio Bolsonaro win the second round of the  | 229 | 5.0 | $2.69 | $0.00 | $2.69 | $0.00 | 0 | 0 | $0.00 |
| run-39611059138 | crowded | Will Aleksandar Vučić – United Serbia win the most | 613 | 5.0 | $2.46 | $0.00 | $2.46 | $0.00 | 0 | 0 | $0.00 |
| run-39611059138 | crowded | Will Ilija Srdanović be the next prime minister of | 134 | 5.0 | $1.90 | $0.00 | $1.90 | $0.00 | 0 | 0 | $0.00 |
| run-39611059138 | empty | Will Donald Trump post 200+ Truth Social posts fro | 105 | 5.0 | $18.70 | $0.00 | $18.70 | $366.35 | 0 | 0 | $0.00 |
| run-39611059138 | empty | Will "Ali G: Who Iz I?" Opening Weekend Box Office | 86 | 5.0 | $15.56 | $2.43 | $17.99 | $96.55 | 6 | 89 | $-2.28 |
| run-39611059138 | empty | Will NYC Mayor post 20-39 posts from October 16 to | 100 | 5.0 | $17.45 | $0.00 | $17.45 | $783.78 | 0 | 0 | $0.00 |
| run-39611059138 | empty | Will Google have the second highest OpenRouter mar | 77 | 5.0 | $15.85 | $0.00 | $15.85 | $406.33 | 0 | 0 | $0.00 |
| run-39611059138 | empty | Will OpenAI have the best Image Edit AI at the end | 124 | 5.0 | $13.81 | $0.00 | $13.81 | $21.28 | 0 | 0 | $0.00 |
| run-39611059138 | empty | Will MrBeast's next video get between 113 and 115  | 150 | 4.2 | $4.67 | $0.00 | $4.67 | $204.77 | 0 | 0 | $0.00 |
| run-39611059138 | empty | Will MrBeast's next video get between 115 and 117  | 150 | 4.2 | $3.76 | $-22.41 | $-18.65 | $217.68 | 4 | -187 | $-22.41 |
| run-39611059138 | medium | Will "Grand Theft Auto VI Launch Trailer" get betw | 716 | 5.0 | $49.19 | $0.00 | $49.19 | $0.00 | 0 | 0 | $0.00 |
| run-39611059138 | medium | Next Fable Model (5.2+) released by October 26, 20 | 202 | 5.0 | $36.89 | $0.00 | $36.89 | $221.56 | 0 | 0 | $0.00 |
| run-39611059138 | medium | Next Fable Model (5.2+) released by October 29, 20 | 200 | 5.0 | $25.72 | $0.00 | $25.72 | $0.00 | 0 | 0 | $0.00 |
| run-39611059138 | medium | Will the next Fable model (5.2+) be released on Oc | 120 | 5.0 | $20.10 | $0.00 | $20.10 | $343.86 | 0 | 0 | $0.00 |
| run-39611059138 | medium | Will Z.ai be the third-best Math AI lab at the end | 123 | 5.0 | $18.24 | $0.00 | $18.24 | $16.56 | 0 | 0 | $0.00 |
| run-39611059138 | medium | Will the lowest temperature in Tokyo be 18°C on Oc | 60 | 5.0 | $12.30 | $-1.60 | $10.70 | $1608.72 | 1 | -40 | $-1.60 |
| run-39611059138 | medium | US imports Russian diesel by December 31? | 100 | 5.0 | $6.48 | $0.00 | $6.48 | $0.00 | 0 | 0 | $0.00 |
