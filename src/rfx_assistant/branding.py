"""Brand tokens, themes, and Streamlit CSS injection.

Palette (replaces the prior Centrica brand) — dark blue · light purple · mint pink:
- DARK_BLUE     #1A2D5E   primary, ink, deep accent
- LIGHT_PURPLE  #C7B8FF   accent, secondary headings, pending state
- MINT_PINK     #F8C8D8   highlight, positive state
- PALE_PURPLE   #EBE3FF   surface wash, zebra rows in light theme
- DEEP_PURPLE   #6E54D6   strong accent (CTAs, focus rings)

The module exposes both the new names (DARK_BLUE, LIGHT_PURPLE, MINT_PINK…) and the
legacy aliases (NAVY, LAVENDER, MINT…) so existing imports keep working with the new
values.

Runtime theme switching is done by emitting different :root CSS variables and global
selectors — UI components reference `var(--*)` so they re-paint on theme change.
"""
from __future__ import annotations
from typing import Literal

# ----------------------------------------------------------------------
# Brand identity (used as direct hex in inline HTML — fine in both themes)
# ----------------------------------------------------------------------

DARK_BLUE    = "#1A2D5E"
LIGHT_PURPLE = "#C7B8FF"
MINT_PINK    = "#F8C8D8"
PALE_PURPLE  = "#EBE3FF"
DEEP_PURPLE  = "#6E54D6"

# Legacy aliases — keep code that imports NAVY / MINT / etc. working.
NAVY          = DARK_BLUE
MINT          = MINT_PINK
LAVENDER      = LIGHT_PURPLE
PALE_LAVENDER = PALE_PURPLE
PURPLE        = DEEP_PURPLE

# Status colours (theme-neutral, brand-aligned, no red)
WARN     = "#E8A33A"
NEGATIVE = "#7A1F8F"

# ----------------------------------------------------------------------
# Theme tokens
# ----------------------------------------------------------------------

Theme = Literal["light", "dark"]


def tokens(theme: Theme) -> dict[str, str]:
    if theme == "dark":
        return {
            # surfaces
            "bg":          "#0B1226",
            "surface":     "#16244D",
            "surface_2":   "#1E2D5E",
            "card":        "#142042",
            "header_grad": f"linear-gradient(135deg, {DARK_BLUE} 0%, {DEEP_PURPLE} 100%)",
            # text
            "text":        "#E8EAF5",
            "muted":       "#9CA3C2",
            "ink_strong":  "#FFFFFF",
            "ink_inverse": DARK_BLUE,
            # roles
            "primary":     LIGHT_PURPLE,
            "accent":      MINT_PINK,
            "highlight":   MINT_PINK,
            "border":      "#2A3568",
            "border_soft": "#1E2D5E",
            "shadow":      "0 4px 18px rgba(0,0,0,0.45)",
            # role surfaces (zebra)
            "surface_alt": "#1A2A56",
            # plotly
            "plot_bg":     "rgba(0,0,0,0)",
            "plot_paper":  "rgba(0,0,0,0)",
            "plot_text":   "#E8EAF5",
            # input
            "input_bg":    "#1A2A56",
            "input_text":  "#E8EAF5",
        }
    # light
    return {
        "bg":          "#FBFAFF",
        "surface":     "#FFFFFF",
        "surface_2":   "#F4EFFD",
        "card":        "#FFFFFF",
        "header_grad": f"linear-gradient(135deg, {DARK_BLUE} 0%, {DEEP_PURPLE} 100%)",
        "text":        "#0E1A3D",
        "muted":       "#6B6B85",
        "ink_strong":  DARK_BLUE,
        "ink_inverse": "#FFFFFF",
        "primary":     DARK_BLUE,
        "accent":      LIGHT_PURPLE,
        "highlight":   MINT_PINK,
        "border":      "#E5E0F2",
        "border_soft": "#ECE6F8",
        "shadow":      "0 4px 18px rgba(15,32,103,0.18)",
        "surface_alt": "#F7F3FE",
        "plot_bg":     "rgba(0,0,0,0)",
        "plot_paper":  "rgba(0,0,0,0)",
        "plot_text":   DARK_BLUE,
        "input_bg":    "#FFFFFF",
        "input_text":  "#0E1A3D",
    }


