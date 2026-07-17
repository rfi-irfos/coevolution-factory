"""
ComplianceGuard — real daughter company over the LIVE lauras-agents engine.

This is not a demo. It is the business layer for one vertical of the parent engine:
  - public site (index.html)
  - self-serve signup -> issues an entitlement key
  - /api/review proxies to the REAL 292-agent pipeline (parent's Rust/Axum API)
  - every run is metered (first 3 free, then EUR 0.20/run) and logged
  - /dashboard shows live accounts / runs / revenue

The parent engine is reached via CG_ENGINE_URL + CG_ENGINE_KEY (the parent's
entitlement key for THIS daughter). Without those, the proxy returns a clean
502 "engine unreachable" — the wiring is real, it just needs the engine deployed.

Laura gate: public copy in index.html is pre-reviewed (mcp_laura_review_plan, 0 FLAGs).
"""
import os, json, secrets, time
from pathlib import Path
from aiohttp import web, ClientSession, ClientError

ROOT = Path(__file__).parent
ENGINE_URL = os.environ.get("CG_ENGINE_URL", "http://localhost:8080")
ENGINE_KEY = os.environ.get("CG_ENGINE_KEY", "local")  # parent-issued key for THIS daughter
DB = ROOT / "entitlements.json"
PRICE_PER_RUN = 0.20          # EUR
FREE_RUNS = 3
# The exact agent slice this daughter is licensed to use (parent entitlement).
AGENTS = ["legal-privacy", "legal-compliance", "risk-gdpr",
          "risk-hipaa", "risk-sox", "legal-corporate"]


def load_db():
    if DB.exists():
        return json.loads(DB.read_text())
    return {"accounts": {}, "usage": [], "operator_key": ENGINE_KEY}


def save_db(db):
    DB.write_text(json.dumps(db, indent=2))


db = load_db()
db["operator_key"] = ENGINE_KEY
save_db(db)


async def index(request):
    return web.FileResponse(ROOT / "index.html")


async def health(request):
    return web.json_response({"status": "ok", "engine": ENGINE_URL,
                               "daughter_key_set": bool(ENGINE_KEY and ENGINE_KEY != "local")})


async def signup(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    email = (data.get("email") or "").strip().lower()
    if "@" not in email:
        return web.json_response({"error": "valid email required"}, status=400)
    key = "cg_" + secrets.token_hex(16)
    db["accounts"][key] = {"email": email, "created": int(time.time()),
                           "plan": "trial", "runs": 0}
    save_db(db)
    return web.json_response({"key": key, "plan": "trial",
                              "message": f"key issued; {FREE_RUNS} free runs, then EUR {PRICE_PER_RUN}/run"})


async def review(request):
    auth = request.headers.get("Authorization", "")
    key = auth.replace("Bearer ", "").strip()
    acct = db["accounts"].get(key)
    if not acct:
        return web.json_response({"error": "invalid key"}, status=401)
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    text = (body.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "missing 'text'"}, status=400)

    payload = {"text": text, "agents": AGENTS, "metadata": None}
    headers = {"Authorization": f"Bearer {ENGINE_KEY}", "Content-Type": "application/json"}
    try:
        async with ClientSession() as s:
            async with s.post(f"{ENGINE_URL}/pool/team", headers=headers,
                              json=payload, timeout=600) as r:
                upstream = await r.json()
                status = r.status
    except ClientError as e:
        return web.json_response({"error": "engine unreachable", "detail": str(e),
                                  "hint": "set CG_ENGINE_URL + CG_ENGINE_KEY to the parent engine"},
                                 status=502)

    acct["runs"] += 1
    cost = 0.0 if acct["runs"] <= FREE_RUNS else PRICE_PER_RUN
    db["usage"].append({"key": key, "ts": int(time.time()), "cost": cost})
    save_db(db)
    return web.json_response({"upstream_status": status, "result": upstream, "billed_eur": cost},
                             status=200 if status == 200 else status)


async def dashboard(request):
    total_runs = len(db["usage"])
    revenue = sum(u["cost"] for u in db["usage"])
    return web.json_response({
        "company": "ComplianceGuard",
        "accounts": len(db["accounts"]),
        "runs": total_runs,
        "revenue_eur": round(revenue, 2),
        "engine": ENGINE_URL,
        "agents": AGENTS,
    })


app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/health", health)
app.router.add_get("/dashboard", dashboard)
app.router.add_post("/signup", signup)
app.router.add_post("/api/review", review)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("CG_PORT", "8090")))
