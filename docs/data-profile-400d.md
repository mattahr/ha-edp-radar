# TED data profile — strict mode, last 400 days

Generated 2026-09-12T17:32:19+00:00 by `scripts/data_profile.py` (taxonomy 2026.09.1/2026.09.1). Countries: all.

## Volume

| measure | value |
| --- | --- |
| raw notices returned | 25750 |
| parse errors | 0 |
| notice versions | 25750 |
| unique notice ids | 25716 |
| unique procedures (incl. unlinked pseudo-procedures) | 15291 |
| central-purchasing-only notices (>10 buyers, buyer signal only) | 787 |

## Versions and changes

| notice-version | count |
| --- | --- |
| 1 | 25002 |
| 2 | 566 |
| 3 | 115 |
| 4 | 38 |
| 5 | 13 |
| 6 | 7 |
| 7 | 2 |
| 8 | 3 |
| 12 | 1 |
| 13 | 2 |
| 22 | 1 |

- notice versions carrying change info: 3640 (v1: 3188, v>1: 452)
- modification notices: 103

## Stage distribution (latest versions)

| stage | count |
| --- | --- |
| competition | 12479 |
| direct_award | 295 |
| modification | 103 |
| other | 30 |
| planning | 612 |
| result | 12197 |

## Match reasons (latest versions)

| reasons | count |
| --- | --- |
| defence_buyer | 18558 |
| defence_buyer+defence_cpv | 868 |
| defence_buyer+defence_cpv+defence_legal_basis | 1389 |
| defence_buyer+defence_legal_basis | 2560 |
| defence_cpv+defence_legal_basis | 498 |
| defence_legal_basis | 1843 |

## Primary buyer country (latest versions, top 30)

| country | count |
| --- | --- |
| PL | 4877 |
| DE | 3376 |
| ES | 2161 |
| FR | 2049 |
| CZ | 1810 |
| RO | 1271 |
| HR | 891 |
| EE | 879 |
| FI | 739 |
| NO | 718 |
| LT | 683 |
| LV | 649 |
| NL | 598 |
| PT | 574 |
| SI | 529 |
| SK | 512 |
| BE | 489 |
| DK | 433 |
| IT | 392 |
| GR | 380 |
| SE | 344 |
| BG | 344 |
| CH | 277 |
| HU | 229 |
| IE | 169 |
| AT | 145 |
| LU | 63 |
| CY | 51 |
| MK | 39 |
| MD | 31 |

## Coverage

| measure | value |
| --- | --- |
| procedure-id coverage (latest versions) | 97.5% |
| buyer-identifier coverage | 98.2% |
| competitions with estimated value | 4599/9543 (48.2%) |
| … convertible to EUR | 4592/9543 (48.1%) |
| results with result value | 6529/11996 (54.4%) |
| … convertible to EUR | 6425/11996 (53.6%) |
| results with winners | 10921/11996 |
| framework-agreement results (ceiling kept, award value unknown) | 4107/11996 |
| … with a winner identifier for every winner | 91.7% |
| … of which with a declared framework ceiling | 3380/4107 |
| results with comparable tender counts | 81.6% |
| results with selection statuses | 99.9% |
| results linked to a competition in the window | 41.6% |
| notices without strategic category | 54.8% |

## Currencies

| currency | monetary fields |
| --- | --- |
| EUR | 10656 |
| PLN | 3083 |
| CZK | 1558 |
| RON | 723 |
| NOK | 386 |
| SEK | 372 |
| DKK | 292 |
| BGN | 261 |
| CHF | 144 |
| HUF | 88 |
| USD | 29 |
| MDL | 29 |
| GBP | 13 |
| MKD | 4 |
| CAD | 3 |
| XPF | 1 |
| ISK | 1 |

## Received-submission type codes (all result notices, per lot entry)

| type code | entries |
| --- | --- |
| t-esubm | 30873 |
| tenders | 29512 |
| t-sme | 26998 |
| t-oth-eea | 23984 |
| t-no-eea | 22974 |
| t-verif-inad-low | 3618 |
| t-verif-inad | 3605 |
| part-req | 3055 |
| t-no-verif | 1479 |
| t-small | 796 |
| t-med | 777 |
| t-micro | 729 |

## Selection status and non-award justifications

| winner-selection-status | lot entries |
| --- | --- |
| selec-w | 30757 |
| clos-nw | 5726 |
| open-nw | 961 |

| non-award-justification | entries |
| --- | --- |
| no-rece | 3045 |
| all-rej | 1124 |
| other | 554 |
| ins-fund | 332 |
| tch-pr-error | 325 |
| no-signed | 143 |
| chan-need | 114 |
| one-admis | 63 |
| rev-body | 9 |
| rev-buyer | 8 |

## Top CPV divisions (latest versions)

| CPV division | notices |
| --- | --- |
| 15 | 6439 |
| 50 | 4997 |
| 45 | 3834 |
| 35 | 3821 |
| 39 | 3614 |
| 34 | 3273 |
| 33 | 3027 |
| 71 | 2525 |
| 72 | 2300 |
| 18 | 2221 |
| 30 | 2122 |
| 90 | 2061 |
| 44 | 2007 |
| 03 | 1962 |
| 42 | 1599 |

## Strategic categories (latest versions, multi-label)

| category | notices |
| --- | --- |
| Logistics & support | 6339 |
| Cyber & IT | 2273 |
| C4ISR & communications | 978 |
| Land systems | 934 |
| Other defence | 620 |
| Naval & maritime | 459 |
| Ammunition & explosives | 397 |
| Air systems | 164 |
| Defence R&D | 152 |
| Sensors, radar & electronic warfare | 105 |
| Air & missile defence | 19 |
| Space | 2 |
| UAS / C-UAS | 1 |

## Raw-array alignment anomalies

| check | notices |
| --- | --- |
| estimated-value-lot vs estimated-value-cur-lot length mismatch | 3304 |
| result-value-lot vs result-value-cur-lot length mismatch | 829 |
| received-submissions code vs val length mismatch | 0 |
| unique winner names vs winner-identifier count mismatch | 922 |
| buyer-identifier count != buyer-country count | 2910 |
| notices with > 10 buyers | 797 |

## Snapshot preview (market metrics, strict universe)

| metric | value |
| --- | --- |
| new competitions 30d / previous | 626 / 712 |
| estimated value 30d | EUR 3.8bn (coverage 43.3%) |
| award value 30d | EUR 1.7bn (coverage 58.3%) |
| top country 90d | PL |
| top category 90d | Cyber & IT |
| median tenders 365d | 2.0 (n=19601) |
| single-bid share 365d | 31.7% |
| median public time to result 365d | 102.0 days (n=3731) |
| non-award share 365d | 13.8% |
| snapshot text | 2154 competitions / 90d · EUR 23.3bn · +84.0% vs previous 90d |
| country ranking text | PL EUR 14.7bn · NO EUR 2.1bn · CZ EUR 1.5bn · ES EUR 1.2bn · SE EUR 774m |
| external latest text | ES · Air systems · EUR 11m · published 2026-09-11 |
| top supplier 365d | ORLEN S.A. |
| supplier top-5 share | 88.0% |
