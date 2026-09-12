# Country purchasing data profile — strict mode, last 760 days

Generated 2026-09-12T20:51:02+00:00 by `scripts/country_purchasing_profile.py` (taxonomy 2026.09.1/2026.09.1). Countries: all. Reference date 2026-09-12.

**Definition of a purchase (plan §4):** the Notice Value (BT-161) of an awarded, non-framework result notice, counted once per notice and converted to EUR at the award date. Framework ceilings, estimates, non-awarded procedures and quarantined implausible values are not purchases.

## Volume

| measure | value |
| --- | --- |
| raw notices returned | 47934 |
| parse errors | 0 |
| months covered | 2024-08 … 2026-09 (26) |
| relevant notice versions (strict, CPB excluded) | 46680 |
| central-purchasing-only notices excluded | 1254 |
| result notices (latest original version) | 21289 |
| … of kind `awarded` | 19239 |
| … of kind `not_awarded` | 2033 |
| … of kind `unknown` | 17 |
| awarded results that are framework agreements | 5924 |
| awarded non-framework results | 13315 |
| … with usable Notice Value | 12167 |

## Award notices and Notice Value coverage by country

`valued` = awarded non-framework results with a positive Notice Value (BT-161). `coverage incl. FW` counts framework results as awarded without a usable value; `EUR` = share of non-framework awarded results convertible to EUR at the award date.

| country | results | non-awarded | framework | non-FW awarded | valued (coverage) | coverage incl. FW | EUR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PL | 4112 | 567 | 71 | 3474 | 3435 (98.9%) | 96.9% | 97.5% |
| DE | 2850 | 331 | 1074 | 1445 | 489 (33.8%) | 19.4% | 33.8% |
| CZ | 1976 | 227 | 800 | 949 | 948 (99.9%) | 54.2% | 97.2% |
| ES | 1733 | 95 | 480 | 1158 | 1151 (99.4%) | 70.3% | 99.4% |
| RO | 1391 | 70 | 1029 | 292 | 292 (100.0%) | 22.1% | 100.0% |
| FR | 1266 | 53 | 839 | 374 | 362 (96.8%) | 29.8% | 96.8% |
| EE | 1241 | 37 | 122 | 1082 | 1082 (100.0%) | 89.9% | 100.0% |
| FI | 1007 | 65 | 51 | 891 | 890 (99.9%) | 94.5% | 99.9% |
| SK | 581 | 34 | 263 | 284 | 242 (85.2%) | 44.2% | 85.2% |
| PT | 499 | 26 | 4 | 469 | 465 (99.1%) | 98.3% | 99.1% |
| NL | 495 | 57 | 212 | 226 | 184 (81.4%) | 42.0% | 80.5% |
| BG | 468 | 60 | 181 | 227 | 227 (100.0%) | 55.6% | 100.0% |
| LV | 441 | 52 | 138 | 251 | 251 (100.0%) | 64.5% | 100.0% |
| LT | 424 | 77 | 1 | 346 | 345 (99.7%) | 99.4% | 99.7% |
| SI | 363 | 32 | 45 | 286 | 285 (99.7%) | 86.1% | 99.7% |
| DK | 329 | 56 | 132 | 141 | 137 (97.2%) | 50.2% | 93.6% |
| SE | 291 | 36 | 148 | 107 | 105 (98.1%) | 41.2% | 91.6% |
| BE | 273 | 14 | 32 | 227 | 202 (89.0%) | 78.0% | 89.0% |
| CH | 266 | 16 | 0 | 250 | 242 (96.8%) | 96.8% | 96.8% |
| NO | 256 | 41 | 120 | 95 | 94 (98.9%) | 43.7% | 97.9% |
| HU | 193 | 29 | 10 | 154 | 154 (100.0%) | 93.9% | 97.4% |
| IT | 188 | 14 | 48 | 126 | 126 (100.0%) | 72.4% | 100.0% |
| HR | 143 | 12 | 63 | 68 | 68 (100.0%) | 51.9% | 100.0% |
| IE | 134 | 13 | 17 | 104 | 103 (99.0%) | 85.1% | 99.0% |
| AT | 124 | 3 | 4 | 117 | 116 (99.1%) | 95.9% | 99.1% |
| GR | 117 | 20 | 31 | 66 | 66 (100.0%) | 68.0% | 100.0% |
| LU | 59 | 2 | 3 | 54 | 54 (100.0%) | 94.7% | 98.1% |
| CY | 44 | 4 | 0 | 40 | 40 (100.0%) | 100.0% | 100.0% |
| MT | 10 | 5 | 0 | 5 | 5 (100.0%) | 100.0% | 100.0% |
| MULTI | 7 | 0 | 5 | 2 | 2 (100.0%) | 28.6% | 100.0% |
| IS | 5 | 2 | 1 | 2 | 2 (100.0%) | 66.7% | 100.0% |
| MD | 3 | 0 | 0 | 3 | 3 (100.0%) | 100.0% | 0.0% |

## Currencies (awarded non-framework results with Notice Value)

| currency | results | convertible to EUR | sum (original) |
| --- | --- | --- | --- |
| EUR | 6613 | 6613 (100.0%) | 58,385,531,553 |
| PLN | 3430 | 3381 (98.6%) | 1,228,392,118,197 |
| CZK | 934 | 908 (97.2%) | 43,935,418,624 |
| RON | 281 | 281 (100.0%) | 8,480,415,831 |
| CHF | 243 | 243 (100.0%) | 1,595,824,620 |
| BGN | 158 | 158 (100.0%) | 685,459,137 |
| HUF | 153 | 149 (97.4%) | 180,407,350,237 |
| SEK | 106 | 99 (93.4%) | 11,171,247,818 |
| DKK | 93 | 89 (95.7%) | 32,422,909,596 |
| NOK | 92 | 91 (98.9%) | 9,492,371,651 |
| USD | 34 | 31 (91.2%) | 709,068,976 |
| GBP | 21 | 21 (100.0%) | 136,830,565 |
| CAD | 4 | 4 (100.0%) | 100,080,123 |
| MDL | 3 | 0 (0.0%) | 9,338,150 |
| USN | 1 | 0 (0.0%) | 689,645 |
| AUD | 1 | 1 (100.0%) | 1,003,110 |

- EUR-convertible share of valued results: 99.2%; converted total EUR 360.8bn before the plausibility quarantine.

## Buyer-country coverage and joint procurement

| distinct buyer countries per result | results |
| --- | --- |
| exactly one | 21282 |
| several (MULTI) | 7 |

- joint/multinational results: 7, attributable awarded value (non-framework, EUR-convertible) EUR 9.7m.
- `buyer-country` arrays are flattened across buyers and not aligned with lots, so no lot-level split by country is possible; the value is kept once under `MULTI`.

| notice | countries | buyers | awarded value | title |
| --- | --- | --- | --- | --- |
| 638000-2024 | DK/SE/NO/IS | 5 | EUR n/a | Contract award notice for the tender "CS-gas" |
| 749322-2024 | NO/SE | 6 | EUR n/a | Breaching tools |
| 797731-2024 | NO/SE | 3 | EUR n/a | 6-axle flat freight railway wagons for heavy load |
| 208278-2025 | NO/FI | 6 | EUR n/a | Hand held alchemometers and accessories |
| 648855-2025 | EE/LT | 2 | EUR n/a | Mobiilsete välihaiglate ostmine |
| 806226-2025 | FI/SE | 2 | EUR 9.0m | LAIVATYKISTÖN AMPUMATARVIKKEET |
| 862502-2025 | FI/SE | 2 | EUR 748k | Ammuslaatikoiden hankinta |

## Framework agreements

| measure | value |
| --- | --- |
| awarded framework results | 5924 |
| … with a positive Notice Value (BT-161) | 2229 |
| … with a Framework Maximum Value (BT-118) | 2274 |
| … with both | 1113 |
| … with at least one positive tender value | 3774 |
| … with tender values all zero | 89 |
| framework-agreement-lot values | fa-wo-rc: 4723, fa-mix: 739, fa-w-rc: 472, none: 16 |

Notice Value ÷ Framework Maximum Value where both exist:

| ratio | results |
| --- | --- |
| 0.5 – 0.99 | 205 |
| 1 – 2 | 33 |
| 2 – 10 | 21 |
| < 0.5 | 716 |
| = 1 | 135 |
| > 10 | 3 |

Largest framework Notice Values (never counted as purchases):

| notice | country | Notice Value | framework max | tender values | title |
| --- | --- | --- | --- | --- | --- |
| 256722-2026 | RO | 3,418,889,493 RON | 3,423,620,527 | 7 | Platforme de transport auto multifuncționale pe roți |
| 759309-2024 | CZ | 3,371,900,826 CZK | — | 1 | Protitankové miny |
| 38915-2026 | FR | 2,449,392,735 EUR | — | 1 | Acquisition et soutien de porteurs logistiques de charge utile 6 tonne |
| 181940-2026 | RO | 2,349,871,072 RON | 3,423,620,527 | 6 | Platforme de transport auto multifuncționale pe roți |
| 195765-2026 | RO | 2,349,871,072 RON | 3,423,620,527 | 6 | Platforme de transport auto multifuncționale pe roți |
| 177460-2026 | RO | 2,326,207,573 RON | 3,423,620,527 | 5 | Platforme de transport auto multifuncționale pe roți |
| 76342-2025 | CZ | 1,943,801,653 CZK | — | 0 | Cisternový automobil plnič techniky |
| 221263-2025 | CZ | 1,890,909,000 CZK | — | 1 | Servisní podpora techniky na podvozku PANDUR II 8x8 KBV a KOT, KOVS a  |

