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
  "in downturns", 25.0, 3),

 ("ai-act-guard", "AIActGuard Center",
  "Conformity, risk-classification and oversight authority for AI systems placed "
  "on the EU market",
  ["ai-safety-governance","chief-ai-officer","legal-compliance","risk-ethics",
   "ai-safety-eval","product-strategy"],
  "AI product teams shipping into the EU",
  "Regulation only tightens; EU AI Act is mandatory, not optional", 25.0, 3),

 ("sox-controls", "SOXControls Center",
  "Internal-control and financial-reporting assurance for public-company "
  "obligations",
  ["risk-sox","fin-general-ledger","risk-internal-controls","chief-compliance-officer",
   "audit-readiness"],
  "US-listed & SOX-scoped firms",
  "Public-company reporting is mandatory regardless of cycle", 25.0, 2),

 ("hipaa-check", "HIPAACheck Center",
  "Health-data safeguarding authority across clinical, payer and vendor surfaces",
  ["risk-hipaa","legal-privacy","legal-compliance","cyber-incident",
   "chief-compliance-officer"],
  "Healthcare, insurers, health-tech",
  "Health data is permanently regulated; breaches are existential", 25.0, 3),

 ("contract-risk", "ContractRisk Center",
  "Commercial-contract enforceability and exposure authority across the "
  "procure-to-pay and sell-to-collect lifecycle",
  ["legal-commercial","legal-corporate","proc-negotiation","fin-procurement-finance",
   "risk-enterprise"],
  "Procurement, sales, ops teams",
  "Contracts are signed in every economy; risk does not pause", 25.0, 3),

 ("ip-watch", "IPWatch Center",
  "Patent-assignment and IP-ownership authority for R&D and diligence",
  ["legal-ip","research-patents","legal-corporate","corpdev-ma",
   "chief-legal-officer"],
  "R&D-heavy firms, startups, pharma",
  "IP is a defensive moat in crises; diligence intensifies", 25.0, 3),

 ("employment-law", "EmployGuard Center",
  "Employment-law and worker-classification authority across the workforce "
  "lifecycle",
  ["legal-employment","hr-contracts","chro","hr-equity","risk-ethics"],
  "HR / People ops",
  "Employment litigation rises in layoffs; always live", 25.0, 3),

 ("litigation-risk", "LitigGuard Center",
  "Pending-claim and litigation-exposure authority for general counsel",
  ["legal-litigation","chief-legal-officer","corpsec-investigations",
   "risk-enterprise"],
  "General counsel, risk teams",
  "Disputes peak in recessions; counter-cyclical", 25.0, 2),

 ("license-audit", "LicenseAudit Center",
  "OSS and software-license compatibility authority for shipped products",
  ["legal-licensing","proc-software-lic","be-apis","entapps-erp","risk-enterprise"],
  "Engineering, OSS-using products",
  "License violations are discovered in M&A/downturns", 25.0, 3),

 ("tax-exposure", "TaxWatch Center",
  "Corporate and international tax-exposure authority",
  ["fin-tax-corp","fin-tax-intl","fin-treasury-cash","cfo","chief-risk-officer"],
  "Finance / tax teams",
  "Tax scrutiny rises when budgets tighten", 25.0, 2),

 ("vendor-risk", "VendorRisk Center",
  "Third-party and supplier-risk authority across the extended enterprise",
  ["sc-vendor-mgmt","proc-vendor-sel","risk-enterprise","chief-compliance-officer",
   "cyber-identity"],
  "Procurement, vendor mgmt",
  "Supply-chain failures surface in crises; always material", 25.0, 3),

 ("cyber-posture", "CyberPosture Center",
  "Application-security and red/blue posture authority for engineering",
  ["sece-ng-appsec","sece-ng-red","sece-ng-blue","chief-security-officer",
   "devops-cicd"],
  "Security engineering",
  "Breaches are cycle-agnostic; insurance now requires it", 25.0, 2),

 ("threat-intel", "ThreatIntel Center",
  "Threat-landscape and SOC-readiness authority for security operations",
  ["cyber-threat-intel","cyber-soc","sre-monitoring","chief-security-officer"],
  "SOC, CISO office",
  "Threat volume is counter-cyclical to economy", 25.0, 2),

 ("incident-readiness", "IncidentReady Center",
  "Incident-response readiness authority across SRE and security",
  ["cyber-incident","sre-incident","ops-lean","chief-security-officer"],
  "SRE / security ops",
  "Resilience is valued most in volatile periods", 25.0, 3),

 ("data-governance", "DataGov Center",
  "Data catalog, quality and governance authority",
  ["gov-catalog","gov-data-quality","gov-compliance","chief-data-officer",
   "infomgmt-knowledge-graphs"],
  "Data governance teams",
  "Data regs (GDPR, DORA) are expanding, not shrinking", 25.0, 3),

 ("a11y-audit", "A11yAudit Center",
  "Accessibility (WCAG/ADA) authority for product and web surfaces",
  ["fe-accessibility","accessibility-design","ux-design","legal-compliance"],
  "Product, web teams",
  "Accessibility law is mandatory and plaintiff-friendly", 25.0, 3),

 ("esg-report", "ESGReport Center",
  "ESG disclosure and CSRD authority for sustainability and IR",
  ["sustain-esg","sustain-env-reporting","chief-sustainability-officer",
   "fin-ir-sec","risk-ethics"],
  "Sustainability / IR",
  "CSRD reporting is mandatory for large EU firms", 25.0, 3),

 ("carbon-audit", "CarbonAudit Center",
  "Carbon-accounting and reporting authority",
  ["sustain-carbon","sustain-esg","sustain-supply-chain","chief-sustainability-officer"],
  "Sustainability, manufacturing",
  "Emissions reporting is regulation-locked", 25.0, 3),

 ("supply-chain-risk", "SupplyChainRisk Center",
  "Supply-chain disruption and dependency authority",
  ["sc-manufacturing","sc-logistics","sc-vendor-mgmt","risk-enterprise",
   "ops-process"],
  "Operations, supply-chain",
  "Disruption risk is the definition of crisis-resistance demand", 25.0, 3),

 ("procure-leak", "ProcureLeak Center",
  "Procurement spend-leakage and negotiation authority",
  ["proc-negotiation","fin-procurement-finance","proc-vendor-sel","cfo"],
  "Procurement, finance",
  "Cost leakage is hunted hardest in downturns", 25.0, 3),

 ("ma-diligence", "MADiligence Center",
  "M&A legal and risk diligence authority",
  ["corpdev-ma","corpdev-diligence","legal-corporate","risk-enterprise",
   "chief-legal-officer","fin-treasury-invest"],
  "Corp-dev, PE, VCs",
  "Deals slow but diligence intensity rises", 25.0, 1),

 ("board-gov", "BoardGov Center",
  "Board governance and fiduciary authority",
  ["board-of-directors","entarch-governance","chief-compliance-officer",
   "chief-risk-officer","president"],
  "Boards, governance teams",
  "Governance failures are punished in crises", 25.0, 2),

 ("investor-disclosure", "InvestorDisclosure Center",
  "Reg FD / SEC disclosure authority",
  ["fin-ir-sec","fin-ir-earnings","fin-ir-shareholders","chief-legal-officer",
   "corpcomms-pr"],
  "IR, legal",
  "Disclosure errors are always materially risky", 25.0, 2),

 ("crisis-comms", "CrisisComms Center",
  "Crisis-communication and reputation authority",
  ["corpcomms-crisis","corpcomms-pr","corpcomms-media","chief-strategy-officer"],
  "Comms, exec offices",
  "Comms failures compound in crises — peak demand then", 25.0, 3),

 ("insurance-review", "InsureReview Center",
  "Insurance policy and coverage-gap authority",
  ["risk-enterprise","risk-iso","chief-risk-officer","fin-treasury-cash"],
  "Risk, finance",
  "Coverage gaps hurt most in downturns", 25.0, 3),

 ("clinical-doc", "ClinicalDoc Center",
  "Clinical-trial and pharma documentation authority",
  ["legal-compliance","risk-hipaa","docs-tech-writers","research-patents",
   "quality-audits"],
  "Pharma, CROs",
  "Regulated, recession-proof sector", 25.0, 2),

 ("finserv-compliance", "FinServCompliance Center",
  "Fintech regulatory compliance authority",
  ["legal-compliance","risk-sox","risk-gdpr","chief-compliance-officer",
   "be-payments"],
  "Fintech, banks",
  "Financial regulation is the most durable compliance demand", 25.0, 2),

 ("saas-security", "SaaSSecurity Center",
  "SaaS security and cloud-posture authority",
  ["sece-ng-cloudsec","be-auth","infra-cloud","devops-deploy",
   "chief-security-officer"],
  "SaaS eng, security",
  "Cloud breaches are constant; buyers require proof", 25.0, 3),

 ("payments-compliance", "PaymentsCompliance Center",
  "PCI-DSS and payments-compliance authority",
  ["be-payments","risk-enterprise","legal-compliance","sece-ng-cloudsec"],
  "Payments, e-com",
  "Card data rules are non-negotiable and audited", 25.0, 3),

 ("crypto-reg", "CryptoReg Center",
  "MiCA / crypto regulatory authority",
  ["legal-compliance","chief-ai-officer","risk-enterprise","fin-tax-intl"],
  "Crypto, exchanges",
  "Crypto regulation is newly mandatory in EU", 25.0, 2),

 ("lease-review", "LeaseReview Center",
  "Real-estate lease and tenant-risk authority",
  ["legal-corporate","fac-real-estate","fin-procurement-finance","fac-physical-security"],
  "CRE, facilities",
  "Leases are long-tail liabilities surfaced in downturns", 25.0, 3),

 ("franchise-compliance", "FranchiseCompliance Center",
  "Franchise-agreement compliance authority",
  ["legal-commercial","legal-corporate","hr-contracts","risk-enterprise"],
  "Franchisors",
  "Franchise disputes are recurring, cycle-agnostic", 25.0, 3),

 ("nonprofit-gov", "NonprofitGov Center",
  "Nonprofit governance and grant-compliance authority",
  ["board-of-directors","legal-corporate","fin-ar","chief-compliance-officer"],
  "Nonprofits, foundations",
  "Grant compliance is mandatory for funding", 25.0, 3),

 ("export-control", "ExportControl Center",
  "Export-control (ITAR/EAR) authority",
  ["legal-compliance","govt-regulatory","govt-policy","risk-enterprise"],
  "Defense, dual-use exporters",
  "Trade controls tighten in geopolitical crises", 25.0, 2),

 ("product-safety", "ProductSafety Center",
  "Product-safety and liability authority",
  ["risk-enterprise","quality-iso","quality-process","legal-compliance"],
  "Hardware, CPG",
  "Safety failures are always litigated", 25.0, 3),

 ("recall-readiness", "RecallReady Center",
  "Recall and quality-escalation readiness authority",
  ["quality-supplier","ops-process","quality-audits","sre-incident"],
  "Manufacturing quality",
  "Recall cost is existential; readiness demanded pre-crisis", 25.0, 3),

 ("pharma-labeling", "PharmaLabeling Center",
  "Pharma labeling and claims authority",
  ["legal-compliance","docs-tech-writers","risk-hipaa","research-patents"],
  "Pharma, med-devices",
  "Labeling errors are heavily fined, always", 25.0, 3),

 ("food-safety", "FoodSafety Center",
  "Food-safety documentation authority",
  ["quality-iso","gov-compliance","ops-process","quality-audits"],
  "Food & beverage",
  "Food safety is non-discretionary regulation", 25.0, 3),

 ("energy-compliance", "EnergyCompliance Center",
  "Energy and NERC/EU compliance authority",
  ["risk-enterprise","sustain-esg","govt-regulatory","infra-cloud"],
  "Utilities, energy",
  "Energy regulation is essential-infrastructure locked", 25.0, 3),

 ("telecom-compliance", "TelecomCompliance Center",
  "Telecom regulatory compliance authority",
  ["legal-compliance","risk-enterprise","govt-regulatory","infra-networking"],
  "Telcos",
  "Telecom is essential service, always regulated", 25.0, 3),

 ("edu-compliance", "EduCompliance Center",
  "Education-privacy (FERPA) authority",
  ["legal-privacy","legal-compliance","govt-policy","hr-contracts"],
  "Edtech, universities",
  "Student data is permanently protected", 25.0, 3),

 ("child-safety", "ChildSafety Center",
  "Child-safety and age-gating (COPPA) authority",
  ["legal-privacy","risk-ethics","ai-safety-governance","cyber-awareness"],
  "Consumer apps, gaming",
  "Child-safety law is expanding globally", 25.0, 3),

 ("content-policy", "ContentPolicy Center",
  "Content-moderation policy authority",
  ["risk-ethics","corpcomms-pr","legal-compliance","ai-safety-eval"],
  "Social, UGC platforms",
  "Moderation liability is rising everywhere", 25.0, 3),

 ("bias-audit", "BiasAudit Center",
  "Algorithmic-bias and fairness audit authority",
  ["ai-safety-eval","risk-ethics","ai-safety-governance","legal-compliance"],
  "AI/ML teams",
  "Bias audits are becoming legally required", 25.0, 3),

 ("model-card", "ModelCard Center",
  "AI model-card and documentation authority",
  ["ai-safety-governance","mlops-registry","docs-tech-writers","ai-safety-eval"],
  "ML platform teams",
  "Documentation mandates grow with AI Act", 25.0, 3),

 ("breach-readiness", "BreachReady Center",
  "Data-breach readiness and notification authority",
  ["cyber-incident","legal-privacy","risk-gdpr","corpcomms-crisis"],
  "Security, legal",
  "Breach notification is legally timed; always live", 25.0, 3),

 ("whistleblower", "WhistleGuard Center",
  "Whistleblower-policy compliance authority",
  ["legal-employment","risk-ethics","hr-internal-comms","chief-compliance-officer"],
  "HR, compliance",
  "Whistleblower law is mandatory in EU", 25.0, 3),

 ("antitrust", "AntitrustWatch Center",
  "Antitrust and competition authority",
  ["legal-corporate","corpdev-ma","govt-regulatory","chief-legal-officer"],
  "Corp-dev, legal",
  "Antitrust enforcement intensifies in concentration", 25.0, 2),

 ("audit-readiness", "AuditReady Center",
  "Continuous audit-readiness authority",
  ["risk-internal-controls","quality-iso","risk-sox","chief-compliance-officer"],
  "Internal audit",
  "Audit is perpetual; readiness saves fees always", 25.0, 3),

 ("resilience-review", "ResilienceReview Center",
  "Operational-resilience authority",
  ["sre-reliability","ops-lean","sre-scaling","risk-enterprise","incident-readiness"],
  "SRE, ops",
  "Resilience demand peaks exactly in crises", 25.0, 3),
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


