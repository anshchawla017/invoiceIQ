"""
src/ui.py
-----------
Shared look-and-feel helpers: theme CSS, motion, page headers, KPI cards,
Plotly styling, number formatting. Every view uses these so the app stays
consistent.

Design choices:
  * one calm accent colour (sky blue); red/orange/amber/green are reserved
    for RISK so a colour always means something
  * Sora for headings and the brand, DM Sans for everything else
  * motion has a job: numbers count up, cards rise in once when a page opens,
    charts are revealed left to right, live/critical things pulse softly
  * everything respects "reduce motion" in the operating system
"""

from __future__ import annotations

import html
import json
import re

import streamlit as st

# ---- colour tokens ---------------------------------------------------------
INK, PANEL, LINE = "#0b1220", "#111a2e", "#22304d"
TEXT, MUTED, ACCENT = "#e5e7eb", "#94a3b8", "#38bdf8"
RISK_COLORS = {"Low": "#22c55e", "Medium": "#f59e0b", "High": "#f97316", "Critical": "#ef4444"}
LEVEL_ORDER = ["Low", "Medium", "High", "Critical"]
LEVEL_DOT = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴", "Not scored": "⚪"}
STATUS_COLORS = {"Paid": "#22c55e", "Pending": "#f59e0b", "Overdue": "#ef4444"}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Sora:wght@500;600;700&display=swap');

:root {
  --iq-ink: #0b1220; --iq-panel: #111a2e; --iq-panel-2: #0f1729; --iq-line: #22304d; --iq-line-2: #334766;
  --iq-text: #e5e7eb; --iq-muted: #94a3b8; --iq-soft: #a8b5cc;
  --iq-accent: #38bdf8; --iq-indigo: #818cf8;
  --iq-ease: cubic-bezier(.2, .8, .2, 1);
}

/* ---------- base type ---------- */
.stApp, .stApp button, .stApp input, .stApp textarea, .stApp select {font-family: 'DM Sans', 'Segoe UI', system-ui, sans-serif;}
.stApp h1, .stApp h2, .stApp h3 {font-family: 'Sora', 'DM Sans', 'Segoe UI', sans-serif; letter-spacing: -0.02em;}
.stApp h1 {font-weight: 700; font-size: 2.2rem; line-height: 1.15; margin-bottom: 0; padding-bottom: .6rem; position: relative;}
.stApp h2, .stApp h3 {font-weight: 600; line-height: 1.25;}
.stApp h3 {font-size: 1.28rem;}
.block-container {padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1360px;}

/* ---------- chrome we do not want ---------- */
#MainMenu, footer, .stDeployButton, [data-testid="stAppDeployButton"], [data-testid="stDeployButton"],
[data-testid="stStatusWidget"] {visibility: hidden; display: none;}
[data-testid="stSidebarNav"], [data-testid="stSidebarNavItems"], [data-testid="stSidebarNavSeparator"] {display: none !important;}
header[data-testid="stHeader"] {background: transparent;}

