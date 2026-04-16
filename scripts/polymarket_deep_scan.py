#!/usr/bin/env python3
"""
Enhanced Polymarket Deep Scraper
Born from 4 waves of global research — April 2026

Usage:
  python3 polymarket_deep_scan.py                    # Full scan
  python3 polymarket_deep_scan.py --keywords iran oil # Keyword search
  python3 polymarket_deep_scan.py --top 20            # Top markets only
"""

import urllib.request
import json
import sys
from datetime import datetime


class PolymarketDeepScraper:
    """Enhanced scraper for Polymarket Gamma API with keyword matching."""

    BASE = "https://gamma-api.polymarket.com"

    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0 (compatible; hermes-research/1.0)"}

    def _get(self, path, params=None):
        url = f"{self.BASE}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{qs}"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return None

    def get_top_markets(self, limit=50):
        return self._get("/markets", {
            "limit": str(limit),
            "active": "true",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false",
        }) or []

    def get_events(self, limit=50):
        return self._get("/events", {
            "limit": str(limit),
            "active": "true",
            "closed": "false",
            "order": "volume",
            "ascending": "false",
        }) or []

    def search_markets(self, keywords, limit=20):
        all_markets = self.get_top_markets(200)
        events = self.get_events(100)

        for ev in events:
            if isinstance(ev, dict) and "markets" in ev:
                all_markets.extend(ev.get("markets", []))

        results = []
        for m in all_markets:
            q = m.get("question", "").lower()
            title = m.get("title", "").lower() if "title" in m else ""
            desc = m.get("description", "").lower() if "description" in m else ""
            text = f"{q} {title} {desc}"

            if any(kw.lower() in text for kw in keywords):
                prices = m.get("outcomePrices", "[]")
                try:
                    p = json.loads(prices) if isinstance(prices, str) else prices
                except:
                    p = []
                vol = float(m.get("volume", 0) or 0)
                vol24 = float(m.get("volume24hr", 0) or 0)

                results.append({
                    "question": m.get("question", "?"),
                    "prices": p,
                    "volume": vol,
                    "volume24hr": vol24,
                    "yes_pct": float(p[0]) * 100 if len(p) >= 2 else None,
                    "slug": m.get("slug", ""),
                })

        results.sort(key=lambda x: x["volume"], reverse=True)
        return results[:limit]

    def format_market(self, m):
        yes_pct = m.get("yes_pct")
        pct_str = f"{yes_pct:.1f}% YES" if yes_pct is not None else "N/A"
        vol = f"${m['volume']:,.0f}"
        vol24 = f"${m['volume24hr']:,.0f}"
        return f"  {m['question'][:90]}\n    {pct_str} | Vol: {vol} | 24h: {vol24}"


CATEGORIES = {
    "Iran/Military": ["iran", "military", "hormuz", "war", "ceasefire", "nuclear"],
    "Economy/Recession": ["recession", "fed", "interest", "inflation", "gdp", "debt"],
    "Oil/Energy": ["oil", "crude", "wti", "brent", "energy", "petroleum"],
    "AI/Tech": ["agi", "artificial intelligence", "ai model", "openai", "anthropic"],
    "Geopolitics": ["nato", "china", "taiwan", "russia", "europe", "brics"],
    "Finance": ["gold", "bitcoin", "dollar", "treasury", "stock", "bank"],
    "Elections": ["election", "president", "congress", "midterm", "democrat"],
}


def main():
    scraper = PolymarketDeepScraper()

    # Parse args
    args = sys.argv[1:]
    keywords = []
    top_only = False

    i = 0
    while i < len(args):
        if args[i] == "--keywords" and i + 1 < len(args):
            keywords = args[i + 1].split(",")
            i += 2
        elif args[i] == "--top" and i + 1 < len(args):
            top_only = True
            i += 2
        else:
            i += 1

    if top_only:
        markets = scraper.get_top_markets(20)
        print(f"\nTOP 20 MARKETS BY 24H VOLUME ({datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')})")
        print("=" * 70)
        for m in markets:
            prices = m.get("outcomePrices", "[]")
            try:
                p = json.loads(prices) if isinstance(prices, str) else prices
            except:
                p = []
            vol = float(m.get("volume", 0) or 0)
            vol24 = float(m.get("volume24hr", 0) or 0)
            q = m.get("question", "?")
            pct = f"{float(p[0])*100:.1f}% YES" if len(p) >= 2 else "N/A"
            print(f"  {q[:85]}")
            print(f"    {pct} | Vol: ${vol:,.0f} | 24h: ${vol24:,.0f}")
            print()
        return

    if keywords:
        print(f"\nSEARCHING: {', '.join(keywords)}")
        print("=" * 70)
        results = scraper.search_markets(keywords, limit=15)
        for r in results:
            print(scraper.format_market(r))
            print()
        return

    # Full category scan
    print("=" * 70)
    print(f"ENHANCED POLYMARKET DEEP SCAN ({datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')})")
    print("=" * 70)

    for cat_name, kws in CATEGORIES.items():
        print(f"\n>>> {cat_name}")
        results = scraper.search_markets(kws, limit=5)
        if results:
            for r in results:
                print(scraper.format_market(r))
        else:
            print("  No matching markets found")
        print()


if __name__ == "__main__":
    main()