# ----------------------------------------------------------------------
# Plotly helpers
# ----------------------------------------------------------------------

def plotly_sequence(theme: Theme) -> list[str]:
    if theme == "dark":
        return [LIGHT_PURPLE, MINT_PINK, "#8AB6FF", DEEP_PURPLE, "#F0D5DF", "#5B6FB7"]
    return [DARK_BLUE, DEEP_PURPLE, MINT_PINK, LIGHT_PURPLE, "#5B4FB7", PALE_PURPLE]


def plotly_heatmap_scale(theme: Theme) -> list[list]:
    if theme == "dark":
        return [[0.0, "#1E2D5E"], [0.5, DEEP_PURPLE], [1.0, LIGHT_PURPLE]]
    return [[0.0, PALE_PURPLE], [0.5, LIGHT_PURPLE], [1.0, DARK_BLUE]]


def plotly_layout(theme: Theme) -> dict:
    t = tokens(theme)
    return dict(
        paper_bgcolor=t["plot_paper"],
        plot_bgcolor=t["plot_bg"],
        font=dict(family="Calibri, Segoe UI, sans-serif", color=t["plot_text"]),
        xaxis=dict(gridcolor=t["border_soft"], zerolinecolor=t["border_soft"]),
        yaxis=dict(gridcolor=t["border_soft"], zerolinecolor=t["border_soft"]),
        legend=dict(font=dict(color=t["plot_text"])),
    )


# ----------------------------------------------------------------------
# CSS injection
# ----------------------------------------------------------------------

