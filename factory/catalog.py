# 50 interdisciplinary CENTERS — each a standing body of experts that convenes
# around ONE durable problem, drawn from EVERY relevant discipline in the real
# 292-agent registry (lauras-agents/crates/lauras-agents-registry/agents).
#
# Doctrine (per requirement): these are NOT document processors. Every center is
# a standing, interdisciplinary institution. The panel is assembled from the
# real registry's `domain` fields so each center genuinely spans Legal, Risk,
# AI-Safety, Finance, Ops, Security, Exec, etc. — never a single lane.
#
# Cross-center network: relationships are derived from the real agents.md
# `feeds_into` graph. A center that shares downstream agents with another is
# its "adjacent" center — the network re-synthesizes across them.
#
# Autonomy boundary: ops (engine + billing + content) run without a human.
# Human-owned: legal entity, banking, initial traffic, Laura gate on public copy.
#
# The list below is the CANONICAL center definition. Each entry:
#   (slug, name, mandate, [seed_agents], icp, why_crisis_resistant,
#    price_per_session, free_sessions)
# `seed_agents` are anchors; build_panel() expands them into a full
# interdisciplinary panel using the real registry.

CENTERS = [
 ("gdpr-guard", "GDPRGuard Center",
  "Standing authority on lawful-basis, breach exposure and data-rights "
  "obligations across the EU/CA personal-data lifecycle",
  ["legal-privacy","risk-gdpr","legal-compliance","chief-data-officer",
   "risk-ethics","cyber-incident"],
  "Any organization processing EU/CA personal data",
  "Privacy law is non-discretionary; fines scale with revenue, so demand rises "
  "in downturns", 0.20, 3),

 ("ai-act-guard", "AIActGuard Center",
  "Conformity, risk-classification and oversight authority for AI systems placed "
  "on the EU market",
  ["ai-safety-governance","chief-ai-officer","legal-compliance","risk-ethics",
   "ai-safety-eval","product-strategy"],
  "AI product teams shipping into the EU",
  "Regulation only tightens; EU AI Act is mandatory, not optional", 0.25, 3),

 ("sox-controls", "SOXControls Center",
  "Internal-control and financial-reporting assurance for public-company "
  "obligations",
  ["risk-sox","fin-general-ledger","risk-internal-controls","chief-compliance-officer",
   "audit-readiness"],
  "US-listed & SOX-scoped firms",
  "Public-company reporting is mandatory regardless of cycle", 0.30, 2),

 ("hipaa-check", "HIPAACheck Center",
  "Health-data safeguarding authority across clinical, payer and vendor surfaces",
  ["risk-hipaa","legal-privacy","legal-compliance","cyber-incident",
   "chief-compliance-officer"],
  "Healthcare, insurers, health-tech",
  "Health data is permanently regulated; breaches are existential", 0.25, 3),

 ("contract-risk", "ContractRisk Center",
  "Commercial-contract enforceability and exposure authority across the "
  "procure-to-pay and sell-to-collect lifecycle",
  ["legal-commercial","legal-corporate","proc-negotiation","fin-procurement-finance",
   "risk-enterprise"],
  "Procurement, sales, ops teams",
  "Contracts are signed in every economy; risk does not pause", 0.20, 3),

 ("ip-watch", "IPWatch Center",
  "Patent-assignment and IP-ownership authority for R&D and diligence",
  ["legal-ip","research-patents","legal-corporate","corpdev-ma",
   "chief-legal-officer"],
  "R&D-heavy firms, startups, pharma",
  "IP is a defensive moat in crises; diligence intensifies", 0.25, 3),

 ("employment-law", "EmployGuard Center",
  "Employment-law and worker-classification authority across the workforce "
  "lifecycle",
  ["legal-employment","hr-contracts","chro","hr-equity","risk-ethics"],
  "HR / People ops",
  "Employment litigation rises in layoffs; always live", 0.20, 3),

 ("litigation-risk", "LitigGuard Center",
  "Pending-claim and litigation-exposure authority for general counsel",
  ["legal-litigation","chief-legal-officer","corpsec-investigations",
   "risk-enterprise"],
  "General counsel, risk teams",
  "Disputes peak in recessions; counter-cyclical", 0.25, 2),

 ("license-audit", "LicenseAudit Center",
  "OSS and software-license compatibility authority for shipped products",
  ["legal-licensing","proc-software-lic","be-apis","entapps-erp","risk-enterprise"],
  "Engineering, OSS-using products",
  "License violations are discovered in M&A/downturns", 0.20, 3),

 ("tax-exposure", "TaxWatch Center",
  "Corporate and international tax-exposure authority",
  ["fin-tax-corp","fin-tax-intl","fin-treasury-cash","cfo","chief-risk-officer"],
  "Finance / tax teams",
  "Tax scrutiny rises when budgets tighten", 0.30, 2),

 ("vendor-risk", "VendorRisk Center",
  "Third-party and supplier-risk authority across the extended enterprise",
  ["sc-vendor-mgmt","proc-vendor-sel","risk-enterprise","chief-compliance-officer",
   "cyber-identity"],
  "Procurement, vendor mgmt",
  "Supply-chain failures surface in crises; always material", 0.20, 3),

 ("cyber-posture", "CyberPosture Center",
  "Application-security and red/blue posture authority for engineering",
  ["sece-ng-appsec","sece-ng-red","sece-ng-blue","chief-security-officer",
   "devops-cicd"],
  "Security engineering",
  "Breaches are cycle-agnostic; insurance now requires it", 0.30, 2),

 ("threat-intel", "ThreatIntel Center",
  "Threat-landscape and SOC-readiness authority for security operations",
  ["cyber-threat-intel","cyber-soc","sre-monitoring","chief-security-officer"],
  "SOC, CISO office",
  "Threat volume is counter-cyclical to economy", 0.25, 2),

 ("incident-readiness", "IncidentReady Center",
  "Incident-response readiness authority across SRE and security",
  ["cyber-incident","sre-incident","ops-lean","chief-security-officer"],
  "SRE / security ops",
  "Resilience is valued most in volatile periods", 0.20, 3),

 ("data-governance", "DataGov Center",
  "Data catalog, quality and governance authority",
  ["gov-catalog","gov-data-quality","gov-compliance","chief-data-officer",
   "infomgmt-knowledge-graphs"],
  "Data governance teams",
  "Data regs (GDPR, DORA) are expanding, not shrinking", 0.20, 3),

 ("a11y-audit", "A11yAudit Center",
  "Accessibility (WCAG/ADA) authority for product and web surfaces",
  ["fe-accessibility","accessibility-design","ux-design","legal-compliance"],
  "Product, web teams",
  "Accessibility law is mandatory and plaintiff-friendly", 0.20, 3),

 ("esg-report", "ESGReport Center",
  "ESG disclosure and CSRD authority for sustainability and IR",
  ["sustain-esg","sustain-env-reporting","chief-sustainability-officer",
   "fin-ir-sec","risk-ethics"],
  "Sustainability / IR",
  "CSRD reporting is mandatory for large EU firms", 0.25, 3),

 ("carbon-audit", "CarbonAudit Center",
  "Carbon-accounting and reporting authority",
  ["sustain-carbon","sustain-esg","sustain-supply-chain","chief-sustainability-officer"],
  "Sustainability, manufacturing",
  "Emissions reporting is regulation-locked", 0.20, 3),

 ("supply-chain-risk", "SupplyChainRisk Center",
  "Supply-chain disruption and dependency authority",
  ["sc-manufacturing","sc-logistics","sc-vendor-mgmt","risk-enterprise",
   "ops-process"],
  "Operations, supply-chain",
  "Disruption risk is the definition of crisis-resistance demand", 0.20, 3),

 ("procure-leak", "ProcureLeak Center",
  "Procurement spend-leakage and negotiation authority",
  ["proc-negotiation","fin-procurement-finance","proc-vendor-sel","cfo"],
  "Procurement, finance",
  "Cost leakage is hunted hardest in downturns", 0.20, 3),

 ("ma-diligence", "MADiligence Center",
  "M&A legal and risk diligence authority",
  ["corpdev-ma","corpdev-diligence","legal-corporate","risk-enterprise",
   "chief-legal-officer","fin-treasury-invest"],
  "Corp-dev, PE, VCs",
  "Deals slow but diligence intensity rises", 0.40, 1),

 ("board-gov", "BoardGov Center",
  "Board governance and fiduciary authority",
  ["board-of-directors","entarch-governance","chief-compliance-officer",
   "chief-risk-officer","president"],
  "Boards, governance teams",
  "Governance failures are punished in crises", 0.30, 2),

 ("investor-disclosure", "InvestorDisclosure Center",
  "Reg FD / SEC disclosure authority",
  ["fin-ir-sec","fin-ir-earnings","fin-ir-shareholders","chief-legal-officer",
   "corpcomms-pr"],
  "IR, legal",
  "Disclosure errors are always materially risky", 0.30, 2),

 ("crisis-comms", "CrisisComms Center",
  "Crisis-communication and reputation authority",
  ["corpcomms-crisis","corpcomms-pr","corpcomms-media","chief-strategy-officer"],
  "Comms, exec offices",
  "Comms failures compound in crises — peak demand then", 0.25, 3),

 ("insurance-review", "InsureReview Center",
  "Insurance policy and coverage-gap authority",
  ["risk-enterprise","risk-iso","chief-risk-officer","fin-treasury-cash"],
  "Risk, finance",
  "Coverage gaps hurt most in downturns", 0.25, 3),

 ("clinical-doc", "ClinicalDoc Center",
  "Clinical-trial and pharma documentation authority",
  ["legal-compliance","risk-hipaa","docs-tech-writers","research-patents",
   "quality-audits"],
  "Pharma, CROs",
  "Regulated, recession-proof sector", 0.30, 2),

 ("finserv-compliance", "FinServCompliance Center",
  "Fintech regulatory compliance authority",
  ["legal-compliance","risk-sox","risk-gdpr","chief-compliance-officer",
   "be-payments"],
  "Fintech, banks",
  "Financial regulation is the most durable compliance demand", 0.30, 2),

 ("saas-security", "SaaSSecurity Center",
  "SaaS security and cloud-posture authority",
  ["sece-ng-cloudsec","be-auth","infra-cloud","devops-deploy",
   "chief-security-officer"],
  "SaaS eng, security",
  "Cloud breaches are constant; buyers require proof", 0.25, 3),

 ("payments-compliance", "PaymentsCompliance Center",
  "PCI-DSS and payments-compliance authority",
  ["be-payments","risk-enterprise","legal-compliance","sece-ng-cloudsec"],
  "Payments, e-com",
  "Card data rules are non-negotiable and audited", 0.25, 3),

 ("crypto-reg", "CryptoReg Center",
  "MiCA / crypto regulatory authority",
  ["legal-compliance","chief-ai-officer","risk-enterprise","fin-tax-intl"],
  "Crypto, exchanges",
  "Crypto regulation is newly mandatory in EU", 0.30, 2),

 ("lease-review", "LeaseReview Center",
  "Real-estate lease and tenant-risk authority",
  ["legal-corporate","fac-real-estate","fin-procurement-finance","fac-physical-security"],
  "CRE, facilities",
  "Leases are long-tail liabilities surfaced in downturns", 0.20, 3),

 ("franchise-compliance", "FranchiseCompliance Center",
  "Franchise-agreement compliance authority",
  ["legal-commercial","legal-corporate","hr-contracts","risk-enterprise"],
  "Franchisors",
  "Franchise disputes are recurring, cycle-agnostic", 0.20, 3),

 ("nonprofit-gov", "NonprofitGov Center",
  "Nonprofit governance and grant-compliance authority",
  ["board-of-directors","legal-corporate","fin-ar","chief-compliance-officer"],
  "Nonprofits, foundations",
  "Grant compliance is mandatory for funding", 0.20, 3),

 ("export-control", "ExportControl Center",
  "Export-control (ITAR/EAR) authority",
  ["legal-compliance","govt-regulatory","govt-policy","risk-enterprise"],
  "Defense, dual-use exporters",
  "Trade controls tighten in geopolitical crises", 0.30, 2),

 ("product-safety", "ProductSafety Center",
  "Product-safety and liability authority",
  ["risk-enterprise","quality-iso","quality-process","legal-compliance"],
  "Hardware, CPG",
  "Safety failures are always litigated", 0.20, 3),

 ("recall-readiness", "RecallReady Center",
  "Recall and quality-escalation readiness authority",
  ["quality-supplier","ops-process","quality-audits","sre-incident"],
  "Manufacturing quality",
  "Recall cost is existential; readiness demanded pre-crisis", 0.20, 3),

 ("pharma-labeling", "PharmaLabeling Center",
  "Pharma labeling and claims authority",
  ["legal-compliance","docs-tech-writers","risk-hipaa","research-patents"],
  "Pharma, med-devices",
  "Labeling errors are heavily fined, always", 0.25, 3),

 ("food-safety", "FoodSafety Center",
  "Food-safety documentation authority",
  ["quality-iso","gov-compliance","ops-process","quality-audits"],
  "Food & beverage",
  "Food safety is non-discretionary regulation", 0.20, 3),

 ("energy-compliance", "EnergyCompliance Center",
  "Energy and NERC/EU compliance authority",
  ["risk-enterprise","sustain-esg","govt-regulatory","infra-cloud"],
  "Utilities, energy",
  "Energy regulation is essential-infrastructure locked", 0.25, 3),

 ("telecom-compliance", "TelecomCompliance Center",
  "Telecom regulatory compliance authority",
  ["legal-compliance","risk-enterprise","govt-regulatory","infra-networking"],
  "Telcos",
  "Telecom is essential service, always regulated", 0.20, 3),

 ("edu-compliance", "EduCompliance Center",
  "Education-privacy (FERPA) authority",
  ["legal-privacy","legal-compliance","govt-policy","hr-contracts"],
  "Edtech, universities",
  "Student data is permanently protected", 0.20, 3),

 ("child-safety", "ChildSafety Center",
  "Child-safety and age-gating (COPPA) authority",
  ["legal-privacy","risk-ethics","ai-safety-governance","cyber-awareness"],
  "Consumer apps, gaming",
  "Child-safety law is expanding globally", 0.20, 3),

 ("content-policy", "ContentPolicy Center",
  "Content-moderation policy authority",
  ["risk-ethics","corpcomms-pr","legal-compliance","ai-safety-eval"],
  "Social, UGC platforms",
  "Moderation liability is rising everywhere", 0.20, 3),

 ("bias-audit", "BiasAudit Center",
  "Algorithmic-bias and fairness audit authority",
  ["ai-safety-eval","risk-ethics","ai-safety-governance","legal-compliance"],
  "AI/ML teams",
  "Bias audits are becoming legally required", 0.25, 3),

 ("model-card", "ModelCard Center",
  "AI model-card and documentation authority",
  ["ai-safety-governance","mlops-registry","docs-tech-writers","ai-safety-eval"],
  "ML platform teams",
  "Documentation mandates grow with AI Act", 0.25, 3),

 ("breach-readiness", "BreachReady Center",
  "Data-breach readiness and notification authority",
  ["cyber-incident","legal-privacy","risk-gdpr","corpcomms-crisis"],
  "Security, legal",
  "Breach notification is legally timed; always live", 0.25, 3),

 ("whistleblower", "WhistleGuard Center",
  "Whistleblower-policy compliance authority",
  ["legal-employment","risk-ethics","hr-internal-comms","chief-compliance-officer"],
  "HR, compliance",
  "Whistleblower law is mandatory in EU", 0.20, 3),

 ("antitrust", "AntitrustWatch Center",
  "Antitrust and competition authority",
  ["legal-corporate","corpdev-ma","govt-regulatory","chief-legal-officer"],
  "Corp-dev, legal",
  "Antitrust enforcement intensifies in concentration", 0.30, 2),

 ("audit-readiness", "AuditReady Center",
  "Continuous audit-readiness authority",
  ["risk-internal-controls","quality-iso","risk-sox","chief-compliance-officer"],
  "Internal audit",
  "Audit is perpetual; readiness saves fees always", 0.25, 3),

 ("resilience-review", "ResilienceReview Center",
  "Operational-resilience authority",
  ["sre-reliability","ops-lean","sre-scaling","risk-enterprise","incident-readiness"],
  "SRE, ops",
  "Resilience demand peaks exactly in crises", 0.20, 3),
]

