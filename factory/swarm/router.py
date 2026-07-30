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


def _parse_value(value: str):
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        return value


def load_firm(slug: str) -> dict[str, Any]:
    path = FIRMS_DIR / f"{slug}.toml"
    if not path.exists():
        raise KeyError(f"unknown firm: {slug}")
    raw = path.read_text()
    out: dict[str, Any] = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#"):
            continue
        if line.startswith("products = ["):
            products: list[dict[str, Any]] = []
            current: dict[str, Any] = {}
            while i < len(lines):
                item_line = lines[i].strip()
                i += 1
                if item_line == "]":
                    if current:
                        products.append(dict(current))
                        current = {}
                    break
                if "=" in item_line:
                    for pair_m in re.finditer(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|[\d]+(?:\.\d+)?|true|false)', item_line):
                        current[pair_m.group(1)] = _parse_value(pair_m.group(2))
            if current:
                products.append(current)
            out["products"] = products
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = _parse_value(value)
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
