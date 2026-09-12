# ha-edp-radar — Phase 2: Country Purchasing Intelligence

**Purpose:** Refocus the existing `ha-edp-radar` integration around one primary question:

> **Which countries buy the most defence materiel — how much, what do they buy, and how is that changing?**

**Status:** Implementation plan  
**Assumption:** Phase 1 is already implemented. The existing TED ingestion, defence relevance filtering, normalization, storage, currency handling, lifecycle handling, and Home Assistant integration shell should be reused rather than redesigned.

---

# 1. Strategic change

From this phase onward, the integration is **country-first**.

The user selects one country as:

```text
My country
```

That country is the main reference point throughout the integration.

The integration still processes all relevant countries in the dataset so that the selected country can be compared with:

- all other countries,
- neighbouring countries,
- Nordic countries,
- selected peers,
- the European total.

For the intended primary use case, the selected country will often be Sweden, but **Sweden must not be hard-coded**.

The wizard must allow the user to select any supported country.

---

# 2. Do not add another data source yet

Do **not** add EDF, NATO, funding, opportunities, news, or any other external source in this phase.

First make the TED-based country purchasing picture trustworthy.

The reason is simple:

> If we cannot confidently answer "Which countries buy the most?" from the existing procurement source, additional sources will only make the model harder to understand.

The next external data source should be considered only after the country-ranking model has been validated.

---

# 3. Primary question

The integration should be designed around:

> **Which countries buy the most defence materiel?**

Natural follow-up questions are:

1. How much does each country buy?
2. Where does my country rank?
3. What share of the total does my country represent?
4. What does my country buy?
5. What do the largest purchasing countries buy?
6. Is my country's purchasing volume increasing or decreasing?
7. Which countries are increasing their purchasing fastest?
8. Which capability areas account for the largest values?
9. Which individual awards explain an unusually high value for a country?
10. Who received the largest publicly reported contracts?

All answers must remain factual and derived from public data.

---

# 4. Definition of "buy"

This definition is critical.

For this integration:

> **A purchase means a publicly reported awarded contract value in TED.**

The primary monetary measure is TED's **Notice Value / BT-161** where it represents the aggregated value of contracts awarded in a result notice.

TED defines Notice Value as the value of all contracts awarded in that notice, including options and renewals.

This is the closest consistent public measure available for the question "how much is the country buying?"

It is **not**:

- defence budget,
- announced political spending,
- planned procurement value,
- tender estimate,
- framework ceiling,
- amount actually invoiced,
- cash paid during the year,
- total programme lifecycle cost.

The UI and documentation should use language such as:

```text
Awarded contract value
Publicly reported awarded value
```

rather than implying actual cash expenditure.

---

# 5. Framework agreements

Framework agreements require special treatment.

TED distinguishes between:

```text
Notice Value
```

and:

```text
Framework Maximum Value
```

The maximum framework value is only the maximum amount that may be spent over the framework's lifetime.

Therefore:

> **Framework maximum values must never be counted as purchases.**

Example:

```text
Framework maximum: EUR 2.0bn
Contracts actually reported as awarded: EUR 250m
```

Country purchasing statistics should count:

```text
EUR 250m
```

not:

```text
EUR 2.0bn
```

Framework maximum values may later be shown as a separate pipeline/capacity measure, but they are outside this phase.

---

# 6. Country attribution

The purchasing country is based on the **buyer**, not the winning supplier.

Normally:

```text
buyer country = purchasing country
```

Example:

```text
Buyer country: Sweden
Winner country: Germany
```

This is:

```text
Swedish purchase
```

not a German purchase.

The winner country may be used later to answer questions about supplier flows, but it must never determine the purchasing-country ranking.

---

# 7. Multi-country procurement

Joint procurement creates a methodological problem.

A single notice can involve buyers from more than one country.

The integration must not count the full award value once for every participating country.

That would inflate the European total and distort country rankings.

Use a conservative rule:

## Single-country buyer set

If all identified buyers belong to the same country:

```text
attribute full value to that country
```

## Multi-country buyer set

If buyers belong to more than one country and the data does not explicitly allocate value between countries:

```text
classify as MULTI / Joint multinational procurement
```

Do not arbitrarily divide the value equally.

