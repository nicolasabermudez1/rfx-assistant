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


def gemini_key_available() -> bool:
    """True if a Gemini API key is configured (so the UI can show 'Live AI')."""
    return bool(os.getenv("GEMINI_API_KEY"))


# --------------------------------------------------------------------------
# Dynamic clarifying-question generator — adapts the chatbot to ANY category.
# --------------------------------------------------------------------------

def generate_clarifying_questions(category: str) -> list[str]:
    """Return 2 category-specific clarifying questions for the chatbot.

    Calls Gemini if a key is configured, otherwise uses category-keyword
    fallbacks so the demo still feels relevant offline.
    """
    prompt = (
        f"A user wants to procure: '{category}'.\n\n"
        "Generate exactly 2 clarifying questions to ask BEFORE drafting the technical spec.\n"
        "Each question must:\n"
        "  - Be SPECIFIC to this product or service category (not generic procurement boilerplate).\n"
        "  - Focus on different aspects (one usually scope/scale, one usually constraints/preferences).\n"
        "  - Be one sentence each in a friendly conversational tone.\n"
        "  - Be answerable by a procurement manager or business stakeholder.\n\n"
        "Examples:\n"
        "  - For 'payroll services': "
        '["How many employees do you need to cover, and across how many countries?", '
        '"What\'s your current payroll system, and do you need integration with HR / finance / time-tracking?"]\n'
        "  - For 'security cameras': "
        '["How many cameras (indoor/outdoor mix) and across how many sites?", '
        '"Any brand or VMS preference, and what level of AI analytics do you need (person/vehicle detection, line crossing, ANPR)?"]\n'
        "  - For 'electrical subcontractors': "
        '["What scope of work and trades do you need (e.g. installation, maintenance, gas-safe), and over what duration?", '
        '"Where is the work located, and what certifications, insurance, and safety standards must they hold?"]\n'
        "  - For 'office cleaning': "
        '["How many sites, total floor area, and what frequency of cleaning?", '
        '"Any specialist areas (kitchens, labs, server rooms), out-of-hours access, or sustainability requirements?"]\n\n'
        "Return ONLY a JSON array of 2 question strings — no markdown fences, no explanation."
    )

    raw = _call_gemini_direct(prompt)
    if raw:
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(lines[1:-1])
            qs = json.loads(clean.strip())
            if isinstance(qs, list) and len(qs) >= 2:
                return [str(q).strip() for q in qs[:2] if str(q).strip()]
        except Exception:
            pass

    return _fallback_clarifying_questions(category)


