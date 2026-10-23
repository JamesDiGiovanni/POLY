## Longshot backtest: FAILED

52,885 resolved two-outcome markets (volume ≥ $5,000, ending 365 days back), 41,409 with price history. 35,257 bets. Test period: bets placed from 2026-06-24 on.

Rule: 1, 3, 7, 14, 30 days before the scheduled end, if one side trades at or below the bucket's price, buy the other side (+1¢ spread, plus the taker fee) and hold to resolution.

Gate: a bucket whose test-period ROI has its 90% interval (resampling whole events) above zero, ≥ 50 events, and ≥ 10% a year on the capital held. Passing: none.

Longshot price = what the market gave the side we bet against; longshot hit = how often it happened. If the hit rate is below the price, longshots are overpriced.

| days before end | longshot ≤ | period | bets | events | longshot price | longshot hit | ROI | 90% CI | annualised | worst event |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1¢ | all | 4,365 | 1,583 | 0.3% | 0.4% | -0.3% | -0.5% to -0.2% | -116% | $-2.00 |
| 1 | 1¢ | test | 992 | 429 | 0.3% | 0.9% | -0.8% | -1.4% to -0.3% | -297% | $-2.00 |
| 1 | 2¢ | all | 922 | 724 | 1.5% | 1.8% | -1.4% | -2.2% to -0.7% | -513% | $-1.00 |
| 1 | 2¢ | test | 272 | 209 | 1.5% | 1.8% | -1.4% | -2.7% to -0.3% | -507% | $-0.99 |
| 1 | 3¢ | all | 557 | 486 | 2.5% | 4.1% | -2.8% | -4.3% to -1.5% | -1010% | $-0.99 |
| 1 | 3¢ | test | 176 | 148 | 2.5% | 2.8% | -1.4% | -3.8% to +0.4% | -529% | $-0.99 |
| 1 | 5¢ | all | 730 | 633 | 4.0% | 6.4% | -3.7% | -5.3% to -2.2% | -1359% | $-1.93 |
| 1 | 5¢ | test | 262 | 218 | 3.9% | 6.5% | -3.8% | -6.6% to -1.1% | -1385% | $-1.93 |
| 1 | 10¢ | all | 1,503 | 1,181 | 7.5% | 11.0% | -5.1% | -6.7% to -3.7% | -1879% | $-1.92 |
| 1 | 10¢ | test | 575 | 404 | 7.4% | 11.0% | -5.2% | -7.5% to -2.9% | -1889% | $-1.89 |
| 1 | 20¢ | all | 2,826 | 2,327 | 15.2% | 20.2% | -7.7% | -9.1% to -6.2% | -2807% | $-2.61 |
| 1 | 20¢ | test | 1,040 | 810 | 15.2% | 23.4% | -11.3% | -13.8% to -8.8% | -4122% | $-2.36 |
| 3 | 1¢ | all | 3,083 | 1,114 | 0.3% | 0.6% | -0.6% | -0.8% to -0.3% | -67% | $-2.00 |
| 3 | 1¢ | test | 702 | 311 | 0.3% | 1.4% | -1.3% | -2.3% to -0.5% | -162% | $-2.00 |
| 3 | 2¢ | all | 970 | 721 | 1.5% | 3.2% | -2.7% | -3.7% to -1.8% | -334% | $-1.98 |
| 3 | 2¢ | test | 231 | 180 | 1.5% | 3.5% | -3.0% | -5.1% to -1.2% | -366% | $-1.00 |
| 3 | 3¢ | all | 677 | 556 | 2.5% | 4.1% | -2.8% | -4.1% to -1.6% | -335% | $-0.99 |
| 3 | 3¢ | test | 204 | 163 | 2.5% | 3.9% | -2.5% | -4.9% to -0.5% | -306% | $-0.99 |
| 3 | 5¢ | all | 915 | 745 | 4.0% | 5.1% | -2.4% | -3.6% to -1.2% | -288% | $-0.98 |
| 3 | 5¢ | test | 278 | 224 | 4.1% | 6.8% | -4.0% | -6.8% to -1.6% | -492% | $-0.98 |
| 3 | 10¢ | all | 1,685 | 1,265 | 7.5% | 11.4% | -5.6% | -7.1% to -4.3% | -683% | $-1.92 |
| 3 | 10¢ | test | 590 | 403 | 7.4% | 9.5% | -3.6% | -5.8% to -1.4% | -436% | $-1.92 |
| 3 | 20¢ | all | 3,012 | 2,298 | 15.2% | 20.1% | -7.5% | -8.8% to -6.2% | -912% | $-2.63 |
| 3 | 20¢ | test | 905 | 695 | 15.2% | 22.1% | -9.9% | -12.4% to -7.3% | -1199% | $-2.27 |
| 7 | 1¢ | all | 2,243 | 713 | 0.3% | 0.5% | -0.4% | -0.7% to -0.2% | -21% | $-1.00 |
| 7 | 1¢ | test | 345 | 128 | 0.3% | 0.9% | -0.8% | -1.6% to +0.1% | -40% | $-1.00 |
| 7 | 2¢ | all | 534 | 353 | 1.5% | 1.5% | -1.1% | -2.0% to -0.3% | -55% | $-1.00 |
| 7 | 2¢ | test | 97 | 72 | 1.4% | 3.1% | -2.7% | -5.8% to -0.5% | -140% | $-1.00 |
| 7 | 3¢ | all | 343 | 253 | 2.5% | 2.9% | -1.5% | -3.1% to -0.0% | -78% | $-0.99 |
| 7 | 3¢ | test | 63 | 55 | 2.5% | 3.2% | -1.7% | -5.6% to +1.5% | -91% | $-0.99 |
| 7 | 5¢ | all | 533 | 392 | 3.9% | 6.0% | -3.3% | -5.1% to -1.6% | -172% | $-0.98 |
| 7 | 5¢ | test | 114 | 95 | 4.0% | 6.1% | -3.4% | -7.3% to +0.1% | -178% | $-0.98 |
| 7 | 10¢ | all | 1,197 | 814 | 7.5% | 10.9% | -4.9% | -6.5% to -3.4% | -257% | $-2.80 |
| 7 | 10¢ | test | 333 | 271 | 7.6% | 8.4% | -2.3% | -5.2% to +0.4% | -118% | $-1.86 |
| 7 | 20¢ | all | 2,145 | 1,680 | 15.2% | 20.1% | -7.5% | -9.2% to -5.9% | -392% | $-1.77 |
| 7 | 20¢ | test | 778 | 647 | 15.4% | 21.1% | -8.4% | -11.1% to -5.8% | -441% | $-1.73 |
| 14 | 1¢ | all | 1,531 | 516 | 0.4% | 0.6% | -0.5% | -0.8% to -0.2% | -13% | $-1.00 |
| 14 | 1¢ | test | 301 | 99 | 0.3% | 1.7% | -1.6% | -2.9% to -0.5% | -41% | $-1.00 |
| 14 | 2¢ | all | 461 | 302 | 1.4% | 1.7% | -1.3% | -2.6% to -0.3% | -34% | $-1.99 |
| 14 | 2¢ | test | 94 | 63 | 1.4% | 3.2% | -2.8% | -7.1% to +0.4% | -73% | $-1.99 |
| 14 | 3¢ | all | 224 | 181 | 2.5% | 2.2% | -0.8% | -2.6% to +0.6% | -21% | $-0.99 |
| 14 | 3¢ | test | 43 | 34 | 2.5% | 0.0% | +1.4% | +1.4% to +1.5% | +37% | $0.01 |
| 14 | 5¢ | all | 356 | 275 | 4.0% | 5.1% | -2.3% | -4.4% to -0.5% | -60% | $-0.98 |
| 14 | 5¢ | test | 68 | 48 | 3.8% | 5.9% | -3.3% | -7.9% to +1.1% | -86% | $-0.98 |
| 14 | 10¢ | all | 603 | 429 | 7.5% | 12.3% | -6.5% | -9.0% to -4.1% | -169% | $-2.79 |
| 14 | 10¢ | test | 108 | 71 | 7.4% | 10.2% | -4.4% | -10.0% to +0.5% | -114% | $-0.96 |
| 14 | 20¢ | all | 645 | 499 | 14.8% | 18.0% | -5.5% | -8.5% to -2.4% | -144% | $-2.53 |
| 14 | 20¢ | test | 106 | 78 | 14.8% | 15.1% | -2.2% | -8.9% to +4.3% | -57% | $-0.90 |
| 30 | 1¢ | all | 1,199 | 311 | 0.3% | 0.5% | -0.4% | -0.8% to -0.1% | -5% | $-1.00 |
| 30 | 1¢ | test | 184 | 62 | 0.3% | 1.1% | -1.0% | -2.4% to +0.1% | -12% | $-1.00 |
| 30 | 2¢ | all | 424 | 280 | 1.5% | 1.9% | -1.4% | -2.6% to -0.5% | -18% | $-0.99 |
| 30 | 2¢ | test | 64 | 47 | 1.5% | 3.1% | -2.7% | -6.4% to +0.5% | -33% | $-0.99 |
| 30 | 3¢ | all | 229 | 180 | 2.4% | 1.3% | +0.1% | -1.3% to +1.0% | +1% | $-0.98 |
| 30 | 3¢ | test | 39 | 32 | 2.5% | 5.1% | -3.8% | -10.3% to +1.4% | -46% | $-0.98 |
| 30 | 5¢ | all | 294 | 236 | 4.0% | 3.7% | -0.9% | -3.0% to +0.9% | -11% | $-1.93 |
| 30 | 5¢ | test | 44 | 38 | 4.0% | 6.8% | -4.1% | -11.0% to +0.9% | -50% | $-0.97 |
| 30 | 10¢ | all | 443 | 328 | 7.4% | 15.1% | -9.6% | -12.9% to -6.4% | -117% | $-1.89 |
| 30 | 10¢ | test | 70 | 57 | 7.3% | 27.1% | -22.5% | -32.4% to -13.3% | -274% | $-1.83 |
| 30 | 20¢ | all | 608 | 412 | 14.9% | 20.4% | -8.2% | -11.4% to -5.0% | -100% | $-2.38 |
| 30 | 20¢ | test | 87 | 65 | 14.7% | 20.7% | -8.7% | -17.3% to -0.6% | -105% | $-1.72 |

