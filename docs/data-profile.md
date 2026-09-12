# TED data profile — strict mode, last 90 days

Generated 2026-09-12T17:32:39+00:00 by `scripts/data_profile.py` (taxonomy 2026.09.1/2026.09.1). Countries: all.

## Volume

| measure | value |
| --- | --- |
| raw notices returned | 6138 |
| parse errors | 0 |
| notice versions | 6138 |
| unique notice ids | 6132 |
| unique procedures (incl. unlinked pseudo-procedures) | 4670 |
| central-purchasing-only notices (>10 buyers, buyer signal only) | 190 |

## Versions and changes

| notice-version | count |
| --- | --- |
| 1 | 5933 |
| 2 | 140 |
| 3 | 43 |
| 4 | 13 |
| 5 | 8 |
| 6 | 1 |

- notice versions carrying change info: 947 (v1: 816, v>1: 131)
- modification notices: 19

## Stage distribution (latest versions)

| stage | count |
| --- | --- |
| competition | 3085 |
| direct_award | 61 |
| modification | 19 |
| other | 3 |
| planning | 102 |
| result | 2862 |

## Match reasons (latest versions)

| reasons | count |
| --- | --- |
| defence_buyer | 4333 |
| defence_buyer+defence_cpv | 218 |
| defence_buyer+defence_cpv+defence_legal_basis | 342 |
| defence_buyer+defence_legal_basis | 659 |
| defence_cpv+defence_legal_basis | 131 |
| defence_legal_basis | 449 |

## Primary buyer country (latest versions, top 30)

| country | count |
| --- | --- |
| PL | 1136 |
| DE | 839 |
| FR | 501 |
| ES | 494 |
| CZ | 444 |
| RO | 337 |
| HR | 224 |
| PT | 195 |
| NO | 193 |
| EE | 191 |
| LT | 191 |
| SK | 147 |
| NL | 145 |
| FI | 129 |
| LV | 122 |
| SI | 121 |
| BE | 110 |
| DK | 107 |
| IT | 93 |
| SE | 65 |
| CH | 60 |
| GR | 58 |
| HU | 58 |
| BG | 53 |
| IE | 42 |
| AT | 31 |
| LU | 21 |
| CY | 12 |
| MK | 5 |
| MD | 5 |

## Coverage

| measure | value |
| --- | --- |
| procedure-id coverage (latest versions) | 98.3% |
| buyer-identifier coverage | 98.3% |
| competitions with estimated value | 1094/2324 (47.1%) |
| … convertible to EUR | 1092/2324 (47.0%) |
| results with result value | 1511/2819 (53.6%) |
| … convertible to EUR | 1449/2819 (51.4%) |
| results with winners | 2540/2819 |
| framework-agreement results (ceiling kept, award value unknown) | 959/2819 |
| … with a winner identifier for every winner | 90.5% |
| … of which with a declared framework ceiling | 752/959 |
| results with comparable tender counts | 88.3% |
| results with selection statuses | 99.9% |
| results linked to a competition in the window | 5.0% |
| notices without strategic category | 56.4% |

## Currencies

| currency | monetary fields |
| --- | --- |
| EUR | 2656 |
| PLN | 702 |
| CZK | 362 |
| RON | 316 |
| NOK | 85 |
| SEK | 74 |
| DKK | 67 |
| HUF | 30 |
| CHF | 27 |
| USD | 6 |
| BGN | 5 |
| MDL | 4 |
| GBP | 3 |
| CAD | 2 |

## Received-submission type codes (all result notices, per lot entry)

| type code | entries |
| --- | --- |
| t-esubm | 7979 |
| tenders | 7868 |
| t-sme | 7626 |
| t-oth-eea | 7091 |
| t-no-eea | 6599 |
| t-verif-inad | 939 |
| t-verif-inad-low | 922 |
| part-req | 767 |
| t-no-verif | 338 |
| t-med | 158 |
| t-micro | 153 |
| t-small | 153 |

## Selection status and non-award justifications

| winner-selection-status | lot entries |
| --- | --- |
| selec-w | 7618 |
| clos-nw | 1488 |
| open-nw | 301 |

| non-award-justification | entries |
| --- | --- |
| no-rece | 825 |
| all-rej | 259 |
| other | 217 |
| ins-fund | 76 |
| tch-pr-error | 49 |
| no-signed | 23 |
| chan-need | 21 |
| one-admis | 12 |
| rev-body | 4 |
| rev-buyer | 2 |

## Top CPV divisions (latest versions)

| CPV division | notices |
| --- | --- |
| 50 | 1151 |
| 15 | 1040 |
| 45 | 955 |
| 35 | 936 |
| 39 | 906 |
| 72 | 820 |
| 34 | 797 |
| 33 | 771 |
| 71 | 662 |
| 44 | 558 |
| 30 | 530 |
| 90 | 470 |
| 18 | 426 |
| 03 | 352 |
| 79 | 346 |

## Strategic categories (latest versions, multi-label)

| category | notices |
| --- | --- |
| Logistics & support | 1341 |
| Cyber & IT | 572 |
| C4ISR & communications | 268 |
| Land systems | 236 |
| Other defence | 135 |
| Naval & maritime | 124 |
| Ammunition & explosives | 87 |
| Air systems | 40 |
| Defence R&D | 35 |
| Sensors, radar & electronic warfare | 19 |
| Air & missile defence | 6 |
| Space | 1 |

## Raw-array alignment anomalies

| check | notices |
| --- | --- |
| estimated-value-lot vs estimated-value-cur-lot length mismatch | 868 |
| result-value-lot vs result-value-cur-lot length mismatch | 180 |
| received-submissions code vs val length mismatch | 0 |
| unique winner names vs winner-identifier count mismatch | 246 |
| buyer-identifier count != buyer-country count | 709 |
| notices with > 10 buyers | 192 |

## Snapshot preview (market metrics, strict universe)

| metric | value |
| --- | --- |
| new competitions 30d / previous | 629 / 724 |
| estimated value 30d | EUR 3.8bn (coverage 43.6%) |
| award value 30d | EUR 1.7bn (coverage 57.7%) |
| top country 90d | PL |
| top category 90d | Cyber & IT |
| median tenders 365d | 2.0 (n=5719) |
| single-bid share 365d | 31.3% |
| median public time to result 365d | 55.0 days (n=114) |
| non-award share 365d | 14.4% |
| snapshot text | 2191 competitions / 90d · EUR 26.1bn |
| country ranking text | PL EUR 14.7bn · FR EUR 3.4bn · NO EUR 2.1bn · CZ EUR 1.5bn · ES EUR 1.2bn |
| external latest text | ES · Air systems · EUR 11m · published 2026-09-11 |
| top supplier 365d | WB Electronics S.A. |
| supplier top-5 share | 56.5% |