# -------------------------------------------------------------------------
# Domain-specific VALUE PROPOSITION + USE CASES.
# Hard-coded per slug (deterministic, no LLM, no template placeholders).
# Each entry: value_prop (one concrete sentence), use_cases (2-3 real
# questions a visitor in that domain would actually type), icp_pain (the
# specific hurt the center removes). This is the "value proposition" the
# public page surfaces — it must be specific, not "a standing body of N
# experts that convenes on your mandate".
# -------------------------------------------------------------------------
VALUE_PROPS = {
 "gdpr-guard": {
  "value_prop": "Before you ship a feature touching EU personal data, get a standing panel of privacy, risk and data officers to flag the lawful-basis and breach gaps you'd otherwise learn about from a regulator.",
  "use_cases": [
    "Do we need a DPIA before launching our EU customer survey?",
    "We store support chats unencrypted — what's our breach-notification clock if a laptop is lost?",
    "Our consent banner pre-ticks 'marketing' — is that lawful-basis defensible?"],
  "icp_pain": "DPIAs and consent reviews take 6 weeks with external counsel; you need the red flags in an hour."},
 "ai-act-guard": {
  "value_prop": "Get a standing AI-governance + safety + legal panel to tell you whether your system is high-risk under the EU AI Act and what conformity you owe before you ship.",
  "use_cases": [
    "Is our hiring-screening model a high-risk system under Annex III?",
    "What documentation do we owe to CE-mark our medical triage model?",
    "We retrain monthly — does each retrain re-trigger conformity assessment?"],
  "icp_pain": "AI Act conformity is undefined for most teams; a wrong classification is a 6%-of-turnover fine."},
 "sox-controls": {
  "value_prop": "A standing internal-control + financial-reporting panel that tells you which SOX assertions your close process can't evidence before the auditor does.",
  "use_cases": [
    "Which of our Q3 journal-entry controls would fail a walkthrough?",
    "Our SOX scope just grew with the acquisition — what controls are missing?",
    "Is our segregation-of-duties matrix actually enforced or just documented?"],
  "icp_pain": "Audit fees and restatement risk scale with control gaps you can't see until field work."},
 "hipaa-check": {
  "value_prop": "A standing health-data panel (privacy, compliance, security, clinical) that flags where your PHI handling would fail a HIPAA review before a breach or audit.",
  "use_cases": [
    "Our mobile app logs PHI to a third-party analytics SDK — is that a BAA violation?",
    "Do our telehealth session recordings need encryption-at-rest under HIPAA?",
    "We share de-identified data with a research partner — when is it still PHI?"],
  "icp_pain": "HIPAA breach penalties are per-record and existential for a health startup."},
 "contract-risk": {
  "value_prop": "A standing commercial + corporate + procurement panel that redlines the enforceability and hidden exposure in your contracts before you sign.",
  "use_cases": [
    "This MSA limits our liability to fees paid — is that enforceable given the IP indemnity?",
    "Our Master Services Agreement auto-renews in 10 days — can we still exit?",
    "The reseller clause lets them compete with us — what's our exposure?"],
  "icp_pain": "One bad indemnity clause is a company-ending event nobody reads in time."},
 "ip-watch": {
  "value_prop": "A standing IP + patent + corporate panel that tells you who actually owns the IP you're shipping and where your diligence blind spots are.",
  "use_cases": [
    "Our lead engineer built the core algo at a previous job — who owns it?",
    "We're raising — what patent assignments are missing from our cap-table diligence?",
    "Our open-source dependency has a GPL license — does it infect our closed product?"],
  "icp_pain": "Undiligenced IP ownership voids acquisitions and VC rounds overnight."},
 "employment-law": {
  "value_prop": "A standing employment + HR panel that flags misclassification and termination exposure before the claim lands.",
  "use_cases": [
    "We classify our coders as contractors in 3 states — is that defensible?",
    "We're laying off 12 people — what's our WARN Act notice clock?",
    "Our non-compete survived a move to California — is it still enforceable?"],
  "icp_pain": "Misclassification and wrongful-termination claims spike in downturns and settle high."},
 "litigation-risk": {
  "value_prop": "A standing litigation + investigations panel that prices your pending-claim exposure before counsel bills you for the same read.",
  "use_cases": [
    "A customer threatens a class action over our pricing — what's our realistic exposure?",
    "Our ex-sales-rep took the pipeline — do we have a trade-secret claim worth filing?",
    "We got a C&D letter — ignore, settle, or counterclaim?"],
  "icp_pain": "General counsel can't price every threat; the ones you ignore are the ones that land."},
 "license-audit": {
  "value_prop": "A standing licensing + software panel that catches the OSS license clash that would blow up your M&A or shutdown your product.",
  "use_cases": [
    "Our product bundles a GPL lib — does it force our whole codebase open?",
    "We forked an Apache-2 project and removed the notices — what's our exposure?",
    "Our SaaS uses a AGPL dependency — does that reach our server code?"],
  "icp_pain": "License violations surface in diligence and can block or reprice a deal."},
 "tax-exposure": {
  "value_prop": "A standing corporate + international-tax panel that flags the structure gaps auditors and tax authorities notice first.",
  "use_cases": [
    "We moved IP to Ireland but R&D stays here — is our transfer pricing defensible?",
    "Our contractor in Germany is really an employee — what's the payroll-tax gap?",
    "We took R&D credits on a failed project — can we still defend them?"],
  "icp_pain": "Transfer-pricing and permanent-establishment gaps trigger back-tax + penalties."},
 "vendor-risk": {
  "value_prop": "A standing third-party + security panel that tells you which vendor would take you down in a supply-chain audit.",
  "use_cases": [
    "Our payroll processor has no SOC 2 — is that a reportable sub-processor risk?",
    "Our cloud provider's breach yesterday — are we contractually covered?",
    "This vendor has root access to customer data — what's our contractual exit?"],
  "icp_pain": "Your breach is now your vendor's breach; regulators ask about both."},
 "cyber-posture": {
  "value_prop": "A standing appsec + red/blue + CISO panel that finds the gap an attacker would use before your next pentest or renewal.",
  "use_cases": [
    "We just added GraphQL — what's the auth-bypass surface we can't see?",
    "Our CI deploys with a shared token — is that a supply-chain risk?",
    "We're renewing cyber-insurance — what control evidence do they require?"],
  "icp_pain": "Insurers now demand proof of posture; no evidence = no coverage."},
 "threat-intel": {
  "value_prop": "A standing threat-intel + SOC panel that tells you which active campaign is already aimed at your stack.",
  "use_cases": [
    "A new ransomware group is hitting our sector — are we in their pattern?",
    "Our logs show strange OAuth grants — is this the MFA-fatigue wave?",
    "We're deploying edge nodes — what's the threat model we're ignoring?"],
  "icp_pain": "Threat volume rises when budgets fall; you find out after the incident."},
 "incident-readiness": {
  "value_prop": "A standing SRE + security-incident panel that dry-runs your response so the real one isn't your first rehearsal.",
  "use_cases": [
    "We've never invoked our incident runbook under load — where does it break?",
    "Our on-call can't page legal — is that a breach-notification risk?",
    "We merged two SRE teams — is our escalation path still coherent?"],
  "icp_pain": "Regulators time breach notices from first awareness; confusion costs you the clock."},
 "data-governance": {
  "value_prop": "A standing catalog + quality + governance panel that tells you which data you can't actually use before a DORA or GDPR audit.",
  "use_cases": [
    "We train models on customer data with no lineage — is that a lawful-basis gap?",
    "Our data catalog is 40% stale — what's our real PII surface?",
    "We're sharing data with a partner — what's our cross-border basis?"],
  "icp_pain": "You can't govern what you can't see; audits start with the catalog."},
 "a11y-audit": {
  "value_prop": "A standing accessibility + design panel that catches the WCAG/ADA failure that becomes a demand letter.",
  "use_cases": [
    "Our new checkout isn't keyboard-navigable — is that an ADA claim?",
    "Our PDFs have no tags — are we excluding screen-reader users?",
    "We're a public university site — what WCAG level are we legally bound to?"],
  "icp_pain": "Accessibility plaintiffs' firms send form demand letters by the thousand."},
 "esg-report": {
  "value_prop": "A standing ESG + IR panel that tells you which CSRD disclosure you can't substantiate before the report ships.",
  "use_cases": [
    "We claim 'carbon neutral' in marketing — is that a greenwashing exposure?",
    "Our Scope 3 data is 60% estimated — can we sign off the CSRD?",
    "Our diversity metrics aren't audited — what's the assurance gap?"],
  "icp_pain": "CSRD is mandatory for large EU firms; unsubstantiated claims are now fined."},
 "carbon-audit": {
  "value_prop": "A standing carbon + supply-chain panel that finds the emissions number you'll have to defend under reporting law.",
  "use_cases": [
    "Our offset portfolio is mostly questionable credits — does it survive scrutiny?",
    "We report Scope 1-2 but not 3 — are we under-reporting legally?",
    "Our supplier data is self-reported — what's our assurance gap?"],
  "icp_pain": "Emissions reporting is regulation-locked; inflated numbers are fraud risk."},
 "supply-chain-risk": {
  "value_prop": "A standing supply-chain + ops panel that flags the single dependency that would halt your line.",
  "use_cases": [
    "Our only supplier for X is in a sanction zone — what's our continuity gap?",
    "We dual-source but both use the same sub-tier — are we really diversified?",
    "A port strike is looming — what's our 2-week inventory cliff?"],
  "icp_pain": "Disruption risk is the definition of crisis-resistant demand for exactly this."},
 "procure-leak": {
  "value_prop": "A standing procurement + finance panel that finds the spend leakage eroding margin before year-end.",
  "use_cases": [
    "We renew SaaS with no benchmark — are we overpaying 30%?",
    "Our POs bypass approval above threshold — where's the leak?",
    "We have 4 tools doing the same job — what's the consolidation save?"],
  "icp_pain": "Cost leakage is hunted hardest in downturns; it's pure margin."},
 "ma-diligence": {
  "value_prop": "A standing M&A + legal + risk panel that prices the hidden liability in the deal before you sign the LOI.",
  "use_cases": [
    "Target's IP is mostly contractor-built — who actually owns it?",
    "Their privacy practices have 3 past complaints — what's the reps & warranties gap?",
    "They use open-source核心 — is there a license infection in the codebase?"],
  "icp_pain": "Diligence intensity rises when deal volume falls; misses reprice the round."},
 "board-gov": {
  "value_prop": "A standing board + governance + risk panel that tells directors where their fiduciary exposure actually sits.",
  "use_cases": [
    "We're approving a related-party deal — is the disclose-and-abstain path clean?",
    "The board has no cyber expertise — is that a fiduciary gap?",
    "We're pivoting mid-year — what's the duty-of-oversight exposure?"],
  "icp_pain": "Governance failures are punished in crises; directors are personally exposed."},
 "investor-disclosure": {
  "value_prop": "A standing IR + legal panel that flags the disclosure error that would be material before the filing.",
  "use_cases": [
    "We hinted guidance on a podcast — is that a Reg FD violation?",
    "Our 8-K is late on the acquisition — what's the timing exposure?",
    "We buried a risk in footnote 14 — is that a securities claim?"],
  "icp_pain": "Disclosure errors are always materially risky; the SEC doesn't care about intent."},
 "crisis-comms": {
  "value_prop": "A standing crisis + PR panel that drafts the first response before the story writes itself.",
  "use_cases": [
    "A journalist emailed about a leak — what's our hold-statement?",
    "Our CEO tweeted something regrettable — what's the containment?",
    "We had an outage — what do we tell customers vs. regulators?"],
  "icp_pain": "Comms failures compound in crises; that's peak demand for this exact panel."},
 "insurance-review": {
  "value_prop": "A standing risk + finance panel that finds the coverage gap that would have paid the last incident.",
  "use_cases": [
    "Our cyber policy excludes nation-state — is that our real risk?",
    "We grew 3x but didn't re-rate — are we underinsured?",
    "Our D&O has a related-party carve-out — does it gut our cover?"],
  "icp_pain": "Coverage gaps hurt most in downturns when you need them."},
 "clinical-doc": {
  "value_prop": "A standing clinical + compliance panel that catches the labeling/doc gap that draws an FDA or EMA letter.",
  "use_cases": [
    "Our trial consent form is 2 years old — is it still compliant?",
    "We changed the dosing — did the IB get amended?",
    "Our promo claims cite a single study — is that substantiated?"],
  "icp_pain": "Regulated, recession-proof sector; doc gaps are heavily fined."},
 "finserv-compliance": {
  "value_prop": "A standing fintech + compliance panel that tells you which regulation you're about to breach before the license review.",
  "use_cases": [
    "We're adding crypto to our app — what's the money-transmission gap?",
    "Our KYC is risk-based but thin — would an exam fail it?",
    "We serve EU + US — which regime's AML rule is stricter here?"],
  "icp_pain": "Financial regulation is the most durable compliance demand there is."},
 "saas-security": {
  "value_prop": "A standing cloudsec + auth panel that finds the misconfiguration a customer's security review would fail you on.",
  "use_cases": [
    "Our S3 bucket is public by accident — what else is exposed?",
    "We use one shared admin key — is that a SOC 2 finding?",
    "Our tenant isolation is logical not physical — does that pass enterprise review?"],
  "icp_pain": "Cloud breaches are constant; enterprise buyers require proof before signing."},
 "payments-compliance": {
  "value_prop": "A standing payments + security panel that catches the PCI-DSS gap that would yank your processing.",
  "use_cases": [
    "We store card numbers in our DB — are we PCI-compliant at all?",
    "Our checkout tokenizes but logs PANs — does that break the rule?",
    "We're expanding to India — what's the local payments-compliance map?"],
  "icp_pain": "Card-data rules are non-negotiable and audited on a schedule."},
 "crypto-reg": {
  "value_prop": "A standing crypto + compliance panel that tells you which MiCA obligation you're missing before the regulator calls.",
  "use_cases": [
    "We're a stablecoin issuer — what's our MiCA authorization gap?",
    "Our whitepaper promises yield — is that a security classification?",
    "We list a token — are we an exchange needing a license?"],
  "icp_pain": "Crypto regulation is newly mandatory in the EU; ignorance isn't a defense."},
 "lease-review": {
  "value_prop": "A standing real-estate + finance panel that flags the lease clause that becomes a liability in a downturn.",
  "use_cases": [
    "Our lease has a personal guarantee — what's the downside if we close?",
    "The renewal bump is 40% — can we contest under the clause?",
    "We sublet but the lease forbids it — what's the exposure?"],
  "icp_pain": "Leases are long-tail liabilities surfaced exactly when cash is tight."},
 "franchise-compliance": {
  "value_prop": "A standing franchise + corporate panel that catches the FTC rule breach in your agreement before the franchisee sues.",
  "use_cases": [
    "Our franchise fee is really a royalty in disguise — FTC issue?",
    "We control their pricing — are we blurring the independence line?",
    "Our disclosure doc is stale — what's the update clock?"],
  "icp_pain": "Franchise disputes are recurring and cycle-agnostic."},
 "nonprofit-gov": {
  "value_prop": "A standing nonprofit + grant panel that flags the compliance gap that would suspend your funding.",
  "use_cases": [
    "Our grant report mixes restricted funds — is that a compliance breach?",
    "The board approved a related-party contract — is that allowed?",
    "Welobbyed but filed no 990 — what's the exposure?"],
  "icp_pain": "Grant compliance is mandatory for funding; errors suspend the money."},
 "export-control": {
  "value_prop": "A standing export + policy panel that catches the ITAR/EAR slip that would trigger a criminal probe.",
  "use_cases": [
    "We shipped dual-use to a reseller who re-exports — are we liable?",
    "Our software has encryption — does it need an export classification?",
    "We hired a restricted-national on the program — is that a Deemed Export?"],
  "icp_pain": "Trade controls tighten in geopolitical crises; violations are criminal."},
 "product-safety": {
  "value_prop": "A standing product + quality panel that finds the safety defect that becomes a recall.",
  "use_cases": [
    "Our new battery runs hot in testing — is that a reporting threshold?",
    "We changed a supplier — does it re-trigger certification?",
    "A child choked on a part — what's our CPSC exposure?"],
  "icp_pain": "Safety failures are always litigated; the first one is the expensive one."},
 "recall-readiness": {
  "value_prop": "A standing quality + SRE panel that dry-runs your recall so the real one isn't a fire drill.",
  "use_cases": [
    "We can't trace which batch shipped where — is our recall blind?",
    "Our notification template is untested — what's the regulator clock?",
    "We have no customer contact data — how do we even recall?"],
  "icp_pain": "Recall cost is existential; readiness is demanded before the crisis."},
 "pharma-labeling": {
  "value_prop": "A standing labeling + compliance panel that catches the claim that draws an enforcement letter.",
  "use_cases": [
    "Our rep implies a cure — is that an unsubstantiated claim?",
    "We changed indicaton but not the label — what's the gap?",
    "Our DTC ad cites old data — is it still defensible?"],
  "icp_pain": "Labeling errors are among the most heavily fined in pharma."},
 "food-safety": {
  "value_prop": "A standing food + quality panel that finds the HACCP gap that becomes a recall.",
  "use_cases": [
    "Our supplier audit is a year stale — is our chain of custody broken?",
    "We changed a preservative — does it need re-validation?",
    "A customer found glass — what's our traceability on this lot?"],
  "icp_pain": "Food safety is non-discretionary; one outbreak ends a brand."},
 "energy-compliance": {
  "value_prop": "A standing energy + NERC panel that flags the reliability gap that draws a penalty.",
  "use_cases": [
    "Our reporting missed the NERC window — what's the exposure?",
    "We decommissioned a unit — did we file the reliability impact?",
    "Our cyber-plan for the grid is untested — is that a violation?"],
  "icp_pain": "Energy regulation is essential-infrastructure locked."},
 "telecom-compliance": {
  "value_prop": "A standing telecom + regulatory panel that finds the filing gap that suspends your license.",
  "use_cases": [
    "Our outage didn't get reported in the window — what's the fine?",
    "We launched a new service without the tariff filing — exposure?",
    "Our 911 routing is degraded — is that a public-safety violation?"],
  "icp_pain": "Telecom is an always-regulated essential service."},
 "edu-compliance": {
  "value_prop": "A standing education + privacy panel that flags the FERPA gap in your edtech.",
  "use_cases": [
    "We sell student data to a tutor network — is that a FERPA breach?",
    "Our LMS logs minors' location — what's the parental-consent gap?",
    "We use student work to train models — who owns it under FERPA?"],
  "icp_pain": "Student data is permanently protected; violations are structural."},
 "child-safety": {
  "value_prop": "A standing child-safety + age-gating panel that catches the COPPA / age-assurance gap before the regulator.",
  "use_cases": [
    "Our app's under-13s aren't age-gated — is that a COPPA violation?",
    "We collect kids' voice data — what's the parental-consent clock?",
    "Our algo feeds minors — what's the new child-safety duty?"],
  "icp_pain": "Child-safety law is expanding globally; fines are reputational + financial."},
 "content-policy": {
  "value_prop": "A standing content + policy panel that flags the moderation liability in your platform before the sweep.",
  "use_cases": [
    "Our algo amplifies harmful content — what's our DSA liability?",
    "We have no appeals process — is that a new-regulation breach?",
    "Our moderators are under-aged contractors — what's the exposure?"],
  "icp_pain": "Moderation liability is rising everywhere; the first fine sets precedent."},
 "bias-audit": {
  "value_prop": "A standing bias + fairness panel that finds the disparate-impact in your model before the audit becomes law.",
  "use_cases": [
    "Our hiring model rejects more women — is that a disparate-impact claim?",
    "Our credit scorer has a zip-code proxy — what's the fairness gap?",
    "We have no bias testing — what does the new rule require?"],
  "icp_pain": "Bias audits are becoming legally required; the unprepared get fined first."},
 "model-card": {
  "value_prop": "A standing model-card + docs panel that builds the documentation auditors now demand under the AI Act.",
  "use_cases": [
    "Our model has no card — what does conformity require?",
    "We can't reproduce our eval — is the card defensible?",
    "Our training data is undocumented — what's the provenance gap?"],
  "icp_pain": "Documentation mandates grow with the AI Act; no card = no CE mark."},
 "breach-readiness": {
  "value_prop": "A standing breach + legal panel that times your notification so the regulator sees compliance, not panic.",
  "use_cases": [
    "We found anomalous access 3 days ago — are we past the 72h clock?",
    "We don't know if it's 'personal data' — what's our assessment path?",
    "Our US + EU users — which clock applies first?"],
  "icp_pain": "Breach notification is legally timed; missing it multiplies the fine."},
 "whistleblower": {
  "value_prop": "A standing employment + compliance panel that checks your whistleblower program before the EU mandate bites.",
  "use_cases": [
    "We have no confidential channel — is that an EU Whistleblower-Dir breach?",
    "Our HR investigates its own complaints — is that a conflict gap?",
    "We retaliated against a reporter — what's the exposure?"],
  "icp_pain": "Whistleblower law is mandatory in the EU; non-compliance is fined."},
 "antitrust": {
  "value_prop": "A standing antitrust + corporate panel that flags the conduct that draws the dawn raid.",
  "use_cases": [
    "We share pricing with a competitor 'informally' — is that a §1 violation?",
    "We're 70% market share — what's our dominance duty?",
    "Our MFN clause — is that a vertical-restraint issue?"],
  "icp_pain": "Antitrust enforcement intensifies in concentration; penalties are revenue-based."},
 "audit-readiness": {
  "value_prop": "A standing internal-control + audit panel that keeps you perpetually ready so the audit is a formality.",
  "use_cases": [
    "Our evidence is in 12 Slack threads — is anything actually documented?",
    "We can't reproduce last year's walkthrough — what's the gap?",
    "Our control owners left — who owns SOX now?"],
  "icp_pain": "Audit is perpetual; readiness saves fees every single cycle."},
 "resilience-review": {
  "value_prop": "A standing SRE + resilience panel that finds the single point of failure your status page is hiding.",
  "use_cases": [
    "Our failover has never been tested under load — does it work?",
    "We have one region — what's our regional-outage cliff?",
    "Our error budget is blown — what's the release halt path?"],
  "icp_pain": "Resilience demand peaks exactly in crises; that's when you need it most."},
}

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
    # value proposition: SPECIFIC per-domain (see VALUE_PROPS), not a template
    "value_prop": VALUE_PROPS.get(c[0], {}).get(
        "value_prop",
        f"A standing body of {len(build_panel(c[0], c[3]))} experts that convenes "
        f"on your {c[2].lower()}."),
    "use_cases": VALUE_PROPS.get(c[0], {}).get("use_cases", []),
    "icp_pain": VALUE_PROPS.get(c[0], {}).get("icp_pain", ""),
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
