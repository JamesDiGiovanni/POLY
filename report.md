## Paper market making for liquidity rewards: 9 sessions

$1,000 quoted per market on both sides at 0.5 x the max spread from the midpoint, re-quoted every `requote` seconds ("at 0.3x": quoted at 0.3 x the max spread instead). Fills come from real taker prints (through our price, or at it once the queue ahead is gone). Markout = fill price against the midpoint later; negative = picked off.

Stale-quote loss: whenever the midpoint jumps past one of our quotes between re-quotes, the whole quote is assumed picked off at that gap, even with no print (an empty book only trades once someone quotes). Net if picked off subtracts it. Lasting jumps counts only jumps still past the quote 5 minutes later (news, not a thin book's quotes coming and going): the most realistic of the three.

| tier | requote | market-hours | rewards | trading P&L | net | net $/day per $1k | stale-quote loss | net if picked off $/day per $1k | lasting jumps loss | net, lasting jumps $/day per $1k | fills | markout 5m | markout 30m | markout 120m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| empty | 60s | 71 | $364.97 | $18.42 | $383.39 | $129.07 | $14,090.86 | $-4,614.52 | $9,960.59 | $-3,224.09 | 15 | $13.15 | $44.25 | $16.31 |
| empty | 10s | 68 | $262.51 | $11.66 | $274.18 | $96.20 | $30,971.52 | $-10,770.66 | $7,098.74 | $-2,394.51 | 24 | $-2.69 | $-13.29 | $5.46 |
| medium | 60s | 71 | $350.01 | $-25.00 | $325.01 | $109.93 | $3,759.16 | $-1,161.53 | $3,426.13 | $-1,048.89 | 4 | $-20.89 | $10.29 | $8.60 |
| medium | 10s | 70 | $319.36 | $-1.60 | $317.76 | $109.00 | $7,929.23 | $-2,610.84 | $3,436.44 | $-1,069.75 | 1 | $-3.20 | $-1.60 | $-1.60 |
| medium | 10s filtered at 0.3x | 50 | $325.70 | $-5.74 | $319.96 | $153.67 | $3,348.85 | $-1,454.67 | $902.55 | $-279.80 | 7 | $2.07 | $0.61 | $-2.40 |
| medium | 10s filtered | 100 | $754.28 | $-4.18 | $750.10 | $180.08 | $9,950.77 | $-2,208.86 | $2,805.20 | $-493.38 | 12 | $12.73 | $9.44 | $3.22 |
| medium | 10s filtered+7d | 50 | $97.18 | $7.09 | $104.26 | $50.07 | $2,654.13 | $-1,224.61 | $575.23 | $-226.19 | 3 | $7.06 | $7.04 | $7.01 |
| crowded | 60s | 71 | $72.73 | $-3.43 | $69.30 | $23.29 | $110.46 | $-13.84 | $78.55 | $-3.11 | 4 | $4.48 | $5.53 | $-3.43 |
| crowded | 10s | 70 | $48.13 | $0.00 | $48.13 | $16.51 | $0.00 | $16.51 | $0.00 | $16.51 | 0 | $0.00 | $0.00 | $0.00 |
| crowded | 10s filtered at 0.3x | 50 | $93.19 | $-27.19 | $66.00 | $31.70 | $538.24 | $-226.80 | $167.29 | $-48.64 | 11 | $13.80 | $10.30 | $-5.80 |
| crowded | 10s filtered | 100 | $98.88 | $-9.99 | $88.90 | $21.34 | $333.09 | $-58.63 | $216.85 | $-30.72 | 9 | $9.75 | $-8.67 | $-9.99 |
| crowded | 10s filtered+7d | 50 | $162.42 | $-0.69 | $161.72 | $77.67 | $204.90 | $-20.74 | $66.88 | $45.55 | 6 | $4.41 | $-4.35 | $-2.62 |

Check on the print data: 3258 taker prints sat on the expected side of the midpoint (buys above, sells below), 1456 did not.

Per market (latest first):

| session | tier | market | pool | hours | rewards | trading P&L | net | lasting jumps loss | fills | inventory | markout 30m |
|---|---|---|---|---|---|---|---|---|---|---|---|
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
| run-39724735561 | crowded | US x Iran ceasefire continues through November 30? | 200 | 5.0 | $8.16 | $0.00 | $8.16 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | crowded | Will Iliana Iotova win the 2026 Bulgarian presiden | 321 | 5.0 | $21.18 | $-13.16 | $8.02 | $206.38 | 1 | 263 | $-11.84 |
| run-39724735561 | crowded | US x Iran ceasefire continues through October 31? | 2000 | 5.0 | $4.82 | $3.17 | $7.99 | $0.00 | 8 | 634 | $3.17 |
| run-39724735561 | crowded | Will Anthropic IPO by December 15, 2026? | 300 | 5.0 | $7.60 | $0.00 | $7.60 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | crowded | Russia x Ukraine ceasefire by December 31, 2027? | 200 | 5.0 | $5.79 | $0.00 | $5.79 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | crowded | France declares state of emergency by October 31,  | 202 | 5.0 | $4.81 | $0.00 | $4.81 | $5.21 | 0 | 0 | $0.00 |
| run-39724735561 | crowded | Russia x Ukraine ceasefire by March 31, 2027? | 200 | 5.0 | $4.62 | $0.00 | $4.62 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | crowded | US x Iran ceasefire continues through October 28? | 1000 | 5.0 | $3.94 | $0.00 | $3.94 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | crowded | Will Aleksandar Vučić be the next Prime Minister o | 745 | 5.0 | $3.53 | $0.00 | $3.53 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | crowded | US-Iran Hormuz Agreement by December 31? | 200 | 5.0 | $2.81 | $0.00 | $2.81 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | medium | Will Bryan Johnson dunk before 2027? | 200 | 5.0 | $26.81 | $0.00 | $26.81 | $232.98 | 0 | 0 | $0.00 |
| run-39724735561 | medium | Will Brazil’s Annual Inflation in 2026 be between  | 126 | 5.0 | $16.72 | $0.00 | $16.72 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | medium | Will Russia enter Druzkhivka by June 30, 2027? | 100 | 5.0 | $15.72 | $0.00 | $15.72 | $21.28 | 0 | 0 | $0.00 |
| run-39724735561 | medium | Will Russia enter Sloviansk by December 31, 2027? | 100 | 5.0 | $15.19 | $0.00 | $15.19 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | medium | Will Connor Wood be eliminated in week 7 of Dancin | 100 | 5.0 | $12.28 | $0.00 | $12.28 | $179.84 | 0 | 0 | $0.00 |
| run-39724735561 | medium | Will Russia enter Sloviansk by June 30, 2027? | 100 | 5.0 | $11.36 | $0.00 | $11.36 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | medium | Will Russia capture Kucheriv Yar by December 31? | 100 | 5.0 | $11.33 | $0.00 | $11.33 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | medium | Will Russia enter Druzkhivka by December 31, 2027? | 100 | 5.0 | $10.39 | $0.00 | $10.39 | $10.53 | 0 | 0 | $0.00 |
| run-39724735561 | medium | Will Russia enter Zaporizhia by December 31, 2027? | 100 | 5.0 | $9.35 | $0.00 | $9.35 | $0.00 | 0 | 0 | $0.00 |
| run-39724735561 | medium | Tesla and SpaceX merger officially announced by Ja | 100 | 5.0 | $8.57 | $0.00 | $8.57 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | crowded | US x Iran ceasefire continues through October 31? | 2002 | 5.0 | $64.07 | $-0.69 | $63.38 | $25.96 | 6 | -28 | $-4.35 |
| run-39774419890 | crowded | US x Iran ceasefire continues through October 28? | 1000 | 5.0 | $47.65 | $0.00 | $47.65 | $30.61 | 0 | 0 | $0.00 |
| run-39774419890 | crowded | US x Iran ceasefire continues through December 31? | 200 | 5.0 | $10.08 | $0.00 | $10.08 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | crowded | US-Iran ceasefire continues through the midterms? | 300 | 5.0 | $9.11 | $0.00 | $9.11 | $10.31 | 0 | 0 | $0.00 |
| run-39774419890 | crowded | Will Jared Kushner attend a US x Iran diplomatic m | 200 | 5.0 | $9.07 | $0.00 | $9.07 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | crowded | France declares state of emergency by December 31, | 200 | 5.0 | $5.08 | $0.00 | $5.08 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | crowded | Will Saudi airspace be closed by December 31? | 100 | 5.0 | $4.67 | $0.00 | $4.67 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | crowded | Will Anna Kelly be the next White House Press Secr | 100 | 5.0 | $4.53 | $0.00 | $4.53 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | crowded | Russia x Ukraine ceasefire by December 31, 2027? | 200 | 5.0 | $4.32 | $0.00 | $4.32 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | crowded | Pete Hegseth out as Secretary of Defense by Decemb | 400 | 5.0 | $3.83 | $0.00 | $3.83 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | medium | US x Iran ceasefire continues through November 15? | 100 | 5.0 | $13.34 | $7.09 | $20.43 | $20.41 | 3 | -706 | $7.04 |
| run-39774419890 | medium | Will Microsoft be the third-largest company in the | 100 | 5.0 | $16.82 | $0.00 | $16.82 | $77.59 | 0 | 0 | $0.00 |
| run-39774419890 | medium | GenLayer FDV above $500M one day after launch? | 80 | 5.0 | $14.81 | $0.00 | $14.81 | $46.55 | 0 | 0 | $0.00 |
| run-39774419890 | medium | Glider FDV above $25M one day after launch? | 80 | 5.0 | $13.00 | $0.00 | $13.00 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | medium | Will Anthropic IPO by December 15, 2026? | 300 | 5.0 | $7.77 | $0.00 | $7.77 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | medium | Will no next Israeli Minister of Finance be appoin | 58 | 5.0 | $7.75 | $0.00 | $7.75 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | medium | Will Bryan Johnson dunk before 2027? | 50 | 5.0 | $6.52 | $0.00 | $6.52 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | medium | Will Katie Zacharia be officially given a new role | 50 | 5.0 | $6.15 | $0.00 | $6.15 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | medium | Ilhan Omar denaturalization case filed by December | 50 | 5.0 | $5.70 | $0.00 | $5.70 | $0.00 | 0 | 0 | $0.00 |
| run-39774419890 | medium | Another critical PHP security flaw in 2026? | 50 | 5.0 | $5.30 | $0.00 | $5.30 | $430.68 | 0 | 0 | $0.00 |
