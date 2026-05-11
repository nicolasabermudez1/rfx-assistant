"""The 'Things' — Centrica's blue fluffy mascots.

A small visual companion that appears whenever the app is asking the user for
input or guiding them. Has three poses (taken from the Centrica/British Gas
'Thing' family campaign), a speech bubble, and theme-aware colouring.

Image assets
------------
Drop these PNG files (transparent backgrounds, ~600px tall) at
``assets/mascots/`` to use the real Centrica mascots:

- ``thing_phone.png``        — Thing holding a phone (chase / email moments)
- ``thing_glasses_vacuum.png``— Glasses-wearing Thing with vacuum (working / cleaning)
- ``thing_family.png``        — Group of Things (celebration / team)
- ``thing_wave.png``          — generic friendly wave (defaults / greeting)
- ``thing_question.png``      — Thing tilting head (open question)

If a PNG is missing, the component falls back to a stylised SVG silhouette in
the brand blue so the demo never looks broken.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Literal

import streamlit as st

from rfx_assistant.paths import ROOT
from rfx_assistant.branding import (
    DARK_BLUE, LIGHT_PURPLE, MINT_PINK, DEEP_PURPLE,
)

ASSETS = ROOT / "assets" / "mascots"
ASSETS.mkdir(parents=True, exist_ok=True)

Pose = Literal["wave", "phone", "vacuum", "family", "question", "celebrate", "guide"]
Side = Literal["left", "right"]
Size = Literal["xs", "sm", "md", "lg"]

SIZE_PX = {"xs": 56, "sm": 86, "md": 130, "lg": 180}

# Pose → preferred filename(s) (first existing wins). Allows graceful fallback.
POSE_FILES: dict[str, list[str]] = {
    "phone":     ["thing_phone.png", "thing_wave.png"],
    "vacuum":    ["thing_glasses_vacuum.png", "thing_phone.png"],
    "family":    ["thing_family.png", "thing_phone.png"],
    "question":  ["thing_question.png", "thing_phone.png"],
    "wave":      ["thing_wave.png", "thing_phone.png"],
    "celebrate": ["thing_family.png", "thing_phone.png"],
    "guide":     ["thing_phone.png", "thing_wave.png"],
}

# Mood-mapped speech bubble accent colour
MOOD_ACCENT: dict[str, str] = {
    "phone":     LIGHT_PURPLE,
    "vacuum":    LIGHT_PURPLE,
    "family":    MINT_PINK,
    "question":  LIGHT_PURPLE,
    "wave":      MINT_PINK,
    "celebrate": MINT_PINK,
    "guide":     LIGHT_PURPLE,
}


def _resolve_image(pose: str) -> Path | None:
    for name in POSE_FILES.get(pose, []):
        candidate = ASSETS / name
        if candidate.exists():
            return candidate
    return None


def _img_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _svg_fallback(pose: str, height: int) -> str:
    """A friendly stylised 'fluff blob' fallback used until the real PNGs land.

    Mascot blue from the Centrica family campaign (~#6CC8F4) with eyes, mouth,
    and a tiny 'phone' or 'tool' in hand depending on pose.
    """
    blue = "#6CC8F4"
    blue_dark = "#3DA9DC"
    pink = MINT_PINK
    eye_white = "#FFFFFF"
    pupil = "#1E2A4A"

    # Common body
    body = f"""
      <ellipse cx='100' cy='130' rx='62' ry='72' fill='{blue}'/>
      <!-- shaggy fluff: layered tufts -->
      <path d='M40 130 q-10 -20 -2 -38 q-14 -2 -16 16 q-12 4 -8 22 q-12 10 -2 22'
            fill='{blue}' opacity='0.85'/>
      <path d='M160 130 q10 -20 2 -38 q14 -2 16 16 q12 4 8 22 q12 10 2 22'
            fill='{blue}' opacity='0.85'/>
      <!-- top tuft -->
      <path d='M70 60 q10 -28 30 -28 q20 0 30 28 q-15 -8 -30 -8 q-15 0 -30 8z'
            fill='{blue_dark}'/>
      <!-- feet -->
      <ellipse cx='80'  cy='198' rx='14' ry='8' fill='{blue_dark}'/>
      <ellipse cx='120' cy='198' rx='14' ry='8' fill='{blue_dark}'/>
      <!-- eyes -->
      <ellipse cx='84'  cy='112' rx='12' ry='14' fill='{eye_white}'/>
      <ellipse cx='116' cy='112' rx='12' ry='14' fill='{eye_white}'/>
      <circle  cx='86'  cy='115' r='5' fill='{pupil}'/>
      <circle  cx='118' cy='115' r='5' fill='{pupil}'/>
      <circle  cx='88'  cy='113' r='1.6' fill='white'/>
      <circle  cx='120' cy='113' r='1.6' fill='white'/>
      <!-- mouth -->
      <path d='M88 142 q12 8 24 0' stroke='{pupil}' stroke-width='2.5'
            stroke-linecap='round' fill='none'/>
    """

    overlay = ""
    if pose in ("phone", "guide"):
        overlay = f"""
          <!-- phone -->
          <rect x='150' y='80' width='28' height='44' rx='5' fill='#1E2A4A'/>
          <rect x='154' y='84' width='20' height='32' rx='2' fill='#9AC9FF'/>
          <circle cx='164' cy='122' r='1.6' fill='#9AC9FF'/>
          <!-- arm -->
          <path d='M150 110 q-6 -4 -12 -4' stroke='{blue_dark}' stroke-width='8'
                stroke-linecap='round' fill='none'/>
        """
    elif pose == "vacuum":
        overlay = f"""
          <!-- glasses -->
          <circle cx='84' cy='112' r='15' fill='none' stroke='{pupil}' stroke-width='2'/>
          <circle cx='116' cy='112' r='15' fill='none' stroke='{pupil}' stroke-width='2'/>
          <line x1='99' y1='112' x2='101' y2='112' stroke='{pupil}' stroke-width='2'/>
          <!-- vacuum tube + mini-thing -->
          <path d='M150 165 q14 -2 22 8' stroke='{blue_dark}' stroke-width='4' fill='none'/>
          <ellipse cx='178' cy='180' rx='14' ry='12' fill='{blue}'/>
          <circle cx='175' cy='178' r='2' fill='{pupil}'/>
        """
    elif pose == "family":
        overlay = f"""
          <ellipse cx='40' cy='180' rx='20' ry='22' fill='{blue}'/>
          <circle cx='35' cy='176' r='2' fill='{pupil}'/>
          <circle cx='44' cy='176' r='2' fill='{pupil}'/>
          <ellipse cx='168' cy='180' rx='20' ry='22' fill='{blue}'/>
          <circle cx='163' cy='176' r='2' fill='{pupil}'/>
          <circle cx='172' cy='176' r='2' fill='{pupil}'/>
        """
    elif pose == "celebrate":
        overlay = f"""
          <path d='M30 60 l8 -22 m132 22 l-8 -22 m-30 0 l-2 -22 m-58 22 l2 -22'
                stroke='{pink}' stroke-width='3' stroke-linecap='round'/>
          <circle cx='42' cy='34' r='4' fill='{pink}'/>
          <circle cx='162' cy='34' r='4' fill='{pink}'/>
        """
    elif pose == "question":
        overlay = f"""
          <text x='148' y='70' font-family='Arial' font-size='40' font-weight='800'
                fill='{pink}'>?</text>
        """

    width = int(height * 1.0)
    svg = f"""
    <svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 220'
         width='{width}' height='{height}' aria-label='Centrica Thing mascot'>
      {body}
      {overlay}
    </svg>
    """
    return svg


def _img_html(pose: str, size: Size) -> str:
    height = SIZE_PX[size]
    real = _resolve_image(pose)
    if real:
        return (
            f"<img src='{_img_data_uri(real)}' alt='Thing — {pose}' "
            f"style='height:{height}px;display:block' />"
        )
    # Streamlit 1.30+ strips raw <svg> from st.markdown even with unsafe_allow_html=True.
    # Encoding as a base64 data URI in an <img> tag bypasses the sanitiser.
    svg_bytes = _svg_fallback(pose, height).encode("utf-8")
    b64 = base64.b64encode(svg_bytes).decode("ascii")
    return (
        f"<img src='data:image/svg+xml;base64,{b64}' alt='Thing — {pose}' "
        f"style='height:{height}px;display:block' />"
    )


# ----------------------------------------------------------------------
# Public renderers
# ----------------------------------------------------------------------

def show(
    text: str,
    *,
    pose: Pose = "guide",
    side: Side = "left",
    size: Size = "md",
    title: str | None = None,
    chips: list[str] | None = None,
    cta_label: str | None = None,
    cta_key: str | None = None,
) -> bool:
    """Render a Thing + speech bubble. Returns True if the optional CTA was clicked.

    Use ``cta_label`` to show a primary button beside the speech bubble (e.g.
    'Got it', 'Open the spec', 'Send the email'). Provide ``cta_key`` to make
    the button click identifiable across rerenders.
    """
    accent = MOOD_ACCENT.get(pose, LIGHT_PURPLE)
    chips_html = ""
    if chips:
        chips_html = "".join(
            f"<span class='centrica-pill pill-lavender' style='margin-top:6px'>{c}</span>"
            for c in chips
        )
    title_html = (
        f"<div style='font-weight:700;color:var(--ink-strong);margin-bottom:4px;"
        f"font-family:Arial'>{title}</div>"
        if title else ""
    )

    bubble = f"""
    <div style='position:relative;flex:1;background:var(--card);border:1px solid var(--border);
    border-left:4px solid {accent};border-radius:12px;padding:12px 16px;color:var(--text);
    box-shadow:var(--shadow);max-width:760px'>
      {title_html}
      <div style='font-size:13px;line-height:1.55'>{text}</div>
      <div style='margin-top:6px'>{chips_html}</div>
      <span style='position:absolute;top:18px;{'left:-9px' if side == 'left' else 'right:-9px'};
        width:14px;height:14px;background:var(--card);
        border-{('left' if side == 'left' else 'right')}:1px solid var(--border);
        border-bottom:1px solid var(--border);transform:rotate({'45deg' if side == 'left' else '-45deg'});
        '></span>
    </div>
    """

    mascot = (
        f"<div style='flex-shrink:0;display:flex;align-items:flex-end'>"
        f"{_img_html(pose, size)}</div>"
    )

    parts = [mascot, bubble] if side == "left" else [bubble, mascot]
    container = (
        "<div style='display:flex;align-items:flex-start;gap:18px;"
        "margin:8px 0 14px 0'>" + "".join(parts) + "</div>"
    )
    st.markdown(container, unsafe_allow_html=True)

    if cta_label:
        clicked = st.button(cta_label, type="primary", key=cta_key)
        return bool(clicked)
    return False


def avatar(pose: Pose = "guide", size: Size = "xs") -> str:
    """Return inline HTML for a small mascot avatar (for chat bubbles, headers)."""
    return _img_html(pose, size)


def inline(text: str, pose: Pose = "guide", size: Size = "sm") -> None:
    """Compact one-line variant — small mascot + a single line of guidance."""
    st.markdown(
        f"""
        <div style='display:flex;align-items:center;gap:10px;margin:6px 0'>
          <div style='flex-shrink:0'>{avatar(pose, size)}</div>
          <div style='font-size:13px;color:var(--text)'>{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
