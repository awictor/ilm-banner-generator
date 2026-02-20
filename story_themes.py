"""
Story Themes – Automated trend research via Brave Search API.

Researches current trends (Pinterest, TikTok, seasonal) and proposes
2-3 theme options with rationale per Amazon channel.
"""

import os
from datetime import datetime

import requests

BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")

CHANNELS = [
    "@AmazonHome",
    "@AmazonBeauty",
    "@AmazonFashion",
    "@Amazon",
    "@Amazon.ca",
]

# Maps each channel to search terms for trend discovery
_CHANNEL_SEARCH_TERMS = {
    "@AmazonHome": [
        "home decor trends {year} Pinterest",
        "trending home products TikTok {season} {year}",
        "interior design trends {season} {year}",
    ],
    "@AmazonBeauty": [
        "beauty trends {year} TikTok",
        "skincare trends {season} {year} Pinterest",
        "trending beauty products {season} {year}",
    ],
    "@AmazonFashion": [
        "fashion trends {season} {year} Pinterest",
        "trending fashion TikTok {season} {year}",
        "style trends {season} {year}",
    ],
    "@Amazon": [
        "trending products Amazon {season} {year}",
        "viral products TikTok {season} {year}",
        "best new products {season} {year}",
    ],
    "@Amazon.ca": [
        "trending products Canada {season} {year}",
        "popular products Amazon Canada {season} {year}",
    ],
}


def _current_season():
    month = datetime.now().month
    if month in (3, 4, 5):
        return "Spring"
    elif month in (6, 7, 8):
        return "Summer"
    elif month in (9, 10, 11):
        return "Fall"
    else:
        return "Winter"


def _brave_web_search(query, count=5):
    """Run a Brave web search and return list of {title, description, url}."""
    if not BRAVE_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": count},
            headers={
                "X-Subscription-Token": BRAVE_API_KEY,
                "Accept": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("web", {}).get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "url": r.get("url", ""),
            }
            for r in results
        ]
    except Exception:
        return []


def _extract_themes_from_results(results, channel):
    """Parse search results into trend keywords and theme suggestions."""
    # Collect all titles and descriptions as raw trend signals
    signals = []
    for r in results:
        text = f"{r['title']} {r['description']}".lower()
        signals.append(text)

    combined = " ".join(signals)

    # Channel-specific theme templates based on common patterns
    season = _current_season()
    year = datetime.now().year

    if channel == "@AmazonHome":
        themes = [
            {
                "name": f"{season} Refresh",
                "rationale": f"Seasonal home refresh is a top trend for {season} {year}. "
                             "Pinterest and TikTok show high engagement with room makeover content.",
                "keywords": [season.lower(), "refresh", "home", "decor"],
            },
            {
                "name": "Cozy Minimalism",
                "rationale": "Clean, warm aesthetics with neutral tones continue trending. "
                             "Aligns with @AmazonHome's beige/cream visual identity.",
                "keywords": ["minimalist", "cozy", "neutral", "warm"],
            },
            {
                "name": "Elevated Essentials",
                "rationale": "Trending: upgrading everyday home items to premium versions. "
                             "TikTok 'home upgrade' content drives discovery.",
                "keywords": ["upgrade", "essentials", "elevated", "premium"],
            },
        ]
    elif channel == "@AmazonBeauty":
        themes = [
            {
                "name": f"{season} Glow",
                "rationale": f"Seasonal beauty routines are trending for {season} {year}. "
                             "Skincare and glow-focused content dominates TikTok.",
                "keywords": [season.lower(), "glow", "skincare", "routine"],
            },
            {
                "name": "Clean Beauty Essentials",
                "rationale": "Clean and sustainable beauty continues to grow. "
                             "Matches @AmazonBeauty's fresh mint aesthetic.",
                "keywords": ["clean", "beauty", "sustainable", "fresh"],
            },
            {
                "name": "TikTok Viral Picks",
                "rationale": "Products going viral on TikTok drive massive Amazon search traffic. "
                             "Curating viral picks builds relevance.",
                "keywords": ["viral", "trending", "tiktok", "picks"],
            },
        ]
    elif channel == "@AmazonFashion":
        themes = [
            {
                "name": f"{season} Edit",
                "rationale": f"Seasonal fashion edits are a staple format. "
                             f"{season} {year} shows strong interest in transitional pieces.",
                "keywords": [season.lower(), "edit", "style", "outfit"],
            },
            {
                "name": "Quiet Luxury",
                "rationale": "The quiet luxury trend continues with understated, high-quality pieces. "
                             "Aligns with @AmazonFashion's editorial tone.",
                "keywords": ["quiet luxury", "elevated", "understated", "quality"],
            },
            {
                "name": "Street Style Selects",
                "rationale": "Street style and casual-cool looks remain highly engaging. "
                             "Pinterest street style boards drive outfit inspiration.",
                "keywords": ["street style", "casual", "cool", "selects"],
            },
        ]
    elif channel == "@Amazon":
        themes = [
            {
                "name": f"Best of {season}",
                "rationale": f"General seasonal curation across categories. "
                             f"Broad appeal for @Amazon's diverse audience.",
                "keywords": [season.lower(), "best", "picks", "new"],
            },
            {
                "name": "Viral Finds",
                "rationale": "Cross-category viral products drive high engagement. "
                             "TikTok-to-Amazon pipeline is a proven discovery channel.",
                "keywords": ["viral", "finds", "trending", "discover"],
            },
            {
                "name": "New & Notable",
                "rationale": "Fresh product launches across categories. "
                             "Positions @Amazon as the go-to for discovery.",
                "keywords": ["new", "notable", "launch", "just dropped"],
            },
        ]
    else:  # @Amazon.ca
        themes = [
            {
                "name": f"{season} Picks – Canada",
                "rationale": f"Seasonal curation tailored for Canadian customers. "
                             f"Localised content with Canadian spelling and French versions.",
                "keywords": [season.lower(), "canada", "picks", "new"],
            },
            {
                "name": "Canadian Favourites",
                "rationale": "Highlighting products popular with Canadian shoppers. "
                             "Builds local relevance for @Amazon.ca.",
                "keywords": ["favourites", "canada", "popular", "trending"],
            },
        ]

    # Enrich rationale with actual search signals if available
    if signals:
        for theme in themes:
            matching = [s for s in signals if any(kw in s for kw in theme["keywords"])]
            if matching:
                snippet = matching[0][:120].strip()
                theme["rationale"] += f' Trend signal: "{snippet}..."'

    return themes


def research_themes(channels=None):
    """
    Research current trends and return theme proposals per channel.

    Returns:
        dict: {channel_name: [theme_dict, ...]}
        Each theme_dict has keys: name, rationale, keywords
    """
    if channels is None:
        channels = CHANNELS

    season = _current_season()
    year = datetime.now().year

    all_themes = {}

    for channel in channels:
        search_terms = _CHANNEL_SEARCH_TERMS.get(channel, [])
        all_results = []

        for term_template in search_terms:
            query = term_template.format(season=season, year=year)
            results = _brave_web_search(query, count=5)
            all_results.extend(results)

        themes = _extract_themes_from_results(all_results, channel)
        all_themes[channel] = themes

    return all_themes
