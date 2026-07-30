"""Live smoke test for money-first cards."""

import re

import pytest
from swarm.router import all_slugs, load_firm

pytestmark = pytest.mark.asyncio


def test_registry_has_money_fields_for_all_slugs():
    slugs = all_slugs()
    assert len(slugs) >= 50, "expected at least 50 firms"
    missing = []
    for slug in slugs:
        firm = load_firm(slug)
        for key in ["offer_title", "one_liner", "cta_hook"]:
            if not firm.get(key):
                missing.append((slug, key))
        for key in ["price_quick_eur", "price_full_eur", "price_retainer_eur"]:
            if not isinstance(firm.get(key), int):
                missing.append((slug, key))
    assert not missing, f"missing fields: {missing[:10]}"


def test_no_jargon_in_titles():
    jargon = [w for w in ["Liability", "Redline", "CFM", "EBITDA", "SOC-2", "DPIA", "HIPAA", "GDPR", "NIS2", "AML", "ITAR", "DORA"]]
    hits = []
    for slug in all_slugs():
        firm = load_firm(slug)
        title = firm.get("offer_title", "")
        for w in jargon:
            if w.lower() in title.lower():
                hits.append((slug, title, w))
    assert not hits, f"titles contain hard jargon: {hits[:10]}"


def test_products_are_solid():
    bad = []
    for slug in all_slugs():
        firm = load_firm(slug)
        products = firm.get("products", [])
        if len(products) < 3:
            bad.append((slug, f"only {len(products)} products"))
            continue
        prices = [p.get("price_eur") for p in products if isinstance(p.get("price_eur"), int)]
        if len(prices) != 3:
            bad.append((slug, "missing product prices"))
    assert not bad, f"product issues: {bad[:10]}"


def test_prices_are_realistic():
    bad = []
    for slug in all_slugs():
        firm = load_firm(slug)
        prices = [firm.get("price_quick_eur"), firm.get("price_full_eur"), firm.get("price_retainer_eur")]
        if any(not isinstance(p, int) for p in prices):
            bad.append((slug, "bad price type"))
            continue
        if prices[2] < prices[1] * 2.5:
            bad.append((slug, f"retainer {prices[2]} too close to full {prices[1]}"))
    assert not bad, f"price issues: {bad[:10]}"