## Notice versions, republication and duplicate values

| measure | value |
| --- | --- |
| result notice versions stored | 21750 |
| version 1 | 21510 |
| version 2 | 201 |
| version 3 | 24 |
| version 4 | 8 |
| version 5 | 3 |
| version 6 | 1 |
| version 8 | 1 |
| version 13 | 2 |
| result notice ids with more than one stored version | 22 |
| result versions carrying change info (not originals) | 443 |
| procedures with one Notice Value in several original results | 92 |
| … repeated value beyond the first notice | EUR 386m |

The store keeps every `(notice-identifier, notice-version)`; the lifecycle index uses the latest version per identifier and excludes change notices, so a republished result is counted once.

## Lot behaviour

| measure | value |
| --- | --- |
| awarded non-framework results without Notice Value | 1148 |
| … where every tender value is positive | 106 |
| non-framework results with a positive `result-value-lot` | 6 |

Notice Value versus the sum of `tender-value` (BT-720) on the same notice:

| relation | results |
| --- | --- |
| sum(tender-value) = Notice Value (±1 %) | 10171 |
| sum(tender-value) > Notice Value | 928 |
| sum(tender-value) < Notice Value | 555 |
| no tender values | 492 |
| tender values all zero | 21 |

Notice Value already represents the notice total; tender values disagree upwards often enough that summing them is not a safe fallback.

## Award-date coverage

| date basis used | awarded results |
| --- | --- |
| decision_date | 8967 |
| publication_date | 10272 |

Publication date minus earliest `winner-decision-date`, where present:

| lag (days) | results |
| --- | --- |
| 0 – 30 | 3120 |
| 181 – 365 | 367 |
| 31 – 60 | 3543 |
| 61 – 90 | 1045 |
| 91 – 180 | 892 |
| > 365 | 417 |

Decision-date basis by country:

| country | awarded results | on decision-date basis |
| --- | --- | --- |
| PL | 3545 | 2497 (70.4%) |
| DE | 2519 | 162 (6.4%) |
| CZ | 1749 | 1440 (82.3%) |
| ES | 1638 | 1589 (97.0%) |
| RO | 1321 | 12 (0.9%) |
| FR | 1213 | 939 (77.4%) |
| EE | 1204 | 0 (0.0%) |
| FI | 942 | 140 (14.9%) |
| SK | 547 | 194 (35.5%) |
| PT | 473 | 130 (27.5%) |
| NL | 438 | 246 (56.2%) |
| BG | 408 | 69 (16.9%) |
| LV | 389 | 389 (100.0%) |
| LT | 347 | 139 (40.1%) |
| SI | 331 | 1 (0.3%) |
| DK | 273 | 202 (74.0%) |
| BE | 259 | 25 (9.7%) |
| SE | 255 | 218 (85.5%) |
| CH | 250 | 0 (0.0%) |
| NO | 215 | 83 (38.6%) |
| IT | 174 | 98 (56.3%) |
| HU | 164 | 153 (93.3%) |
| HR | 131 | 109 (83.2%) |
| AT | 121 | 1 (0.8%) |
| IE | 121 | 82 (67.8%) |
| GR | 97 | 33 (34.0%) |
| LU | 57 | 0 (0.0%) |
| CY | 40 | 10 (25.0%) |
| MULTI | 7 | 4 (57.1%) |
| MT | 5 | 0 (0.0%) |
| MD | 3 | 0 (0.0%) |
| IS | 3 | 2 (66.7%) |

## Procedure types among awarded results

All of these count as purchases (plan §32); `neg-wo-call` is a direct award.

| procedure-type | awarded results |
| --- | --- |
| open | 10464 |
| restricted | 4466 |
| neg-wo-call | 2250 |
| neg-w-call | 1495 |
| oth-single | 390 |
| oth-mult | 73 |
| (none) | 65 |
| comp-dial | 27 |
| comp-tend | 7 |
| innovation | 2 |

## Largest 50 awarded values (non-framework, EUR at award date)

Quarantine flags (`above_absolute_cap`, `exceeds_estimate`, `exceeds_tender_values`, `duplicate_value_in_procedure`) exclude a value from every total; `unverified_large` keeps it but marks that no real estimate corroborates an award of EUR 250m or more.

