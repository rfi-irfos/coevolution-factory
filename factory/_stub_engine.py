# STUB engine for LOCAL verification only. Mimics the real lauras-agents
# /pool/team contract: POST {text, agents} -> {responses:[{agent, findings:[...]}]}
# It returns deterministic, honest findings based on keyword hits in `text`
# so we can verify the cross_synthesize() path WITHOUT touching any network,
# the real engine, or real money. NOT for production.
import os, json
from aiohttp import web, ClientSession

STUB_PORT = int(os.environ.get("STUB_PORT", "8099"))


async def pool_team(request):
    body = await request.json()
    agents = body.get("agents", [])
    text = (body.get("text") or "").lower()
    responses = []
    # deterministic, rule-based findings (clearly a stub, no fabrication of real
    # legal advice — only structural so the orchestration is verifiable)
    for a in agents:
        findings = []
        if "unencrypted" in text and "gdpr" in a:
            findings.append({"severity": "flag",
                             "description": "Unencrypted storage of personal data "
                                            "lacks GDPR Art.32 technical measures.",
                             "evidence": "store it unencrypted"})
        if "legitimate interest" in text and "gdpr" in a:
            findings.append({"severity": "flag",
                             "description": "Legitimate interest without DPIA is "
                                            "not documented as required.",
                             "evidence": "legitimate interest without a DPIA"})
        if "unencrypted" in text and "hipaa" in a:
            findings.append({"severity": "flag",
                             "description": "Unencrypted PHI breaches HIPAA "
                                            "Security Rule safeguards.",
                             "evidence": "store it unencrypted"})
        responses.append({"agent": a, "findings": findings})
    return web.json_response({"responses": responses})


async def health(request):
    return web.json_response({"status": "ok", "mode": "stub"})


app = web.Application()
app.router.add_get("/health", health)
app.router.add_post("/pool/team", pool_team)

if __name__ == "__main__":
    web.run_app(app, host="127.0.0.1", port=STUB_PORT)
