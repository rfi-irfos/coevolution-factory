# Central Stripe link pool — RFI-IRFOS account (verified by Simeon, 2026-07-16).
# These are REAL payment links already connected to the live Stripe account.
# The 50 factories + parent embed from THIS pool. No new Stripe setup needed.
#
# Mapping philosophy: each daughter factory maps to the closest existing link by
# price tier + problem domain. The "run" (per-doc) micro-payment uses the
# smallest links; enterprise/diligence factories surface the larger sprint links.
# This is the bridge: autonomous engine -> real money in the RFI-IRFOS account.

STRIPE_LINKS = {
    # small / micro (per-run style)
    "case_intake_scan":        "https://buy.stripe.com/9B6dRbdd6bU3euxazC7N60i",   # EUR 700
    "mangelcluster_sprint":    "https://buy.stripe.com/bJefZjc92aPZ869bDG7N60j",  # EUR 2200
    "market_intel":            "https://buy.stripe.com/cNi3cxb4Y3nx9ad37a7N60l",  # EUR 6500
    "framework_magnification": "https://buy.stripe.com/9B600l8WQf6fgCF0Z27N60m",  # EUR 7500
    "emergent_case_sprint":    "https://buy.stripe.com/00w3cxc92bU30DH2367N60n",  # EUR 12500
    "multiagent_design":       "https://buy.stripe.com/7sY6oJdd60blfyB9vy7N60o",  # EUR 24500
    "implementation_build":    "https://buy.stripe.com/aFa9AVb4YcY7fyB2367N60p",  # EUR 35000
    "retainer_monitoring":     "https://buy.stripe.com/4gM00lgpi9LV5Y19vy7N60q",  # EUR 2700
    "framework_update":        "https://buy.stripe.com/14AdRbgpi1fpdqt6jm7N60r",  # EUR 1100
    "systemaudit":             "https://buy.stripe.com/7sY7sN2ysf6fdqt4be7N60s",  # EUR 4500
    "rollenreview":            "https://buy.stripe.com/4gMbJ3a0U3nxdqt8ru7N60t",  # EUR 3000
    "prozessreview":           "https://buy.stripe.com/fZu14p3Cwe2b869ePS7N60u",  # EUR 4500
    "root_level_review":       "https://buy.stripe.com/7sY00lc92aPZ1HL0Z27N60v",  # EUR 5500
    "schnittstellenreview":    "https://buy.stripe.com/aFabJ37SM1fp9adfTW7N60w",  # EUR 4500
    "betriebsreview":          "https://buy.stripe.com/fZu3cx6OI8HRbil5fi7N60x",  # EUR 5000
    "organisationsreview":     "https://buy.stripe.com/dRm28tdd6gaj3PTcHK7N60y",  # EUR 5500
    "produktreview":           "https://buy.stripe.com/6oU7sN3CwaPZ7256jm7N60z",  # EUR 5500
    "framework_design":        "https://buy.stripe.com/dRm9AVgpi7DNdqt37a7N60A",  # EUR 19500
    "system_design_deploy":    "https://buy.stripe.com/aFa28t1uogaj9ad6jm7N60B",  # EUR 55000
    "watchtower_retainment":   "https://buy.stripe.com/3cI7sN4GA4rB5Y16jm7N60C",  # EUR 3000
    "multiagent_coord":        "https://buy.stripe.com/8x28wRc925vFdqtcHK7N60D",  # EUR 3500
    "further_dev_monthly":     "https://buy.stripe.com/fZu14p3Cwe2b869ePS7N60u",  # EUR 5500 / mo
    # the three already on rfi-irfos.com
    "site_link_1":             "https://buy.stripe.com/dRm5kF0qkaPZeuxePS7N603",
    "site_link_2":             "https://buy.stripe.com/14AeVfdd6e2b3PTdLO7N602",
    "site_link_3":             "https://buy.stripe.com/28EcN7b4Y6zJgCFgY07N601",
    # PER-SESSION LINK (THE ONE THAT WAS MISSING):
    # Every center sells ONE "Sitzung" at c["price"] (currently €25). There
    # was no €25 link in the pool before, so price=25 fell through to the
    # "enterprise" tier and surfaced a €3,000 link while the button promised
    # €25 — that mismatch is why nobody bought. Create this link in your
    # Stripe Dashboard (Payment Links -> New -> one-off price €25, currency
    # EUR) and PASTE the real ID below, replacing the placeholder.
    "session_25":              "https://buy.stripe.com/00w28tehae2baehcHK7N60F",
}

# Which link a center surfaces, by its price tier.
# tier = ceil(price per run) bucket -> pick a link at/above that value.
#
# NOTE (2026-07-20 fix): the per-session price is €25 — there is no "small"
# or "mid" link below €700. Before this fix, price=25 (> 5.00) fell into the
# "enterprise" tier and surfaced a €3,000 link while the button text said
# "€25". That 120x mismatch is the core reason no sessions were ever bought.
# Now: any single-session price (<= 100) maps to the real per-session link.
# Higher tiers (real sprints/enterprise engagements) keep their own links.
TIER_TO_LINK = {
    "session": "session_25",              # <= 100  -> the real €25-per-session link
    "small":   "mangelcluster_sprint",    # legacy tiered/sprint pricing
    "mid":     "systemaudit",
    "large":   "emergent_case_sprint",
    "enterprise": "system_design_deploy",
}


def link_for_factory(slug, price):
    """Return the Stripe link a center should surface, by price tier.

    Center attribution: a static buy-link cannot carry per-center
    metadata through a URL param — Stripe Payment Links ignore
    ?metadata[...] query strings. REAL per-center attribution must be set
    when the Payment Link is created in the Stripe Dashboard / API
    (metadata["center"] = <slug>). This function therefore returns the
    bare link only; do NOT append ?metadata[center]= here (it is silently
    dropped by Stripe and gives a false sense of tracking).

    For the current flat per-session pricing, every center maps to the
    same real €25 link. If you later introduce tiered/sprint pricing per
    center, extend the tier logic below.
    """
    if price <= 100:
        tier = "session"
    elif price <= 0.60:
        tier = "small"
    elif price <= 1.00:
        tier = "mid"
    elif price <= 5.00:
        tier = "large"
    else:
        tier = "enterprise"
    return STRIPE_LINKS[TIER_TO_LINK[tier]]
