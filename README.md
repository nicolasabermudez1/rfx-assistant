# RFx Assistant — Centrica Procurement Demo

An Ariba-native overlay that takes a Centrica category strategy → generates an RFP → ingests
multi-format supplier bids → scores against the Centrica framework → ranks a shortlist →
emits a governance-ready audit report.

Built for the **IT-INF-DC-COOL-2026** Data Centre Cooling category as the worked example.

## Quickstart

**Windows**: double-click `run_demo.bat` (or run it in a terminal).
**macOS / Linux / Git Bash**: `./run_demo.sh`.

The launcher:
1. Copies `.env.example` → `.env` if missing.
2. Generates the 3 supplier bid fixtures (PDF, Excel, Word) if missing.
3. Launches Streamlit at <http://localhost:8501>.

## Manual setup (if you prefer)

```bash
pip install -r requirements.txt
python scripts/generate_fixtures.py
python -m streamlit run src/rfx_assistant/main.py --server.port 8501
```

## Demo flow (left-to-right tabs)

0. **Co-author Spec** — Collaborative spec workspace. Procurement (Priya) and the business stakeholder (Mark) co-author the RFP spec with agent assistance. Includes AI-drafted questions for Mark, inline chat, comment threads, sign-off flow, automated chase email with a magic link (no Ariba login for the business), and Teams ping. Solves the "chasing a tiny spec input across the business" pain point.
1. **Generate RFP** — Loads the approved category strategy + Centrica Sourcing Library, produces a Centrica-branded RFP `.docx` and one response template per RFP section.
2. **Bid Intake** — Routes Aurora (PDF), Helios (Excel), NorthernAir (Word) through format-specific parsers and produces a side-by-side gap analysis with confidence per answer.
3. **Score Matrix** — 9-criterion heatmap with confidence; SME panel can override TECHNICAL and SUSTAIN rows.
4. **Shortlist & Award** — Ranked recommendations with rationale, recommended cluster awards, consolidated deviation register, sorry-but-thanks email drafts.
5. **Audit Report** — Word + JSON for write-back into the Ariba Sourcing event (Doc12876211).
6. **Trace** — Per-run JSON traces with token accounting and tool-call timeline.

## Modes

By default the demo runs in **pre-computed mode** (`DEMO_OFFLINE_MODE=1` in `.env`) — every step uses the curated Centrica fixtures so the demo runs end-to-end without an API key.

Set `DEMO_OFFLINE_MODE=0` and add your `OPENAI_API_KEY` in `.env` to layer live `gpt-4o` calls on top (currently used for the executive summary in Tab 1; other steps remain authoritative on the curated fixtures so the narrative stays consistent in front of clients).

## Centrica branding

Every artefact and every UI surface uses the Centrica palette:
- Dark blue `#1A2D5E` · Light purple `#C7B8FF` · Mint pink `#F8C8D8` · Pale purple `#EBE3FF` · Deep purple `#6E54D6`

Legacy aliases (`NAVY`, `MINT`, `LAVENDER`, etc.) map to the above so existing imports continue to work.

No red anywhere.

## Project layout

```
RFx Assistant/
├── run_demo.bat / run_demo.sh   ← one-click launchers
├── requirements.txt
├── .env.example                 ← copy to .env
├── README.md
├── scripts/
│   └── generate_fixtures.py     ← builds the 3 supplier bid files
├── src/rfx_assistant/
│   ├── main.py                  ← Streamlit entry point
│   ├── branding.py              ← Centrica palette + CSS
│   ├── data_loader.py           ← reads fixtures
│   ├── doc_writer.py            ← Word document generation
│   ├── agents.py                ← agent step functions + run trace
│   └── paths.py
├── data/
│   ├── fixtures/
│   │   ├── category_strategy_data_centre_cooling.md
│   │   ├── sourcing_library/    ← 3 categories
│   │   ├── scoring_framework.yml
│   │   ├── boilerplate_terms.md
│   │   ├── bids/                ← 3 generated supplier bids
│   │   └── precomputed/         ← curated agent outputs (suppliers, scores, shortlist, etc.)
│   └── runs/                    ← per-run JSON traces
├── outputs/                     ← generated artefacts (RFP, audit report)
└── schemas/audit_report.json
```
