"""Agent layer.

Each function corresponds to a step in the pipeline. They always produce a
correct result by reading the precomputed fixtures, and may optionally call
Gemini to generate a small "live" flourish (e.g. a one-paragraph executive summary)
when a GEMINI_API_KEY is set and DEMO_OFFLINE_MODE != 1.

This means: the demo runs flawlessly without an API key, and gets a touch of
real LLM output when one is present.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from rfx_assistant import data_loader as dl
from rfx_assistant import doc_writer
from rfx_assistant.paths import RUNS, OUTPUTS

# ----------------- run trace -----------------

class RunTrace:
    """Lightweight per-run tracer — appends events to a JSON file in data/runs/."""

    def __init__(self, name: str):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = RUNS / f"{ts}_{name}.json"
        self.events: list[dict] = []
        self.start = time.time()

    def event(self, kind: str, payload: dict):
        self.events.append({
            "t": round(time.time() - self.start, 3),
            "kind": kind,
            **payload,
        })
        self.flush()

    def flush(self):
        self.path.write_text(json.dumps({
            "started_at": datetime.now().isoformat(),
            "events": self.events,
        }, indent=2), encoding="utf-8")


# ----------------- model client (optional) -----------------

def _gemini_available() -> bool:
    if os.getenv("DEMO_OFFLINE_MODE", "1") == "1":
        return False
    return bool(os.getenv("GEMINI_API_KEY"))


def _maybe_call_gemini(prompt: str, model: str | None = None) -> str | None:
    """Best-effort live Gemini call via REST API. Returns None on any failure — caller falls back to precomputed."""
    if not _gemini_available():
        return None
    try:
        import requests
        api_key = os.getenv("GEMINI_API_KEY")
        model_name = model or os.getenv("GEMINI_MODEL_PRIMARY", "gemini-2.0-flash")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models"
            f"/{model_name}:generateContent"
        )
        resp = requests.post(
            url,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


# ----------------- step functions -----------------

ProgressCB = Callable[[float, str], None]


def _step(progress: ProgressCB | None, pct: float, message: str):
    if progress:
        progress(pct, message)


def generate_rfp(progress: ProgressCB | None = None, simulate_seconds: float = 4.0) -> dict:
    trace = RunTrace("rfp_generator")
    trace.event("agent_start", {"agent": "RFx Generator"})

    library = dl.sourcing_library()
    framework = dl.scoring_framework()
    strategy = dl.category_strategy()
    trace.event("tool_call", {"tool": "load_category_strategy", "result": "12 sections, 1,520 words"})
    _step(progress, 0.10, "Loaded category strategy (Data Centre Cooling, IT-INF-DC-COOL-2026)")
    time.sleep(simulate_seconds * 0.10)

    trace.event("tool_call", {"tool": "load_sourcing_library", "result": f"{len(library)} categories loaded"})
    _step(progress, 0.25, "Loaded Centrica Sourcing Library — 3 categories")
    time.sleep(simulate_seconds * 0.10)

    _step(progress, 0.40, "gemini-2.0-flash synthesising RFP introduction…")
    time.sleep(simulate_seconds * 0.20)
    trace.event("llm_call", {"model": "gemini-2.0-flash", "prompt_tokens": 1820, "completion_tokens": 642})

    _step(progress, 0.65, "Rendering RFP body — 9 sections, 8 mandatory requirements, 26 questions")
    time.sleep(simulate_seconds * 0.20)
    rfp_path = doc_writer.render_rfp(strategy, library, scoring_framework=framework)
    trace.event("artefact_written", {"path": str(rfp_path)})
    _step(progress, 0.80, f"RFP saved → {rfp_path.name}")

    template_paths = []
    cooling_lib = library["data_centre_cooling"]
    for sec in cooling_lib["sections"]:
        p = doc_writer.render_response_template(sec["id"], sec["title"], sec["questions"])
        template_paths.append(p)
        trace.event("artefact_written", {"path": str(p)})

    _step(progress, 0.95, f"{len(template_paths)} response templates written")
    time.sleep(simulate_seconds * 0.10)

    summary = _maybe_call_gemini(
        "In one paragraph (max 70 words), summarise the strategic intent of Centrica's "
        "data centre cooling RFP IT-INF-DC-COOL-2026. Focus on Tier III+ resilience, "
        "PUE ≤ 1.25, and net-zero alignment. Be concrete, not corporate."
    ) or (
        "Centrica is consolidating its smart-meter data ingestion into four regional Tier III+ edge "
        "data centres. This RFP secures cooling that hits PUE ≤ 1.25 at full IT load, runs ≥ 4,200 hours "
        "of free cooling per year, and aligns to a net zero 2045 group target. Award is by regional "
        "cluster — no single supplier takes all three."
    )
    trace.event("agent_end", {"summary_words": len(summary.split())})

    _step(progress, 1.0, "Done — RFP ready for issue via SAP Ariba Sourcing")

    return {
        "rfp_path": rfp_path,
        "template_paths": template_paths,
        "summary": summary,
        "trace_path": trace.path,
    }


def ingest_bids(progress: ProgressCB | None = None, simulate_seconds: float = 5.0) -> dict:
    trace = RunTrace("bid_ingestor")
    trace.event("agent_start", {"agent": "Bid Ingestor"})
    extractions = dl.bid_extractions()
    files = dl.bid_files()

    _step(progress, 0.05, f"Located {len(files)} bid files in fixtures/bids/")
    time.sleep(simulate_seconds * 0.05)

    parsed = []
    for i, e in enumerate(extractions):
        pct = 0.05 + (i + 1) / len(extractions) * 0.85
        fmt = e["format"]
        sup = e["supplier_name"]
        parser = {"PDF": "pypdf", "Excel": "openpyxl", "Word": "python-docx"}[fmt]
        _step(progress, pct - 0.10, f"Routing {sup} bid → {parser} parser ({fmt})")
        time.sleep(simulate_seconds * 0.10)
        trace.event("tool_call", {"tool": "parse_bid", "supplier": sup, "format": fmt, "parser": parser})

        _step(progress, pct, f"gemini-2.0-flash-lite normalising {sup} into common schema")
        time.sleep(simulate_seconds * 0.15)
        trace.event("llm_call", {"model": "gemini-2.0-flash-lite", "supplier": sup, "prompt_tokens": 4200, "completion_tokens": 980})
        parsed.append(e)

    _step(progress, 1.0, f"All {len(parsed)} bids normalised. Confidence: high · high · medium")
    trace.event("agent_end", {"bids_parsed": len(parsed)})
    return {"parsed": parsed, "trace_path": trace.path}


def score_bids(progress: ProgressCB | None = None, simulate_seconds: float = 6.0) -> dict:
    trace = RunTrace("scorer")
    trace.event("agent_start", {"agent": "Scorer"})
    framework = dl.scoring_framework()
    s = dl.scores()

    pillar_count = len(set(c["pillar"] for c in framework["criteria"]))
    _step(progress, 0.10, f"Loaded scoring framework — 9 criteria, {pillar_count} pillars")
    time.sleep(simulate_seconds * 0.10)

    suppliers = dl.suppliers()
    for i, sup in enumerate(suppliers):
        pct = 0.10 + (i + 1) / len(suppliers) * 0.80
        _step(progress, pct - 0.12, f"gemini-2.0-flash scoring {sup['name']} across 9 criteria with rationale + confidence")
        time.sleep(simulate_seconds * 0.20)
        trace.event("llm_call", {"model": "gemini-2.0-flash", "supplier": sup["name"], "prompt_tokens": 5400, "completion_tokens": 1820})

    _step(progress, 1.0, "All bids scored. Awaiting SME panel review on Technical & Sustainability pillars.")
    trace.event("agent_end", {})
    return {"scores": s, "framework": framework, "trace_path": trace.path}


def rank_shortlist(progress: ProgressCB | None = None, simulate_seconds: float = 3.0) -> dict:
    trace = RunTrace("recommender")
    trace.event("agent_start", {"agent": "Recommender"})
    shortlist = dl.shortlist()

    _step(progress, 0.30, "Applying weighted scores per cluster scope")
    time.sleep(simulate_seconds * 0.30)
    trace.event("llm_call", {"model": "gemini-2.0-flash", "prompt_tokens": 3100, "completion_tokens": 1240})

    _step(progress, 0.70, "Generating ranked shortlist with rationale and watch flags")
    time.sleep(simulate_seconds * 0.30)

    _step(progress, 0.95, "Consolidating contract deviation register")
    time.sleep(simulate_seconds * 0.20)

    _step(progress, 1.0, "Shortlist ready for Procurement Council on 28 July 2026")
    trace.event("agent_end", {})
    return {"shortlist": shortlist, "trace_path": trace.path}


def emit_audit_report(progress: ProgressCB | None = None, simulate_seconds: float = 3.0) -> dict:
    trace = RunTrace("audit_reporter")
    trace.event("agent_start", {"agent": "Audit Reporter"})
    state = dl.shortlist()

    _step(progress, 0.30, "Composing decision summary, ranked shortlist, deviations, audit metadata")
    time.sleep(simulate_seconds * 0.30)

    _step(progress, 0.70, "Rendering Word + JSON, Centrica branded")
    time.sleep(simulate_seconds * 0.30)
    word_path, json_path = doc_writer.render_audit_report(state)
    trace.event("artefact_written", {"path": str(word_path)})
    trace.event("artefact_written", {"path": str(json_path)})

    _step(progress, 1.0, "Audit report written. JSON ready for Ariba write-back.")
    trace.event("agent_end", {})
    return {"word_path": word_path, "json_path": json_path, "trace_path": trace.path}


def latest_trace_files(limit: int = 12) -> list[Path]:
    runs = sorted(RUNS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[:limit]


# --------------------------------------------------------------------------
# Interactive spec builder — always tries Gemini if key is present,
# regardless of DEMO_OFFLINE_MODE (which only gates pipeline simulations).
# --------------------------------------------------------------------------

def _call_gemini_direct(prompt: str) -> str | None:
    """Gemini REST call that bypasses DEMO_OFFLINE_MODE. Returns None on any failure."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import requests
        model_name = os.getenv("GEMINI_MODEL_PRIMARY", "gemini-2.0-flash")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models"
            f"/{model_name}:generateContent"
        )
        resp = requests.post(
            url,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=45,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


def generate_spec_from_conversation(messages: list[dict]) -> dict:
    """
    Build a procurement spec table from a chatbot conversation.
    Calls Gemini directly (ignores DEMO_OFFLINE_MODE); falls back to
    keyword-matched demo fixtures if no key or API failure.

    messages: list of {"role": "user"|"assistant", "content": str}
    Returns: {"category": str, "summary": str, "requirements": list[dict]}
    """
    user_text = "\n".join(
        m["content"] for m in messages if m["role"] == "user"
    )

    prompt = (
        "You are an expert procurement advisor. "
        "Based on this procurement conversation, generate a technical specification table.\n\n"
        "CONVERSATION (user messages only):\n"
        f"{user_text}\n\n"
        "Return ONLY valid JSON — no markdown fences, no explanation — with this exact structure:\n"
        '{\n'
        '  "category": "Short spend category name (e.g. Battery Energy Storage Systems)",\n'
        '  "summary": "1-2 sentence summary of what is being procured and why",\n'
        '  "requirements": [\n'
        '    {\n'
        '      "id": "REQ-001",\n'
        '      "section": "Technical",\n'
        '      "title": "Short requirement name",\n'
        '      "description": "Detailed description with specific measurable acceptance criteria.",\n'
        '      "priority": "Must",\n'
        '      "owner": "business",\n'
        '      "status": "Draft",\n'
        '      "comments": ""\n'
        '    }\n'
        '  ]\n'
        "}\n\n"
        "Rules:\n"
        "- Generate 10-14 requirements tailored to this specific spend category.\n"
        "- section must be one of: Technical, Commercial, Legal, Operational, ESG.\n"
        "- priority must be one of: Must, Should, Could.\n"
        "- owner: 'business' for domain/technical sign-off; 'procurement' for commercial/legal.\n"
        "- Requirements must be specific and measurable, not generic boilerplate.\n"
        "- Cover all relevant sections for the category (not just Technical)."
    )

    raw = _call_gemini_direct(prompt)
    if raw:
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(lines[1:-1])
            return json.loads(clean.strip())
        except Exception:
            pass

    return _fallback_spec(user_text)


def _fallback_spec(user_text: str) -> dict:
    t = user_text.lower()
    if any(k in t for k in ["batter", "bess", "energy storage", "grid storage", "lithium"]):
        return _SPEC_BESS
    if any(k in t for k in ["software", "saas", "cloud", "licence", "license", "platform", "application"]):
        return _SPEC_SOFTWARE
    if any(k in t for k in ["cool", "hvac", "chiller", "data centre", "datacenter", "data center"]):
        return _SPEC_COOLING
    if any(k in t for k in ["consult", "advisory", "professional service", "managed service"]):
        return _SPEC_SERVICES
    return _SPEC_GENERIC


_SPEC_BESS: dict = {
    "category": "Battery Energy Storage Systems (BESS)",
    "summary": "Procurement of utility-scale battery energy storage systems including supply, installation, commissioning, and long-term O&M.",
    "requirements": [
        {"id": "REQ-001", "section": "Technical", "title": "Usable Energy Capacity", "description": "Minimum 10 MWh usable capacity per site at end-of-warranty, demonstrated via factory acceptance test at 100% rated capacity.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-002", "section": "Technical", "title": "Round-Trip Efficiency", "description": "AC-AC round-trip efficiency >= 88% at rated power, 20 degC ambient, per IEC 62619.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-003", "section": "Technical", "title": "Cycle Life", "description": "Min 4,000 full cycles at 80% DoD before capacity falls below 80% of rated. Degradation curve with supporting data required.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-004", "section": "Technical", "title": "Response Time", "description": "Full power delivery within 200ms of dispatch signal for both frequency response and manual dispatch modes.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-005", "section": "Technical", "title": "Battery Management System", "description": "Cell-level monitoring, thermal management, SoC/SoH reporting, and open API (MODBUS TCP / IEC 61850) for SCADA integration.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-006", "section": "Technical", "title": "Fire Safety & Containment", "description": "Compliant with NFPA 855 and BS EN IEC 62933-5-2. Early warning detection, suppression, and explosion-relief venting in each enclosure.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-007", "section": "Technical", "title": "Grid Connection", "description": "Compliance with National Grid ESO Grid Code, ER G99, and DNO requirements including reactive power capability +/-0.95 pf.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-008", "section": "Commercial", "title": "Total Cost of Ownership", "description": "Itemised CAPEX and 10-year OPEX (O&M, insurance, spares, end-of-life). TCO is primary commercial evaluation criterion.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-009", "section": "Commercial", "title": "Warranty & Performance Guarantee", "description": "10-year manufacturer warranty on capacity, efficiency, and safety. Liquidated damages for capacity below 80% within warranty period.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-010", "section": "Legal", "title": "Product Liability Insurance", "description": "Minimum 20M GBP product liability and professional indemnity cover for design life of the installation.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-011", "section": "Legal", "title": "UK REACH & RoHS Compliance", "description": "All materials comply with UK REACH (SR 2020/1577) and RoHS 2. Substance declarations for battery cells required.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-012", "section": "ESG", "title": "End-of-Life Battery Recycling", "description": "Certified recycling plan achieving >= 95% material recovery by weight, aligned with UK Battery Regulations 2009.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-013", "section": "ESG", "title": "Supply Chain Carbon Footprint", "description": "Scope 1, 2, and 3 emissions disclosure for delivered system. Reduction roadmap aligned with SBTi or equivalent.", "priority": "Should", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-014", "section": "Operational", "title": "Commissioning & Training", "description": "FAT and SAT required. Minimum 3-day on-site operator training for client personnel. Grid commissioning sign-off by DNO.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
    ],
}

_SPEC_SOFTWARE: dict = {
    "category": "Enterprise Software / SaaS Platform",
    "summary": "Procurement of a cloud-hosted enterprise software platform including licences, implementation, integration, and ongoing support.",
    "requirements": [
        {"id": "REQ-001", "section": "Technical", "title": "Functional Coverage", "description": "Platform must satisfy all capabilities in the functional requirements schedule (Appendix A). Supplier provides capability mapping: Full / Partial / Not available.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-002", "section": "Technical", "title": "API & Integration", "description": "RESTful API with OpenAPI 3.0 docs. SAML 2.0 / OAuth 2.0 SSO with Azure AD. Integration connectors for SAP S/4HANA and Microsoft 365 required.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-003", "section": "Technical", "title": "Performance & Scalability", "description": "Support 5,000 concurrent users. Page load < 3s at P95 under peak. Auto-scaling demonstrated via load test results submitted at bid.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-004", "section": "Technical", "title": "Accessibility (WCAG 2.1 AA)", "description": "All end-user interfaces meet WCAG 2.1 AA. VPAT or equivalent conformance statement required.", "priority": "Should", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-005", "section": "Legal", "title": "ISO 27001 & Security", "description": "Current ISO 27001 certification in-scope for the SaaS platform. Completed Centrica Supplier Security Questionnaire. Annual penetration test report.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-006", "section": "Legal", "title": "UK GDPR & Data Residency", "description": "DPA compliant with UK GDPR. Data to remain in UK/EEA. Right to erasure supported. No personal data used for AI model training without written consent.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-007", "section": "Legal", "title": "IP Ownership", "description": "All custom developments, configurations, and client data are sole IP of the buyer. No licence retained by supplier post-termination.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-008", "section": "Commercial", "title": "Licence & Pricing Model", "description": "Named-user or consumption-based pricing on minimum 3-year term. Year-on-year fee schedule; annual increases capped at CPI + 2%.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-009", "section": "Commercial", "title": "SLA & Uptime", "description": "99.9% monthly uptime. P1 incident: ack within 15 min, resolved within 4 hours. Credits: 10% of monthly fee per 0.1% shortfall.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-010", "section": "Commercial", "title": "Exit & Data Portability", "description": "Full data export in open format (JSON/CSV/XML) within 30 days of termination. 6-month transition support period included.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-011", "section": "Operational", "title": "Implementation Timeline", "description": "Go-live within 90 days of contract signature. Dedicated implementation consultant and named PM throughout.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-012", "section": "Operational", "title": "Training & Change Management", "description": "Role-based training for end users, admins, and super users. Min 40-hour live training plus online self-service materials.", "priority": "Should", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-013", "section": "ESG", "title": "Carbon Neutral Hosting", "description": "Cloud hosting powered by 100% renewable energy or equivalent offsets. Annual carbon footprint report for client instance.", "priority": "Should", "owner": "procurement", "status": "Draft", "comments": ""},
    ],
}

_SPEC_COOLING: dict = {
    "category": "Data Centre Cooling Systems",
    "summary": "Procurement of high-efficiency cooling for Tier III+ data centres, targeting PUE <= 1.25 and net-zero alignment.",
    "requirements": [
        {"id": "REQ-001", "section": "Technical", "title": "Cooling Capacity", "description": "Min 2 MW IT load cooling per cluster with N+1 redundancy. Demonstrated via thermal load test at 100% design IT load.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-002", "section": "Technical", "title": "PUE Target", "description": "Annualised PUE <= 1.25 at 100% IT load across all clusters. Measured monthly via DCIM integration.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-003", "section": "Technical", "title": "Free Cooling Hours", "description": "Min 4,200 free cooling hours per year per cluster using ambient air or adiabatic pre-cooling.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-004", "section": "Technical", "title": "Refrigerant Compliance", "description": "GWP <= 675. Compliant with F-Gas Regulation as retained in UK law. Transition roadmap to natural refrigerants by 2030.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-005", "section": "Technical", "title": "Redundancy & Resilience", "description": "N+1 active cooling redundancy. Automatic failover within 30 seconds. Concurrent maintainability for all primary components.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-006", "section": "Technical", "title": "DCIM Integration", "description": "MODBUS TCP / BACnet / SNMP integration with DCIM. Real-time telemetry: temperature, humidity, power draw, PUE at rack level.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-007", "section": "Commercial", "title": "Total Cost of Ownership", "description": "Itemised CAPEX and 10-year OPEX (energy at GBP 0.12/kWh baseline, maintenance, refresh). Used as primary commercial criterion.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-008", "section": "Commercial", "title": "Service & Maintenance SLA", "description": "24/7 remote monitoring, 4-hour on-site P1 response. Preventive maintenance with 48-hour advance notice. Spares within 50 miles.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-009", "section": "Legal", "title": "Liability & Insurance", "description": "Min GBP 10M employers liability, GBP 10M public liability, GBP 5M product liability. Professional indemnity for 6 years post-completion.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-010", "section": "Legal", "title": "Certifications", "description": "Compliance with BS EN 15251, ASHRAE 90.4, UK Building Regulations Part L. F-Gas Category I certified installers.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-011", "section": "ESG", "title": "Net Zero Alignment", "description": "SBTi-aligned or equivalent net-zero pathway. Scope 1 and 2 emissions from this contract disclosed and offset annually.", "priority": "Should", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-012", "section": "Operational", "title": "Commissioning & FAT/SAT", "description": "Full factory and site acceptance tests. Commissioning plan 4 weeks before installation. Client sign-off on FAT/SAT reports.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
    ],
}

_SPEC_SERVICES: dict = {
    "category": "Professional / Managed Services",
    "summary": "Procurement of specialist advisory or managed services with defined deliverables, governance, and performance management.",
    "requirements": [
        {"id": "REQ-001", "section": "Technical", "title": "Statement of Work", "description": "Detailed SoW covering all deliverables, exclusions, dependencies, and assumptions. To be agreed before contract signature.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-002", "section": "Technical", "title": "Team Qualifications", "description": "Named key personnel with verified qualifications confirmed at award. No substitution without written client consent within first 6 months.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-003", "section": "Technical", "title": "Methodology & QA", "description": "Documented delivery methodology, QA checkpoints, and review gates. All outputs subject to client approval before next phase.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-004", "section": "Technical", "title": "Reporting & Governance", "description": "Weekly progress reports, monthly executive dashboards, quarterly business reviews. RAID log shared fortnightly. RAG status for all workstreams.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-005", "section": "Commercial", "title": "Fee Structure", "description": "Fixed-fee milestones preferred. T&M pre-approved and capped. Rate card locked for contract duration with CPI cap on annual uplift.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-006", "section": "Commercial", "title": "Payment Terms", "description": "Payment linked to milestone acceptance, not calendar dates. 45-day payment terms. Disputed invoices escalated within 5 business days.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-007", "section": "Commercial", "title": "Performance Incentives", "description": "Gainshare for demonstrable value above baseline KPIs. Service credits up to 15% of monthly fee for KPI failure.", "priority": "Should", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-008", "section": "Legal", "title": "IR35 & Employment Status", "description": "IR35 status confirmed for all resources at start and on any change. Client is not liable for undisclosed assessments.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-009", "section": "Legal", "title": "Confidentiality & NDA", "description": "All personnel sign client NDA. UK GDPR compliant data handling. No client data used for AI model training without explicit written consent.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-010", "section": "Legal", "title": "IP Ownership", "description": "All deliverables, code, reports, and frameworks created under this contract are sole IP of the client. Supplier retains no licence post-termination.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-011", "section": "ESG", "title": "Supplier ESG Commitments", "description": "Completed ESG assessment. Modern Slavery Act statement. Living Wage employer accreditation preferred.", "priority": "Should", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-012", "section": "Operational", "title": "Knowledge Transfer", "description": "Structured knowledge transfer at contract end. All documentation in editable formats. Client team shadows key activities for minimum 4 weeks pre-close.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
    ],
}

_SPEC_GENERIC: dict = {
    "category": "General Procurement",
    "summary": "Procurement of goods or services covering technical, commercial, legal, operational, and ESG dimensions.",
    "requirements": [
        {"id": "REQ-001", "section": "Technical", "title": "Core Specification Compliance", "description": "Full compliance with technical specification in tender documents. Deviations clearly identified and qualified in bid.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-002", "section": "Technical", "title": "Quality Standards", "description": "Compliance with applicable ISO standards and UK regulations. ISO 9001 or equivalent QMS and quality plan required.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-003", "section": "Technical", "title": "Delivery & Lead Times", "description": "Delivery schedule confirmed at bid. Lead times meet operational requirements. Penalties apply for agreed-date delays.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-004", "section": "Commercial", "title": "Pricing & Cost Transparency", "description": "Fully itemised pricing. Price held firm 12 months from award. Year 2+ increases capped at CPI.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-005", "section": "Commercial", "title": "Warranty & Aftercare", "description": "Min 12-month warranty on defects in materials and workmanship. Spares availability committed for 5 years post-delivery.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-006", "section": "Commercial", "title": "Financial Stability", "description": "Last 3 years audited accounts. Min BBB- credit rating (S&P) or equivalent. Parent guarantee may be required for SMEs.", "priority": "Should", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-007", "section": "Legal", "title": "Insurance Requirements", "description": "Public liability min GBP 5M. Employers liability GBP 10M. Professional indemnity GBP 2M (if applicable). Annual evidence required.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-008", "section": "Legal", "title": "Regulatory Compliance", "description": "Compliance with H&S at Work Act 1974, Modern Slavery Act 2015, and UK GDPR where personal data is processed.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-009", "section": "ESG", "title": "Environmental Management", "description": "ISO 14001 or equivalent EMS. Carbon footprint data for this contract; year-on-year reduction commitment.", "priority": "Should", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-010", "section": "ESG", "title": "Social Value", "description": "Local employment, apprenticeships, or supply chain diversity aligned with client Social Value Charter.", "priority": "Could", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-011", "section": "Operational", "title": "Account Management", "description": "Named account manager and escalation contact. Monthly reviews for contracts > GBP 500k pa. Direct access to delivery team.", "priority": "Should", "owner": "business", "status": "Draft", "comments": ""},
    ],
}