Do not attribute the whole value to every country.

If the data explicitly associates individual lots/contracts and values with specific buyers/countries, those values may be attributed at that lower level.

Any such allocation must be deterministic and testable.

The European total may include the joint value once.

Country totals should include only values that can be attributed without guessing.

---

# 8. Time basis

The primary ranking period should be:

```text
rolling 12 months
```

This gives a useful view without being dominated by calendar-year boundaries.

Primary comparison:

```text
current rolling 12 months
vs
previous 12 months
```

Secondary periods:

```text
90 days
30 days
```

Use 90 days mainly for current momentum.

Use 30 days mainly for recent activity.

The central answer to "which countries buy most?" should remain the 12-month ranking.

---

# 9. Award date versus publication date

Prefer the actual award/winner-decision date where TED provides it.

If a reliable award date is unavailable, use the result notice publication date as fallback.

Store the basis used.

This matters because a result published in January may concern an award decision made in December.

Statistics should remain reproducible.

---

# 10. Currency

All cross-country comparisons must use one comparable currency.

Use:

```text
EUR
```

Reuse the historical ECB conversion already available from Phase 1.

Keep the original amount and currency.

Country totals should be based on normalized EUR values.

Never sum:

```text
SEK + PLN + EUR
```

directly.

---

# 11. Defence relevance

Reuse Phase 1 defence-relevance logic.

Do not redesign the defence universe in this phase.

The same configured defence relevance criteria must apply consistently to every country.

A country's ranking must not use a broader or narrower filter than another country's ranking.

---

# 12. What must be validated before creating new sensors

The first task in this phase is **data profiling**, not UI work.

Before adding country-ranking sensors, analyse actual result notices and answer:

## Award-value coverage

For each country:

```text
How many awarded result notices exist?
How many contain usable Notice Value?
What percentage of results have a usable award value?
What percentage of procedures have a usable award value?
```

## Buyer-country coverage

```text
How often is buyer country present?
How often is there exactly one buyer country?
How often is procurement multinational?
```

## Currency coverage

```text
Which currencies occur?
How much award value can be converted to EUR?
```

## Framework behaviour

```text
How many results are framework agreements?
How often are Notice Value and Framework Maximum Value both present?
Do sample notices confirm that these are being interpreted correctly?
```

## Duplicate/version behaviour

```text
How often are result notices republished?
Are old notice versions being replaced correctly?
Can the same awarded value appear in more than one notice version?
```

## Lot behaviour

```text
When Notice Value exists, does it already represent the total?
When it does not exist, can lot values be safely combined?
How often would summing lot-level values risk double counting?
```

## Joint procurement

```text
How many result notices have buyers from multiple countries?
How much reported award value falls into this category?
```

The implementation agent should produce a short reproducible report before enabling the final ranking.

Suggested artifact:

```text
docs/country-purchasing-data-profile.md
```

---

# 13. Golden rule for aggregation

For each result notice:

```text
Use Notice Value once when a valid Notice Value exists.
```

Do not also add its lot values.

If Notice Value is missing:

- investigate whether lower-level contract/lot values can be summed safely;
- only do so when the structure proves they represent non-overlapping awarded values;
- otherwise leave monetary value unknown.

Missing value is preferable to a wrong value.

---

# 14. Outlier protection

Defence awards are naturally lumpy.

A single very large contract can legitimately dominate a country for a period.

Do not automatically discard statistical outliers.

Instead identify suspicious records for diagnostics:

```text
award value > EUR 10bn
value increased by orders of magnitude between notice versions
unknown or invalid currency
duplicate notice/procedure/value combination
apparent value equal to framework maximum where semantics are unclear
```

The purpose is data-quality checking, not removal of genuine large procurements.

Every large value that materially changes a country's ranking should be traceable to its underlying TED notice.

---

# 15. Core country dataset

After normalization, the system should be able to produce one record per country and period:

```text
CountryPurchaseSummary

country
period_start
period_end

award_value_eur
award_count
procedures_with_value
total_awarded_procedures
value_coverage_pct

share_of_total_pct
rank

previous_period_value_eur
change_eur
change_pct

top_categories
largest_awards
```

This country summary becomes the basis for Home Assistant entities.

---

# 16. European total

