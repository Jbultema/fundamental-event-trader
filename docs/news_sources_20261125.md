# News And Event Data

## Working Current-News Lane

The bot now reads public financial reporting in addition to company and official disclosures.
It does not wait for the historical stock dataset to qualify before collecting current news.
Nine explicitly configured subscriptions cover BBC Business, Guardian Business, CNBC,
Financial Times Markets, MarketWatch, PR Newswire, NVIDIA's newsroom, the Fed and BLS.

The first preserved collection returned 116 recent items from seven feeds and extracted 16
article bodies. MarketWatch and BLS were unavailable at their robots/access checks. FT was
deliberately headline/feed-summary only. Source access is not a license to bypass a subscription.
This is a current observation result, not an event-strategy backtest.

The collector uses feedparser and Trafilatura, with an identified client, bounded requests,
source-host allowlists, robots checks, and no account/netrc authentication. It does not rotate
identities, retry denied access, use logged-in browser sessions, execute page scripts or bypass
paywalls. Public-source article text stays in the local evidence archive; the dashboard displays
short attributed extracts and source links rather than republishing complete articles.

Source definitions live in `news_sources.py`, not in a current-winning-stock universe. Entity
tags are current observation aids, not verified historical CIK/security mappings. Topics are
transparent dictionary routing, not sentiment, predicted returns or an allocation model.
Issuer publicity is labeled as interested-party evidence. Legal solicitation releases are
separated and excluded by default. Similar boilerplate for different companies is not merged.

## Time And Provenance

Each item preserves publisher time, first feed observation, content-version first observation,
and feature availability. Availability is no earlier than observation of that particular version.
A changed headline or feed summary is a new version even if the article body is unchanged.
Undated, timezone-ambiguous, future-dated and stale feed entries do not enter the current list.

Immutable captures bind raw feed/HTTP bytes, extracted article bodies, source health and item
metadata. A SQLite index retains first-seen identities across captures; it is not a trading
journal or a trusted timestamp authority. Portfolio Lab copies the bound public evidence into
the desk archive so the report does not depend on mutable external URLs or a missing sibling
directory. The hourly refresh lock is released by the kernel if the process crashes.

Today's RSS contents cannot manufacture what the system knew on previous market days. News is
withheld on historical desk selections and does not enter any of the 40 reconstructed price
fact packs. Existing allocation rules and return paths are unchanged. Missing or stale coverage
is not neutral/bearish evidence, and a failed refresh labels any retained older news as stale.

## Creative Source Landscape

| Source family | Useful information | Main limitation | Next treatment |
|---|---|---|---|
| Financial publishers | Earnings coverage, financing stress, policy and sector developments | Syndication, commentary, subscriptions, revisions | Working current RSS/article reader; preserve source and version |
| Issuer IR and prepared remarks | Guidance, capex, order books, cancellations, supply constraints | Promotional framing; prepared remarks differ from Q&A | Add broad-sector issuer coverage and primary call transcripts, not only AI winners |
| Release wires | Timely issuer announcements and corporate actions | Publicity and law-firm solicitation volume | Working current reader, source-type labels, solicitation filter |
| GDELT raw GKG/mentions | Broad international news discovery with timestamped update files | Sparse company identifiers, changing coverage, syndication and translated text | Raw manifest access verified; sample and audit actual historical files next |
| GDELT DOC search | Focused near-term discovery, including non-US reporting | Rolling search window is not a decade-long archive | Discovery adapter only after availability/source attribution audit |
| Common Crawl CC-NEWS | Archived public news document versions from 2016 onward | Large corpus, crawl latency, missingness, publisher rights | Candidate only: index access was robots-excluded in this check; do not bypass |
| DOJ/FTC/competition authorities and court records | Antitrust, litigation, approvals, distress | Filing/action is not a judicial finding; allegations differ from outcomes | Add primary-event metadata with jurisdiction and publication timestamps |
| Industry and operating releases | Semiconductor shipments, electricity demand, freight, inventories | Revisions, commercial restrictions and inconsistent histories | Source-by-source public-data and timestamp audit |

The feasible next historical experiment is news-event information, not a sentiment keyword score
rebranded as a strategy. Lock event definitions first: guidance/capex reductions, funding or
credit events, export restrictions, demand cancellations, and public legal/regulatory actions.
Use source text to distinguish an event from opinion or a solicitation. Separate announcement,
publication, capture and executable decision times. Test immediate gap versus post-publication
drift, 1/2/5-session human execution delays, costs and ordinary-market versus transition periods.
Use cross-company/sector and chronological holdouts, matched non-event controls, false-alarm
costs and the complete experiment registry. Do not select only memorable crises or today's
successful issuers. News-based strategy admission remains off until that evidence exists.

## Primary References

- [Guardian feed guidance](https://www.theguardian.com/help/feeds): personal RSS use and feeds.
- [NVIDIA published RSS subscriptions](https://nvidianews.nvidia.com/rss).
- [Federal Reserve subscriptions](https://www.federalreserve.gov/feeds/feeds.htm).
- [PR Newswire RSS](https://www.prnewswire.com/rss/).
- [GDELT DOC API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/).
- [GDELT GKG codebook](https://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf).
- [Common Crawl news archive description](https://commoncrawl.org/blog/news-dataset-available).

Local access-audit evidence: `reports/news_archive_feasibility_20261125`. Its successful GDELT
manifest check verifies metadata reachability only. It does not qualify historical article
coverage, publication latency, tradable security identities, terminal prices or investment alpha.

## Local Release Evidence

- Native tests: 165 passed, zero skipped/failed, recorded in
  `reports/verification/news_reader_final_20261125.xml`; dependency integrity and Ruff passed.
- Final current-news capture: `data/news/captures/20261126T013821749072Z` (November 25 local),
  116 items, 16 article bodies, seven of nine configured feeds usable.
- Capture manifest SHA256:
  `34814714259a12261a56ea755133b9a69ad64ea97d8120f00cc22d3639cfd6d3`.
- Portfolio Lab publishes a self-contained news copy in
  `reports/market_desk_news_20261125`, with 60 evidence files and 40 historical market sessions.
  Historical price fact packs, timeline and outcomes are unchanged by the news addition.
- News is available for observation and interpretation. No qualified historical stock dataset,
  news-event performance result or new allocation permission is claimed.