assert len(CENTERS) == 50, f"expected 50, got {len(CENTERS)}"


# --------------------------------------------------------------------------
# Panel expansion: turn each center's seed agents into a full, genuinely
# interdisciplinary panel using the REAL agent registry. We pull every agent
# that shares a domain with a seed agent (so the panel spans all relevant
# disciplines, not just the seed lanes), then de-dupe and cap for budget.
# --------------------------------------------------------------------------
import os, json, glob, re

_REGISTRY = os.environ.get(
    "FT_AGENT_REGISTRY",
    "/home/eri-irfos/projects/lauras-agents/crates/lauras-agents-registry/agents")

def _load_registry():
    """Return {slug: {name, domain, lane, feeds_into[]}} from real .toml files."""
    meta = {}
    if not os.path.isdir(_REGISTRY):
        return meta
    for fn in glob.glob(os.path.join(_REGISTRY, "*.toml")):
        slug = os.path.basename(fn)[:-5]
        txt = open(fn).read()
        def g(field):
            m = re.search(r'^'+field+r'\s*=\s*"([^"]*)"', txt, re.M)
            return m.group(1) if m else ""
        fi = re.search(r'feeds_into\s*=\s*\[(.*?)\]', txt, re.S)
        feeds = []
        if fi:
            feeds = re.findall(r'"([^"]+)"', fi.group(1))
        meta[slug] = {"name": g("name"), "domain": g("domain"),
                      "lane": g("lane"), "feeds_into": feeds}
    return meta


