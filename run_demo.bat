@echo off
REM RFx Assistant — one-click launcher for Centrica demo (Windows)
setlocal

cd /d "%~dp0"

REM Copy .env if missing
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" > nul
        echo Created .env from .env.example. Edit OPENAI_API_KEY if you want live LLM calls.
        echo Demo runs perfectly without it (DEMO_OFFLINE_MODE=1 by default^).
        echo.
    )
)

REM Generate fixtures if missing
if not exist "data\fixtures\bids\Aurora_Cooling_Bid_Centrica_RFP_IT-INF-DC-COOL-2026.pdf" (
    echo Generating supplier bid fixtures...
    python scripts\generate_fixtures.py
    echo.
)

echo Launching RFx Assistant on http://localhost:8501 ...
python -m streamlit run src\rfx_assistant\main.py --server.port 8501 --server.headless false --browser.gatherUsageStats false

endlocal
