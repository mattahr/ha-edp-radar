# TED data profile — broad mode, last 90 days

Generated 2026-09-12T17:32:41+00:00 by `scripts/data_profile.py` (taxonomy 2026.09.1/2026.09.1). Countries: all.

## Volume

| measure | value |
| --- | --- |
| raw notices returned | 6581 |
| parse errors | 0 |
| notice versions | 6581 |
| unique notice ids | 6573 |
| unique procedures (incl. unlinked pseudo-procedures) | 5002 |
| central-purchasing-only notices (>10 buyers, buyer signal only) | 190 |

## Versions and changes

| notice-version | count |
| --- | --- |
| 1 | 6344 |
| 2 | 164 |
| 3 | 48 |
| 4 | 13 |
| 5 | 10 |
| 6 | 1 |
| 14 | 1 |

- notice versions carrying change info: 1022 (v1: 874, v>1: 148)
- modification notices: 82

## Stage distribution (latest versions)

| stage | count |
| --- | --- |
| competition | 3289 |
| direct_award | 64 |
| modification | 82 |
| other | 5 |
| planning | 116 |
| result | 3017 |

## Match reasons (latest versions)

| reasons | count |
| --- | --- |
| defence_buyer | 4333 |
| defence_buyer+defence_cpv | 218 |
| defence_buyer+defence_cpv+defence_legal_basis | 342 |
| defence_buyer+defence_legal_basis | 659 |
| defence_cpv | 441 |
| defence_cpv+defence_legal_basis | 131 |
| defence_legal_basis | 449 |

## Primary buyer country (latest versions, top 30)

| country | count |
| --- | --- |
| PL | 1217 |
| DE | 882 |
| ES | 569 |
| FR | 529 |
| CZ | 466 |
| RO | 364 |
| HR | 224 |
| PT | 218 |
| NO | 200 |
| LT | 196 |
| EE | 194 |
| NL | 157 |
| SK | 156 |
| FI | 131 |
| BE | 128 |
| LV | 126 |
| SI | 122 |
| IT | 116 |
| DK | 108 |
| GR | 80 |
| SE | 73 |
| CH | 63 |
| HU | 60 |
| IE | 55 |
| BG | 54 |
| AT | 31 |
| LU | 21 |
| CY | 15 |
| MT | 7 |
| MK | 5 |

## Coverage

| measure | value |
| --- | --- |
| procedure-id coverage (latest versions) | 98.2% |
| buyer-identifier coverage | 98.4% |
| competitions with estimated value | 1186/2474 (47.9%) |
| … convertible to EUR | 1184/2474 (47.9%) |
| results with result value | 1587/2970 (53.4%) |
| … convertible to EUR | 1525/2970 (51.3%) |
| results with winners | 2668/2970 |
| framework-agreement results (ceiling kept, award value unknown) | 1012/2970 |
| … with a winner identifier for every winner | 90.6% |
| … of which with a declared framework ceiling | 797/1012 |
| results with comparable tender counts | 88.2% |
| results with selection statuses | 99.9% |
| results linked to a competition in the window | 5.2% |
| notices without strategic category | 52.6% |

## Currencies

| currency | monetary fields |
| --- | --- |
| EUR | 2890 |
| PLN | 728 |
| CZK | 384 |
| RON | 340 |
| NOK | 91 |
| SEK | 83 |
| DKK | 67 |
| HUF | 32 |
| CHF | 29 |
| USD | 6 |
| BGN | 5 |
| MDL | 4 |
| GBP | 3 |
| CAD | 2 |

## Received-submission type codes (all result notices, per lot entry)

| type code | entries |
| --- | --- |
| t-esubm | 8823 |
| tenders | 8762 |
| t-sme | 8459 |
| t-oth-eea | 7913 |
| t-no-eea | 7417 |
| t-verif-inad | 1008 |
| t-verif-inad-low | 983 |
| part-req | 806 |
| t-no-verif | 368 |
| t-med | 192 |
| t-micro | 187 |
| t-small | 187 |

## Selection status and non-award justifications

| winner-selection-status | lot entries |
| --- | --- |
| selec-w | 8395 |
| clos-nw | 1643 |
| open-nw | 320 |

| non-award-justification | entries |
| --- | --- |
| no-rece | 923 |
| all-rej | 284 |
| other | 242 |
| ins-fund | 79 |
| tch-pr-error | 49 |
| chan-need | 24 |
| no-signed | 23 |
| one-admis | 12 |
| rev-body | 5 |
| rev-buyer | 2 |

## Top CPV divisions (latest versions)

| CPV division | notices |
| --- | --- |
| 45 | 1507 |
| 35 | 1373 |
| 50 | 1200 |
| 15 | 1040 |
| 39 | 932 |
| 34 | 929 |
| 72 | 901 |
| 33 | 878 |
| 71 | 839 |
| 30 | 632 |
| 44 | 631 |
| 18 | 516 |
| 90 | 476 |
| 32 | 448 |
| 48 | 418 |

## Strategic categories (latest versions, multi-label)

| category | notices |
| --- | --- |
| Logistics & support | 1446 |
| Cyber & IT | 637 |
| C4ISR & communications | 332 |
| Land systems | 299 |
| Other defence | 199 |
| Naval & maritime | 174 |
| Ammunition & explosives | 164 |
| Defence R&D | 95 |
| Air systems | 76 |
| Sensors, radar & electronic warfare | 47 |
| Space | 10 |
| Air & missile defence | 7 |

## Raw-array alignment anomalies

| check | notices |
| --- | --- |
| estimated-value-lot vs estimated-value-cur-lot length mismatch | 957 |
| result-value-lot vs result-value-cur-lot length mismatch | 202 |
| received-submissions code vs val length mismatch | 0 |
| unique winner names vs winner-identifier count mismatch | 256 |
| buyer-identifier count != buyer-country count | 801 |
| notices with > 10 buyers | 195 |

## Snapshot preview (market metrics, broad universe)

| metric | value |
| --- | --- |
| new competitions 30d / previous | 672 / 766 |
| estimated value 30d | EUR 3.9bn (coverage 45.2%) |
| award value 30d | EUR 1.7bn (coverage 57.2%) |
| top country 90d | PL |
| top category 90d | Cyber & IT |
| median tenders 365d | 2.0 (n=6613) |
| single-bid share 365d | 30.5% |
| median public time to result 365d | 54.0 days (n=125) |
| non-award share 365d | 14.6% |
| snapshot text | 2330 competitions / 90d · EUR 26.6bn |
| country ranking text | PL EUR 14.7bn · FR EUR 3.4bn · NO EUR 2.1bn · CZ EUR 1.5bn · ES EUR 1.3bn |
| external latest text | ES · Air systems · EUR 11m · published 2026-09-11 |
| top supplier 365d | WB Electronics S.A. |
| supplier top-5 share | 54.1% |