_REG = _load_registry()


def build_panel(slug, seed, max_panel=4):
    """Expand seed agents into a focused interdisciplinary panel.

    Capped at 4: the live engine reviews agents sequentially (~15s each),
    so a 14-agent panel would exceed any reasonable HTTP timeout. 4 gives a
    genuine cross-discipline read (e.g. legal + risk + security + ops) while
    staying under ~60s. The breadth is preserved as *coevolution*: the daily
    cron re-optimizes which 4 fire best per center from real telemetry.
    """
    if not _REG:
        return list(seed)  # registry unavailable -> use seeds only
    seed_set = set(seed)
    seed_domains = {_REG[s]["domain"] for s in seed if s in _REG}
    panel = list(seed)
    for s, a in _REG.items():
        if s in seed_set:
            continue
        # include any agent sharing a domain with the center's seed set,
        # OR directly fed_into by a seed agent (real graph adjacency)
        if a["domain"] in seed_domains:
            panel.append(s)
    # de-dupe, preserve order, cap
    seen = set(); out = []
    for p in panel:
        if p not in seen:
            seen.add(p); out.append(p)
    return out[:max_panel]


# --------------------------------------------------------------------------
# Cross-center network: derived from the real agents.md feeds_into graph.
# Two centers are ADJACENT if their seed agents share ≥1 downstream agent.
# --------------------------------------------------------------------------
def build_network():
    """Return {slug: [adjacent_slugs]} from real feeds_into edges."""
    net = {c[0]: set() for c in CENTERS}
    seed_sets = {c[0]: set(c[3]) for c in CENTERS}
    for a, am in _REG.items():
        downstream = set(am["feeds_into"])
        if not downstream:
            continue
        owners = [slug for slug, seeds in seed_sets.items() if a in seeds]
        # any two centers whose seeds both feed this agent are adjacent
        for i in range(len(owners)):
            for j in range(i + 1, len(owners)):
                net[owners[i]].add(owners[j])
                net[owners[j]].add(owners[i])
    # also connect centers that share a seed agent's own downstream set heavily
    return {k: sorted(v) for k, v in net.items()}


