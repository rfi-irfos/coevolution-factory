"""factory/swarm/router.py — lightweight dispatch from registry TOML to panel config.

This module intentionally avoids heavy deps. It reads the existing
`factory/registry/firms/<slug>.toml` files and returns a deterministic
panel config for the runtime. No network calls, no DB writes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import re

HERE = Path(__file__).parent
FIRMS_DIR = HERE.parent / "registry" / "firms"


def _parse_toml_value(line: str):
    line = line.strip()
    if not line or line.startswith("#"):
        return None, None
    if "=" not in line:
        return None, None
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if value.startswith('"') and value.endswith('"') and value.count('"') == 2:
        return key, value[1:-1]
    if value.startswith('"'):
        return key, value[1:-1]
    try:
        return key, int(value)
    except ValueError:
        return key, value


def load_firm(slug: str) -> dict[str, Any]:
    path = FIRMS_DIR / f"{slug}.toml"
    if not path.exists():
        raise KeyError(f"unknown firm: {slug}")
    raw = path.read_text()
    out: dict[str, Any] = {}
    products: list[dict[str, Any]] = []
    in_products = False
    current: dict[str, Any] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if in_products:
            if stripped == "]":
                if current:
                    products.append(current)
                    current = {}
                in_products = False
                continue
            if stripped.startswith(("{", "}", "[")):
                continue
            key, value = _parse_toml_value(stripped)
            if key is None or current is None:
                continue
            current[key] = value
            continue
        key, value = _parse_toml_value(stripped)
        if key is None:
            continue
        if key == "products":
            in_products = True
            continue
        out[key] = value
    if products:
        out["products"] = products
    # Default fallbacks
    out.setdefault("swarm_agents", [])
    out.setdefault("delivery_mode", "serial")
    out.setdefault("auto_spawn", False)
    out.setdefault("offer_title", slug)
    out.setdefault("cta_hook", "Jetzt prüfen lassen")
    out.setdefault("sla_hours", 24)
    return out


def panel_for(slug: str) -> dict[str, Any]:
    firm = load_firm(slug)
    return {
        "slug": slug,
        "offer_title": firm.get("offer_title", slug),
        "cta_hook": firm.get("cta_hook", "Jetzt prüfen lassen"),
        "sla_hours": int(firm.get("sla_hours", 24)),
        "delivery_mode": firm.get("delivery_mode", "serial"),
        "auto_spawn": bool(firm.get("auto_spawn", False)),
        "agents": list(firm.get("swarm_agents", [])),
        "pricing": {
            "quick": firm.get("price_quick_eur"),
            "full": firm.get("price_full_eur"),
            "retainer": firm.get("price_retainer_eur"),
            "currency": firm.get("currency", "EUR"),
        },
        "products": firm.get("products", []),
    }


def all_slugs() -> list[str]:
    return [p.stem for p in FIRMS_DIR.glob("*.toml")]
