#!/usr/bin/env bash
# RFx Assistant — one-click launcher for Centrica demo (macOS / Linux / Git Bash)
set -e
cd "$(dirname "$0")"

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit OPENAI_API_KEY if you want live LLM calls."
fi

if [ ! -f "data/fixtures/bids/Aurora_Cooling_Bid_Centrica_RFP_IT-INF-DC-COOL-2026.pdf" ]; then
  echo "Generating supplier bid fixtures..."
  python scripts/generate_fixtures.py
fi

echo "Launching RFx Assistant on http://localhost:8501 ..."
python -m streamlit run src/rfx_assistant/main.py \
  --server.port 8501 \
  --server.headless false \
  --browser.gatherUsageStats false