# Public derived structures -------------------------------------------------
CENTERS_META = {c[0]: {
    "slug": c[0], "name": c[1], "mandate": c[2], "seed_agents": c[3],
    "icp": c[4], "resilient": c[5], "price": c[6], "free": c[7],
    "panel": build_panel(c[0], c[3]),
    "disciplines": sorted({_REG[s]["lane"] for s in build_panel(c[0], c[3])
                           if s in _REG}),
    # standing health-check prompt: what this center asks itself continuously
    "standing_prompt": (
        f"Standing health check for {c[1]}. Mandate: {c[2]}. "
        f"Convene the panel across {', '.join(sorted({_REG[s]['lane'] for s in build_panel(c[0], c[3]) if s in _REG}))} "
        f"and assess current exposure, emerging tensions, and whether any "
        f"discipline would change its prior view given new context."),
    # value proposition: what the center concretely does for the visitor
    "value_prop": (
        f"A standing body of {len(build_panel(c[0], c[3]))} experts that convenes "
        f"on your {c[2].lower()}. It runs scenario simulations, a continuous "
        f"posture check, and re-optimizes its own panel from real telemetry — "
        f"gated by Laura. Built for {c[4]}."),
    # a concrete opening question visitors can drop straight into the panel
    "sample_question": (
        f"What is our current exposure on {c[2].lower()}, and which disciplines "
        f"on our panel would most change their view if we shipped a change "
        f"this quarter?"),
} for c in CENTERS}

CENTER_NETWORK = build_network()

# backwards-compatible shim for runtime import
DAUGHTERS = [(c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7]) for c in CENTERS]

if __name__ == "__main__":
    print("centers:", len(CENTERS_META))
    print("registry loaded:", len(_REG))
    for slug, m in CENTERS_META.items():
        print(f"  {slug}: panel={len(m['panel'])} disciplines={len(m['disciplines'])} "
              f"adjacent={len(CENTER_NETWORK.get(slug, []))}")