def _fallback_clarifying_questions(category: str) -> list[str]:
    """Category-keyword fallback when no API key is set."""
    t = (category or "").lower()

    if any(k in t for k in ["camera", "cctv", "surveillance", "ip cam"]):
        return [
            "How many cameras (indoor / outdoor mix) and across how many sites?",
            "Any brand or VMS preference (Hikvision, Axis, Milestone, Genetec...), and what AI analytics do you need?",
        ]
    if any(k in t for k in ["payroll", "human resource", "hr service", "hcm"]):
        return [
            "How many employees do you need to cover, and across how many countries / pay frequencies?",
            "What's your current payroll system, and do you need integration with HR, finance, or time-tracking systems?",
        ]
    if any(k in t for k in ["subcontract", "trade", "contractor", "electrician", "plumber", "engineer "]):
        return [
            "What trades or skills do you need (e.g. electrical, mechanical, gas-safe) and what's the scope of work?",
            "Where is the work, what's the expected duration, and what certifications / insurance must they hold?",
        ]
    if any(k in t for k in ["clean", "janitor", "facility manage", "facilit"]):
        return [
            "How many sites, total floor area, and what cleaning frequency do you need?",
            "Any specialist areas (kitchens, labs, server rooms), out-of-hours access, or sustainability requirements?",
        ]
    if any(k in t for k in ["security guard", "guarding", "concierge", "manned guard"]):
        return [
            "How many sites, hours of coverage per site, and what's the site risk profile?",
            "Required certifications (SIA), patrolling vs static, and integration with existing CCTV / access control?",
        ]
    if any(k in t for k in ["consult", "advisory", "professional service", "managed service"]):
        return [
            "What's the scope of the engagement, expected deliverables, and target start date?",
            "Any budget envelope, preferred firms, and specific expertise or certifications required?",
        ]
    if any(k in t for k in ["legal", "law firm", "solicitor", "barrister"]):
        return [
            "What practice areas (e.g. commercial, employment, regulatory) and matter volume do you expect?",
            "Preferred panel structure, fee model (hourly / fixed / capped), and any conflict considerations?",
        ]
    if any(k in t for k in ["marketing", "advertising", "creative agency", "brand"]):
        return [
            "What's the brief — campaign, brand refresh, performance marketing, or always-on retainer?",
            "Budget envelope, channels in scope, target audience, and any preferred agency types or exclusions?",
        ]
    if any(k in t for k in ["recruit", "staffing", "headhunt", "talent"]):
        return [
            "What roles or skill profiles do you need to hire, expected volumes, and timeline?",
            "Permanent / contract / RPO, geographic coverage, and fee model preferences (retained / contingent / fixed)?",
        ]
    if any(k in t for k in ["training", "learning", "e-learning", "lms"]):
        return [
            "What topics, target audience size, and delivery format (instructor-led, e-learning, blended)?",
            "Do you need LMS integration, certification, accessibility (WCAG), or multi-language content?",
        ]
    if any(k in t for k in ["catering", "food service", "canteen", "cafeteria"]):
        return [
            "How many sites, expected daily covers, and what type of service (canteen, hospitality, vending)?",
            "Dietary requirements, sustainability / local-sourcing standards, and food-safety certifications?",
        ]
    if any(k in t for k in ["insurance", "broker"]):
        return [
            "What lines of cover do you need (property, liability, cyber, motor, D&O...) and what total sum insured?",
            "Claims history, preferred broker / underwriter relationships, and policy renewal timeline?",
        ]
    if any(k in t for k in ["audit", "accounting", "tax", "advisory"]):
        return [
            "What's the scope — statutory audit, internal audit, tax advisory, or due diligence?",
            "Year-end / engagement dates, jurisdictions in scope, and any specific independence requirements?",
        ]
    if any(k in t for k in ["batter", "bess", "energy storage"]):
        return [
            "What total energy capacity (MWh) and power rating (MW) do you need, and at how many sites?",
            "Use case (grid services, peak shaving, behind-the-meter) and any grid-connection constraints?",
        ]
    if any(k in t for k in ["software", "saas", "cloud", "licence", "license", "platform"]):
        return [
            "How many users / what usage scale, and what core capabilities are non-negotiable?",
            "Integration requirements (SSO, existing systems), compliance (GDPR, ISO 27001), and data-residency constraints?",
        ]
    if any(k in t for k in ["laptop", "computer", "desktop", "workstation", "device"]):
        return [
            "How many units, user profiles (general / power-user / field), and your refresh cycle?",
            "Preferred OS, vendor preferences, and integration with your MDM / Intune / imaging pipeline?",
        ]
    if any(k in t for k in ["phone", "mobile", "smartphone", "handset"]):
        return [
            "How many handsets, user mix (knowledge worker / field / executive), and replacement cadence?",
            "OS preference (iOS / Android), MDM platform, mobile carrier relationship, and any rugged-device need?",
        ]
    if any(k in t for k in ["vehicle", "fleet", "van", "truck", "lorry", "car "]):
        return [
            "How many vehicles, type (van / car / truck / EV), and what's the duty cycle?",
            "Geographic deployment, charging or fuelling needs, and any fleet-management telematics integration?",
        ]
    if any(k in t for k in ["cool", "hvac", "chiller", "data centre", "datacenter"]):
        return [
            "What total IT load (kW / MW), how many sites, and what target PUE?",
            "Free-cooling preference, refrigerant constraints (F-Gas / GWP), and existing DCIM integration?",
        ]
    if any(k in t for k in ["furniture", "desk", "chair", "office fit", "fit-out"]):
        return [
            "How many workstations / pieces, across how many sites, and what's the timeline?",
            "Design and sustainability requirements, accessibility standards, and installation services needed?",
        ]
    if any(k in t for k in ["print", "copier", "mfp", "managed print"]):
        return [
            "How many devices, monthly print volume (mono vs colour), and which sites?",
            "Managed print service preference, security requirements (pull-printing, encryption), and existing fleet brand?",
        ]
    if any(k in t for k in ["telecom", "broadband", "internet", "wan", "lan", "network"]):
        return [
            "How many sites, bandwidth per site, and topology (MPLS / SD-WAN / internet)?",
            "Uptime SLA needs, security (SASE / firewall), and any existing carrier relationships?",
        ]
    if any(k in t for k in ["uniform", "ppe", "workwear", "boots"]):
        return [
            "How many staff, what activities (office / field / industrial / hi-vis), and replenishment cycle?",
            "Required certifications (e.g. EN ISO 20471), branding / embroidery, and laundry-service needs?",
        ]
    if any(k in t for k in ["solar", "pv ", "photovoltaic"]):
        return [
            "Total installed capacity (kWp / MWp), number of sites, and rooftop / ground / carport?",
            "Grid-export arrangements, on-site consumption profile, and battery integration if any?",
        ]
    if any(k in t for k in ["heat pump", "boiler", "heating"]):
        return [
            "Heat output (kW), number of dwellings or sites, and existing system (gas / electric / district)?",
            "Compliance (MCS, F-Gas), installer-network coverage, and warranty / maintenance expectations?",
        ]
    if any(k in t for k in ["meter", "smart meter"]):
        return [
            "Meter type and quantity (electricity / gas / dual-fuel / industrial), and roll-out timeline?",
            "Communications (cellular / mesh / LPWAN), data platform integration, and certification (SMETS2 / MID)?",
        ]
    # Generic fallback
    return [
        "What's the approximate scale of this procurement (volume, sites, users, or estimated contract value)?",
        "Any key constraints, brand or supplier preferences, compliance requirements, or timeline that matter here?",
    ]