/* ---------- ambient background (sits behind everything) ---------- */
.stApp {isolation: isolate;}
.stApp::before {
  content: ""; position: fixed; inset: -25%; z-index: -1; pointer-events: none;
  background:
    radial-gradient(38% 34% at 18% 22%, rgba(56, 189, 248, .13), transparent 70%),
    radial-gradient(34% 38% at 82% 16%, rgba(129, 140, 248, .12), transparent 70%),
    radial-gradient(42% 38% at 64% 88%, rgba(20, 184, 166, .08), transparent 70%);
  animation: iq-drift 32s ease-in-out infinite alternate;
}
.stApp::after {
  content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background-image: linear-gradient(rgba(148, 163, 184, .045) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(148, 163, 184, .045) 1px, transparent 1px);
  background-size: 46px 46px;
  -webkit-mask-image: radial-gradient(ellipse at 50% 0%, #000 0%, transparent 72%);
          mask-image: radial-gradient(ellipse at 50% 0%, #000 0%, transparent 72%);
}
@keyframes iq-drift {
  0%   {transform: translate3d(0, 0, 0) scale(1);}
  50%  {transform: translate3d(3%, 2%, 0) scale(1.06) rotate(2deg);}
  100% {transform: translate3d(-3%, 3%, 0) scale(1.02) rotate(-2deg);}
}

/* ---------- page header ---------- */
.stApp h1::after {
  content: ""; position: absolute; left: 0; bottom: 0; height: 3px; width: 64px; border-radius: 3px;
  background: linear-gradient(90deg, var(--iq-accent), var(--iq-indigo));
  animation: iq-bar .9s .1s var(--iq-ease) backwards;
}
@keyframes iq-bar {from {width: 0;}}
.page-sub {color: var(--iq-muted); font-size: 1.04rem; margin: 6px 0 1.6rem 0; max-width: 760px; line-height: 1.55;
           animation: iq-fade .7s .15s ease backwards;}
@keyframes iq-fade {from {opacity: 0;}}
@keyframes iq-rise-b {from {opacity: 0; transform: translateY(16px); filter: blur(3px);} to {opacity: 1; transform: none; filter: none;}}
@keyframes iq-sheen-b {to {transform: translateX(260%);}}
@keyframes iq-beam-b {from {transform: translateX(-100%);} to {transform: translateX(300%);}}
@keyframes iq-rise {
  from {opacity: 0; transform: translateY(16px); filter: blur(3px);}
  to   {opacity: 1; transform: none; filter: none;}
}

/* ---------- KPI cards ---------- */
.kpi {
  --accent: #38bdf8;
  position: relative; overflow: hidden; height: 100%; min-width: 0; box-sizing: border-box;
  background: linear-gradient(180deg, rgba(23, 34, 58, .92), rgba(15, 23, 41, .92));
  border: 1px solid var(--iq-line); border-top: 3px solid var(--accent); border-radius: 14px; padding: 16px 18px 15px;
  box-shadow: 0 10px 30px -18px rgba(0, 0, 0, .8);
  animation: iq-rise .7s var(--iq-ease) backwards; animation-delay: calc(var(--i, 0) * 90ms + 80ms);
  transition: transform .25s var(--iq-ease), border-color .25s ease, box-shadow .25s ease;
}
.kpi::before {  /* soft glow from the accent edge */
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(120% 90% at 50% -25%, color-mix(in srgb, var(--accent) 18%, transparent), transparent 62%);
}
.kpi::after {   /* one light sweep when the card appears */
  content: ""; position: absolute; top: 0; bottom: 0; left: 0; width: 60%; pointer-events: none;
  background: linear-gradient(105deg, transparent 30%, rgba(255, 255, 255, .09) 50%, transparent 70%);
  transform: translateX(-130%);
  animation: iq-sheen 1.3s ease-out 1 forwards; animation-delay: calc(var(--i, 0) * 90ms + 450ms);
}
@keyframes iq-sheen {to {transform: translateX(260%);}}
.kpi:hover {transform: translateY(-3px); border-color: var(--iq-line-2); box-shadow: 0 16px 34px -18px rgba(0, 0, 0, .9);}
.kpi .label {position: relative; font-size: .86rem; color: var(--iq-muted); font-weight: 500; line-height: 1.3;}
.kpi .value {position: relative; font-size: clamp(1.4rem, 1.9vw, 1.9rem); font-weight: 700; color: #f8fafc; margin-top: 4px;
             line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
             font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1;}
.kpi .sub {position: relative; font-size: .82rem; color: #8494ad; margin-top: 4px; line-height: 1.35; overflow-wrap: anywhere;}

/* ---------- badges, findings, reasons, notes, steps ---------- */
.badge {display: inline-block; padding: 3px 12px; border-radius: 999px; font-size: .8rem; font-weight: 700; color: #0b1220; line-height: 1.4;}
.badge.critical {animation: iq-pulse 2.2s ease-out infinite;}
@keyframes iq-pulse {
  0%   {box-shadow: 0 0 0 0 rgba(239, 68, 68, .55);}
  70%  {box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);}
  100% {box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);}
}
.reason {background: var(--iq-panel); border: 1px solid var(--iq-line); border-left: 4px solid var(--iq-accent); border-radius: 10px;
         padding: 11px 14px; margin-bottom: 9px; line-height: 1.5; overflow: hidden; overflow-wrap: anywhere;
         animation: iq-rise .6s var(--iq-ease) backwards;}
.reason .pts {float: right; margin: 0 0 4px 14px; padding: 1px 10px; border-radius: 999px; font-weight: 700; font-size: .86rem;
              color: var(--iq-accent); background: rgba(56, 189, 248, .12);}
.finding {position: relative; background: var(--iq-panel); border: 1px solid var(--iq-line); border-radius: 12px; padding: 13px 18px;
          margin-bottom: 10px; line-height: 1.5; overflow-wrap: anywhere;
          animation: iq-rise .6s var(--iq-ease) backwards; animation-delay: calc(var(--i, 0) * 80ms + 120ms);
          transition: border-color .25s ease, transform .25s var(--iq-ease);}
.finding:hover {transform: translateX(3px); border-color: var(--iq-line-2);}
.finding.high {border-left: 4px solid #ef4444; background: linear-gradient(90deg, rgba(239, 68, 68, .09), var(--iq-panel) 45%);}
.finding.medium {border-left: 4px solid #f59e0b; background: linear-gradient(90deg, rgba(245, 158, 11, .08), var(--iq-panel) 45%);}
.finding.info {border-left: 4px solid #38bdf8; background: linear-gradient(90deg, rgba(56, 189, 248, .08), var(--iq-panel) 45%);}
.finding b {color: #f1f5f9;} .finding span {color: var(--iq-soft); font-size: .93rem;}
.note {display: flex; gap: 12px; align-items: flex-start; background: var(--iq-panel-2); border: 1px dashed var(--iq-line-2);
       border-radius: 12px; padding: 14px 16px; color: var(--iq-soft); font-size: .92rem; line-height: 1.6;}
.note::before {content: "i"; flex: 0 0 22px; height: 22px; margin-top: 1px; border-radius: 50%; text-align: center; line-height: 22px;
               font-family: 'Sora', sans-serif; font-weight: 700; font-size: .78rem; color: var(--iq-accent); background: rgba(56, 189, 248, .14);}
.step {position: relative; height: 100%; box-sizing: border-box; background: var(--iq-panel); border: 1px solid var(--iq-line);
       border-radius: 14px; padding: 18px 20px; overflow: hidden;
       animation: iq-rise .7s var(--iq-ease) backwards; animation-delay: calc(var(--i, 0) * 120ms + 100ms);
       transition: border-color .25s ease, transform .25s var(--iq-ease);}
.step:hover {border-color: var(--iq-line-2); transform: translateY(-3px);}
.step h4 {display: flex; align-items: center; gap: 10px; margin: 0 0 8px 0; font-size: 1.05rem; line-height: 1.3;}
.step .n {flex: 0 0 28px; height: 28px; border-radius: 50%; text-align: center; line-height: 28px; font-size: .85rem; font-weight: 700;
          color: #0b1220; background: linear-gradient(135deg, var(--iq-accent), var(--iq-indigo));}
.step p {margin: 0; color: var(--iq-soft); font-size: .93rem; line-height: 1.55;}

/* ---------- invoice detail list ---------- */
.detail {background: var(--iq-panel); border: 1px solid var(--iq-line); border-radius: 14px; padding: 6px 16px; margin-top: 6px;}
.detail .row {display: flex; justify-content: space-between; align-items: baseline; gap: 16px; padding: 9px 0; border-bottom: 1px solid var(--iq-line);}
.detail .row:last-child {border-bottom: 0;}
.detail .k {color: var(--iq-muted); font-size: .88rem; flex: 0 0 auto;}
.detail .v {color: #f1f5f9; font-weight: 600; text-align: right; min-width: 0; overflow-wrap: anywhere;}

/* ---------- animated risk ring ---------- */
@property --iq-p {syntax: '<number>'; inherits: false; initial-value: 0;}
.ring-wrap {display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 8px 0 4px;}
.ring {
  --ring: #38bdf8; --iq-p: 0; position: relative; width: 190px; height: 190px; border-radius: 50%;
  background: conic-gradient(from 0deg, var(--ring) calc(var(--iq-p) * 3.6deg), #1a2740 0);
  filter: drop-shadow(0 0 16px color-mix(in srgb, var(--ring) 45%, transparent));
  animation: iq-ring 1.5s .2s var(--iq-ease) backwards;
}
@keyframes iq-ring {from {--iq-p: 0;}}
.ring::before {content: ""; position: absolute; inset: 15px; border-radius: 50%; background: #0f1729; box-shadow: inset 0 0 0 1px #22304d;}
.ring .mid {position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;}
.ring .num {font-family: 'Sora', sans-serif; font-size: 2.5rem; font-weight: 700; color: #f8fafc; line-height: 1; font-variant-numeric: tabular-nums;}
.ring .of {margin-top: 6px; font-size: .8rem; color: var(--iq-muted);}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {border-right: 1px solid var(--iq-line); background: linear-gradient(180deg, #0d1526 0%, #0b1220 100%);}
[data-testid="stSidebar"] hr {border-color: var(--iq-line); margin: 1rem 0;}
.brand-row {display: flex; align-items: center; gap: 12px; margin: 2px 0 6px;}
.logo {position: relative; flex: 0 0 42px; width: 42px; height: 42px; border-radius: 12px; overflow: hidden;
       background: linear-gradient(135deg, #38bdf8, #6366f1); box-shadow: 0 6px 20px -6px rgba(56, 189, 248, .7);
       animation: iq-glow 3.6s ease-in-out infinite;}
.logo i {position: absolute; left: 10px; height: 3px; border-radius: 2px; background: rgba(255, 255, 255, .92);}
.logo i:nth-child(1) {top: 11px; width: 22px;} .logo i:nth-child(2) {top: 19px; width: 16px;} .logo i:nth-child(3) {top: 27px; width: 20px;}
.logo b {position: absolute; left: 0; right: 0; top: 0; height: 12px;
         background: linear-gradient(180deg, transparent, rgba(255, 255, 255, .55), transparent);
         animation: iq-scan 2.8s ease-in-out infinite;}
@keyframes iq-scan {0% {transform: translateY(-14px);} 100% {transform: translateY(46px);}}
@keyframes iq-glow {0%, 100% {box-shadow: 0 6px 20px -6px rgba(56, 189, 248, .55);} 50% {box-shadow: 0 6px 26px -4px rgba(129, 140, 248, .85);}}
.brand {font-family: 'Sora', sans-serif; font-size: 1.32rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.1;}
.brand-sub {color: var(--iq-muted); font-size: .8rem; line-height: 1.35; margin-top: 3px;}
.brand-tag {color: var(--iq-muted); font-size: .86rem; margin: 6px 0 14px; line-height: 1.4;}

[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {gap: 2px;}
[data-testid="stSidebar"] label[data-baseweb="radio"] {
  position: relative; display: flex; align-items: center; width: 100%; box-sizing: border-box;
  padding: 9px 12px; margin: 0; border-radius: 10px; cursor: pointer; overflow: hidden;
  transition: background .2s ease, transform .2s var(--iq-ease);
}
[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {display: none;}
[data-testid="stSidebar"] label[data-baseweb="radio"] p {margin: 0; font-size: .96rem; font-weight: 500; color: var(--iq-soft); transition: color .2s ease;}
[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {background: rgba(56, 189, 248, .07); transform: translateX(2px);}
[data-testid="stSidebar"] label[data-baseweb="radio"]:hover p {color: #f1f5f9;}
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
  background: linear-gradient(90deg, rgba(56, 189, 248, .2), rgba(129, 140, 248, .05));
}
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p {color: #f8fafc; font-weight: 600;}
[data-testid="stSidebar"] label[data-baseweb="radio"]::before {
  content: ""; position: absolute; left: 0; top: 20%; bottom: 20%; width: 3px; border-radius: 0 3px 3px 0;
  background: linear-gradient(180deg, var(--iq-accent), var(--iq-indigo));
  transform: scaleY(0); transition: transform .3s var(--iq-ease);
}
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked)::before {transform: scaleY(1);}

.status-pill {display: inline-flex; align-items: center; gap: 9px; padding: 7px 13px; border-radius: 999px;
              background: rgba(34, 197, 94, .09); border: 1px solid rgba(34, 197, 94, .28); color: var(--iq-soft); font-size: .86rem;}
.status-pill b {color: #f1f5f9;}
.status-pill .dot {width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: iq-dot 2s ease-out infinite;}
.status-pill.empty {background: rgba(148, 163, 184, .08); border-color: var(--iq-line);}
.status-pill.empty .dot {background: #64748b; animation: none;}
@keyframes iq-dot {0% {box-shadow: 0 0 0 0 rgba(34, 197, 94, .6);} 70% {box-shadow: 0 0 0 8px rgba(34, 197, 94, 0);} 100% {box-shadow: 0 0 0 0 rgba(34, 197, 94, 0);}}

/* ---------- controls ---------- */
.stButton button, .stDownloadButton button {
  border-radius: 10px; font-weight: 600; border: 1px solid var(--iq-line-2); background: rgba(17, 26, 46, .85);
  transition: transform .2s var(--iq-ease), border-color .2s ease, box-shadow .2s ease, background .2s ease;
}
.stButton button:hover, .stDownloadButton button:hover {transform: translateY(-2px); border-color: var(--iq-accent); box-shadow: 0 10px 24px -12px rgba(56, 189, 248, .55);}
.stButton button:active, .stDownloadButton button:active {transform: translateY(0) scale(.98);}
.stButton button[kind="primary"] {border: 0; color: #06121f; background: linear-gradient(135deg, #38bdf8, #818cf8); background-size: 160% 100%;}
.stButton button[kind="primary"]:hover {background-position: 100% 0; box-shadow: 0 12px 28px -10px rgba(99, 102, 241, .75);}
.stButton button[kind="primary"] p {color: #06121f;}
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"], .stTextInput input {border-radius: 10px;}
[data-testid="stExpander"] {border-radius: 12px; border: 1px solid var(--iq-line); background: rgba(17, 26, 46, .55);}
[data-testid="stExpander"] summary {font-weight: 600;}
[data-testid="stAlert"] {border-radius: 12px; animation: iq-rise .5s var(--iq-ease) backwards;}
[data-testid="stFileUploader"] section {border-radius: 14px; border: 1.5px dashed var(--iq-line-2); background: rgba(17, 26, 46, .5); transition: border-color .2s ease, background .2s ease;}
[data-testid="stFileUploader"] section:hover {border-color: var(--iq-accent); background: rgba(56, 189, 248, .06);}
.stCaption, [data-testid="stCaptionContainer"] {line-height: 1.5;}

/* ---------- charts and tables sit on quiet panels ---------- */
[data-testid="stPlotlyChart"], .stPlotlyChart {
  background: rgba(17, 26, 46, .55); border: 1px solid var(--iq-line); border-radius: 14px; padding: 6px 8px; box-sizing: border-box;
  animation: iq-wipe 1s .1s var(--iq-ease) backwards;
}
@keyframes iq-wipe {from {clip-path: inset(0 100% 0 0 round 14px); opacity: .3;} to {clip-path: inset(0 0 0 0 round 14px); opacity: 1;}}
.js-plotly-plot .modebar {opacity: 0; transition: opacity .2s ease;}
.js-plotly-plot:hover .modebar {opacity: 1;}
[data-testid="stDataFrame"] {border: 1px solid var(--iq-line); border-radius: 14px; overflow: hidden;}
[data-testid="stTable"] table {border-collapse: separate; border-spacing: 0; width: 100%; border: 1px solid var(--iq-line); border-radius: 14px; overflow: hidden;}
[data-testid="stTable"] th {background: #0f1729; color: var(--iq-muted); font-weight: 600; padding: 10px 14px;}
[data-testid="stTable"] td {padding: 9px 14px; border-top: 1px solid var(--iq-line);}
[data-testid="stTable"] tr {transition: background .15s ease;}
[data-testid="stTable"] tbody tr:hover {background: rgba(56, 189, 248, .06);}

/* ---------- scrollbars and focus ---------- */
* {scrollbar-width: thin; scrollbar-color: #2b3d5f transparent;}
:focus-visible {outline: 2px solid var(--iq-accent); outline-offset: 2px;}

/* ---------- v3: welcome hero ---------- */
.hero {position: relative; display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 32px; align-items: center;
       padding: 34px 36px; margin-bottom: 22px; border-radius: 22px; overflow: hidden;
       background: linear-gradient(135deg, rgba(20, 32, 58, .9), rgba(12, 19, 36, .9)); border: 1px solid var(--iq-line-2);
       box-shadow: 0 30px 60px -30px rgba(0, 0, 0, .9);}
.hero::before {content: ""; position: absolute; inset: -40%; pointer-events: none;
  background: conic-gradient(from 0deg, transparent 0 60%, rgba(56, 189, 248, .16) 78%, transparent 92%); animation: iq-spin 14s linear infinite;}
.hero > * {position: relative;}
.hero h1 {font-size: clamp(2rem, 3.4vw, 3rem) !important; line-height: 1.08 !important; padding-bottom: .9rem !important; margin: 0 !important;}
.hero p {color: var(--iq-soft); font-size: 1.06rem; line-height: 1.6; margin: 10px 0 0; max-width: 520px;}
.hero .chips {display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px;}
.hero .chip {padding: 5px 13px; border-radius: 999px; font-size: .84rem; font-weight: 600; color: #e2e8f0; background: rgba(148, 163, 184, .12);
             border: 1px solid var(--iq-line-2); animation: iq-rise .7s var(--iq-ease) backwards; animation-delay: calc(var(--i) * 120ms + 500ms);}
.demo {position: relative; height: 250px; perspective: 900px;}
.demo .inv {position: absolute; left: 6%; right: 6%; height: 74px; padding: 12px 16px; box-sizing: border-box; border-radius: 14px;
            background: #14203a; border: 1px solid var(--iq-line-2); box-shadow: 0 14px 30px -14px rgba(0, 0, 0, .9);
            display: flex; justify-content: space-between; align-items: center; gap: 12px; animation: iq-float2 6s ease-in-out infinite;}
.demo .inv:nth-child(1) {top: 0;}
.demo .inv:nth-child(2) {top: 88px; animation-delay: -2s; left: 12%; right: 0;}
.demo .inv:nth-child(3) {top: 176px; animation-delay: -4s;}
.demo .inv .l {min-width: 0;} .demo .inv .id {font-weight: 700; font-size: .92rem; color: #f1f5f9;}
.demo .inv .vd {font-size: .78rem; color: var(--iq-muted); margin-top: 2px;}
.demo .inv .amt {font-weight: 700; font-variant-numeric: tabular-nums; color: #f1f5f9; font-size: .98rem;}
.demo .tag {flex: 0 0 auto; padding: 3px 11px; border-radius: 999px; font-size: .74rem; font-weight: 700; color: #0b1220; opacity: 0; transform: scale(.6);
            animation: iq-pop 6s ease-in-out infinite;}
.demo .tag.ok {background: #22c55e; animation-delay: 1.2s;} .demo .tag.warn {background: #f59e0b; animation-delay: 2.4s;}
.demo .tag.bad {background: #ef4444; animation-delay: 3.4s;}
.demo .scan {position: absolute; left: 0; right: 0; top: 0; height: 3px; border-radius: 3px; z-index: 2;
             background: linear-gradient(90deg, transparent, #38bdf8, transparent); box-shadow: 0 0 22px 4px rgba(56, 189, 248, .7);
             animation: iq-scanY 6s ease-in-out infinite;}
@keyframes iq-scanY {0% {transform: translateY(0); opacity: 0;} 8% {opacity: 1;} 60% {transform: translateY(250px); opacity: 1;} 68%, 100% {transform: translateY(250px); opacity: 0;}}
@keyframes iq-pop {0%, 10% {opacity: 0; transform: scale(.6);} 16%, 84% {opacity: 1; transform: scale(1);} 96%, 100% {opacity: 0; transform: scale(.6);}}
@keyframes iq-float2 {0%, 100% {transform: translateY(0) rotateX(2deg);} 50% {transform: translateY(-7px) rotateX(-1deg);}}
@media (max-width: 900px) {.hero {grid-template-columns: 1fr; padding: 24px;} .demo {height: 220px;}}

/* ---------- v3: pipeline (Data Import progress) ---------- */
.pipe {display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 0; margin: 4px 0 6px;}
.pipe .st {position: relative; padding: 4px 14px 0 0; min-width: 0;}
.pipe .st .dotn {position: relative; z-index: 1; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
                 font-weight: 700; font-size: .92rem; color: var(--iq-muted); background: #14203a; border: 2px solid var(--iq-line-2); transition: all .3s ease;}
.pipe .st::before {content: ""; position: absolute; left: 34px; right: 0; top: 21px; height: 2px; background: var(--iq-line);}
.pipe .st::after {content: ""; position: absolute; left: 34px; top: 21px; height: 2px; width: 0; background: linear-gradient(90deg, #38bdf8, #818cf8);}
.pipe .st:last-child::before, .pipe .st:last-child::after {display: none;}
.pipe .st.done .dotn {color: #06121f; border-color: transparent; background: linear-gradient(135deg, #38bdf8, #818cf8);}
.pipe .st.done::after {animation: iq-line .8s .2s var(--iq-ease) forwards; width: 0;}
@keyframes iq-line {to {width: calc(100% - 34px);}}
.pipe .st.now .dotn {color: #f8fafc; border-color: #38bdf8; animation: iq-ringpulse 1.8s ease-out infinite;}
@keyframes iq-ringpulse {0% {box-shadow: 0 0 0 0 rgba(56, 189, 248, .6);} 70% {box-shadow: 0 0 0 12px rgba(56, 189, 248, 0);} 100% {box-shadow: 0 0 0 0 rgba(56, 189, 248, 0);}}
.pipe .t {margin-top: 10px; font-weight: 600; color: #f1f5f9; font-size: .98rem; line-height: 1.3;}
.pipe .d {margin-top: 3px; color: var(--iq-muted); font-size: .86rem; line-height: 1.45; padding-right: 8px;}
.pipe .st.todo .t {color: var(--iq-soft);}

/* ---------- v3: upload dropzone ---------- */
[data-testid="stFileUploader"] section {position: relative; padding: 26px 22px; overflow: hidden;
  background: linear-gradient(180deg, rgba(56, 189, 248, .05), rgba(17, 26, 46, .5));}
[data-testid="stFileUploader"] section::after {content: ""; position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(100deg, transparent 35%, rgba(56, 189, 248, .10) 50%, transparent 65%); background-size: 250% 100%;
  animation: iq-shine 4.5s ease-in-out infinite;}
@keyframes iq-shine {from {background-position: 150% 0;} to {background-position: -50% 0;}}
[data-testid="stFileUploader"] section:hover {transform: translateY(-2px); box-shadow: 0 18px 40px -24px rgba(56, 189, 248, .7);}
[data-testid="stFileUploader"] section svg {animation: iq-bob 2.6s ease-in-out infinite; color: var(--iq-accent);}
@keyframes iq-bob {0%, 100% {transform: translateY(0);} 50% {transform: translateY(-5px);}}
[data-testid="stFileUploaderFile"] {animation: iq-rise .5s var(--iq-ease) backwards;}

/* ---------- v3: filters and tables ---------- */
[data-testid="stVerticalBlockBorderWrapper"]:has(.iq-panel-mark) {
  border: 1px solid var(--iq-line); border-radius: 16px; background: rgba(17, 26, 46, .6); padding: 6px 10px 10px; box-shadow: 0 14px 34px -22px rgba(0, 0, 0, .9);}
.stTextInput input, [data-baseweb="select"] > div {transition: border-color .2s ease, box-shadow .2s ease, background .2s ease;}
.stTextInput input:focus, [data-baseweb="select"] > div:focus-within {border-color: var(--iq-accent) !important; box-shadow: 0 0 0 3px rgba(56, 189, 248, .22) !important;}
[data-baseweb="tag"] {border-radius: 999px !important; background: rgba(56, 189, 248, .16) !important; border: 1px solid rgba(56, 189, 248, .35); animation: iq-pop-in .3s var(--iq-ease);}
[data-baseweb="tag"] span {color: #e0f2fe !important;}
@keyframes iq-pop-in {from {transform: scale(.7); opacity: 0;}}
[data-testid="stSlider"] [role="slider"] {box-shadow: 0 0 0 5px rgba(56, 189, 248, .18); transition: box-shadow .2s ease, transform .2s var(--iq-ease);}
[data-testid="stSlider"] [role="slider"]:hover {transform: scale(1.15); box-shadow: 0 0 0 8px rgba(56, 189, 248, .25);}
[data-testid="stCheckbox"] label {transition: color .2s ease;} [data-testid="stCheckbox"] label:hover {color: #f8fafc;}
[data-testid="stDataFrame"] {background: rgba(17, 26, 46, .55); box-shadow: 0 14px 34px -22px rgba(0, 0, 0, .9);
  animation: iq-wipe 1s .1s var(--iq-ease) backwards;}
.count-chip {display: inline-flex; align-items: center; gap: 10px; margin: 4px 0 10px; padding: 6px 14px; border-radius: 999px; font-size: .9rem;
             color: var(--iq-soft); background: rgba(56, 189, 248, .09); border: 1px solid rgba(56, 189, 248, .25);}
.count-chip b {color: #f8fafc; font-variant-numeric: tabular-nums;}
.count-chip .bar {position: relative; width: 70px; height: 6px; border-radius: 6px; background: #1a2740; overflow: hidden;}
.count-chip .bar i {position: absolute; left: 0; top: 0; bottom: 0; width: var(--pct); border-radius: 6px; background: linear-gradient(90deg, #38bdf8, #818cf8);
                    animation: iq-fill .8s var(--iq-ease) backwards;}
@keyframes iq-fill {from {width: 0;}}
.iq-empty {display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 34px 20px; border: 1px dashed var(--iq-line-2); border-radius: 16px;
        color: var(--iq-soft); text-align: center; background: var(--iq-panel-2); animation: iq-rise .6s var(--iq-ease) backwards;}
.iq-empty .ico {font-size: 2rem; animation: iq-bob 2.6s ease-in-out infinite;} .iq-empty b {color: #f1f5f9; font-size: 1.05rem;}

/* ---------- v4: fixes from real screenshot ---------- */
/* chart panel: the chart fills the box exactly, so no inner scrollbars */
[data-testid="stPlotlyChart"], .stPlotlyChart {padding: 0 !important; overflow: hidden !important;}
[data-testid="stPlotlyChart"] > div, [data-testid="stPlotlyChart"] .js-plotly-plot, [data-testid="stPlotlyChart"] .plot-container,
[data-testid="stPlotlyChart"] .svg-container {overflow: hidden !important; scrollbar-width: none;}
[data-testid="stPlotlyChart"] ::-webkit-scrollbar {display: none;}
/* breathing room above section headings */
[data-testid="stHeading"] h2, [data-testid="stHeading"] h3, .stApp h2, .stApp h3 {padding-top: 1.1rem;}
.stApp h1 {padding-top: 0;}
/* confirmation banner fades itself away after a few seconds */
.flash {display: flex; align-items: center; gap: 12px; overflow: hidden; padding: 13px 18px; border-radius: 12px; line-height: 1.5;
        color: #bbf7d0; background: rgba(34, 197, 94, .12); border: 1px solid rgba(34, 197, 94, .35);
        animation: iq-flash 7s var(--iq-ease) forwards;}
.flash::before {content: "\2713"; flex: 0 0 24px; height: 24px; border-radius: 50%; text-align: center; line-height: 24px; font-weight: 700; color: #052e16; background: #22c55e;}
@keyframes iq-flash {0% {opacity: 0; transform: translateY(-10px); max-height: 0; padding-top: 0; padding-bottom: 0;}
  8% {opacity: 1; transform: none; max-height: 140px; padding-top: 13px; padding-bottom: 13px;}
  88% {opacity: 1; max-height: 140px; padding-top: 13px; padding-bottom: 13px; margin-bottom: 0;}
  100% {opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-width: 0; margin: 0;}}
</style>
"""

# Streamlit strips <script> tags from markdown, so the count-up lives in a tiny
# zero-height component that copies this script into the main page once.
_MOTION_JS = r"""
(function () {
  function still() { return !!document.getElementById('iq-still-flag'); }
  var RX = /^(\D{0,3}?)(-?\d[\d,]*(?:\.\d+)?)([%KMBx]?)$/;
  function ease(t) { return 1 - Math.pow(1 - t, 3); }
  function run(el) {
    if (el.getAttribute('data-iq-done')) return;
    el.setAttribute('data-iq-done', '1');
    if (still()) return;
    var txt = (el.textContent || '').trim();
    var m = RX.exec(txt);
    if (!m) return;
    var pre = m[1], numStr = m[2], suf = m[3];
    var target = parseFloat(numStr.replace(/,/g, ''));
    if (!isFinite(target)) return;
    var dec = (numStr.split('.')[1] || '').length;
    var comma = numStr.indexOf(',') > -1;
    var delay = parseFloat(el.getAttribute('data-iq-delay') || '0');
    function fmt(v) {
      var s = v.toFixed(dec);
      if (comma) { var p = s.split('.'); p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ','); s = p.join('.'); }
      return pre + s + suf;
    }
    el.textContent = fmt(0);
    var t0 = null, dur = 1000;
    function step(ts) {
      if (t0 === null) t0 = ts;
      var k = Math.min(1, (ts - t0) / dur);
      el.textContent = fmt(target * ease(k));
      if (k < 1) requestAnimationFrame(step); else el.textContent = txt;
    }
    setTimeout(function () { requestAnimationFrame(step); }, delay);
  }
  function grow(chart) {
    if (still() || chart.getAttribute('data-iq-grown')) return;
    var traces = chart.querySelectorAll('.barlayer .trace');
    var lines = chart.querySelectorAll('.scatterlayer .trace .js-line');
    if (!traces.length && !lines.length) return;
    chart.setAttribute('data-iq-grown', '1');
    traces.forEach(function (tr) {
      var bars = tr.querySelectorAll('.points .point path');
      if (!bars.length) return;
      var boxes = [];
      bars.forEach(function (b) { boxes.push(b.getBoundingClientRect()); });
      var sameLeft = boxes.every(function (r) { return Math.abs(r.left - boxes[0].left) < 1.5; });
      var sameBottom = boxes.every(function (r) { return Math.abs(r.bottom - boxes[0].bottom) < 1.5; });
      var horizontal = sameLeft && !sameBottom;
      bars.forEach(function (b, i) {
        b.style.transformBox = 'fill-box';
        b.style.transformOrigin = horizontal ? 'left center' : 'center bottom';
        b.animate([{transform: horizontal ? 'scaleX(0)' : 'scaleY(0)'}, {transform: 'scale(1)'}],
                  {duration: 800, delay: 200 + Math.min(i, 24) * 35, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'backwards'});
      });
    });
    lines.forEach(function (ln) {
      try {
        var len = ln.getTotalLength();
        ln.animate([{strokeDasharray: len + ' ' + len, strokeDashoffset: len}, {strokeDasharray: len + ' ' + len, strokeDashoffset: 0}],
                   {duration: 1400, delay: 200, easing: 'ease-out', fill: 'backwards'});
      } catch (e) {}
    });
  }
  function scan() {
    var n = document.querySelectorAll('[data-iq-count]');
    for (var i = 0; i < n.length; i++) run(n[i]);
    var c = document.querySelectorAll('.js-plotly-plot');
    for (var j = 0; j < c.length; j++) grow(c[j]);
  }
  var queued = false;
  new MutationObserver(function () {
    if (queued) return;
    queued = true;
    requestAnimationFrame(function () { queued = false; scan(); });
  }).observe(document.body, {childList: true, subtree: true});
  scan(); setTimeout(scan, 400); setTimeout(scan, 1200);
})();
"""

_LOADER = (
    "<script>(function(){try{var d=window.parent.document;"
    "if(d.getElementById('iq-motion'))return;"
    "var s=d.createElement('script');s.id='iq-motion';s.text=" + json.dumps(_MOTION_JS) + ";"
    "d.head.appendChild(s);}catch(e){}})();</script>"
)

_HIDE_LOADER_CSS = """
<style>
.element-container:has(iframe[height="0"]), .stElementContainer:has(iframe[height="0"]),
[data-testid="stElementContainer"]:has(iframe[height="0"]), .element-container:has(iframe[srcdoc*="iq-motion"]),
.stElementContainer:has(iframe[srcdoc*="iq-motion"]), [data-testid="stElementContainer"]:has(iframe[srcdoc*="iq-motion"])
{position: absolute; width: 0; height: 0; margin: 0; overflow: hidden;}
</style>
"""

_COUNTABLE = re.compile(r"^\D{0,3}?-?\d[\d,]*(?:\.\d+)?[%KMBx]?$")


def inject_css(animate: bool = True) -> None:
    """animate=False stops every animation and transition on the page."""
    still = "" if animate else ('<style>*, *::before, *::after {animation: none !important; transition: none !important;}'
                                '.stApp::before {display: none;}</style><span id="iq-still-flag"></span>')
    st.markdown(_CSS + _HIDE_LOADER_CSS + still + '<div class="iq-orbs"><i></i><i></i><i></i><i></i></div>',
                unsafe_allow_html=True)
    try:   # newer Streamlit has st.iframe; older versions only have components.html
        if hasattr(st, "iframe"):
            st.iframe(_LOADER, height=1)
        else:
            import streamlit.components.v1 as components
            components.html(_LOADER, height=0)
    except Exception:   # motion is a bonus; the app must never fail because of it
        pass


def _phase() -> str:
    """'a' or 'b'; flips whenever the page changes so CSS animations restart."""
    return st.session_state.get("_iq_phase", "a")


# ---- text helpers ------------------------------------------------------------
def money(x: float) -> str:
    """$1,234,567 for big numbers, $1,234.56 for small ones."""
    if x is None:
        return "-"
    return f"${x:,.0f}" if abs(x) >= 10000 else f"${x:,.2f}"


def level_label(level: str) -> str:
    """'High' -> '🟠 High' so risk levels read at a glance inside tables."""
    return f"{LEVEL_DOT.get(level, '⚪')} {level}"


def page_header(title: str, subtitle: str) -> None:
    if st.session_state.get("_iq_title") != title:
        st.session_state["_iq_title"] = title
        st.session_state["_iq_phase"] = "b" if _phase() == "a" else "a"
    ph = _phase()
    st.markdown(f'<div class="iq-beam ph-{ph}"></div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="page-sub">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def brand_block() -> str:
    """Sidebar logo + name. The bar in the logo scans down the invoice lines."""
    return ('<div class="brand-row"><div class="logo"><i></i><i></i><i></i><b></b></div>'
            '<div><div class="brand">InvoiceIQ</div></div></div>'
            '<div class="brand-tag">Spot risky invoices before you pay them</div>')


def status_pill(n_invoices: int) -> str:
    if n_invoices:
        return f'<div class="status-pill"><span class="dot"></span><span><b>{n_invoices:,}</b> invoices loaded</span></div>'
    return '<div class="status-pill empty"><span class="dot"></span><span>No invoices loaded yet</span></div>'


# ---- building blocks -----------------------------------------------------------
def kpi_row(items: list[tuple]) -> None:
    """items = [(label, value, sub_text, accent_colour, tooltip), ...]; the
    last three parts are optional. The accent colours the top edge and glow.
    Numeric values count up when the page opens."""
    cols = st.columns(len(items))
    for i, (col, item) in enumerate(zip(cols, items)):
        label, value = item[0], str(item[1])
        sub = item[2] if len(item) > 2 else ""
        accent = item[3] if len(item) > 3 else ACCENT
        tip = item[4] if len(item) > 4 else ""
        count = f' data-iq-count="1" data-iq-delay="{i * 90 + 120}"' if _COUNTABLE.match(value) else ""
        card = (f'<div class="kpi ph-{_phase()}" style="--accent:{html.escape(accent)};--i:{i}" title="{html.escape(tip)}">'
                f'<div class="label">{html.escape(str(label))}</div>'
                f'<div class="value"{count}>{html.escape(value)}</div>'
                f'<div class="sub">{html.escape(str(sub))}</div></div>')
        col.markdown(card, unsafe_allow_html=True)


def badge(level: str) -> str:
    colour = RISK_COLORS.get(level, "#64748b")
    cls = "badge critical" if level == "Critical" else "badge"
    return f'<span class="{cls}" style="background:{colour}">{html.escape(str(level))}</span>'


def finding_card(severity: str, headline: str, detail: str, idx: int = 0) -> str:
    return (f'<div class="finding ph-{_phase()} {html.escape(severity)}" style="--i:{int(idx)}"><b>{html.escape(headline)}</b><br>'
            f'<span>{html.escape(detail)}</span></div>')


def step_cards(steps: list[tuple[str, str]]) -> None:
    """A genuine sequence (used on the welcome screen and Data Import)."""
    cols = st.columns(len(steps))
    for i, (col, (title, body)) in enumerate(zip(cols, steps)):
        col.markdown(f'<div class="step ph-{_phase()}" style="--i:{i}"><h4><span class="n">{i + 1}</span>{html.escape(title)}</h4>'
                     f'<p>{html.escape(body)}</p></div>', unsafe_allow_html=True)


def welcome_hero(title: str, body: str) -> None:
    """Landing block for the first run: headline on the left, an animated invoice scan on the right."""
    chips = "".join(f'<span class="chip" style="--i:{i}">{html.escape(c)}</span>'
                    for i, c in enumerate(["Unusual amounts", "Late payments", "Possible duplicates"]))
    demo = (
        '<div class="demo"><div class="scan"></div>'
        '<div class="inv"><div class="l"><div class="id">INV-00412</div><div class="vd">Northwind Supplies</div></div>'
        '<div class="amt">$1,240.00</div><span class="tag ok">Low</span></div>'
        '<div class="inv"><div class="l"><div class="id">INV-00695</div><div class="vd">Copperleaf Ltd</div></div>'
        '<div class="amt">$8,915.50</div><span class="tag warn">Medium</span></div>'
        '<div class="inv"><div class="l"><div class="id">INV-00696</div><div class="vd">Copperleaf Ltd</div></div>'
        '<div class="amt">$8,915.50</div><span class="tag bad">Duplicate?</span></div></div>')
    st.markdown(f'<div class="hero"><div><h1>{html.escape(title)}</h1><p>{html.escape(body)}</p>'
                f'<div class="chips">{chips}</div></div>{demo}</div>', unsafe_allow_html=True)


def pipeline(steps: list[tuple[str, str]], active: int = 0) -> None:
    """Progress steps for a real sequence. Steps before `active` are done, `active` pulses."""
    parts = []
    for i, (title, body) in enumerate(steps):
        cls = "done" if i < active else ("now" if i == active else "todo")
        mark = "&#10003;" if i < active else str(i + 1)
        parts.append(f'<div class="st {cls} ph-{_phase()}"><div class="dotn">{mark}</div>'
                     f'<div class="t">{html.escape(title)}</div><div class="d">{html.escape(body)}</div></div>')
    st.markdown(f'<div class="pipe">{"".join(parts)}</div>', unsafe_allow_html=True)


def panel_mark() -> None:
    """Call first inside `with st.container(border=True):` to give that box the styled filter-panel look."""
    st.markdown('<span class="iq-panel-mark"></span>', unsafe_allow_html=True)


def count_chip(shown: int, total: int, what: str = "invoices") -> None:
    pct = 0 if total == 0 else max(2, min(100, round(100 * shown / total)))
    st.markdown(f'<div class="count-chip">Showing <b data-iq-count="1">{shown:,}</b> of {total:,} {html.escape(what)}'
                f'<span class="bar"><i style="--pct:{pct}%"></i></span></div>', unsafe_allow_html=True)


def empty_state(title: str, hint: str, icon: str = "🔎") -> None:
    st.markdown(f'<div class="iq-empty"><div class="ico">{icon}</div><b>{html.escape(title)}</b>'
                f'<span>{html.escape(hint)}</span></div>', unsafe_allow_html=True)


def flash(text: str) -> None:
    """Green confirmation banner that fades away by itself."""
    st.markdown(f'<div class="flash"><span>{html.escape(text)}</span></div>', unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="note"><div>{html.escape(text)}</div></div>', unsafe_allow_html=True)


def detail_list(pairs: list[tuple[str, str]]) -> None:
    """A tidy label/value list (used for the selected invoice)."""
    rows = "".join(f'<div class="row"><span class="k">{html.escape(str(k))}</span>'
                   f'<span class="v">{html.escape(str(v))}</span></div>' for k, v in pairs)
    st.markdown(f'<div class="detail">{rows}</div>', unsafe_allow_html=True)


def risk_ring(score: float, level: str) -> None:
    """Animated ring that fills to the risk score, with the number counting up."""
    colour = RISK_COLORS.get(level, "#64748b")
    pct = max(0.0, min(100.0, float(score)))
    st.markdown(
        f'<div class="ring-wrap"><div class="ring" style="--ring:{colour};--iq-p:{pct:.1f}">'
        f'<div class="mid"><div class="num" data-iq-count="1">{pct:.1f}</div><div class="of">out of 100</div></div></div>'
        f'{badge(level)}</div>', unsafe_allow_html=True)


def style_fig(fig, height: int = 340, money_axis: str | None = None):
    """Apply the dark, transparent Plotly look. money_axis='x' or 'y' puts a
    $ prefix and thousands separators on that axis.

    Layout rule that prevents overlapping text: the title is pinned to the very
    top-left, the legend (if any) sits in its own row directly above the plot,
    and the top margin is sized to fit both."""
    is_pie = any(t.type == "pie" for t in fig.data)
    has_title = bool(fig.layout.title.text)
    has_legend = (not is_pie and fig.layout.showlegend is not False and len(fig.data) > 1
                  and any(t.showlegend is not False for t in fig.data))
    top = (30 if has_title else 0) + (34 if has_legend else 0) + 22

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=14, r=18, t=top, b=14),
        font=dict(family="DM Sans, Segoe UI, sans-serif", color="#cbd5e1", size=13),
        title=dict(font=dict(size=16, color="#f1f5f9", family="Sora, DM Sans, sans-serif"),
                   x=0, xanchor="left", y=1, yanchor="top", yref="container", pad=dict(t=12, l=6)),
        hoverlabel=dict(bgcolor="#0b1220", bordercolor="#334766", font=dict(family="DM Sans, sans-serif", size=13)),
        transition=dict(duration=600, easing="cubic-in-out"),
    )
    if is_pie:
        fig.update_layout(legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, title_text=""))
        fig.update_traces(selector=dict(type="pie"), textinfo="percent", textposition="outside",
                          texttemplate="%{percent:.1%}", insidetextorientation="horizontal", sort=False,
                          marker=dict(line=dict(color="#0b1220", width=2)))
        fig.update_layout(uniformtext=dict(minsize=12, mode="show"), margin=dict(l=24, r=110, t=top + 22, b=26))
    else:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                                      title_text="", bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(gridcolor="#1a2740", zeroline=False, automargin=True)
    fig.update_yaxes(gridcolor="#1a2740", zeroline=False, automargin=True)
    for t in fig.data:   # value labels on bars must never be clipped or drawn over the bar edge
        if t.type == "bar" and getattr(t, "text", None) is not None:
            t.update(textposition="outside", cliponaxis=False)
    if money_axis == "y":
        fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    elif money_axis == "x":
        fig.update_xaxes(tickprefix="$", tickformat=",.0f")
    return fig


def ensure_scored(df) -> bool:
    """If some invoices have no risk score yet, show a banner with a button
    that runs the analysis. Returns True when everything is scored."""
    if df["analysed"].all():
        return True
    missing = int((~df["analysed"]).sum())
    st.warning(f"{missing:,} invoice(s) have not been scored yet, so risk figures are incomplete.")
    if st.button("Score invoices now", key="run_analysis_banner", type="primary"):
        from src.ml_models import run_full_analysis
        try:
            with st.spinner("Training the models and scoring invoices..."):
                run_full_analysis()
        except Exception as exc:
            st.error(f"Scoring failed: {exc}")
            return False
        st.rerun()
    return False