Longshots that hit in the test period (cheapest first):

- Will Ryan Fox win the 2026 The Open Championship? — 0.1¢, 1 days out
- Will David Crowley win the 2026 Wisconsin Governor Democratic primary election? — 0.1¢, 30 days out
- Will the price of Bitcoin be above $72,000 on August 20? — 0.1¢, 1 days out
- Will the next diplomatic US-Iran meeting be in the United States by September 30, 2026? — 0.1¢, 14 days out
- Will the next diplomatic US-Iran meeting be in the United States by September 30, 2026? — 0.1¢, 30 days out
- Will Elon Musk post 320-339 tweets from October 2 to October 9, 2026? — 0.1¢, 3 days out
- Will the price of Bitcoin be above $72,000 on August 20? — 0.2¢, 3 days out
- Will the highest temperature in Istanbul be 13°C or below on October 20? — 0.2¢, 1 days out
- Will Elon Musk post 240-259 tweets from August 14 to August 21, 2026? — 0.2¢, 3 days out
- Will Rodri win the Golden Ball at the 2026 FIFA World Cup? — 0.4¢, 14 days out
- Will the price of Bitcoin be above $72,000 on August 22? — 0.4¢, 3 days out
- Will Elon Musk post 360-379 tweets from October 6 to October 13, 2026? — 0.4¢, 7 days out
- World Cup: Folarin Balogun to Play vs. Belgium? — 0.4¢, 1 days out
- Will Ryan Fox win the 2026 The Open Championship? — 0.4¢, 3 days out
- Will Elon Musk post 320-339 tweets from August 18 to August 25, 2026? — 0.4¢, 7 days out