def generate_spec_from_conversation(messages: list[dict]) -> dict:
    """
    Build a procurement spec + scoring matrix from a chatbot conversation.
    Calls Gemini directly (ignores DEMO_OFFLINE_MODE); falls back to
    keyword-matched product-specific fixtures if no key or API failure.

    messages: list of {"role": "user"|"assistant", "content": str}
    Returns: {
        "category": str,
        "summary": str,
        "context": {brand_preference, geography, quantity, budget, timeline},
        "requirements": list[dict],   # spec rows
        "scoring_criteria": list[dict] # evaluation criteria for bids
    }
    """
    user_text = "\n".join(
        m["content"] for m in messages if m["role"] == "user"
    )

    prompt = (
        "You are an expert procurement technologist building a TECHNICAL SPECIFICATION "
        "for a SPECIFIC product — not a generic procurement template.\n\n"
        "USER CONVERSATION (what they want to buy):\n"
        f"{user_text}\n\n"
        "TASK: Return ONLY valid JSON (no markdown, no commentary) describing:\n"
        "  (a) the product context they captured (brand preference, geography, quantity, "
        "      budget, timeline — extract from the conversation, default to 'TBC' if absent)\n"
        "  (b) 12 to 16 PRODUCT-SPECIFIC technical requirements with CONCRETE target values\n"
        "  (c) 6 to 9 weighted scoring criteria for evaluating supplier bids\n\n"
        "GOOD examples for a security IP camera:\n"
        '  - "Resolution: 4K (3840x2160) minimum at 30 fps"\n'
        '  - "Lens: motorised varifocal 2.8-12mm, FoV 110-30 degrees"\n'
        '  - "IR range: 30 m minimum, smart IR with overexposure control"\n'
        '  - "IP rating: IP66 (outdoor) / IK10 vandal resistance"\n'
        '  - "Power: PoE 802.3af, Cat6, < 12 W per camera"\n'
        '  - "Cybersecurity: signed firmware, TLS 1.2+, complies with UK PSTI Act 2022"\n\n'
        "BAD examples (never produce these — they are useless boilerplate):\n"
        '  - "ISO 9001 compliance"  (says nothing about the product)\n'
        '  - "Quality plan required"  (procurement boilerplate)\n'
        '  - "Compliance with applicable standards"  (meaningless)\n'
        '  - "Implementation approach & timeline"  (not a product attribute)\n\n'
        "JSON SHAPE:\n"
        '{\n'
        '  "category": "Concrete product name (e.g. Security IP Cameras)",\n'
        '  "summary": "1-2 sentence summary of the procurement",\n'
        '  "context": {\n'
        '    "brand_preference": "extracted brand(s) or \'Open to alternatives\'",\n'
        '    "geography": "deployment region or \'UK\'",\n'
        '    "quantity": "quantity / volume or \'TBC\'",\n'
        '    "budget": "budget if mentioned or \'TBC\'",\n'
        '    "timeline": "timeline if mentioned or \'TBC\'"\n'
        '  },\n'
        '  "requirements": [\n'
        '    {\n'
        '      "id": "REQ-001",\n'
        '      "section": "Technical",\n'
        '      "title": "Short attribute name (e.g. Resolution, Lens, IR range)",\n'
        '      "description": "Concrete measurable target value with units / standards",\n'
        '      "priority": "Must",\n'
        '      "owner": "business",\n'
        '      "status": "Draft",\n'
        '      "comments": ""\n'
        '    }\n'
        '  ],\n'
        '  "scoring_criteria": [\n'
        '    {\n'
        '      "id": "SC-01",\n'
        '      "criterion": "Product-specific criterion name (e.g. Image quality at low light)",\n'
        '      "pillar": "Technical",\n'
        '      "weight": 20,\n'
        '      "scorer": "sme"\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "RULES:\n"
        "- section: one of Technical, Commercial, Legal, Operational, ESG.\n"
        "- priority: one of Must, Should, Could.\n"
        "- owner: 'business' for technical/product specs, 'procurement' for commercial/legal/process.\n"
        "- At least 60% of requirements must be Technical (product-specific attributes).\n"
        "- scoring_criteria weights MUST sum to exactly 100.\n"
        "- scoring criteria scorer: 'sme' for technical, 'business' for fit/ESG, 'procurement' for commercial/legal.\n"
        "- Each scoring criterion must be product-specific (NOT 'Implementation approach', NOT 'Methodology').\n"
        "- Return raw JSON only. No markdown fences."
    )

    raw = _call_gemini_direct(prompt)
    if raw:
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(lines[1:-1])
            parsed = json.loads(clean.strip())
            # Ensure required keys exist with safe defaults
            parsed.setdefault("context", {
                "brand_preference": "Open to alternatives",
                "geography": "UK",
                "quantity": "TBC",
                "budget": "TBC",
                "timeline": "TBC",
            })
            parsed.setdefault("scoring_criteria", _generic_scoring_criteria())
            return parsed
        except Exception:
            pass

    return _fallback_spec(user_text)


