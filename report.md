## Paper market making for liquidity rewards: 7 sessions

$1,000 quoted per market on both sides at 0.5 x the max spread from the midpoint, re-quoted every `requote` seconds ("at 0.3x": quoted at 0.3 x the max spread instead). Fills come from real taker prints (through our price, or at it once the queue ahead is gone). Markout = fill price against the midpoint later; negative = picked off.

Stale-quote loss: whenever the midpoint jumps past one of our quotes between re-quotes, the whole quote is assumed picked off at that gap, even with no print (an empty book only trades once someone quotes). Net if picked off subtracts it. Lasting jumps counts only jumps still past the quote 5 minutes later (news, not a thin book's quotes coming and going): the most realistic of the three.

| tier | requote | market-hours | rewards | trading P&L | net | net $/day per $1k | stale-quote loss | net if picked off $/day per $1k | lasting jumps loss | net, lasting jumps $/day per $1k | fills | markout 5m | markout 30m | markout 120m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| empty | 60s | 71 | $364.97 | $18.42 | $383.39 | $129.07 | $14,090.86 | $-4,614.52 | $9,960.59 | $-3,224.09 | 15 | $13.15 | $44.25 | $16.31 |
| empty | 10s | 68 | $262.51 | $11.66 | $274.18 | $96.20 | $30,971.52 | $-10,770.66 | $7,098.74 | $-2,394.51 | 24 | $-2.69 | $-13.29 | $5.46 |
| medium | 60s | 71 | $350.01 | $-25.00 | $325.01 | $109.93 | $3,759.16 | $-1,161.53 | $3,426.13 | $-1,048.89 | 4 | $-20.89 | $10.29 | $8.60 |
| medium | 10s | 70 | $319.36 | $-1.60 | $317.76 | $109.00 | $7,929.23 | $-2,610.84 | $3,436.44 | $-1,069.75 | 1 | $-3.20 | $-1.60 | $-1.60 |
| medium | 10s filtered at 0.3x | 50 | $325.70 | $-5.74 | $319.96 | $153.67 | $3,348.85 | $-1,454.67 | $902.55 | $-279.80 | 7 | $2.07 | $0.61 | $-2.40 |
| medium | 10s filtered | 50 | $616.58 | $-4.18 | $612.40 | $293.98 | $8,498.81 | $-3,785.79 | $2,360.57 | $-839.19 | 12 | $12.73 | $9.44 | $3.22 |
| crowded | 60s | 71 | $72.73 | $-3.43 | $69.30 | $23.29 | $110.46 | $-13.84 | $78.55 | $-3.11 | 4 | $4.48 | $5.53 | $-3.43 |
| crowded | 10s | 70 | $48.13 | $0.00 | $48.13 | $16.51 | $0.00 | $16.51 | $0.00 | $16.51 | 0 | $0.00 | $0.00 | $0.00 |
| crowded | 10s filtered at 0.3x | 50 | $93.19 | $-27.19 | $66.00 | $31.70 | $538.24 | $-226.80 | $167.29 | $-48.64 | 11 | $13.80 | $10.30 | $-5.80 |
| crowded | 10s filtered | 50 | $31.64 | $0.00 | $31.64 | $15.19 | $5.26 | $12.66 | $5.26 | $12.66 | 0 | $0.00 | $0.00 | $0.00 |

Check on the print data: 2497 taker prints sat on the expected side of the midpoint (buys above, sells below), 1246 did not.

Per market (latest first):

| session | tier | market | pool | hours | rewards | trading P&L | net | lasting jumps loss | fills | inventory | markout 30m |
|---|---|---|---|---|---|---|---|---|---|---|---|
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
| run-39658784244 | crowded | US imports Russian diesel by November 30? | 100 | 5.0 | $5.09 | $0.00 | $5.09 | $5.26 | 0 | 0 | $0.00 |
| run-39658784244 | crowded | Will no next Israeli Minister of Justice be appoin | 86 | 5.0 | $4.73 | $0.00 | $4.73 | $0.00 | 0 | 0 | $0.00 |
| run-39658784244 | crowded | Will Anna Kelly be the next White House Press Secr | 109 | 5.0 | $3.76 | $0.00 | $3.76 | $0.00 | 0 | 0 | $0.00 |
| run-39658784244 | crowded | Will Flávio Bolsonaro win the second round of the  | 237 | 5.0 | $3.52 | $0.00 | $3.52 | $0.00 | 0 | 0 | $0.00 |
| run-39658784244 | crowded | France declares state of emergency by December 31, | 200 | 5.0 | $3.01 | $0.00 | $3.01 | $0.00 | 0 | 0 | $0.00 |
| run-39658784244 | crowded | Will Anthropic's valuation hit (HIGH) $2.0T by Dec | 500 | 5.0 | $2.87 | $0.00 | $2.87 | $0.00 | 0 | 0 | $0.00 |
| run-39658784244 | crowded | Skin cancer vaccine FDA approved by December 31, 2 | 100 | 5.0 | $2.38 | $0.00 | $2.38 | $0.00 | 0 | 0 | $0.00 |
| run-39658784244 | crowded | Iran-Oman Hormuz Agreement by December 31? | 100 | 5.0 | $2.35 | $0.00 | $2.35 | $0.00 | 0 | 0 | $0.00 |
| run-39658784244 | crowded | Iran-Oman Hormuz Agreement by November 30? | 100 | 5.0 | $2.06 | $0.00 | $2.06 | $0.00 | 0 | 0 | $0.00 |
| run-39658784244 | crowded | Will Delcy Rodríguez be the leader of Venezuela en | 125 | 5.0 | $1.87 | $0.00 | $1.87 | $0.00 | 0 | 0 | $0.00 |
| run-39658784244 | medium | US x Iran ceasefire continues through October 31? | 2000 | 5.0 | $252.92 | $-13.86 | $239.06 | $359.44 | 4 | 132 | $-9.31 |
| run-39658784244 | medium | US x Iran ceasefire continues through October 28? | 1000 | 5.0 | $143.72 | $3.02 | $146.74 | $537.71 | 6 | -302 | $12.10 |
| run-39658784244 | medium | Will Jynxzi beat the Elden Ring DLC by October 23? | 200 | 5.0 | $40.56 | $0.00 | $40.56 | $42.11 | 0 | 0 | $0.00 |
| run-39658784244 | medium | Will Jynxzi beat the Elden Ring DLC by October 25? | 200 | 5.0 | $35.33 | $0.00 | $35.33 | $10.64 | 0 | 0 | $0.00 |
| run-39658784244 | medium | US-Iran ceasefire continues through the midterms? | 300 | 5.0 | $27.88 | $6.66 | $34.54 | $109.05 | 2 | -333 | $6.66 |
| run-39658784244 | medium | Will Vivek Ramaswamy pull the Amy Acton mother ad? | 200 | 5.0 | $30.13 | $0.00 | $30.13 | $1206.77 | 0 | 0 | $0.00 |
| run-39658784244 | medium | US Gov confirms PHP2Shell exploited by October 31, | 200 | 5.0 | $26.78 | $0.00 | $26.78 | $63.27 | 0 | 0 | $0.00 |
| run-39658784244 | medium | Another critical PHP security flaw in 2026? | 200 | 5.0 | $24.00 | $0.00 | $24.00 | $31.58 | 0 | 0 | $0.00 |
| run-39658784244 | medium | Tornado in California by October 25? | 200 | 5.0 | $23.86 | $0.00 | $23.86 | $0.00 | 0 | 0 | $0.00 |
| run-39658784244 | medium | US Gov confirms PHP2Shell exploited by December 31 | 200 | 5.0 | $11.40 | $0.00 | $11.40 | $0.00 | 0 | 0 | $0.00 |
| run-39680581468 | crowded | Another critical PHP security flaw in 2026? | 200 | 5.0 | $17.29 | $0.00 | $17.29 | $0.00 | 0 | 0 | $0.00 |
| run-39680581468 | crowded | US x Iran ceasefire continues through November 30? | 200 | 5.0 | $10.38 | $1.27 | $11.65 | $5.05 | 1 | -127 | $1.91 |
| run-39680581468 | crowded | Will Anna Kelly be the next White House Press Secr | 109 | 5.0 | $10.34 | $0.00 | $10.34 | $131.73 | 0 | 0 | $0.00 |
| run-39680581468 | crowded | Will Aleksandar Vučić be the next Prime Minister o | 750 | 5.0 | $8.22 | $0.00 | $8.22 | $0.00 | 0 | 0 | $0.00 |
| run-39680581468 | crowded | Will Flávio Bolsonaro win the second round of the  | 293 | 5.0 | $6.78 | $0.00 | $6.78 | $0.00 | 0 | 0 | $0.00 |
| run-39680581468 | crowded | US-Iran Hormuz Agreement by December 31? | 200 | 5.0 | $5.31 | $0.00 | $5.31 | $0.00 | 0 | 0 | $0.00 |
| run-39680581468 | crowded | Will Flávio Bolsonaro win the second round of the  | 209 | 5.0 | $5.22 | $0.00 | $5.22 | $0.00 | 0 | 0 | $0.00 |
| run-39680581468 | crowded | US announces end of Iranian blockade by October 31 | 200 | 5.0 | $4.01 | $0.00 | $4.01 | $25.41 | 0 | 0 | $0.00 |
| run-39680581468 | crowded | Will oil be at least $85 on November 2 and the Dem | 500 | 5.0 | $3.81 | $0.00 | $3.81 | $0.00 | 0 | 0 | $0.00 |
| run-39680581468 | crowded | US x Iran ceasefire continues through October 24? | 1000 | 5.0 | $21.83 | $-28.46 | $-6.62 | $5.10 | 10 | -1546 | $8.39 |
| run-39680581468 | medium | US x Iran ceasefire continues through October 31? | 2000 | 5.0 | $85.67 | $-0.68 | $84.99 | $85.23 | 1 | 136 | $0.68 |
| run-39680581468 | medium | US x Iran ceasefire continues through October 28? | 1000 | 5.0 | $56.04 | $-0.22 | $55.82 | $20.25 | 2 | -44 | $0.08 |
| run-39680581468 | medium | France accuses foreign country of provoking unrest | 200 | 5.0 | $32.01 | $0.00 | $32.01 | $127.97 | 0 | 0 | $0.00 |
| run-39680581468 | medium | Paris curfew effectively lifted by November 7? | 200 | 5.0 | $27.44 | $0.00 | $27.44 | $262.73 | 0 | 0 | $0.00 |
| run-39680581468 | medium | US x Iran ceasefire continues through October 22? | 1010 | 5.0 | $31.98 | $-4.87 | $27.11 | $0.00 | 3 | -165 | $-0.17 |
| run-39680581468 | medium | Will GPT Astra 6.1+ debut at a score of at least 1 | 200 | 5.0 | $23.31 | $0.00 | $23.31 | $0.00 | 0 | 0 | $0.00 |
| run-39680581468 | medium | Will Vivek Ramaswamy pull the Amy Acton mother ad? | 200 | 5.0 | $22.78 | $0.00 | $22.78 | $56.65 | 0 | 0 | $0.00 |
| run-39680581468 | medium | Will Alphabet be the third-largest company in the  | 110 | 5.0 | $21.31 | $0.03 | $21.34 | $349.72 | 1 | 3 | $0.02 |
| run-39680581468 | medium | Will Russia capture Svitle by December 31? | 100 | 5.0 | $14.53 | $0.00 | $14.53 | $0.00 | 0 | 0 | $0.00 |
| run-39680581468 | medium | Russia x Ukraine ceasefire by March 31, 2027? | 200 | 5.0 | $10.62 | $0.00 | $10.62 | $0.00 | 0 | 0 | $0.00 |