The European total should represent:

```text
all attributable single-country awards
+
joint/multinational awards counted once
```

This preserves the total market picture without duplicating multinational procurement.

Expose separately:

```text
country-attributable award value
joint/multinational award value
```

This allows the user to see how much of the total is not safely assignable to one country.

---

# 17. My country

The setup wizard must include:

```text
My country
[ Sweden ▼ ]
```

The user can select any country supported by the ingested data.

If Home Assistant's configured country is available and is supported, it may be pre-selected as a convenience, but the user must be able to change it.

Store the country as an ISO country code.

Example:

```text
SE
```

not a localized display string.

---

# 18. Country ranking

The central derived dataset is:

```text
Rank | Country | Awarded value 12m | Share | Change vs previous 12m
```

Example structure:

```text
1   Country A    EUR 18.4bn    18.2%   +22%
2   Country B    EUR 14.7bn    14.5%   +84%
3   Country C    EUR 11.2bn    11.1%    +7%
...
5   Sweden        EUR 6.1bn     6.0%   +30%
```

The selected country must always be available to the UI even if it is outside the normal top-N display.

For example:

```text
Top 10
+
My country
```

---

# 19. Main Home Assistant view

The user should be able to understand the main situation from a phone in a few seconds.

The first view should answer:

```text
How much does my country buy?
Where does it rank?
Who buys the most?
How large is the total market?
Is my country's public awarded value rising or falling?
```

Suggested factual presentation:

```text
MY COUNTRY — SWEDEN

Awarded value 12m        EUR 6.1bn
Rank                     5 / 27
Share                    6.0%
Previous 12m             EUR 4.7bn
Change                   +29.8%
```

And:

```text
EUROPE

Awarded value 12m        EUR 101.4bn
Largest buyer            Country A
Largest buyer value      EUR 18.4bn
Joint/multinational      EUR 3.2bn
```

---

# 20. What does my country buy?

The second important view is category composition.

Example:

```text
MY COUNTRY — AWARDED VALUE 12m

Air & missile defence       EUR 1.8bn   30%
Ammunition & explosives     EUR 1.4bn   23%
Naval & maritime            EUR 1.1bn   18%
C4ISR                       EUR 0.8bn   13%
Land systems                EUR 0.6bn   10%
Other                       EUR 0.4bn    6%
```

Use the existing deterministic strategic-category model from Phase 1.

Do not invent narrative category classifications.

A result may need to be classified as:

```text
Other / Unclassified
```

when the data is insufficient.

Expose the unclassified share.

---

# 21. What do other countries buy?

The data model must support the same category breakdown for every country.

Do not create dozens of permanent Home Assistant devices by default.

Instead make the complete country/category matrix available to the integration so the UI can expose:

```text
top countries
selected country
comparison countries
```

A later options flow may allow the user to pin specific comparison countries.

---

# 22. Largest awards

Country totals should always be explainable.

For the selected country, expose the largest awards behind the 12-month total.

Example:

```text
Largest awards — my country

EUR 620m   Category A   Buyer X
EUR 410m   Category B   Buyer Y
EUR 270m   Category A   Buyer Z
```

The same data should be available for top-ranked countries.

This is essential because one or two large contracts may explain most of a country's movement.

Every item should link back to its TED source where possible.

---

# 23. Growth

Growth should be factual:

```text
current rolling 12m
vs
previous 12m
```

Example:

```text
Sweden

Current 12m      EUR 6.1bn
Previous 12m     EUR 4.7bn
Difference       EUR +1.4bn
Change           +29.8%
```

For country growth rankings, avoid absurd percentages caused by near-zero previous periods.

A country should only appear in a "fastest-growing" ranking if it meets a minimum activity threshold.

The threshold should be simple and documented.

Example eligibility:

```text
at least 5 valued awards in current period
OR
at least EUR 50m awarded value
```

The raw country ranking by absolute value must never use such a threshold.

---

# 24. Primary Home Assistant entities

Do not create an excessive number of entities.

## Device: My Country

Suggested core sensors:

```text
Awarded value 12m
Awarded value previous 12m
Awarded value change %
Country rank 12m
Share of total %
Award count 12m
Value coverage %
Top category
Largest award
```

## Device: European Market