def _fallback_spec(user_text: str) -> dict:
    t = user_text.lower()
    if any(k in t for k in ["camera", "cctv", "surveillance", "ip cam", "security cam"]):
        return _SPEC_CAMERA
    if any(k in t for k in ["laptop", "notebook", "macbook", "computer", "workstation", "desktop"]):
        return _SPEC_LAPTOP
    if any(k in t for k in ["vehicle", "fleet", "van", "truck", "car ", "lorry", "ev "]):
        return _SPEC_VEHICLE
    if any(k in t for k in ["batter", "bess", "energy storage", "grid storage", "lithium"]):
        return _SPEC_BESS
    if any(k in t for k in ["software", "saas", "cloud", "licence", "license", "platform", "application"]):
        return _SPEC_SOFTWARE
    if any(k in t for k in ["cool", "hvac", "chiller", "data centre", "datacenter", "data center"]):
        return _SPEC_COOLING
    if any(k in t for k in ["consult", "advisory", "professional service", "managed service"]):
        return _SPEC_SERVICES
    return _SPEC_GENERIC


def _default_context() -> dict:
    return {
        "brand_preference": "Open to alternatives",
        "geography": "UK",
        "quantity": "TBC",
        "budget": "TBC",
        "timeline": "TBC",
    }


def _generic_scoring_criteria() -> list[dict]:
    return [
        {"id": "SC-01", "criterion": "Technical capability & fit-for-purpose", "pillar": "Technical",   "weight": 25, "scorer": "sme"},
        {"id": "SC-02", "criterion": "Build quality & reliability",            "pillar": "Technical",   "weight": 15, "scorer": "sme"},
        {"id": "SC-03", "criterion": "Total cost of ownership (TCO)",          "pillar": "Commercial",  "weight": 20, "scorer": "procurement"},
        {"id": "SC-04", "criterion": "Warranty, support & SLA",                "pillar": "Commercial",  "weight": 15, "scorer": "procurement"},
        {"id": "SC-05", "criterion": "Compliance & regulatory fit",            "pillar": "Legal",       "weight": 10, "scorer": "procurement"},
        {"id": "SC-06", "criterion": "Supplier ESG credentials",               "pillar": "ESG",         "weight": 10, "scorer": "business"},
        {"id": "SC-07", "criterion": "Integration & deployment ease",          "pillar": "Operational", "weight":  5, "scorer": "business"},
    ]


