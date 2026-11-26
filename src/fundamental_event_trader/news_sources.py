"""Public news subscriptions. Issuer publicity is not independent financial reporting."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    kind: str
    feed: str
    hosts: tuple[str, ...]
    read_articles: bool = True

    def specification(self):
        return asdict(self)


SOURCES = (
    Source("bbc_business", "BBC Business", "financial_press",
           "https://feeds.bbci.co.uk/news/business/rss.xml", ("feeds.bbci.co.uk", "www.bbc.co.uk", "www.bbc.com")),
    Source("guardian_business", "Guardian Business", "financial_press",
           "https://www.theguardian.com/business/rss", ("www.theguardian.com",)),
    Source("cnbc_markets", "CNBC", "financial_press",
           "https://www.cnbc.com/id/100003114/device/rss/rss.html", ("www.cnbc.com",)),
    Source("marketwatch", "MarketWatch", "financial_press",
           "https://feeds.content.dowjones.io/public/rss/mw_topstories", ("feeds.content.dowjones.io", "www.marketwatch.com")),
    Source("ft_markets", "Financial Times Markets", "financial_press",
           "https://www.ft.com/markets?format=rss", ("www.ft.com",), False),
    Source("prnewswire", "PR Newswire", "issuer_release_wire",
           "https://www.prnewswire.com/rss/news-releases-list.rss", ("www.prnewswire.com",)),
    Source("nvidia", "NVIDIA Newsroom", "issuer_newsroom",
           "https://nvidianews.nvidia.com/cats/press_release.xml", ("nvidianews.nvidia.com",)),
    Source("federal_reserve", "Federal Reserve", "official_release",
           "https://www.federalreserve.gov/feeds/press_all.xml", ("www.federalreserve.gov",)),
    Source("bls", "Bureau of Labor Statistics", "official_release",
           "https://www.bls.gov/feed/bls_latest.rss", ("www.bls.gov",)),
)

# Topic routing is explicitly not sentiment, a causal explanation, or a trading score.
TOPICS = {
    "AI spending and infrastructure": ("artificial intelligence", "ai spending", "data center", "data centre", "nvidia", "semiconductor", "gpu", "hyperscaler"),
    "Earnings and guidance": ("earnings", "guidance", "profit warning", "revenue", "quarterly results", "outlook"),
    "Credit and funding": ("credit", "liquidity", "bankruptcy", "default", "refinanc", "bond yield", "debt market"),
    "Trade and policy": ("tariff", "export control", "trade war", "sanction", "import tax"),
    "Rates, inflation and employment": ("interest rate", "federal reserve", "inflation", "payroll", "unemployment", "consumer price", "fomc"),
    "Deals and capital returns": ("acquisition", "merger", "takeover", "buyback", "dividend", "share repurchase", "spin-off"),
    "Regulation and legal events": ("antitrust", "regulator", "lawsuit", "court ruling", "securities fraud", "investigation"),
    "Energy and supply chains": ("oil price", "crude", "opec", "supply chain", "shipping", "natural gas", "electricity"),
    "Consumer and industrial demand": ("retail sales", "consumer spending", "factory", "manufacturing", "housing", "automaker", "airline"),
}

ENTITIES = {
    "NVIDIA": ("nvidia",), "Microsoft": ("microsoft",), "Alphabet": ("alphabet", "google"),
    "Amazon": ("amazon",), "Meta Platforms": ("meta platforms",), "Apple": ("apple",),
    "TSMC": ("tsmc", "taiwan semiconductor"), "ASML": ("asml",),
    "JPMorgan": ("jpmorgan",), "Exxon Mobil": ("exxon",), "Eli Lilly": ("eli lilly",),
    "Walmart": ("walmart",), "Berkshire Hathaway": ("berkshire hathaway",),
}
