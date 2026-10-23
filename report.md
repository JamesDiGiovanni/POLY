## Paper market making for liquidity rewards: 15 sessions

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
| crowded | 10s filtered+7d | 350 | $354.04 | $41.28 | $395.31 | $27.12 | $532.12 | $-9.39 | $213.08 | $12.50 | 20 | $30.17 | $30.20 | $34.93 |

Check on the print data: 3942 taker prints sat on the expected side of the midpoint (buys above, sells below), 1623 did not.

Per market (latest first):

| session | tier | market | pool | hours | rewards | trading P&L | net | lasting jumps loss | fills | inventory | markout 30m |
|---|---|---|---|---|---|---|---|---|---|---|---|
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
| run-39820203569-s0 | crowded | NATO x Russia military clash by October 31, 2026? | 650 | 5.0 | $44.06 | $41.97 | $86.03 | $61.59 | 14 | 144 | $34.54 |
| run-39820203569-s0 | crowded | France declares state of emergency by December 31, | 200 | 5.0 | $5.22 | $0.00 | $5.22 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s0 | crowded | Will OpenAI announce another Millennium Prize solu | 200 | 5.0 | $2.11 | $0.00 | $2.11 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s0 | crowded | JD Vance 2028 presidential odds leader on November | 50 | 5.0 | $1.69 | $0.00 | $1.69 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s0 | crowded | Will the Democratic Party win the AL-02 House seat | 49 | 5.0 | $1.24 | $0.00 | $1.24 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s0 | crowded | US-Iran Hormuz Agreement by December 31? | 200 | 5.0 | $1.23 | $0.00 | $1.23 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s0 | crowded | Will oil be at least $85 on November 2 and the Rep | 500 | 5.0 | $1.12 | $0.00 | $1.12 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s0 | crowded | Will oil be at least $80 on November 2 and the Dem | 500 | 5.0 | $1.11 | $0.00 | $1.11 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s0 | crowded | Will the Democratic Party win the IA-02 House seat | 51 | 5.0 | $0.82 | $0.00 | $0.82 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s0 | crowded | Will the Democratic Party win the NV-02 House seat | 50 | 5.0 | $0.67 | $0.00 | $0.67 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s1 | crowded | Will Anthropic IPO by December 15, 2026? | 300 | 5.0 | $8.70 | $0.00 | $8.70 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s1 | crowded | Pedro Sánchez out as PM of Spain by January 15, 20 | 50 | 5.0 | $2.90 | $0.00 | $2.90 | $69.15 | 0 | 0 | $0.00 |
| run-39820203569-s1 | crowded | Will the Republican Party win the MI-04 House seat | 50 | 5.0 | $1.81 | $0.00 | $1.81 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s1 | crowded | Next US-Iran senior diplomatic meeting by November | 50 | 5.0 | $1.67 | $0.00 | $1.67 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s1 | crowded | Next White House Press Secretary announced by Dece | 50 | 5.0 | $1.65 | $0.00 | $1.65 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s1 | crowded | Israel x Iran ceasefire continues through October  | 100 | 5.0 | $1.35 | $0.00 | $1.35 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s1 | crowded | Will the Democratic Party win the FL-13 House seat | 50 | 5.0 | $1.31 | $0.00 | $1.31 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s1 | crowded | Will the Democratic Party win the AL-02 House seat | 49 | 5.0 | $1.24 | $0.00 | $1.24 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s1 | crowded | US-Iran Hormuz Agreement by December 31? | 200 | 5.0 | $1.23 | $0.00 | $1.23 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s1 | crowded | Will oil be at least $80 on November 2 and the Rep | 500 | 5.0 | $0.99 | $0.00 | $0.99 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s2 | crowded | US x Iran ceasefire continues through October 28? | 1000 | 5.0 | $11.07 | $0.00 | $11.07 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s2 | crowded | Russia x Ukraine ceasefire by December 31, 2027? | 200 | 5.0 | $3.59 | $0.00 | $3.59 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s2 | crowded | Next White House Press Secretary announced by Nove | 50 | 5.0 | $1.72 | $0.00 | $1.72 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s2 | crowded | Will no next Israeli Minister of National Security | 80 | 5.0 | $1.71 | $0.00 | $1.71 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s2 | crowded | JD Vance 2028 presidential odds leader on November | 50 | 5.0 | $1.70 | $0.00 | $1.70 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s2 | crowded | Will the Democratic Party win the NC-01 House seat | 50 | 5.0 | $1.28 | $0.00 | $1.28 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s2 | crowded | Will oil be at least $85 on November 2 and the Dem | 500 | 5.0 | $1.19 | $0.00 | $1.19 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s2 | crowded | Will the Democratic Party win the NC-11 House seat | 53 | 5.0 | $1.14 | $0.00 | $1.14 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s2 | crowded | Will oil be at least $85 on November 2 and the Rep | 500 | 5.0 | $1.11 | $0.00 | $1.11 | $0.00 | 0 | 0 | $0.00 |
| run-39820203569-s2 | crowded | Will the Democratic Party win the NV-02 House seat | 50 | 5.0 | $0.67 | $0.00 | $0.67 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s0 | crowded | US x Iran ceasefire continues through October 31? | 2002 | 5.0 | $7.43 | $0.00 | $7.43 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s0 | crowded | US x Iran ceasefire continues through November 30? | 200 | 5.0 | $5.36 | $0.00 | $5.36 | $5.15 | 0 | 0 | $0.00 |
| run-39858909252-s0 | crowded | Russia x Ukraine ceasefire by December 31, 2027? | 200 | 5.0 | $4.85 | $0.00 | $4.85 | $10.31 | 0 | 0 | $0.00 |
| run-39858909252-s0 | crowded | Will 1 Fed rate hike happen in 2026? | 200 | 5.0 | $4.30 | $0.00 | $4.30 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s0 | crowded | Another Fed rate hike in 2026? | 150 | 5.0 | $2.74 | $0.00 | $2.74 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s0 | crowded | Iran-Oman Hormuz Agreement by December 31? | 100 | 5.0 | $2.09 | $0.00 | $2.09 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s0 | crowded | Will the Republican Party win the NJ-02 House seat | 51 | 5.0 | $1.47 | $0.00 | $1.47 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s0 | crowded | Will no next Israeli Minister of National Security | 80 | 5.0 | $1.46 | $0.00 | $1.46 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s0 | crowded | Iran-Oman Hormuz Agreement by November 30? | 100 | 5.0 | $1.25 | $0.00 | $1.25 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s0 | crowded | Will the Democratic Party win the NC-11 House seat | 52 | 5.0 | $1.24 | $0.00 | $1.24 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s1 | crowded | Will the next GPT Terra model (5.7+) debut at a sc | 200 | 5.0 | $8.42 | $0.00 | $8.42 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s1 | crowded | US x Iran ceasefire continues through December 31? | 200 | 5.0 | $3.28 | $0.00 | $3.28 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s1 | crowded | Will Saudi airspace be closed by December 31? | 100 | 5.0 | $3.19 | $0.00 | $3.19 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s1 | crowded | Another Fed rate hike in 2026? | 150 | 5.0 | $2.72 | $0.00 | $2.72 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s1 | crowded | Will there be no change in Fed interest rates afte | 108 | 5.0 | $1.86 | $0.00 | $1.86 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s1 | crowded | Will the Republican Party win the AL-02 House seat | 50 | 5.0 | $1.80 | $0.00 | $1.80 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s1 | crowded | Will the Democratic Party win the MT-01 House seat | 50 | 5.0 | $1.75 | $0.00 | $1.75 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s1 | crowded | US announces end of Iranian blockade by December 3 | 100 | 5.0 | $1.58 | $0.00 | $1.58 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s1 | crowded | Will no next Israeli Minister of National Security | 80 | 5.0 | $1.46 | $0.00 | $1.46 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s1 | crowded | Will the Republican Party win the PA-08 House seat | 50 | 5.0 | $1.11 | $0.00 | $1.11 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s2 | crowded | Will Jared Kushner attend a US x Iran diplomatic m | 200 | 5.0 | $9.08 | $0.00 | $9.08 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s2 | crowded | Will Saudi airspace be closed by December 31? | 100 | 5.0 | $3.20 | $0.00 | $3.20 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s2 | crowded | Will Anthropic IPO by December 15, 2026? | 100 | 5.0 | $2.98 | $0.00 | $2.98 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s2 | crowded | Will there be no change in Fed interest rates afte | 108 | 5.0 | $1.86 | $0.00 | $1.86 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s2 | crowded | US x Iran ceasefire continues through October 28? | 1000 | 5.0 | $1.81 | $0.00 | $1.81 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s2 | crowded | Will the Democratic Party win the MT-01 House seat | 50 | 5.0 | $1.74 | $0.00 | $1.74 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s2 | crowded | Will the Republican Party win the PA-08 House seat | 50 | 5.0 | $1.11 | $0.00 | $1.11 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s2 | crowded | US-Iran ceasefire continues through the midterms? | 300 | 5.0 | $1.09 | $0.00 | $1.09 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s2 | crowded | Israel x Iran ceasefire continues through October  | 100 | 5.0 | $1.08 | $0.00 | $1.08 | $0.00 | 0 | 0 | $0.00 |
| run-39858909252-s2 | crowded | Will there be no change in Fed interest rates afte | 90 | 5.0 | $1.02 | $0.00 | $1.02 | $0.00 | 0 | 0 | $0.00 |