def inject_css(theme: Theme = "light") -> str:
    t = tokens(theme)
    css_vars = "\n".join(f"  --{k.replace('_', '-')}: {v};" for k, v in t.items())
    return f"""
    <style>
      :root {{
{css_vars}
        --brand-dark-blue: {DARK_BLUE};
        --brand-light-purple: {LIGHT_PURPLE};
        --brand-mint-pink: {MINT_PINK};
        --brand-pale-purple: {PALE_PURPLE};
        --brand-deep-purple: {DEEP_PURPLE};
      }}

      /* Streamlit base */
      .stApp,
      [data-testid="stAppViewContainer"] {{
        background: var(--bg) !important;
        color: var(--text) !important;
      }}
      [data-testid="stHeader"] {{
        background: transparent !important;
      }}
      [data-testid="stSidebar"] > div:first-child {{
        background: var(--surface) !important;
        border-right: 1px solid var(--border-soft) !important;
      }}
      [data-testid="stSidebar"] * {{
        color: var(--text);
      }}

      /* Typography */
      html, body, [class*="css"] {{
        font-family: 'Calibri', 'Segoe UI', sans-serif !important;
        color: var(--text);
      }}
      h1, h2, h3, h4 {{
        font-family: 'Arial', 'Calibri', sans-serif !important;
        color: var(--ink-strong) !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em;
      }}
      p, span, label, li {{ color: var(--text); }}
      a {{ color: var(--brand-deep-purple); }}
      hr {{ border-color: var(--border-soft) !important; }}

      /* Tabs */
      .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background: var(--surface-2);
        padding: 6px;
        border-radius: 10px;
      }}
      .stTabs [data-baseweb="tab"] {{
        background-color: var(--surface);
        color: var(--ink-strong);
        font-weight: 600;
        border-radius: 8px;
        padding: 10px 18px;
        border: 1px solid var(--border-soft);
      }}
      .stTabs [data-baseweb="tab"] p {{ color: var(--ink-strong); }}
      .stTabs [aria-selected="true"] {{
        background: var(--header-grad) !important;
        color: white !important;
        border-color: transparent !important;
        box-shadow: var(--shadow);
      }}
      .stTabs [aria-selected="true"] p {{ color: white !important; }}

      /* Buttons */
      .stButton button[kind="primary"] {{
        background: var(--header-grad);
        color: white;
        border: none;
        font-weight: 600;
        padding: 10px 24px;
        border-radius: 8px;
        box-shadow: var(--shadow);
      }}
      .stButton button[kind="primary"]:hover {{
        transform: translateY(-1px);
        filter: brightness(1.06);
      }}
      .stButton button[kind="secondary"] {{
        border: 1.5px solid var(--primary);
        color: var(--ink-strong);
        background: var(--surface);
        font-weight: 600;
        border-radius: 8px;
      }}

      /* Banner / hero */
      .centrica-banner {{
        background: var(--header-grad);
        color: white;
        padding: 24px 28px;
        border-radius: 14px;
        box-shadow: var(--shadow);
      }}
      .centrica-banner h1 {{
        color: white !important;
        margin: 0 0 4px 0;
        font-size: 28px;
      }}
      .centrica-banner p {{
        color: rgba(255,255,255,0.86);
        margin: 0;
        font-size: 14px;
      }}

      /* Cards */
      .centrica-card {{
        background: var(--card);
        color: var(--text);
        border: 1px solid var(--border);
        border-left: 4px solid var(--brand-deep-purple);
        border-radius: 10px;
        padding: 16px 18px;
        margin: 8px 0;
      }}
      .centrica-card-mint     {{ border-left-color: var(--brand-mint-pink); }}
      .centrica-card-lavender {{ border-left-color: var(--brand-light-purple); }}
      .centrica-card-amber    {{ border-left-color: {WARN}; }}
      .centrica-card-deep     {{ border-left-color: var(--brand-deep-purple); }}

      /* Pills */
      .centrica-pill {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.02em;
        margin-right: 6px;
        border: 1px solid transparent;
      }}
      .pill-mint     {{ background: var(--brand-mint-pink);    color: var(--brand-dark-blue); }}
      .pill-lavender {{ background: var(--brand-light-purple); color: var(--brand-dark-blue); }}
      .pill-pale     {{ background: var(--brand-pale-purple);  color: var(--brand-dark-blue); }}
      .pill-amber    {{ background: {WARN};                    color: white;  }}
      .pill-purple   {{ background: var(--brand-deep-purple);  color: white;  }}
      .pill-navy     {{ background: var(--brand-dark-blue);    color: white;  }}

      /* Progress bar */
      .stProgress > div > div > div > div {{
        background: linear-gradient(90deg, var(--brand-dark-blue) 0%, var(--brand-deep-purple) 100%);
      }}

      /* Agent thought box */
      .agent-thought {{
        font-family: 'Consolas', 'SF Mono', monospace;
        background: var(--surface-2);
        border: 1px dashed var(--brand-light-purple);
        border-radius: 6px;
        padding: 10px 14px;
        font-size: 12px;
        color: var(--ink-strong);
        margin: 4px 0;
      }}

      /* Inputs */
      .stTextInput > div > div input,
      .stTextArea textarea,
      .stSelectbox > div > div,
      .stNumberInput input {{
        background-color: var(--input-bg) !important;
        color: var(--input-text) !important;
        border: 1px solid var(--border) !important;
      }}
      .stTextInput > div > div input::placeholder,
      .stTextArea textarea::placeholder {{
        color: var(--muted) !important;
        opacity: 0.85;
      }}

      /* Metrics */
      [data-testid="stMetricLabel"] {{ color: var(--muted); }}
      [data-testid="stMetricValue"] {{ color: var(--ink-strong); font-weight: 700; }}

      /* DataFrame / tables */
      .stDataFrame {{
        border: 1px solid var(--border);
        border-radius: 8px;
        background: var(--surface);
      }}
      .stDataFrame [data-testid="StyledDataFrameRowHeaderCell"],
      .stDataFrame [data-testid="StyledDataFrameDataCell"] {{
        color: var(--text) !important;
      }}

      /* Expander */
      .stExpander {{
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        background: var(--surface) !important;
      }}
      .stExpander summary,
      .stExpander summary p {{
        color: var(--ink-strong) !important;
      }}

      /* Toast */
      [data-testid="stToast"] {{
        background: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
      }}

      /* Small helpers */
      .small-muted {{
        color: var(--muted);
        font-size: 12px;
      }}
      .panel-soft {{
        background: var(--surface-2);
        border: 1px solid var(--border-soft);
        border-radius: 10px;
        padding: 12px 14px;
      }}

      footer {{ visibility: hidden; }}
      #MainMenu {{ visibility: hidden; }}
    </style>
    """