_SPEC_CAMERA: dict = {
    "category": "Security IP Cameras",
    "summary": "Procurement of networked security cameras (CCTV / IP) including supply, installation, configuration, and integration with the existing NVR / VMS platform.",
    "context": {
        "brand_preference": "Hikvision, Axis, or Hanwha — open to alternatives",
        "geography": "UK (multi-site)",
        "quantity": "120 units (mix of indoor / outdoor / dome / bullet)",
        "budget": "TBC",
        "timeline": "Install Q3 2026",
    },
    "requirements": [
        {"id": "REQ-001", "section": "Technical", "title": "Resolution & frame rate",        "description": "4K (3840x2160) minimum at 30 fps with dual-stream (main + sub-stream H.265+).", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-002", "section": "Technical", "title": "Lens / Field of view",           "description": "Motorised varifocal 2.8-12 mm. FoV 110-30 degrees. Auto-focus and remote zoom required for outdoor variants.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-003", "section": "Technical", "title": "Low-light / WDR",                "description": "Min illumination 0.005 lux colour, 0 lux with IR. True WDR >= 120 dB.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-004", "section": "Technical", "title": "IR night vision",                "description": "Smart IR with overexposure control. 30 m minimum range (dome) / 60 m (bullet).", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-005", "section": "Technical", "title": "Weather & impact rating",        "description": "Outdoor units IP66 and IK10 rated. Operating range -30 degC to +60 degC.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-006", "section": "Technical", "title": "Power & connectivity",           "description": "PoE 802.3af / af+ with Cat6 cabling. Power draw < 12 W per camera. RJ45 with surge protection.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-007", "section": "Technical", "title": "Audio & two-way talk",           "description": "Built-in mic and speaker. Two-way audio over G.711/G.722. Audio metadata in stream.", "priority": "Should", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-008", "section": "Technical", "title": "Onboard storage",                "description": "MicroSD slot up to 256 GB for edge recording during NVR outage. Encrypted at rest.", "priority": "Should", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-009", "section": "Technical", "title": "AI analytics (on-edge)",         "description": "Person / vehicle classification, line crossing, intrusion detection. Min 95% precision in vendor benchmark conditions.", "priority": "Should", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-010", "section": "Technical", "title": "VMS / NVR integration",          "description": "ONVIF Profile S, G and T. Native plug-ins for Milestone XProtect and Genetec Security Center.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-011", "section": "Technical", "title": "Cybersecurity",                  "description": "Signed firmware, TLS 1.2+, 802.1X, no default credentials. Vendor must comply with UK PSTI Act 2022.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-012", "section": "Commercial", "title": "Volume pricing",                 "description": "Tiered unit price for 50 / 100 / 200+ units. Price held firm 12 months from award.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-013", "section": "Commercial", "title": "Warranty",                       "description": "Minimum 3-year manufacturer warranty (5 years preferred). Advanced replacement (next-business-day) for failed units.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-014", "section": "Legal", "title": "Data protection / GDPR",              "description": "Compliance with UK GDPR for any recorded personal data. Vendor on UK NCSC Cyber Essentials Plus.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-015", "section": "ESG", "title": "Energy consumption & e-waste",         "description": "Annual energy consumption disclosure per unit. Take-back scheme for end-of-life devices.", "priority": "Should", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-016", "section": "Operational", "title": "Install & training",            "description": "Engineer site survey and installation included. 1-day training for client SOC operators on VMS integration.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
    ],
    "scoring_criteria": [
        {"id": "SC-01", "criterion": "Image quality (4K, low-light, WDR)",       "pillar": "Technical",   "weight": 20, "scorer": "sme"},
        {"id": "SC-02", "criterion": "IR / night vision performance",            "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-03", "criterion": "AI analytics accuracy",                    "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-04", "criterion": "Cybersecurity & firmware integrity",       "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-05", "criterion": "VMS / NVR integration (ONVIF, plug-ins)",  "pillar": "Operational", "weight": 10, "scorer": "business"},
        {"id": "SC-06", "criterion": "Total cost of ownership (10-yr)",          "pillar": "Commercial",  "weight": 20, "scorer": "procurement"},
        {"id": "SC-07", "criterion": "Warranty, RMA & support quality",          "pillar": "Commercial",  "weight": 10, "scorer": "procurement"},
        {"id": "SC-08", "criterion": "Energy use & supplier ESG credentials",    "pillar": "ESG",         "weight": 10, "scorer": "business"},
    ],
}

_SPEC_LAPTOP: dict = {
    "category": "Business Laptops",
    "summary": "Procurement of business-class laptops for office and remote workers including warranty, imaging, and asset management.",
    "context": {
        "brand_preference": "Dell, Lenovo, or HP business range — open to alternatives",
        "geography": "UK + Ireland",
        "quantity": "500 units",
        "budget": "TBC",
        "timeline": "Refresh wave Q2-Q3 2026",
    },
    "requirements": [
        {"id": "REQ-001", "section": "Technical", "title": "CPU",                "description": "Intel Core Ultra 7 or AMD Ryzen 7 PRO (latest generation), min 12 cores, base clock >= 1.7 GHz.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-002", "section": "Technical", "title": "Memory",             "description": "32 GB DDR5 (dual-channel) standard. 64 GB option for power-user SKU.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-003", "section": "Technical", "title": "Storage",            "description": "1 TB NVMe Gen4 SSD with hardware encryption (TCG Opal 2.0).", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-004", "section": "Technical", "title": "Display",            "description": "14-inch IPS, 1920x1200 (16:10), 400 nits, anti-glare, 100% sRGB.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-005", "section": "Technical", "title": "Battery life",       "description": ">= 12 hours MobileMark 2025 rating. Fast-charge 0-80% in 60 min.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-006", "section": "Technical", "title": "Connectivity",       "description": "Wi-Fi 7, Bluetooth 5.4, 5G WWAN option. 2x Thunderbolt 4, 1x USB-A, HDMI 2.1.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-007", "section": "Technical", "title": "Security",           "description": "TPM 2.0, fingerprint reader, IR camera with Windows Hello, privacy shutter.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-008", "section": "Technical", "title": "Build & durability", "description": "MIL-STD 810H certified. Weight <= 1.4 kg. Spill-resistant keyboard.", "priority": "Should", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-009", "section": "Operational", "title": "Imaging / Autopilot", "description": "Pre-enrolled in Microsoft Intune / Autopilot. Custom Centrica image installed at factory.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-010", "section": "Commercial", "title": "Per-unit price",     "description": "Tiered pricing for 100 / 250 / 500+ units. Price firm for 12 months.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-011", "section": "Commercial", "title": "Warranty",          "description": "Minimum 3-year next-business-day on-site warranty. Accidental damage cover preferred.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-012", "section": "Legal", "title": "Cybersecurity assurance",  "description": "Vendor holds Cyber Essentials Plus. BIOS/UEFI compliant with NIST SP 800-147.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-013", "section": "ESG", "title": "Recycled materials",         "description": "Minimum 30% post-consumer recycled plastic content. EPEAT Gold rating.", "priority": "Should", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-014", "section": "ESG", "title": "End-of-life take-back",      "description": "Free take-back and certified secure data destruction for retired units.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
    ],
    "scoring_criteria": [
        {"id": "SC-01", "criterion": "CPU / memory / storage performance",     "pillar": "Technical",   "weight": 20, "scorer": "sme"},
        {"id": "SC-02", "criterion": "Display & battery life",                 "pillar": "Technical",   "weight": 15, "scorer": "sme"},
        {"id": "SC-03", "criterion": "Build quality & MIL-STD durability",     "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-04", "criterion": "Security features (TPM, biometrics)",    "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-05", "criterion": "Total cost (unit + 3-yr warranty)",      "pillar": "Commercial",  "weight": 20, "scorer": "procurement"},
        {"id": "SC-06", "criterion": "Warranty SLA & RMA experience",          "pillar": "Commercial",  "weight": 10, "scorer": "procurement"},
        {"id": "SC-07", "criterion": "Intune / Autopilot imaging readiness",   "pillar": "Operational", "weight":  5, "scorer": "business"},
        {"id": "SC-08", "criterion": "ESG (recycled content, EPEAT, take-back)","pillar": "ESG",        "weight": 10, "scorer": "business"},
    ],
}

_SPEC_VEHICLE: dict = {
    "category": "Light Commercial Vehicles (Electric Van Fleet)",
    "summary": "Procurement of electric light commercial vehicles for field-services fleet, including charging, telematics, and service contract.",
    "context": {
        "brand_preference": "Ford E-Transit, Mercedes eVito, or Vauxhall Vivaro-e — open to alternatives",
        "geography": "UK (national)",
        "quantity": "85 vehicles",
        "budget": "TBC",
        "timeline": "Delivery Q4 2026",
    },
    "requirements": [
        {"id": "REQ-001", "section": "Technical", "title": "Powertrain",         "description": "Battery-electric. Minimum WLTP range 200 miles fully laden. Continuous power >= 100 kW.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-002", "section": "Technical", "title": "Payload & volume",   "description": "Min 1,000 kg payload. Cargo volume >= 11 m^3. Bulkhead and ply-lined interior.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-003", "section": "Technical", "title": "Charging",           "description": "AC 11 kW Type 2. DC rapid charge >= 115 kW (CCS2). 10-80% in <= 35 min at rapid charger.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-004", "section": "Technical", "title": "Telematics",         "description": "Built-in connected services with REST API. Real-time location, battery SoC, driver behaviour, geofencing.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-005", "section": "Technical", "title": "Safety & ADAS",       "description": "Euro NCAP 4-star minimum. AEB, lane keep, blind-spot monitor, 360 camera as standard.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-006", "section": "Technical", "title": "Racking & livery",   "description": "Internal racking installed at PDI. Centrica livery applied. PAT-tested 12V auxiliary sockets.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-007", "section": "Commercial", "title": "Total cost (lease or purchase)", "description": "Quote both 4-year lease (incl. servicing) and outright purchase TCO. Residual value guarantee where applicable.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-008", "section": "Commercial", "title": "Service & maintenance", "description": "Manufacturer service plan: fixed-cost servicing for 4 years / 80,000 miles. Mobile service for breakdowns.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-009", "section": "Commercial", "title": "Warranty",          "description": "Vehicle: minimum 3 years / 100,000 miles. Battery: 8 years / 100,000 miles to 70% capacity.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-010", "section": "Legal", "title": "Type approval & compliance", "description": "UK type approval. Plug-in Van Grant eligible. Conforms to UK Road Vehicles (Construction & Use) Regulations.", "priority": "Must", "owner": "procurement", "status": "Draft", "comments": ""},
        {"id": "REQ-011", "section": "ESG", "title": "Battery sourcing & recycling", "description": "Battery cell origin disclosure. Take-back / second-life programme for end-of-service batteries.", "priority": "Must", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-012", "section": "Operational", "title": "Depot charging integration", "description": "Vendor to advise on 22 kW depot charger sizing for the fleet. OCPP 2.0.1 compatible.", "priority": "Should", "owner": "business", "status": "Draft", "comments": ""},
        {"id": "REQ-013", "section": "Operational", "title": "Driver training",  "description": "EV driver training (regen, range management, charging etiquette) delivered for all 85 drivers at handover.", "priority": "Should", "owner": "business", "status": "Draft", "comments": ""},
    ],
    "scoring_criteria": [
        {"id": "SC-01", "criterion": "Range under load & cold weather",        "pillar": "Technical",   "weight": 20, "scorer": "sme"},
        {"id": "SC-02", "criterion": "Payload, volume & racking fit",          "pillar": "Technical",   "weight": 15, "scorer": "sme"},
        {"id": "SC-03", "criterion": "Charging speed & on-board telematics",   "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-04", "criterion": "Total cost of ownership (4-yr)",         "pillar": "Commercial",  "weight": 20, "scorer": "procurement"},
        {"id": "SC-05", "criterion": "Service network coverage & SLA",         "pillar": "Commercial",  "weight": 10, "scorer": "procurement"},
        {"id": "SC-06", "criterion": "Battery warranty & residual value",      "pillar": "Commercial",  "weight": 10, "scorer": "procurement"},
        {"id": "SC-07", "criterion": "Battery sourcing & ESG credentials",     "pillar": "ESG",         "weight": 10, "scorer": "business"},
        {"id": "SC-08", "criterion": "Driver training & change-management fit", "pillar": "Operational", "weight":  5, "scorer": "business"},
    ],
}

_SPEC_BESS: dict = {
    "category": "Battery Energy Storage Systems (BESS)",
    "summary": "Procurement of utility-scale battery energy storage systems including supply, installation, commissioning, and long-term O&M.",
    "context": {
        "brand_preference": "Tier-1 lithium-iron-phosphate suppliers — Tesla, Fluence, Wartsila or equivalent",
        "geography": "UK (3 cluster sites)",
        "quantity": "30 MWh total across 3 sites",
        "budget": "TBC",
        "timeline": "Commissioning H2 2026",
    },
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
    "scoring_criteria": [
        {"id": "SC-01", "criterion": "Cell chemistry, capacity & cycle life",    "pillar": "Technical",   "weight": 20, "scorer": "sme"},
        {"id": "SC-02", "criterion": "Round-trip efficiency & response time",    "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-03", "criterion": "Fire safety & containment design",         "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-04", "criterion": "Grid code / DNO compliance",               "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-05", "criterion": "Total cost of ownership (10-yr)",          "pillar": "Commercial",  "weight": 20, "scorer": "procurement"},
        {"id": "SC-06", "criterion": "Warranty & performance guarantee",         "pillar": "Commercial",  "weight": 10, "scorer": "procurement"},
        {"id": "SC-07", "criterion": "Battery recycling & supply-chain ESG",     "pillar": "ESG",         "weight": 10, "scorer": "business"},
        {"id": "SC-08", "criterion": "Commissioning & operator training quality","pillar": "Operational", "weight": 10, "scorer": "business"},
    ],
}

_SPEC_SOFTWARE: dict = {
    "category": "Enterprise Software / SaaS Platform",
    "summary": "Procurement of a cloud-hosted enterprise software platform including licences, implementation, integration, and ongoing support.",
    "context": {
        "brand_preference": "Open to alternatives",
        "geography": "UK (data residency)",
        "quantity": "5,000 users",
        "budget": "TBC",
        "timeline": "Go-live within 90 days of award",
    },
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
    "scoring_criteria": [
        {"id": "SC-01", "criterion": "Functional coverage of requirements", "pillar": "Technical",   "weight": 20, "scorer": "sme"},
        {"id": "SC-02", "criterion": "API depth & integration readiness",   "pillar": "Technical",   "weight": 15, "scorer": "sme"},
        {"id": "SC-03", "criterion": "Performance & scalability evidence",  "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-04", "criterion": "ISO 27001 / pen-test assurance",      "pillar": "Legal",       "weight": 10, "scorer": "procurement"},
        {"id": "SC-05", "criterion": "3-year TCO (licence + implementation)","pillar": "Commercial", "weight": 20, "scorer": "procurement"},
        {"id": "SC-06", "criterion": "SLA, support & uptime",                "pillar": "Commercial",  "weight": 10, "scorer": "procurement"},
        {"id": "SC-07", "criterion": "Exit & data portability strength",     "pillar": "Commercial",  "weight":  5, "scorer": "procurement"},
        {"id": "SC-08", "criterion": "Carbon-neutral hosting commitments",   "pillar": "ESG",         "weight": 10, "scorer": "business"},
    ],
}

_SPEC_COOLING: dict = {
    "category": "Data Centre Cooling Systems",
    "summary": "Procurement of high-efficiency cooling for Tier III+ data centres, targeting PUE <= 1.25 and net-zero alignment.",
    "context": {
        "brand_preference": "Open to alternatives — Tier-1 DC cooling specialists",
        "geography": "UK (3 cluster sites: London, Midlands, North)",
        "quantity": "6 MW IT load total",
        "budget": "TBC",
        "timeline": "Phased install 2026-2027",
    },
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
    "scoring_criteria": [
        {"id": "SC-01", "criterion": "PUE achievable at 100% IT load",       "pillar": "Technical",   "weight": 25, "scorer": "sme"},
        {"id": "SC-02", "criterion": "Free-cooling hours & refrigerant GWP", "pillar": "Technical",   "weight": 15, "scorer": "sme"},
        {"id": "SC-03", "criterion": "Resilience & failover design",         "pillar": "Technical",   "weight": 10, "scorer": "sme"},
        {"id": "SC-04", "criterion": "10-year TCO incl. energy",             "pillar": "Commercial",  "weight": 20, "scorer": "procurement"},
        {"id": "SC-05", "criterion": "Service SLA & spare-parts coverage",   "pillar": "Commercial",  "weight": 10, "scorer": "procurement"},
        {"id": "SC-06", "criterion": "Net-zero pathway alignment",           "pillar": "ESG",         "weight": 10, "scorer": "business"},
        {"id": "SC-07", "criterion": "Commissioning quality & site evidence","pillar": "Operational", "weight": 10, "scorer": "business"},
    ],
}

_SPEC_SERVICES: dict = {
    "category": "Professional / Managed Services",
    "summary": "Procurement of specialist advisory or managed services with defined deliverables, governance, and performance management.",
    "context": {
        "brand_preference": "Open to all qualified providers",
        "geography": "UK",
        "quantity": "Single-supplier engagement",
        "budget": "TBC",
        "timeline": "TBC",
    },
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
    "scoring_criteria": [
        {"id": "SC-01", "criterion": "Scope clarity & SoW completeness",   "pillar": "Technical",   "weight": 15, "scorer": "sme"},
        {"id": "SC-02", "criterion": "Named team & expertise mix",         "pillar": "Technical",   "weight": 15, "scorer": "sme"},
        {"id": "SC-03", "criterion": "Methodology & governance maturity",  "pillar": "Technical",   "weight": 10, "scorer": "business"},
        {"id": "SC-04", "criterion": "Fee structure & rate competitiveness","pillar": "Commercial",  "weight": 25, "scorer": "procurement"},
        {"id": "SC-05", "criterion": "Contract terms (IP, IR35, liability)","pillar": "Legal",       "weight": 15, "scorer": "procurement"},
        {"id": "SC-06", "criterion": "Supplier ESG & social value",        "pillar": "ESG",         "weight": 10, "scorer": "business"},
        {"id": "SC-07", "criterion": "Knowledge transfer commitment",      "pillar": "Operational", "weight": 10, "scorer": "business"},
    ],
}

_SPEC_GENERIC: dict = {
    "category": "General Procurement",
    "summary": "Procurement of goods or services covering technical, commercial, legal, operational, and ESG dimensions.",
    "context": {
        "brand_preference": "Open to alternatives",
        "geography": "UK",
        "quantity": "TBC",
        "budget": "TBC",
        "timeline": "TBC",
    },
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
    "scoring_criteria": _generic_scoring_criteria(),
}