| # | notice | country | EUR | original | estimate | Σ tenders | flags | title |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [157377-2026](https://ted.europa.eu/en/notice/-/detail/157377-2026) | PL | EUR 257.8bn | 1,086,150,000,000 PLN | — | 1,086,150,000,000 | above_absolute_cap | Dostawa oleju napędowego w latach 2026-2028 |
| 2 | [175957-2026](https://ted.europa.eu/en/notice/-/detail/175957-2026) | PT | EUR 11.7bn | 11,739,600,000 EUR | 29,313,711 EUR | 11,739,600,000 | above_absolute_cap, exceeds_estimate | CONCURSO PÚBLICO PARA AQUISIÇÃO DE SERVIÇOS DE DISPONIBILIZAÇÃO E LOCA |
| 3 | [220199-2026](https://ted.europa.eu/en/notice/-/detail/220199-2026) | PT | EUR 7.3bn | 7,274,615,930 EUR | 7,317,073 EUR | 7,274,615,930 | exceeds_estimate | AQUISIÇÃO DE AERONAVES DE INSTRUÇÃO ELEMENTAR - DEP 5025009947 |
| 4 | [177041-2026](https://ted.europa.eu/en/notice/-/detail/177041-2026) | PT | EUR 5.4bn | 5,443,680,000 EUR | 29,313,711 EUR | 5,443,680,000 | exceeds_estimate | CONCURSO PÚBLICO PARA AQUISIÇÃO DE SERVIÇOS DE DISPONIBILIZAÇÃO E LOCA |
| 5 | [219007-2026](https://ted.europa.eu/en/notice/-/detail/219007-2026) | PL | EUR 3.7bn | 15,477,039,450 PLN | 18,483,118 PLN | 18,483,118,270 | exceeds_estimate | Usługa sprzątania powierzchni wewnętrznych w rejonie odpowiedzialności |
| 6 | [766565-2024](https://ted.europa.eu/en/notice/-/detail/766565-2024) | PL | EUR 2.9bn | 12,407,025,000 PLN | — | 12,407,025,000 | unverified_large | Dostawa sosów, zup, przypraw przetworzonych, kawy, herbaty, miodu, dań |
| 7 | [419618-2026](https://ted.europa.eu/en/notice/-/detail/419618-2026) | PL | EUR 2.2bn | 9,311,212,000 PLN | — | 9,311,212,000 | unverified_large | Dostawa bmo BSP-U GLADIUS |
| 8 | [822738-2025](https://ted.europa.eu/en/notice/-/detail/822738-2025) | DK | EUR 2.1bn | 2,115,606,235 EUR | — | 2,115,606,235 | unverified_large | Procurement of Surface Based Air and Missile Defence capability |
| 9 | [435837-2026](https://ted.europa.eu/en/notice/-/detail/435837-2026) | PL | EUR 1.8bn | 7,902,251,478 PLN | 7,985,386,477 PLN | 7,902,251,478 |  | Dostawa elementów składowych do 155 mm dywizjonowych modułów ogniowych |
| 10 | [394720-2025](https://ted.europa.eu/en/notice/-/detail/394720-2025) | PL | EUR 1.7bn | 7,247,040,000 PLN | — | 7,247,040 | exceeds_tender_values | Dostawa filtropochłaniaczy |
| 11 | [759366-2024](https://ted.europa.eu/en/notice/-/detail/759366-2024) | PL | EUR 1.6bn | 7,036,104,000 PLN | — | 7,036,104,000 | unverified_large | Dostawa mięsa czerwonego, wędlin z mięsa czerwonego oraz tłuszczy zwie |
| 12 | [181558-2026](https://ted.europa.eu/en/notice/-/detail/181558-2026) | FR | EUR 1.5bn | 1,486,387,775 EUR | — | 1,486,387,775 | unverified_large | Maintien en Condition Opérationnelle des avions C-130J-30 et KC-130J d |
| 13 | [269132-2026](https://ted.europa.eu/en/notice/-/detail/269132-2026) | DK | EUR 1.5bn | 1,468,348,800 EUR | 1,468,348,800 EUR | 1,468,348,800 |  | Procurement of Surface Based Air and Missile Defence capability |
| 14 | [340509-2026](https://ted.europa.eu/en/notice/-/detail/340509-2026) | IT | EUR 1.4bn | 1,393,362,000 EUR | 1,408,174,965 EUR | 1,393,362,000 |  | GARA EUROPEA A PROCEDURA RISTRETTA PER IL RINNOVAMENTO, POTENZIAMENTO  |
| 15 | [282948-2025](https://ted.europa.eu/en/notice/-/detail/282948-2025) | BE | EUR 1.3bn | 1,338,125,174 EUR | — | 1,338,125,174 | unverified_large | nvt |
| 16 | [822641-2025](https://ted.europa.eu/en/notice/-/detail/822641-2025) | DK | EUR 1.2bn | 1,224,895,396 EUR | — | 1,224,895,396 | unverified_large | Procurement of Surface Based Air and Missile Defence capability |
| 17 | [499753-2026](https://ted.europa.eu/en/notice/-/detail/499753-2026) | PT | EUR 1.2bn | 1,159,000,000 EUR | 1,450,000,000 EUR | 1,450,000,000 |  | 4025033649/DA/A0395/2025-Modernização de Viaturas Táticas Land Cruiser |
| 18 | [385159-2026](https://ted.europa.eu/en/notice/-/detail/385159-2026) | LT | EUR 1.1bn | 1,092,005,666 EUR | — | 1,092,005,666 | unverified_large | Įvairios paskirties karinių sunkvežimių ir visureigių pirkimas |
| 19 | [774863-2024](https://ted.europa.eu/en/notice/-/detail/774863-2024) | PL | EUR 1.1bn | 4,620,720,000 PLN | — | 4,620,720,000 | unverified_large | Dostawa ziemniaków, warzyw, owoców gr. I i II dla 25. WOG w Białymstok |
| 20 | [436728-2026](https://ted.europa.eu/en/notice/-/detail/436728-2026) | PL | EUR 1.0bn | 4,498,707,782 PLN | 2,728,944,886 PLN | 4,498,707,782 |  | Dostawa elementów składowych na potrzeby kompanijnych modułów ogniowyc |
| 21 | [822608-2025](https://ted.europa.eu/en/notice/-/detail/822608-2025) | BE | EUR 1.0bn | 1,009,799,572 EUR | — | 830,076,546 | unverified_large | Marché public N°21AP004 relatif à la réalisation d’un contrat de servi |
| 22 | [491853-2024](https://ted.europa.eu/en/notice/-/detail/491853-2024) | RO | EUR 925m | 4,602,657,510 RON | — | 4,602,657,510 | unverified_large | Sistem obuzier cal. 155 mm de nivel Batalion, Lovitură 155 mm cu proie |
| 23 | [651754-2025](https://ted.europa.eu/en/notice/-/detail/651754-2025) | PL | EUR 910m | 3,862,200,002 PLN | — | 38,469,000 | exceeds_tender_values | Wykonanie dokumentacji projektowej i wykonanie robót budowlanych w ram |
| 24 | [163-2025](https://ted.europa.eu/en/notice/-/detail/163-2025) | PL | EUR 759m | 3,236,069,080 PLN | — | 3,236,069,080 | unverified_large | Dostawa drobiu i wędlin drobiowych dla 25. WOG w Białymstoku |
| 25 | [241852-2026](https://ted.europa.eu/en/notice/-/detail/241852-2026) | PL | EUR 749m | 3,188,718,051 PLN | — | 3,188,718,051 | unverified_large | Modernizacja techniczna Prywatnej Chmury Obliczeniowej „PChO” wraz z z |
| 26 | [107790-2025](https://ted.europa.eu/en/notice/-/detail/107790-2025) | PT | EUR 690m | 690,000,000 EUR | 690,000 EUR | 690,000 | exceeds_estimate, exceeds_tender_values | Fornecimento de Impulsor de Proa - NRP Sagres |
| 27 | [202260-2026](https://ted.europa.eu/en/notice/-/detail/202260-2026) | PL | EUR 673m | 2,837,540,220 PLN | 2,837,540 PLN | 181,155,760 | exceeds_estimate | „Dostawa – sukcesywny zakup i dostawa części zamiennych, ogumienia, ak |
| 28 | [210859-2025](https://ted.europa.eu/en/notice/-/detail/210859-2025) | PT | EUR 642m | 641,598,000 EUR | — | 641,598 | exceeds_tender_values | Aquisição de serviços de vigilância eletrónica, para execução de decis |
| 29 | [745959-2024](https://ted.europa.eu/en/notice/-/detail/745959-2024) | PL | EUR 610m | 2,650,656,960 PLN | — | 2,650,656,960 | unverified_large | Zabezpieczenie w przenośne urządzenia sanitarne dostosowane do potrzeb |
| 30 | [801004-2024](https://ted.europa.eu/en/notice/-/detail/801004-2024) | PL | EUR 606m | 2,585,769,641 PLN | — | 2,585,769,641 | unverified_large | ”Outsourcing w zakresie SUFO w podziale na 4 zadania”. |
| 31 | [340004-2025](https://ted.europa.eu/en/notice/-/detail/340004-2025) | FR | EUR 601m | 601,062,000 EUR | — | 601,062,000 | unverified_large | Acquisition et soutien d’aéronefs, moyens, travaux d’infrastructures e |
| 32 | [153677-2026](https://ted.europa.eu/en/notice/-/detail/153677-2026) | PL | EUR 584m | 2,461,622,400 PLN | — | 2,461,622,400 | unverified_large | Usługa odbioru i zagospodarowania zmieszanych odpadów komunalnych, odp |
| 33 | [452407-2026](https://ted.europa.eu/en/notice/-/detail/452407-2026) | PL | EUR 573m | 2,426,880,000 PLN | 1,973,073 PLN | 2,426,880 | exceeds_estimate, exceeds_tender_values | Badania diagnostyczne i konsultacje specjalistyczne dla potrzeb orzeka |
| 34 | [429414-2025](https://ted.europa.eu/en/notice/-/detail/429414-2025) | PL | EUR 571m | 2,426,880,000 PLN | 1,973,073 PLN | 2,426,880 | exceeds_estimate, exceeds_tender_values | Badania diagnostyczne i konsultacje specjalistyczne dla potrzeb orzeka |
| 35 | [824674-2025](https://ted.europa.eu/en/notice/-/detail/824674-2025) | DK | EUR 540m | 539,981,084 EUR | — | 539,981,084 | unverified_large | Procurement of Surface Based Air and Missile Defence capability |
| 36 | [42128-2026](https://ted.europa.eu/en/notice/-/detail/42128-2026) | DK | EUR 521m | 3,892,780,485 DKK | — | 3,892,780,485 | unverified_large | The acquisition of Fixed Air Defence Radars (FADR), including support  |
| 37 | [193451-2025](https://ted.europa.eu/en/notice/-/detail/193451-2025) | NL | EUR 516m | 529,000,000 USD | 529,000,000 USD | 1,058,000,000 |  | PATRIOT Backfill Major end itmes DCS |
| 38 | [680073-2024](https://ted.europa.eu/en/notice/-/detail/680073-2024) | PL | EUR 495m | 2,126,256,995 PLN | — | 2,151,725,988 | unverified_large | Usług kompleksowego utrzymania czystości pomieszczeń w budynkach, utrz |
| 39 | [558890-2026](https://ted.europa.eu/en/notice/-/detail/558890-2026) | FR | EUR 458m | 458,017,000 EUR | — | 458,017,000 | unverified_large | Fourniture de cibles "EMATT AAT" destinées à l'entraînement élémentair |
| 40 | [52272-2026](https://ted.europa.eu/en/notice/-/detail/52272-2026) | DK | EUR 453m | 3,386,645,501 DKK | — | 3,386,645,501 | unverified_large | Indgåelse af OPP-kontrakt vedrørende Danske kaserner som Offentligt Pr |
| 41 | [220215-2025](https://ted.europa.eu/en/notice/-/detail/220215-2025) | PT | EUR 430m | 429,986,410 EUR | — | 429,986,410 | unverified_large | Fornecimento de eletricidade para as instalações da Direção-Geral de R |
| 42 | [781006-2025](https://ted.europa.eu/en/notice/-/detail/781006-2025) | DK | EUR 429m | 3,200,000,000 DKK | — | 3,200,000,000 | unverified_large | Anskaffelse af 44 CV9035 MkIIIC |
| 43 | [482388-2025](https://ted.europa.eu/en/notice/-/detail/482388-2025) | DK | EUR 391m | 390,762,500 EUR | — | 390,762,500 | unverified_large | Procurement of a Surface Based Air and Missile Defence (land) capabili |
| 44 | [70569-2025](https://ted.europa.eu/en/notice/-/detail/70569-2025) | FR | EUR 369m | 369,482,534 EUR | 369,482,534 EUR | 369,482,534 |  | Fourniture de coups complets PROJ 120 ECL F2 et PROJ 120 PRY IR F3 |
| 45 | [131085-2026](https://ted.europa.eu/en/notice/-/detail/131085-2026) | BE | EUR 358m | 358,217,852 EUR | — | 2,200,043,495 | unverified_large | Marché mixte pluriannuel pour le soutien du matériel CaMo, y compris u |
| 46 | [161437-2026](https://ted.europa.eu/en/notice/-/detail/161437-2026) | PT | EUR 353m | 352,648,330 EUR | 352,648 EUR | 352,648,330 | exceeds_estimate | DAT 5025011672 - CONCURSO PÚBLICO PLURIANUAL 2026-2027 PARA A REPARAÇÃ |
| 47 | [634673-2025](https://ted.europa.eu/en/notice/-/detail/634673-2025) | CH | EUR 347m | 324,300,000 CHF | — | 324,300,000 | unverified_large | Mini Unmanned Aerial Systems (MUAS), MUAS-Einzelteile/Baugruppen, ergä |
| 48 | [431025-2026](https://ted.europa.eu/en/notice/-/detail/431025-2026) | PL | EUR 319m | 1,367,352,302 PLN | — | 1,367,352,302 | unverified_large | Dostawa kaset minowych ISM z minami narzutowymi MN-123 |
| 49 | [519721-2025](https://ted.europa.eu/en/notice/-/detail/519721-2025) | PL | EUR 304m | 1,292,568,500 PLN | — | 1,292,568 | exceeds_tender_values | DOSTAWA MATERIAŁÓW EKSPLOATACYJNYCH DO DRUKAREK I URZĄDZEŃ WIELOFUNKCY |
| 50 | [809906-2025](https://ted.europa.eu/en/notice/-/detail/809906-2025) | DK | EUR 268m | 2,000,000,000 DKK | — | 2,000,000,000 | unverified_large | Anskaffelse af miltære lastbiler |

Flags over all valued non-framework awards (duplicates are detected in the model, see below):

| flag | results |
| --- | --- |
| above_absolute_cap | 2 |
| exceeds_estimate | 17 |
| exceeds_tender_values | 21 |
| unverified_large | 30 |
| total valued results | 12167 |

## Model preview: rolling 12 months (purchasing model, strict universe)

Period: 2025-09-12 < award date ≤ 2026-09-12; previous period of equal length.

| rank | country | awarded 12m | share | vs previous 12m | awards | value coverage | framework results | quarantined | unverified large | top category |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PL | EUR 11.8bn | 36.8% | +6.3% | 1483 | 95.5% | 32 | 13 | 4 / EUR 3.8bn | Unclassified |
| 2 | FR | EUR 3.2bn | 10.2% | +46.8% | 508 | 32.7% | 338 | 0 | 2 / EUR 1.9bn | Unclassified |
| 3 | BE | EUR 2.6bn | 8.1% | +30.0% | 120 | 83.3% | 15 | 0 | 2 / EUR 1.4bn | Logistics & support |
| 4 | DK | EUR 2.4bn | 7.5% | -67.1% | 122 | 56.6% | 50 | 0 | 2 / EUR 975m | Unclassified |
| 5 | IT | EUR 1.7bn | 5.2% | +869.9% | 70 | 77.1% | 15 | 1 | — | Unclassified |
| 6 | LT | EUR 1.6bn | 5.1% | +178.8% | 163 | 98.8% | 1 | 0 | 1 / EUR 1.1bn | Logistics & support |
| 7 | CH | EUR 1.4bn | 4.3% | +392.7% | 143 | 92.3% | 0 | 3 | 1 / EUR 347m | Unclassified |
| 8 | PT | EUR 1.4bn | 4.3% | +21.1% | 242 | 95.0% | 2 | 10 | — | Land systems |
| 9 | CZ | EUR 798m | 2.5% | -28.1% | 726 | 53.7% | 330 | 6 | — | Unclassified |
| 10 | RO | EUR 774m | 2.4% | +149.2% | 646 | 18.9% | 522 | 2 | — | Unclassified |
| 11 | SE | EUR 589m | 1.8% | +175.7% | 94 | 41.5% | 54 | 1 | — | Defence R&D |
| 12 | NO | EUR 485m | 1.5% | +60.8% | 115 | 41.7% | 67 | 0 | — | Unclassified |
| 13 | NL | EUR 455m | 1.4% | -60.5% | 194 | 37.6% | 97 | 0 | — | Unclassified |
| 14 | ES | EUR 393m | 1.2% | -35.1% | 705 | 68.7% | 210 | 9 | — | Unclassified |
| 15 | AT | EUR 285m | 0.9% | -7.4% | 55 | 100.0% | 0 | 0 | — | Unclassified |
| 16 | DE | EUR 278m | 0.9% | -9.4% | 1122 | 18.4% | 497 | 1 | — | Unclassified |
| 17 | SI | EUR 272m | 0.8% | -29.4% | 152 | 83.6% | 23 | 1 | — | Unclassified |
| 18 | BG | EUR 248m | 0.8% | -2.4% | 173 | 59.5% | 69 | 1 | — | Unclassified |
| 19 | LU | EUR 247m | 0.8% | +202.0% | 35 | 88.6% | 2 | 2 | — | Unclassified |
| 20 | EE | EUR 214m | 0.7% | -11.1% | 635 | 90.2% | 49 | 13 | — | Unclassified |
| 21 | LV | EUR 212m | 0.7% | +27.9% | 178 | 57.3% | 71 | 5 | — | Unclassified |
| 22 | FI | EUR 174m | 0.5% | -57.0% | 389 | 92.0% | 31 | 0 | — | Unclassified |
| 23 | SK | EUR 154m | 0.5% | +219.8% | 323 | 58.5% | 128 | 5 | — | Unclassified |
| 24 | HU | EUR 144m | 0.5% | -51.7% | 60 | 93.3% | 4 | 0 | — | Unclassified |
| 25 | GR | EUR 79m | 0.2% | +228.0% | 35 | 97.1% | 1 | 0 | — | Unclassified |
| 26 | HR | EUR 50m | 0.2% | +1.9% | 70 | 44.3% | 39 | 0 | — | Unclassified |
| 27 | IE | EUR 45m | 0.1% | -79.6% | 44 | 79.5% | 8 | 0 | — | Logistics & support |
| 28 | CY | EUR 17m | 0.1% | -16.9% | 19 | 100.0% | 0 | 0 | — | Logistics & support |
| 29 | MT | EUR 2.6m | 0.0% | +941.4% | 2 | 100.0% | 0 | 0 | — | Logistics & support |

| country without usable value | awarded | framework results |
| --- | --- | --- |
| IS | 1 | 1 |
| MD | 1 | 0 |

| measure | value |
| --- | --- |
| European total 12m | EUR 32.0bn |
| country-attributable | EUR 32.0bn |
| joint/multinational (MULTI) | EUR 9.7m |
| unknown buyer country | EUR n/a |
| previous 12m total | EUR 31.3bn |
| awarded results / with usable value | 8628 / 5408 |
| countries with attributable value | 29 |
| countries active | 31 |
| quarantined results (excluded, listed) | 73 |
| identity: Σ ranked countries + MULTI + unknown = total | OK |

Fastest-growing eligible countries (≥ 5 valued awards or ≥ EUR 50m now):

| rank | country | change | awarded 12m |
| --- | --- | --- | --- |
| 1 | IT | +869.9% | EUR 1.7bn |
| 2 | CH | +392.7% | EUR 1.4bn |
| 3 | GR | +228.0% | EUR 79m |
| 4 | SK | +219.8% | EUR 154m |
| 5 | LU | +202.0% | EUR 247m |
| 6 | LT | +178.8% | EUR 1.6bn |
| 7 | SE | +175.7% | EUR 589m |
| 8 | RO | +149.2% | EUR 774m |
| 9 | NO | +60.8% | EUR 485m |
| 10 | FR | +46.8% | EUR 3.2bn |

Quarantined awards (all stored periods):

| notice | country | EUR | original | flags | title |
| --- | --- | --- | --- | --- | --- |
| [157377-2026](https://ted.europa.eu/en/notice/-/detail/157377-2026) | PL | EUR 257.8bn | 1,086,150,000,000 PLN | above_absolute_cap | Dostawa oleju napędowego w latach 2026-2028 |
| [175957-2026](https://ted.europa.eu/en/notice/-/detail/175957-2026) | PT | EUR 11.7bn | 11,739,600,000 EUR | above_absolute_cap, exceeds_estimate | CONCURSO PÚBLICO PARA AQUISIÇÃO DE SERVIÇOS DE DISPONIBILIZA |
| [220199-2026](https://ted.europa.eu/en/notice/-/detail/220199-2026) | PT | EUR 7.3bn | 7,274,615,930 EUR | exceeds_estimate | AQUISIÇÃO DE AERONAVES DE INSTRUÇÃO ELEMENTAR - DEP 50250099 |
| [177041-2026](https://ted.europa.eu/en/notice/-/detail/177041-2026) | PT | EUR 5.4bn | 5,443,680,000 EUR | exceeds_estimate | CONCURSO PÚBLICO PARA AQUISIÇÃO DE SERVIÇOS DE DISPONIBILIZA |
| [219007-2026](https://ted.europa.eu/en/notice/-/detail/219007-2026) | PL | EUR 3.7bn | 15,477,039,450 PLN | exceeds_estimate | Usługa sprzątania powierzchni wewnętrznych w rejonie odpowie |
| [394720-2025](https://ted.europa.eu/en/notice/-/detail/394720-2025) | PL | EUR 1.7bn | 7,247,040,000 PLN | exceeds_tender_values | Dostawa filtropochłaniaczy |
| [651754-2025](https://ted.europa.eu/en/notice/-/detail/651754-2025) | PL | EUR 910m | 3,862,200,002 PLN | exceeds_tender_values | Wykonanie dokumentacji projektowej i wykonanie robót budowla |
| [107790-2025](https://ted.europa.eu/en/notice/-/detail/107790-2025) | PT | EUR 690m | 690,000,000 EUR | exceeds_estimate, exceeds_tender_values | Fornecimento de Impulsor de Proa - NRP Sagres |
| [202260-2026](https://ted.europa.eu/en/notice/-/detail/202260-2026) | PL | EUR 673m | 2,837,540,220 PLN | exceeds_estimate | „Dostawa – sukcesywny zakup i dostawa części zamiennych, ogu |
| [210859-2025](https://ted.europa.eu/en/notice/-/detail/210859-2025) | PT | EUR 642m | 641,598,000 EUR | exceeds_tender_values | Aquisição de serviços de vigilância eletrónica, para execuçã |
| [452407-2026](https://ted.europa.eu/en/notice/-/detail/452407-2026) | PL | EUR 573m | 2,426,880,000 PLN | exceeds_estimate, exceeds_tender_values | Badania diagnostyczne i konsultacje specjalistyczne dla potr |
| [429414-2025](https://ted.europa.eu/en/notice/-/detail/429414-2025) | PL | EUR 571m | 2,426,880,000 PLN | exceeds_estimate, exceeds_tender_values | Badania diagnostyczne i konsultacje specjalistyczne dla potr |
| [161437-2026](https://ted.europa.eu/en/notice/-/detail/161437-2026) | PT | EUR 353m | 352,648,330 EUR | exceeds_estimate | DAT 5025011672 - CONCURSO PÚBLICO PLURIANUAL 2026-2027 PARA  |
| [519721-2025](https://ted.europa.eu/en/notice/-/detail/519721-2025) | PL | EUR 304m | 1,292,568,500 PLN | exceeds_tender_values | DOSTAWA MATERIAŁÓW EKSPLOATACYJNYCH DO DRUKAREK I URZĄDZEŃ W |
| [160625-2026](https://ted.europa.eu/en/notice/-/detail/160625-2026) | PT | EUR 257m | 256,642,880 EUR | exceeds_estimate | Aquisição de material para manutenção do Sistema de Retenção |
| [177113-2026](https://ted.europa.eu/en/notice/-/detail/177113-2026) | PT | EUR 256m | 255,649,860 EUR | exceeds_estimate | DMSA 5025014125 - CONCURSO PÚBLICO PARA LOCAÇÃO DE SISTEMAS  |
| [313429-2026](https://ted.europa.eu/en/notice/-/detail/313429-2026) | PL | EUR 174m | 741,576,016 PLN | exceeds_estimate, exceeds_tender_values | Dostawa przedmiotów umundurowania i wyekwipowania (umundurow |
| [373053-2026](https://ted.europa.eu/en/notice/-/detail/373053-2026) | PL | EUR 173m | 732,151,880 PLN | duplicate_value_in_procedure | Dostawa modułowych, przenośnych i kontenerowych centrów dany |
| [159180-2026](https://ted.europa.eu/en/notice/-/detail/159180-2026) | PL | EUR 166m | 699,449,970 PLN | exceeds_estimate | „Dostawa dań instant, miodu, sosów, zup, przypraw przetworzo |
| [528266-2026](https://ted.europa.eu/en/notice/-/detail/528266-2026) | PT | EUR 162m | 162,000,000 EUR | exceeds_estimate, exceeds_tender_values | 4026013948/DA/G0011/2026-Contratação de voo dedicado (charte |
| [148891-2026](https://ted.europa.eu/en/notice/-/detail/148891-2026) | DE | EUR 130m | 129,754,035 EUR | exceeds_tender_values | Fliesenarbeiten |
| [667435-2025](https://ted.europa.eu/en/notice/-/detail/667435-2025) | PL | EUR 76m | 323,121,000 PLN | exceeds_tender_values | Dostawa sprzętu kwaterunkowego – dostawa krzeseł i foteli bi |
| [502957-2026](https://ted.europa.eu/en/notice/-/detail/502957-2026) | RO | EUR 61m | 317,342,000 RON | duplicate_value_in_procedure | „REALIZARE INFRASTRUCTURĂ- ZONĂ OPERAȚIONALĂ ÎN CAZARMA 1833 |
| [542411-2026](https://ted.europa.eu/en/notice/-/detail/542411-2026) | PL | EUR 43m | 184,500,000 PLN | exceeds_tender_values | Wykonanie serwisowania stacji radiolokacyjnych |
| [764345-2024](https://ted.europa.eu/en/notice/-/detail/764345-2024) | PL | EUR 34m | 149,041,500 PLN | exceeds_tender_values | Dostawa produktów żywnościowych do 35 WOG tj. mięsa czerwone |
| [142545-2026](https://ted.europa.eu/en/notice/-/detail/142545-2026) | PL | EUR 29m | 120,969,785 PLN | exceeds_tender_values | Świadczenie całodobowej ochrony osób i mienia w systemie zmi |
| [738312-2025](https://ted.europa.eu/en/notice/-/detail/738312-2025) | SI | EUR 25m | 24,510,800 EUR | exceeds_estimate | GOI dela za redno tekoče in investicijsko vzdrževanje objekt |
| [150791-2025](https://ted.europa.eu/en/notice/-/detail/150791-2025) | IT | EUR 21m | 21,069,842 EUR | duplicate_value_in_procedure | Approvvigionamento autocarri del genio |
| [181665-2026](https://ted.europa.eu/en/notice/-/detail/181665-2026) | PL | EUR 20m | 83,472,000 PLN | exceeds_estimate | DOSTAWA PRZEDMIOTÓW UMUNDUROWANIA I WYEKWIPOWANIA – SKARPETY |
| [182771-2026](https://ted.europa.eu/en/notice/-/detail/182771-2026) | HR | EUR 11m | 10,872,721 EUR | duplicate_value_in_procedure | Pružanje energetske usluge u svrhu poboljšanja energetske uč |
| [713691-2025](https://ted.europa.eu/en/notice/-/detail/713691-2025) | CH | EUR 10m | 9,729,000 CHF | duplicate_value_in_procedure | Persönliche Dienstfahrzeuge (BEV) für Berufsmilitärs |
| [743990-2024](https://ted.europa.eu/en/notice/-/detail/743990-2024) | CY | EUR 8.5m | 8,500,000 EUR | duplicate_value_in_procedure | ΔΙΑΓΩΝΙΣΜΟΣ ΓΙΑ ΤΗΝ ΠΡΟΜΗΘΕΙΑ ΕΙΔΩΝ ΚΨΜ ΕΦ ΓΙΑ ΠΕΡΙΟΔΟ 2 ΕΤΩ |
| [580541-2024](https://ted.europa.eu/en/notice/-/detail/580541-2024) | LT | EUR 6.7m | 6,664,091 EUR | duplicate_value_in_procedure | Mėsa, žuvis ir jų produktai |
| [419428-2026](https://ted.europa.eu/en/notice/-/detail/419428-2026) | LU | EUR 5.1m | 5,128,205 EUR | exceeds_tender_values | Fourniture de services de fret aérien intercontinental au pr |
| [654598-2025](https://ted.europa.eu/en/notice/-/detail/654598-2025) | CZ | EUR 4.9m | 120,000,000 CZK | exceeds_tender_values | Pronájem vrtulníků En-480B-G |
| [714556-2025](https://ted.europa.eu/en/notice/-/detail/714556-2025) | CH | EUR 3.5m | 3,243,000 CHF | duplicate_value_in_procedure | Persönliche Dienstfahrzeuge (BEV) für Berufsmilitärs |
| [236045-2025](https://ted.europa.eu/en/notice/-/detail/236045-2025) | CZ | EUR 3.3m | 81,818,182 CZK | duplicate_value_in_procedure | Kovový nábytek 2025-2028 |
| [270526-2026](https://ted.europa.eu/en/notice/-/detail/270526-2026) | CZ | EUR 2.9m | 71,074,380 CZK | duplicate_value_in_procedure | DNS – zpracování analýz a odborná podpora v různých oblastec |
| [296701-2026](https://ted.europa.eu/en/notice/-/detail/296701-2026) | CZ | EUR 2.9m | 71,074,380 CZK | duplicate_value_in_procedure | DNS – zpracování analýz a odborná podpora v různých oblastec |
| [382490-2026](https://ted.europa.eu/en/notice/-/detail/382490-2026) | CZ | EUR 2.9m | 71,074,380 CZK | duplicate_value_in_procedure | DNS – zpracování analýz a odborná podpora v různých oblastec |
| [406975-2026](https://ted.europa.eu/en/notice/-/detail/406975-2026) | CZ | EUR 2.9m | 71,074,380 CZK | duplicate_value_in_procedure | DNS – zpracování analýz a odborná podpora v různých oblastec |
| [529283-2026](https://ted.europa.eu/en/notice/-/detail/529283-2026) | SK | EUR 2.8m | 2,800,000 EUR | duplicate_value_in_procedure | Hygienické potreby a čistiace a dezinfekčné prostriedky - DN |
| [262061-2025](https://ted.europa.eu/en/notice/-/detail/262061-2025) | ES | EUR 2.8m | 2,792,138 EUR | duplicate_value_in_procedure | Plataforma de transformación digital INTAQLAB |
| [420225-2026](https://ted.europa.eu/en/notice/-/detail/420225-2026) | LU | EUR 2.8m | 2,777,778 EUR | exceeds_tender_values | Fourniture de services d’évacuations aéromédicales stratégiq |
| [542746-2024](https://ted.europa.eu/en/notice/-/detail/542746-2024) | PL | EUR 2.7m | 11,709,600 PLN | duplicate_value_in_procedure | Dostawa Pojazdów operacyjnych WS grupy A i B z podziałem na  |
| [277997-2025](https://ted.europa.eu/en/notice/-/detail/277997-2025) | SE | EUR 2.6m | 30,000,000 SEK | duplicate_value_in_procedure | Bygg |
| [278691-2025](https://ted.europa.eu/en/notice/-/detail/278691-2025) | SE | EUR 2.6m | 30,000,000 SEK | duplicate_value_in_procedure | Bygg |
| [262434-2026](https://ted.europa.eu/en/notice/-/detail/262434-2026) | PT | EUR 2.5m | 2,504,944 EUR | duplicate_value_in_procedure | Z0009/2025-Aquisição de Gás Propano e Butano a Granel para a |
| [265483-2026](https://ted.europa.eu/en/notice/-/detail/265483-2026) | PT | EUR 2.5m | 2,504,944 EUR | duplicate_value_in_procedure | Z0009/2025-Aquisição de Gás Propano e Butano a Granel para a |
| [542814-2024](https://ted.europa.eu/en/notice/-/detail/542814-2024) | PL | EUR 2.1m | 8,817,122 PLN | duplicate_value_in_procedure | Dostawa Pojazdów operacyjnych WS grupy A i B z podziałem na  |
| [344320-2025](https://ted.europa.eu/en/notice/-/detail/344320-2025) | ES | EUR 2.0m | 1,984,400 EUR | duplicate_value_in_procedure | Suministro de munición cartuchería de calibre medio |
| [344925-2025](https://ted.europa.eu/en/notice/-/detail/344925-2025) | ES | EUR 2.0m | 1,984,400 EUR | duplicate_value_in_procedure | Suministro de munición cartuchería de calibre medio |
| [345357-2025](https://ted.europa.eu/en/notice/-/detail/345357-2025) | ES | EUR 2.0m | 1,984,400 EUR | duplicate_value_in_procedure | Suministro de munición cartuchería de calibre medio |
| [345482-2025](https://ted.europa.eu/en/notice/-/detail/345482-2025) | ES | EUR 2.0m | 1,984,400 EUR | duplicate_value_in_procedure | Suministro de munición cartuchería de calibre medio |
| [346174-2025](https://ted.europa.eu/en/notice/-/detail/346174-2025) | ES | EUR 2.0m | 1,984,400 EUR | duplicate_value_in_procedure | Suministro de munición cartuchería de calibre medio |
| [361305-2025](https://ted.europa.eu/en/notice/-/detail/361305-2025) | ES | EUR 2.0m | 1,984,400 EUR | duplicate_value_in_procedure | Suministro de munición cartuchería de calibre medio |
| [175814-2025](https://ted.europa.eu/en/notice/-/detail/175814-2025) | HU | EUR 1.9m | 783,464,568 HUF | exceeds_tender_values | Vegyijelző műszerek amortizációs pótlása 2024-2027 |
| [716328-2025](https://ted.europa.eu/en/notice/-/detail/716328-2025) | CH | EUR 1.7m | 1,621,500 CHF | duplicate_value_in_procedure | Persönliche Dienstfahrzeuge (BEV) für Berufsmilitärs |
| [663833-2025](https://ted.europa.eu/en/notice/-/detail/663833-2025) | PL | EUR 1.6m | 6,610,487 PLN | duplicate_value_in_procedure | Ochrona fizyczna realizowana przez Specjalistyczne Uzbrojone |
| [574951-2025](https://ted.europa.eu/en/notice/-/detail/574951-2025) | CH | EUR 1.4m | 1,301,524 CHF | duplicate_value_in_procedure | Pannen- und Unfallhilfe für Fahrzeuge aller Antriebsarten |
| [447895-2025](https://ted.europa.eu/en/notice/-/detail/447895-2025) | CH | EUR 1.3m | 1,167,480 CHF | duplicate_value_in_procedure | Instandhaltung Handfeuerlöscher |
| [359796-2025](https://ted.europa.eu/en/notice/-/detail/359796-2025) | PL | EUR 1.2m | 5,076,082 PLN | duplicate_value_in_procedure | Usługi w zakresie ochrony fizycznej osób i mienia oraz monit |
| [601878-2025](https://ted.europa.eu/en/notice/-/detail/601878-2025) | HR | EUR 1.1m | 1,077,861 EUR | duplicate_value_in_procedure | Održavanje informacijskog sustava za upravljanje ljudskim po |
| [861362-2025](https://ted.europa.eu/en/notice/-/detail/861362-2025) | HR | EUR 1.1m | 1,077,861 EUR | duplicate_value_in_procedure | Održavanje informacijskog sustava za upravljanje ljudskim po |
| [865437-2025](https://ted.europa.eu/en/notice/-/detail/865437-2025) | HR | EUR 1.1m | 1,077,861 EUR | duplicate_value_in_procedure | Održavanje informacijskog sustava za upravljanje ljudskim po |
| [869101-2025](https://ted.europa.eu/en/notice/-/detail/869101-2025) | HR | EUR 1.1m | 1,077,861 EUR | duplicate_value_in_procedure | Održavanje informacijskog sustava za upravljanje ljudskim po |
| [712798-2024](https://ted.europa.eu/en/notice/-/detail/712798-2024) | ES | EUR 1.0m | 1,033,058 EUR | duplicate_value_in_procedure | OTACV.-Contrato de servicios de adiestramiento en mantenimie |
| [292555-2025](https://ted.europa.eu/en/notice/-/detail/292555-2025) | PL | EUR 1.0m | 4,346,144 PLN | duplicate_value_in_procedure | Dostawa podstawowego sprzętu informatyki do RON |
| [624300-2024](https://ted.europa.eu/en/notice/-/detail/624300-2024) | PL | EUR 1.0m | 4,346,144 PLN | duplicate_value_in_procedure | Dostawa podstawowego sprzętu informatyki do RON |
| [624310-2024](https://ted.europa.eu/en/notice/-/detail/624310-2024) | PL | EUR 1.0m | 4,346,144 PLN | duplicate_value_in_procedure | Dostawa podstawowego sprzętu informatyki do RON |
| [624644-2024](https://ted.europa.eu/en/notice/-/detail/624644-2024) | PL | EUR 1.0m | 4,346,144 PLN | duplicate_value_in_procedure | Dostawa podstawowego sprzętu informatyki do RON |
| [624793-2024](https://ted.europa.eu/en/notice/-/detail/624793-2024) | PL | EUR 1.0m | 4,346,144 PLN | duplicate_value_in_procedure | Dostawa podstawowego sprzętu informatyki do RON |
| [626251-2024](https://ted.europa.eu/en/notice/-/detail/626251-2024) | PL | EUR 1.0m | 4,346,144 PLN | duplicate_value_in_procedure | Dostawa podstawowego sprzętu informatyki do RON |
| [626864-2024](https://ted.europa.eu/en/notice/-/detail/626864-2024) | PL | EUR 1.0m | 4,346,144 PLN | duplicate_value_in_procedure | Dostawa podstawowego sprzętu informatyki do RON |
| [567564-2024](https://ted.europa.eu/en/notice/-/detail/567564-2024) | PL | EUR 980k | 4,182,000 PLN | duplicate_value_in_procedure | Zakup telefonów IP oraz terminali VTC dla RON |
| [264406-2026](https://ted.europa.eu/en/notice/-/detail/264406-2026) | PT | EUR 968k | 967,867 EUR | duplicate_value_in_procedure | Z0009/2025-Aquisição de Gás Propano e Butano a Granel para a |
| [92042-2025](https://ted.europa.eu/en/notice/-/detail/92042-2025) | CZ | EUR 911k | 22,839,817 CZK | duplicate_value_in_procedure | Obměna přístrojového vybavení zdravotnického praporu – nákup |
| [584361-2024](https://ted.europa.eu/en/notice/-/detail/584361-2024) | LT | EUR 789k | 788,792 EUR | duplicate_value_in_procedure | VALYMO PASLAUGŲ GENEROLO SILVESTRO ŽUKAUSKO POLIGONO ĮSIGIJI |
| [554625-2024](https://ted.europa.eu/en/notice/-/detail/554625-2024) | PL | EUR 699k | 3,000,000 PLN | exceeds_tender_values | Usługa zakupu międzynarodowych biletów lotniczych i kolejowy |
| [17901-2025](https://ted.europa.eu/en/notice/-/detail/17901-2025) | PL | EUR 695k | 2,998,889 PLN | duplicate_value_in_procedure | Dostawa technicznych środków materiałowych do statków powiet |
| [35038-2025](https://ted.europa.eu/en/notice/-/detail/35038-2025) | PL | EUR 695k | 2,998,889 PLN | duplicate_value_in_procedure | Dostawa technicznych środków materiałowych do statków powiet |
| [35707-2025](https://ted.europa.eu/en/notice/-/detail/35707-2025) | PL | EUR 695k | 2,998,889 PLN | duplicate_value_in_procedure | Dostawa technicznych środków materiałowych do statków powiet |
| [47102-2025](https://ted.europa.eu/en/notice/-/detail/47102-2025) | PL | EUR 695k | 2,998,889 PLN | duplicate_value_in_procedure | Dostawa technicznych środków materiałowych do statków powiet |
| [57367-2025](https://ted.europa.eu/en/notice/-/detail/57367-2025) | PL | EUR 695k | 2,998,889 PLN | duplicate_value_in_procedure | Dostawa technicznych środków materiałowych do statków powiet |
| [57685-2025](https://ted.europa.eu/en/notice/-/detail/57685-2025) | PL | EUR 695k | 2,998,889 PLN | duplicate_value_in_procedure | Dostawa technicznych środków materiałowych do statków powiet |
| [744971-2024](https://ted.europa.eu/en/notice/-/detail/744971-2024) | PL | EUR 695k | 2,998,889 PLN | duplicate_value_in_procedure | Dostawa technicznych środków materiałowych do statków powiet |
| [791993-2024](https://ted.europa.eu/en/notice/-/detail/791993-2024) | PL | EUR 695k | 2,998,889 PLN | duplicate_value_in_procedure | Dostawa technicznych środków materiałowych do statków powiet |
| [792098-2024](https://ted.europa.eu/en/notice/-/detail/792098-2024) | PL | EUR 695k | 2,998,889 PLN | duplicate_value_in_procedure | Dostawa technicznych środków materiałowych do statków powiet |
| [692967-2024](https://ted.europa.eu/en/notice/-/detail/692967-2024) | HU | EUR 638k | 253,093,365 HUF | duplicate_value_in_procedure | Közlekedési szaktechnikai eszközök karbantartása |
| [772945-2025](https://ted.europa.eu/en/notice/-/detail/772945-2025) | ES | EUR 572k | 572,500 EUR | duplicate_value_in_procedure | Adquisición de munición de calibre 25 mm |
| [534847-2025](https://ted.europa.eu/en/notice/-/detail/534847-2025) | EE | EUR 500k | 500,000 EUR | duplicate_value_in_procedure | Kaitseväelaste toitlustamine 01.09.2025-31.08.2026 Tallinnas |
| [60811-2025](https://ted.europa.eu/en/notice/-/detail/60811-2025) | LV | EUR 496k | 495,868 EUR | duplicate_value_in_procedure | Lidlauka pretledus reaģentu iegāde |
| [592344-2026](https://ted.europa.eu/en/notice/-/detail/592344-2026) | SE | EUR 490k | 5,302,500 SEK | duplicate_value_in_procedure | Anskaffning av Vapenrock M87 Vit och Långbyxa M87 Vit |
| [367428-2026](https://ted.europa.eu/en/notice/-/detail/367428-2026) | LV | EUR 455k | 454,545 EUR | duplicate_value_in_procedure | Ceļu un piegulošās teritorijas uzturēšana, atjaunošana |
| [367468-2026](https://ted.europa.eu/en/notice/-/detail/367468-2026) | LV | EUR 455k | 454,545 EUR | duplicate_value_in_procedure | Ceļu un piegulošās teritorijas uzturēšana, atjaunošana |
| [654385-2024](https://ted.europa.eu/en/notice/-/detail/654385-2024) | ES | EUR 448k | 448,332 EUR | duplicate_value_in_procedure | 20247313 Reposición vehículo autoextintor medio |
| [617174-2024](https://ted.europa.eu/en/notice/-/detail/617174-2024) | PL | EUR 435k | 1,869,600 PLN | duplicate_value_in_procedure | Zakup telefonów IP oraz terminali VTC dla RON |
| [769652-2025](https://ted.europa.eu/en/notice/-/detail/769652-2025) | ES | EUR 412k | 412,328 EUR | duplicate_value_in_procedure | APO 133 INFRA - Suministro y adecuación de Automatismos en G |
| [769846-2025](https://ted.europa.eu/en/notice/-/detail/769846-2025) | ES | EUR 412k | 412,328 EUR | duplicate_value_in_procedure | APO 133 INFRA - Suministro y adecuación de Automatismos en G |
| [771676-2025](https://ted.europa.eu/en/notice/-/detail/771676-2025) | ES | EUR 412k | 412,328 EUR | duplicate_value_in_procedure | APO 133 INFRA - Suministro y adecuación de Automatismos en G |
| [386285-2026](https://ted.europa.eu/en/notice/-/detail/386285-2026) | IT | EUR 410k | 410,000 EUR | duplicate_value_in_procedure | MANUTENZIONE IMPIANTI ANTINCENDIO COMANDO BRIGATA E REPARTI  |
| [473902-2025](https://ted.europa.eu/en/notice/-/detail/473902-2025) | EE | EUR 400k | 400,000 EUR | duplicate_value_in_procedure | Hooneautomaatika hooldus ja remont |
| [521229-2026](https://ted.europa.eu/en/notice/-/detail/521229-2026) | EE | EUR 400k | 400,000 EUR | duplicate_value_in_procedure | Toitlustusteenuse ja cateringi tellimine Harjumaal, Tartu ma |
| [659737-2024](https://ted.europa.eu/en/notice/-/detail/659737-2024) | IT | EUR 400k | 400,000 EUR | duplicate_value_in_procedure | SERVIZIO DI MANUTENZIONE, RIPARAZIONE, SOCCORSO E RECUPERO A |
| [676088-2024](https://ted.europa.eu/en/notice/-/detail/676088-2024) | IT | EUR 400k | 400,000 EUR | duplicate_value_in_procedure | MANUTENZIONE RIPARAZIONE E SOCCORSO VEICOLI TATTICI |
| [748997-2025](https://ted.europa.eu/en/notice/-/detail/748997-2025) | EE | EUR 400k | 400,000 EUR | duplicate_value_in_procedure | Sõidukite, seadmete filtrite ja nende tarvikute kestvushanke |
| [625301-2026](https://ted.europa.eu/en/notice/-/detail/625301-2026) | CZ | EUR 383k | 9,230,225 CZK | exceeds_estimate | Navigační prostředky |
| [774214-2025](https://ted.europa.eu/en/notice/-/detail/774214-2025) | PL | EUR 365k | 1,565,790 PLN | duplicate_value_in_procedure | Kompleksowe pełnienie nadzoru inwestorskiego dla zadania nr  |
| [543514-2024](https://ted.europa.eu/en/notice/-/detail/543514-2024) | RO | EUR 363k | 1,806,700 RON | duplicate_value_in_procedure | Stand testare filtre |
| [171416-2025](https://ted.europa.eu/en/notice/-/detail/171416-2025) | PL | EUR 346k | 1,446,942 PLN | duplicate_value_in_procedure | USŁUGI UTRZYMANIA POWIERZCHNI ZEWNĘTRZNYCH UTWARDZONYCH, TER |
| [171895-2025](https://ted.europa.eu/en/notice/-/detail/171895-2025) | PL | EUR 346k | 1,446,942 PLN | duplicate_value_in_procedure | USŁUGI UTRZYMANIA POWIERZCHNI ZEWNĘTRZNYCH UTWARDZONYCH, TER |
| [589396-2025](https://ted.europa.eu/en/notice/-/detail/589396-2025) | SE | EUR 286k | 3,200,000 SEK | duplicate_value_in_procedure | Förrådscontainrar |
| [42696-2025](https://ted.europa.eu/en/notice/-/detail/42696-2025) | ES | EUR 254k | 253,801 EUR | duplicate_value_in_procedure | Actualización del sistema de adquisición de dinámicos |
| [62042-2025](https://ted.europa.eu/en/notice/-/detail/62042-2025) | ES | EUR 235k | 235,191 EUR | duplicate_value_in_procedure | Modelos qm y fm del pmp para talisman |
| [785378-2024](https://ted.europa.eu/en/notice/-/detail/785378-2024) | FI | EUR 230k | 230,000 EUR | duplicate_value_in_procedure | Kemiallisesti pestävien vaatteiden pesulapalvelut |
| [499119-2024](https://ted.europa.eu/en/notice/-/detail/499119-2024) | ES | EUR 222k | 221,950 EUR | duplicate_value_in_procedure | Ampliación capacidades CEUS |
| [124155-2025](https://ted.europa.eu/en/notice/-/detail/124155-2025) | ES | EUR 218k | 218,400 EUR | duplicate_value_in_procedure | Acreditaciones enac del inta para el año 2025 |
| [340553-2026](https://ted.europa.eu/en/notice/-/detail/340553-2026) | EE | EUR 200k | 200,000 EUR | duplicate_value_in_procedure | Lasketiiru hooldus ja remont (KHL 2a) |
| [574783-2026](https://ted.europa.eu/en/notice/-/detail/574783-2026) | EE | EUR 200k | 200,000 EUR | duplicate_value_in_procedure | Isikukaitsevahendid 2026 |
| [58097-2026](https://ted.europa.eu/en/notice/-/detail/58097-2026) | EE | EUR 200k | 200,000 EUR | duplicate_value_in_procedure | Moondamiskostüüm ja relva maskeerimiskate |
| [584555-2026](https://ted.europa.eu/en/notice/-/detail/584555-2026) | EE | EUR 200k | 200,000 EUR | duplicate_value_in_procedure | Valguspulgad |
| [597289-2026](https://ted.europa.eu/en/notice/-/detail/597289-2026) | EE | EUR 200k | 200,000 EUR | duplicate_value_in_procedure | Katelokid ja söögiriistade komplektid |
| [700439-2025](https://ted.europa.eu/en/notice/-/detail/700439-2025) | RO | EUR 167k | 849,562 RON | duplicate_value_in_procedure | Sisteme desktop tip 1 si Sisteme desktop tip 2 |
| [414597-2025](https://ted.europa.eu/en/notice/-/detail/414597-2025) | CZ | EUR 160k | 4,000,000 CZK | exceeds_tender_values | Rámcová kupní smlouva na dodávky technických a vzácných plyn |
| [192346-2026](https://ted.europa.eu/en/notice/-/detail/192346-2026) | EE | EUR 150k | 150,000 EUR | duplicate_value_in_procedure | Mustapesukotid |
| [372157-2026](https://ted.europa.eu/en/notice/-/detail/372157-2026) | EE | EUR 150k | 150,000 EUR | duplicate_value_in_procedure | Pimenduskatete ostmine |
| [492408-2025](https://ted.europa.eu/en/notice/-/detail/492408-2025) | EE | EUR 150k | 150,000 EUR | duplicate_value_in_procedure | Maskeerimiskreem nahale 2025 |
| [556858-2026](https://ted.europa.eu/en/notice/-/detail/556858-2026) | BG | EUR 140k | 139,990 EUR | duplicate_value_in_procedure | Техническа поддръжка и ремонт на автомобили |
| [267036-2025](https://ted.europa.eu/en/notice/-/detail/267036-2025) | CZ | EUR 120k | 3,000,000 CZK | exceeds_tender_values | POSKYTOVÁNÍ STĚHOVACÍCH SLUŽEB |
| [715914-2025](https://ted.europa.eu/en/notice/-/detail/715914-2025) | FR | EUR 118k | 118,000 EUR | duplicate_value_in_procedure | Travaux de création d'un plafond suspendu dans la cuisine et |
| [164809-2026](https://ted.europa.eu/en/notice/-/detail/164809-2026) | LV | EUR 103k | 103,306 EUR | duplicate_value_in_procedure | Jumtu un noteku tīrīšana |
| [165077-2026](https://ted.europa.eu/en/notice/-/detail/165077-2026) | LV | EUR 103k | 103,306 EUR | duplicate_value_in_procedure | Jumtu un noteku tīrīšana |
| [166559-2026](https://ted.europa.eu/en/notice/-/detail/166559-2026) | LV | EUR 103k | 103,306 EUR | duplicate_value_in_procedure | Jumtu un noteku tīrīšana |
| [144866-2026](https://ted.europa.eu/en/notice/-/detail/144866-2026) | SK | EUR 102k | 101,500 EUR | duplicate_value_in_procedure | Šitie výstrojných súčiastok a odevov – DNS |
| [679864-2024](https://ted.europa.eu/en/notice/-/detail/679864-2024) | EE | EUR 100k | 100,000 EUR | duplicate_value_in_procedure | Veoautode, ratassoomukite, busside ja haagiste pesu Tartumaa |
| [543522-2026](https://ted.europa.eu/en/notice/-/detail/543522-2026) | EE | EUR 90k | 90,000 EUR | duplicate_value_in_procedure | Helkurriba |
| [18071-2026](https://ted.europa.eu/en/notice/-/detail/18071-2026) | PL | EUR 77k | 326,000 PLN | duplicate_value_in_procedure | Usługa serwisowania, obsługiwania i naprawy pojazdów |
| [711503-2024](https://ted.europa.eu/en/notice/-/detail/711503-2024) | PL | EUR 69k | 299,520 PLN | duplicate_value_in_procedure | wykonywanie usługi zapewnienia załogi na jednostce s/v ZODIA |
| [712340-2024](https://ted.europa.eu/en/notice/-/detail/712340-2024) | PL | EUR 69k | 299,520 PLN | duplicate_value_in_procedure | wykonywanie usługi zapewnienia załogi na jednostce s/v ZODIA |
| [20610-2025](https://ted.europa.eu/en/notice/-/detail/20610-2025) | HR | EUR 66k | 66,032 EUR | duplicate_value_in_procedure | Laboratorijska oprema za NBK Laboratorij |
| [595252-2025](https://ted.europa.eu/en/notice/-/detail/595252-2025) | CZ | EUR 61k | 1,509,750 CZK | duplicate_value_in_procedure | DVISÚ - Polygrafické stroje a zařízení 2025 |
| [866105-2025](https://ted.europa.eu/en/notice/-/detail/866105-2025) | ES | EUR 53k | 53,440 EUR | duplicate_value_in_procedure | Servicios de Apoyo Técnico para la realización de Análisis I |
| [710613-2024](https://ted.europa.eu/en/notice/-/detail/710613-2024) | PL | EUR 52k | 224,640 PLN | duplicate_value_in_procedure | wykonywanie usługi zapewnienia załogi na jednostce s/v ZODIA |
| [711730-2024](https://ted.europa.eu/en/notice/-/detail/711730-2024) | PL | EUR 52k | 224,640 PLN | duplicate_value_in_procedure | wykonywanie usługi zapewnienia załogi na jednostce s/v ZODIA |
| [738364-2024](https://ted.europa.eu/en/notice/-/detail/738364-2024) | PL | EUR 50k | 216,299 PLN | duplicate_value_in_procedure | Dostawa filtrów do pojazdów |
| [380365-2026](https://ted.europa.eu/en/notice/-/detail/380365-2026) | SK | EUR 45k | 45,000 EUR | duplicate_value_in_procedure | Kuchynské stroje a zariadenia - DNS |
| [387235-2026](https://ted.europa.eu/en/notice/-/detail/387235-2026) | SK | EUR 45k | 45,000 EUR | duplicate_value_in_procedure | Kuchynské stroje a zariadenia – DNS -výzva č.9 |
| [607498-2024](https://ted.europa.eu/en/notice/-/detail/607498-2024) | ES | EUR 40k | 40,000 EUR | duplicate_value_in_procedure | SERFER. PA. Suministro abierto de repuestos para el sostenim |
| [616117-2024](https://ted.europa.eu/en/notice/-/detail/616117-2024) | ES | EUR 40k | 40,000 EUR | duplicate_value_in_procedure | SERFER. PA. Suministro abierto de repuestos para el sostenim |
| [430999-2026](https://ted.europa.eu/en/notice/-/detail/430999-2026) | EE | EUR 30k | 30,000 EUR | duplicate_value_in_procedure | Mehitamata 24/7 valveteenuse hankimine Rebase 9 ja Vaksali 3 |
| [678128-2024](https://ted.europa.eu/en/notice/-/detail/678128-2024) | EE | EUR 30k | 30,000 EUR | duplicate_value_in_procedure | Väikesõidukite pesulateenus Ida-Virumaal |
| [788099-2024](https://ted.europa.eu/en/notice/-/detail/788099-2024) | ES | EUR 30k | 30,000 EUR | duplicate_value_in_procedure | Suministro diverso material para labores de mantenimiento |
| [194699-2026](https://ted.europa.eu/en/notice/-/detail/194699-2026) | PL | EUR 27k | 115,600 PLN | duplicate_value_in_procedure | Wykonanie usługi w zakresie ochrony terenów, obiektów, urząd |
| [624505-2025](https://ted.europa.eu/en/notice/-/detail/624505-2025) | SK | EUR 22k | 21,580 EUR | duplicate_value_in_procedure | Nábytok a interiérové zariadenie - DNS |
| [598263-2025](https://ted.europa.eu/en/notice/-/detail/598263-2025) | LV | EUR 20k | 20,000 EUR | duplicate_value_in_procedure | Dinamiskās iepirkumu sistēmas izveide centralizētai degviela |
| [464849-2026](https://ted.europa.eu/en/notice/-/detail/464849-2026) | EE | EUR 15k | 15,000 EUR | duplicate_value_in_procedure | Mehitamata 24/7 valveteenuse hankimine Pärnusse |
| [750295-2025](https://ted.europa.eu/en/notice/-/detail/750295-2025) | LV | EUR 15k | 15,000 EUR | duplicate_value_in_procedure | Dinamiskās iepirkumu sistēmas izveide centralizētai degviela |
| [760122-2025](https://ted.europa.eu/en/notice/-/detail/760122-2025) | LV | EUR 15k | 15,000 EUR | duplicate_value_in_procedure | Dinamiskās iepirkumu sistēmas izveide centralizētai degviela |
| [761796-2025](https://ted.europa.eu/en/notice/-/detail/761796-2025) | LV | EUR 15k | 15,000 EUR | duplicate_value_in_procedure | Dinamiskās iepirkumu sistēmas izveide centralizētai degviela |
| [203354-2026](https://ted.europa.eu/en/notice/-/detail/203354-2026) | ES | EUR 13k | 13,430 EUR | duplicate_value_in_procedure | Realizar el servicio de mantenimiento y reparaciones diversa |
| [747239-2025](https://ted.europa.eu/en/notice/-/detail/747239-2025) | ES | EUR 10k | 10,331 EUR | duplicate_value_in_procedure | JAT. Servicios de reparación de vehículos del cargo del Parq |
| [792347-2025](https://ted.europa.eu/en/notice/-/detail/792347-2025) | ES | EUR 7k | 6,612 EUR | duplicate_value_in_procedure | JAT. Servicios de reparación de vehículos del cargo del Parq |
| [192742-2025](https://ted.europa.eu/en/notice/-/detail/192742-2025) | CZ | EUR 5k | 116,000 CZK | duplicate_value_in_procedure | Znalecký posudek ¨k posouzení ceny obvyklé – Vozidla TITUS 6 |
| [216006-2026](https://ted.europa.eu/en/notice/-/detail/216006-2026) | ES | EUR 400 | 400 EUR | duplicate_value_in_procedure | Mantenimiento de equipos de detección NRBQ de dotación (Anti |
| [113601-2025](https://ted.europa.eu/en/notice/-/detail/113601-2025) | DE | EUR 0 | 0 EUR | duplicate_value_in_procedure | 1512-SL-Mobilfunkzubehör-DB_EA-15_Los 1 bis 4 |
| [156580-2025](https://ted.europa.eu/en/notice/-/detail/156580-2025) | DE | EUR 0 | 0 EUR | duplicate_value_in_procedure | Q/E2DT/R8451_79 - 79. EA DBS AM - Ceftriaxondinatrium zur In |
| [180646-2025](https://ted.europa.eu/en/notice/-/detail/180646-2025) | DE | EUR 0 | 0 EUR | duplicate_value_in_procedure | Q/E2DT/R8451_81 - 81. EA DBS AM - FUSIDINSAEURE/BETAMETHASON |
| [353391-2026](https://ted.europa.eu/en/notice/-/detail/353391-2026) | EE | EUR 0 | 0 EUR | duplicate_value_in_procedure | Väikesõidukite pesulateenus Tallinnas |
| [646774-2024](https://ted.europa.eu/en/notice/-/detail/646774-2024) | DE | EUR 0 | 0 EUR | duplicate_value_in_procedure | 1512-SL-Mobilfunkzubehör-DB_EA-12_Los 1 bis 3 |
| [753031-2024](https://ted.europa.eu/en/notice/-/detail/753031-2024) | DE | EUR 0 | 0 EUR | duplicate_value_in_procedure | 1512-SL-Mobilfunkzubehör-DB_EA-13 Los 1 bis 5 |
| [791257-2024](https://ted.europa.eu/en/notice/-/detail/791257-2024) | DE | EUR 0 | 0 EUR | duplicate_value_in_procedure | 1512-SL-Mobilfunkzuebhör DB_EA-14 Los 1 bis 3 |
