#!/usr/bin/env python3
"""Pre-flight + live-verify script for the center modal.

Context
-------
The center modal (factory/runtime.py :: center_card_html) is being reworked
(see .hermes/plans/2026-07-22_193000-product-list-rework.md) so that, instead
of the old self-evident "Was du bekommst" / "What you get" bullets and the
prompt-style "servicelist", it renders ONE honest "Produkte & Leistungen" /
"Products & Services" block (class="productsblock") with >= 7 concrete
deliverables per center.

This script verifies that rework, both locally (rendering via the imported
runtime) and live (fetching the deployed Fly page). It is meant to be run in
CI / pre-deploy and must NEVER crash on import or on render even when the
product data has not landed yet.

Severity model
--------------
* HARD   -> always a failure (exit 1): Python exception during render/import,
            or the first <script> block failing `node --check` (real JS error).
            These mean the page is genuinely broken.
* PENDING-> a content assertion that is not yet satisfied. This is EXPECTED
            before the rework data lands (products list empty, old blocks
            still present). Reported clearly but does NOT crash the script and
            does NOT fail the default run. Once the rework merges, every one of
            these clears and the run is fully green.
* SKIP   -> could not be performed for environmental reasons (Fly unreachable,
            `node` binary missing). Non-fatal.
* OK     -> a check that passed.

Exit codes
----------
  0  no HARD errors (default mode tolerates PENDING gaps)
  1  at least one HARD error, OR (with --strict) any PENDING gap remains
     (use --strict in CI once the rework is merged).

Usage
-----
  python3 scripts/verify_modal.py            # local + live, tolerant
  python3 scripts/verify_modal.py --strict   # PENDING gaps also fail
  python3 scripts/verify_modal.py --no-live  # skip the Fly fetch
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# --- repo layout: scripts/verify_modal.py -> repo/factory -------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
FACTORY_DIR = REPO_ROOT / "factory"
sys.path.insert(0, str(FACTORY_DIR))

SLUGS = ("nonprofit-gov", "gdpr-guard")
LANGS = ("en", "de")
LIVE_BASE = "https://coevolution-factory-sparkling-mountain-1802.fly.dev"

# Strings that must be GONE after the rework (old/dead boxes).
FORBIDDEN = ("Was du bekommst", "What you get", "servicelist")


def expected_title(lang: str) -> str:
    """The product-block heading we expect per language."""
    return "Produkte & Leistungen" if lang == "de" else "Products & Services"


class Report:
    def __init__(self):
        self.ok = []
        self.pending = []
        self.skipped = []
        self.hard = []

    def add_ok(self, msg):
        self.ok.append(msg)

    def add_pending(self, msg):
        self.pending.append(msg)

    def add_skip(self, msg):
        self.skipped.append(msg)

    def add_hard(self, msg):
        self.hard.append(msg)


def _node_check(js: str, report: Report, tag: str):
    """Write js to a temp file and run `node --check`; record result."""
    if not js.strip():
        report.add_pending(f"{tag}: extracted <script> is empty, nothing to parse")
        return
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False
        ) as tf:
            tf.write(js)
            tmp = tf.name
        proc = subprocess.run(
            ["node", "--check", tmp],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            report.add_hard(
                f"{tag}: JS PARSE FAIL (node --check)\n{proc.stderr.strip()}"
            )
        else:
            report.add_ok(f"PARSES OK {tag}")
    except FileNotFoundError:
        report.add_skip(f"{tag}: `node` binary not found — skipped JS syntax check")
    except subprocess.TimeoutExpired:
        report.add_hard(f"{tag}: `node --check` timed out")
    except Exception as exc:  # pragma: no cover - defensive
        report.add_hard(f"{tag}: could not run node --check: {exc}")
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def check_render(report: Report):
    """Render every slug/lang locally via the imported runtime and assert."""
    try:
        import runtime  # noqa: WPS433 (intentional dynamic import)
    except Exception as exc:
        report.add_hard(f"IMPORT FAILED: {type(exc).__name__}: {exc}")
        return

    for slug in SLUGS:
        for lang in LANGS:
            tag = f"[{slug}/{lang}]"
            try:
                html = runtime.center_card_html(slug, lang=lang)
            except Exception as exc:
                report.add_hard(
                    f"RENDER CRASH {tag}: {type(exc).__name__}: {exc}"
                )
                continue

            report.add_ok(f"RENDER OK {tag}")

            # --- content assertions (PENDING until rework data lands) -------
            title = expected_title(lang)
            if title not in html:
                report.add_pending(
                    f"{tag}: product title '{title}' NOT present"
                )
            if 'class="productsblock"' not in html:
                report.add_pending(
                    f'{tag}: \'class="productsblock"\' NOT present'
                )
            li_count = html.count("<li>")
            if li_count < 7:
                report.add_pending(
                    f"{tag}: <li> count {li_count} < 7 (products missing)"
                )
            for banned in FORBIDDEN:
                if banned in html:
                    report.add_pending(
                        f"{tag}: forbidden string '{banned}' STILL present "
                        f"(old block not removed yet)"
                    )

            # --- JS syntax check on the first <script> block ---------------
            m = re.search(r"<script>(.*?)</script>", html, re.S)
            if not m:
                report.add_pending(f"{tag}: no <script> block found to parse")
                continue
            _node_check(m.group(1), report, tag)


def check_live(report: Report):
    """Fetch the deployed page and assert the product block is live."""
    for slug in SLUGS:
        for lang in LANGS:
            tag = f"LIVE [{slug}/{lang}]"
            url = f"{LIVE_BASE}/{slug}?lang={lang}"
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "verify_modal/1.0"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    body = resp.read().decode("utf-8", "replace")
            except (urllib.error.URLError, OSError, ValueError) as exc:
                report.add_skip(f"{tag}: fetch failed: {exc}")
                continue

            title = expected_title(lang)
            if title not in body:
                report.add_pending(f"{tag}: product title '{title}' NOT present")
            if 'class="productsblock"' not in body:
                report.add_pending(
                    f'{tag}: \'class="productsblock"\' NOT present'
                )
            li_count = body.count("<li>")
            if li_count < 7:
                report.add_pending(f"{tag}: <li> count {li_count} < 7")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="treat PENDING content gaps as failures (exit 1)",
    )
    ap.add_argument(
        "--no-live",
        action="store_true",
        help="skip the live Fly.dev fetch",
    )
    args = ap.parse_args()

    report = Report()
    check_render(report)
    if not args.no_live:
        check_live(report)

    for line in report.ok:
        print(line)
    for line in report.pending:
        print("PENDING:", line)
    for line in report.skipped:
        print("SKIP:   ", line)
    for line in report.hard:
        print("ERROR:  ", line)

    print(
        f"\nSummary: {len(report.ok)} ok | "
        f"{len(report.pending)} pending | "
        f"{len(report.skipped)} skipped | "
        f"{len(report.hard)} errors"
    )

    if report.hard:
        return 1
    if report.pending and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