Suggested core sensors:

```text
Total awarded value 12m
Total awarded value 90d
Largest buyer country 12m
Largest buyer value 12m
Number of countries with attributable value
Joint/multinational value 12m
```

## Device: Country Ranking

One main ranking sensor can expose the ordered country table as structured attributes.

The selected country must be included even when outside the displayed top group.

---

# 25. Useful text sensors

Compact factual text is useful on a mobile dashboard.

Examples:

```text
My country summary
"SE · EUR 6.1bn / 12m · #5 · 6.0% · +29.8%"
```

```text
Top buyers
"DE EUR 18.4bn · PL EUR 14.7bn · FR EUR 11.2bn · IT EUR 8.6bn · SE EUR 6.1bn"
```

```text
My country categories
"Air defence EUR 1.8bn · Ammunition EUR 1.4bn · Naval EUR 1.1bn"
```

These are presentation helpers.

Numeric sensors and structured country summaries remain the source of truth.

---

# 26. Visualization

The main ranking is naturally a horizontal bar chart:

```text
Awarded defence contract value — 12 months

Country A   ██████████████████   EUR 18.4bn
Country B   ██████████████       EUR 14.7bn
Country C   ███████████          EUR 11.2bn
Country D   ████████              EUR 8.6bn
Sweden      ██████                EUR 6.1bn
```

The selected country should be visually identifiable wherever the frontend allows it.

If the selected country is outside the top displayed countries:

```text
Top 10
...
My country: #17 — EUR ...
```

Never hide the user's selected country just because its rank is low.

---

# 27. Trend visualization

For the selected country:

```text
rolling awarded value
```

should be visible over time.

Prefer:

```text
rolling 12-month value
```

or:

```text
monthly awarded value
```

over misleading snapshots.

Because awards are lumpy, a rolling 12-month line is particularly useful.

The integration should retain enough history to make this possible.

---

# 28. Comparison with all countries

The full dataset must support comparison against every country represented in the relevant TED data.

Do not pre-select a fixed peer group as the only comparison.

The selected country should be comparable with:

```text
all countries
Nordic countries
EU countries
individual countries
```

These are views over the same country summary data.

No separate ingestion is needed.

---

# 29. Data-quality visibility

A country ranking without coverage information can be misleading.

For every country, retain:

```text
award result count
award results with monetary value
value coverage %
buyer-country coverage
number/value of multinational results
```

The selected-country device should expose at least:

```text
Value coverage
```

The ranking sensor should include coverage for each country in its attributes.

Example:

```text
Sweden
Awarded value: EUR 6.1bn
Value coverage: 82%
```

Do not rank missing values as zero.

---

# 30. Countries with low coverage

A country may have procurement activity but poor monetary-value publication.

The ranking should distinguish:

```text
EUR 0
```

from:

```text
unknown / insufficient monetary coverage
```

If a country has no usable award values but has award notices:

```text
award_value = unknown
```

not zero.

Such a country should not misleadingly appear at the bottom as if it bought nothing.

---

# 31. Validation against underlying notices

Before release, manually inspect a sample of:

```text
top 10 largest awards
top 5 countries
selected country
framework agreements
multi-lot results
multinational procurements
direct awards
```

For each sample verify:

```text
buyer country
result status
Notice Value
currency
award date/publication date
framework semantics
notice version
defence relevance
```

The goal is to ensure the ranking can be explained notice by notice.

---

# 32. Direct awards

The ranking is about purchases, not competition method.

Therefore valid publicly reported awarded contracts should be included regardless of whether they arose from:

```text
open competition
restricted competition
negotiated procedure
direct award
other valid procurement procedure
```

Do not measure only competitive tenders.

The result must answer:

```text
What has been awarded?
```

not:

```text
What has been competitively tendered?
```

---

# 33. Cancelled / non-awarded procedures

Do not count a procedure as a purchase when no winner was selected.

Non-award notices may later support process statistics, but they must contribute:

```text
EUR 0 to awarded-value totals
```

because no purchase was reported as awarded.

This zero is semantically different from a missing monetary value on an actually awarded result.

Keep those cases distinct internally.

---

# 34. What not to do in this phase

Do not spend time on:

- NATO opportunities,
- EU funding opportunities,
- planned procurement pipeline,
- media/news monitoring,
- AI summaries,
- supplier intelligence beyond what is necessary to explain awards,
- custom Lovelace cards,
- complex peer configuration,
- predictive analytics,
- arbitrary scoring,
- red/yellow/green ratings.

The goal is narrower:

> **Make the country purchasing picture correct, transparent, and useful.**

---

# 35. Implementation sequence

## Step 1 — data profile

Run the existing TED ingestion over sufficient history.

Recommended minimum:

```text
24 months of relevant result notices
```

Produce:

```text
docs/country-purchasing-data-profile.md
```

The report should contain:

```text
award notices by country
Notice Value coverage by country
currency distribution
buyer-country coverage
multinational procurement count/value
framework count/value
notice-version duplicates
award-date coverage
largest 50 values
```

Stop and investigate obvious anomalies before continuing.

---

## Step 2 — establish award-value extraction rules

Implement one deterministic function conceptually equivalent to:

```text
extract_awarded_value(result notice)
```

It must return:

```text
value
currency
source field
confidence/quality metadata
```

Primary source:

```text
Notice Value / BT-161
```

Fallback to lower levels only when proven safe.

Add fixtures for every supported path.

---

## Step 3 — country attribution

Implement and test:

```text
single-country buyer
multiple buyers same country
multiple-country buyer
missing country
```

Multinational cases must never duplicate award value across countries.

---

## Step 4 — country summaries

Calculate for every country:

```text
12m
previous 12m
90d
30d
```

including:

```text
award value
award count
coverage
share
change
category split
largest awards
```

---

## Step 5 — ranking

Create:

```text
rank by 12m awarded value
```

Validate that:

```text
sum(country-attributable values)
+
joint/multinational value
=
European total
```

within defined handling of missing/unknown values.

---

## Step 6 — selected country

Add `My country` to setup/options.

Existing installations should receive an options/config migration that asks for or derives the selected country without breaking existing stored data.

The selected country controls presentation, not ingestion.

---

## Step 7 — Home Assistant entities

Only after the ranking has been validated, add the core:

```text
My Country
European Market
Country Ranking
```

devices/sensors.

---

## Step 8 — category breakdown

Use the already implemented strategic classification to answer:

```text
What does my country buy?
What do the top countries buy?
```

Always expose the unclassified portion.

---

## Step 9 — documentation

Document prominently:

> Awarded value is publicly reported TED contract-award value. It is not defence expenditure or cash paid.

Also document:

- coverage,
- multinational handling,
- framework exclusion,
- time periods,
- currency conversion.

---

# 36. Acceptance criteria

This phase is complete when the integration can reliably answer:

## Question 1

```text
Which country has the highest publicly reported defence contract award value over the latest 12 months?
```

## Question 2

```text
How much is the selected country reported to have awarded?
```

## Question 3

```text
What is the selected country's rank and share?
```

## Question 4

```text
How does the selected country's latest 12 months compare with its previous 12 months?
```

## Question 5

```text
Which categories account for the selected country's awarded value?
```

## Question 6

```text
Which individual awards account for the largest parts of the selected country's total?
```

## Question 7

```text
Can every material total be traced back to public source notices?
```

## Question 8

```text
Can the integration state how complete the underlying monetary data is?
```

If any of these cannot be answered reliably, do not hide the limitation behind additional sensors.

---

# 37. Later phases

Only after this country model is stable should the project reconsider other data sources.

A future source should be evaluated by one criterion:

> **Does it improve our ability to understand what countries are buying, or provide genuinely complementary context to that question?**

Possible later additions may include:

```text
NATO procurement results
other structured national award sources
EU joint procurement
```

Funding and vendor opportunities should not be added merely because data exists.

The integration remains a **buyer-focused defence procurement radar**.

---

# 38. Summary

The phase has one objective:

```text
               WHICH COUNTRIES BUY MOST?
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
        HOW MUCH?       WHAT?         TREND?
            │             │             │
            └─────────────┼─────────────┘
                          ▼
                     MY COUNTRY
                          │
                          ▼
                  COMPARE WITH ALL
```

Everything else is secondary.

Build the data foundation first.

Build sensors only after the country ranking is proven correct.
