"""
Louisiana Opportunity Zones 2.0 - Developer Connection Portal
=============================================================

Five sections, in order:
  1. Louisiana nomination process   (timeline + key numbers)
  2. Regional partners              (one row per region, nominated-tract counts, OZ page links)
  3. Development incentives         (site readiness / workforce / business costs)
  4. Asset map                      (map, selected-tract details + partner justification, anchors, shortlist)
  5. Tell us about your project     (introduction request routed by region)

DATA SOURCES
  CSV / JSON in the repo   : master data file, la_anchors.csv, tl_2025_22_tract.json
  Google Sheet "Recommendations" : the nominated tracts and each partner's justification
        - optional column "Status": only rows that are blank, "Published", "Nominated" or
          "Approved" appear publicly (see VISIBLE_STATUSES). Without a Status column every row appears.
        - if a tract appears more than once, the newest row with text wins.
  Google Sheet "Regions" (optional): Region, Partner, OZ_URL, Contact_Email
  Google Sheet "Introductions" (create it): receives every introduction request
  Google Sheet "Users" (optional): only used for partner sign-in

SECRETS (optional, .streamlit/secrets.toml)
  require_login = true     -> put the whole site behind partner sign-in (default: public)

All page copy that is still a placeholder lives in CONTENT below.
"""

import html as _html
import re
import ssl
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# --- 0. INITIAL CONFIG ---
st.set_page_config(
    page_title="Louisiana Opportunity Zones 2.0",
    layout="wide",
    initial_sidebar_state="collapsed",
)

try:
    # Kept from the original app so Google Sheets connectivity behaves exactly as before.
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass


def _secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


REQUIRE_LOGIN = str(_secret("require_login", "false")).strip().lower() in ("1", "true", "yes")

# Rows in the Recommendations sheet are public when their Status is one of these (blank counts too).
VISIBLE_STATUSES = {"", "published", "nominated", "approved"}

CATEGORIES = [
    "Housing Development",
    "Business Development",
    "Technology & Research",
    "Healthcare & Community Services",
]

ANCHOR_COLORS = {}  # filled after the anchors load, using the same Bold palette as the original map

# Fallback OZ page links by region name (the "Regions" sheet overrides these).
REGION_OZ_URLS = {
    # "GBREP": "https://example.org/oz",
}

# --- PAGE COPY (replace the bracketed placeholders) ---
CONTENT = {
    "process_intro": "[One or two sentences describing the Louisiana nomination process.]",
    "process_steps": [
        {"title": "Regions recommend", "text": "[One line on how regions identified tracts.]", "date": "[Date]"},
        {"title": "Tracts are documented", "text": "[One line on the case behind each tract.]", "date": "[Date]"},
        {"title": "The state nominates", "text": "[One line on the nomination step.]", "date": "[Date]"},
        {"title": "Developers connect", "text": "[One line on how developers connect.]", "date": "We are here", "now": True},
    ],
    "partners_intro": "[One line on who these organizations are.]",
    "incentives_intro": "[One line on how state and local incentives layer with the federal OZ benefits.]",
    # "rule" decides which tracts an incentive applies to. None = every tract.
    # Supported keys: nmtc (bool), deep_distress (bool), metro ("Metropolitan" / "Rural"),
    #                 regions (list of region names), parishes (list of parish names)
    "incentives": [
        {
            "label": "Site readiness", "question": "Is the site ready to build?", "color": "#4ADE80", "text_color": "#4ADE80",
            "items": [
                {"name": "[Incentive name]", "text": "[What it does, in one line.]", "eligibility": "[Who qualifies]", "rule": None},
                {"name": "[Incentive name]", "text": "[What it does, in one line.]", "eligibility": "[Who qualifies]", "rule": None},
            ],
        },
        {
            "label": "Workforce", "question": "Can I hire and train?", "color": "#60A5FA", "text_color": "#93C5FD",
            "items": [
                {"name": "[Incentive name]", "text": "[What it does, in one line.]", "eligibility": "[Who qualifies]", "rule": None},
                {"name": "[Incentive name]", "text": "[What it does, in one line.]", "eligibility": "[Who qualifies]", "rule": None},
            ],
        },
        {
            "label": "Business costs", "question": "Will the numbers work?", "color": "#FBBF24", "text_color": "#FCD34D",
            "items": [
                {"name": "[Incentive name]", "text": "[What it does, in one line.]", "eligibility": "[Who qualifies]", "rule": None},
                {"name": "[Incentive name]", "text": "[What it does, in one line.]", "eligibility": "[Who qualifies]", "rule": None},
            ],
        },
    ],
    "project_intro": "Your request goes to the regional partner for the tracts you select. [Add expected response time.]",
    "project_steps": [
        {"title": "Routed to the right region", "text": "[One line.]"},
        {"title": "A partner reaches out", "text": "[One line.]"},
        {"title": "Incentives are mapped to your project", "text": "[One line.]"},
    ],
    "privacy_line": "[Privacy and consent line.]",
    "agency": "[Sponsoring agency]",
}

# Master-data column names
POP_COL = "Estimate!!Total!!Population for whom poverty status is determined"
POV_COL = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
MFI_COL = "Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)"
METRO_COL = "Metro Status (Metropolitan/Rural)"

# Session state
for _k, _v in {
    "active_tract": None,
    "shortlist": [],
    "partner": None,
    "_last_search": None,
    "find_parish": "Select a parish",
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# --- HELPERS ---
def safe_float(val):
    try:
        if pd.isna(val) or val == "" or val == "N/A":
            return 0.0
        s = str(val).replace("$", "").replace(",", "").replace("%", "").strip()
        return float(s)
    except Exception:
        return 0.0


def safe_int(val):
    return int(safe_float(val))


def esc(value):
    """HTML-escape any dynamic text. '$' is escaped too so Streamlit never reads it as math."""
    return _html.escape("" if value is None else str(value), quote=True).replace("$", "&#36;")


def safe_url(url):
    u = str(url or "").strip()
    return u if re.match(r"^https?://", u, re.I) else ""


def norm_geoid(value):
    s = str(value).strip()
    if s in ("", "nan", "None", "NaN"):
        return ""
    try:
        s = str(int(float(s)))
    except Exception:
        s = s.split(".")[0]
    return s.zfill(11)


def render(markup):
    """Render an HTML block. Lines are stripped and blank lines removed so Markdown
    never mistakes indentation or a gap for the end of the HTML block."""
    clean = "\n".join(line.strip() for line in markup.splitlines() if line.strip())
    st.markdown(clean, unsafe_allow_html=True)


def spacer(px):
    render(f"<div style='height:{int(px)}px'></div>")


def section(name):
    """A keyed container (Streamlit >= 1.39) so each section can have its own full-bleed band."""
    try:
        return st.container(key=f"sec-{name}")
    except TypeError:
        return st.container()


def plot(fig, **kwargs):
    try:
        return st.plotly_chart(fig, width="stretch", **kwargs)
    except TypeError:
        return st.plotly_chart(fig, use_container_width=True, **kwargs)


def para_html(text):
    text = str(text).replace("\r\n", "\n").strip()
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) <= 1:
        parts = [p.strip() for p in text.split("\n") if p.strip()]
    return "".join(f"<p>{esc(p)}</p>" for p in parts)


# --- 1. DATA ---
@st.cache_data(ttl=3600, show_spinner="Loading Louisiana data...")
def load_assets():
    gj = None
    if os.path.exists("tl_2025_22_tract.json"):
        with open("tl_2025_22_tract.json", "r") as f:
            gj = json.load(f)

    def read_csv_with_fallback(path):
        for enc in ["utf-8", "latin1", "cp1252"]:
            try:
                return pd.read_csv(path, encoding=enc)
            except Exception:
                continue
        return pd.read_csv(path)

    master = read_csv_with_fallback("Opportunity Zones 2.0 - Master Data File.csv")
    master["geoid_str"] = master["11-digit FIP"].astype(str).str.split(".").str[0].str.zfill(11)

    master["Eligibility_Status"] = master["Opportunity Zones Insiders Eligibilty"].apply(
        lambda x: "Eligible" if str(x).strip().lower() in ["eligible", "yes", "1", "true"] else "Ineligible"
    )

    def get_nmtc_status(row):
        is_deep = str(row.get("Deep Distress", "")).strip().upper()
        is_eligible = str(row.get("NMTC Eligible", "")).strip().upper()
        if is_deep in ["YES", "TRUE", "1"]:
            return "Deep Distress"
        elif is_eligible in ["YES", "TRUE", "1"]:
            return "Eligible"
        return "Ineligible"

    master["NMTC_Calculated"] = master.apply(get_nmtc_status, axis=1)

    anchors = read_csv_with_fallback("la_anchors.csv")
    anchors["Lat"] = pd.to_numeric(anchors["Lat"], errors="coerce")
    anchors["Lon"] = pd.to_numeric(anchors["Lon"], errors="coerce")
    anchors = anchors.dropna(subset=["Lat", "Lon"])
    anchors["Type"] = anchors["Type"].astype(str).str.strip()
    type_mapping = {
        "Rural Healthcare Facility": "Rural Healthcare Facility",
        "Medical": "Rural Healthcare Facility",
        "Land": "Land",
        "Buildings": "Buildings",
        "Louisiana Main Street": "Main Street",
        "Main Street": "Main Street",
        "Certified Site": "Certified Site",
        "Fastsites": "FastSite",
        "FastSite": "FastSite",
        "Fast Site": "FastSite",
    }
    anchors["Type"] = anchors["Type"].map(type_mapping)
    anchors = anchors.dropna(subset=["Type"]).reset_index(drop=True)

    centers = {}
    if gj:
        for feature in gj["features"]:
            geoid = feature["properties"].get("GEOID") or feature["properties"].get("GEOID20")
            try:
                geom = feature["geometry"]
                if geom["type"] == "Polygon":
                    pts = np.array(geom["coordinates"][0])
                elif geom["type"] == "MultiPolygon":
                    pts = np.array(geom["coordinates"][0][0])
                centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
            except Exception:
                continue
    return gj, master, anchors, centers


def _empty_nominations():
    return pd.DataFrame(columns=["geoid_str", "justification", "category", "username", "status"])


def _coalesce(frame, prefix):
    """First non-blank value across columns named <prefix>, <prefix>.1, ... (case-insensitive).
    The Recommendations sheet has duplicated headers, which pandas renames with a '.1' suffix."""
    cols = [c for c in frame.columns if str(c).strip().lower().split(".")[0] == prefix]
    if not cols:
        return pd.Series([""] * len(frame), index=frame.index)
    sub = frame[cols].fillna("").astype(str).apply(lambda s: s.str.strip())
    sub = sub.replace({"nan": "", "None": "", "NaN": ""})
    out = sub.iloc[:, 0]
    for c in sub.columns[1:]:
        out = out.where(out != "", sub[c])
    return out


@st.cache_data(ttl=120, show_spinner=False)
def load_nominations():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        raw = conn.read(worksheet="Recommendations", ttl=0)
    except Exception:
        return _empty_nominations()
    if raw is None or len(raw) == 0:
        return _empty_nominations()

    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    df = pd.DataFrame(
        {
            "geoid_str": _coalesce(raw, "tract").map(norm_geoid),
            "justification": _coalesce(raw, "justification"),
            "category": _coalesce(raw, "category"),
            "username": _coalesce(raw, "username"),
            "status": _coalesce(raw, "status").str.lower(),
        }
    )
    df = df[df["geoid_str"] != ""]
    df = df[df["status"].isin(VISIBLE_STATUSES)]
    if df.empty:
        return _empty_nominations()
    # newest row with text wins for each tract
    df = df.replace("", np.nan).groupby("geoid_str", as_index=False, sort=False).last().fillna("")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_regions_sheet():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Regions", ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame(columns=["region", "partner", "oz_url", "contact_email"])


def save_introduction(row):
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        existing = conn.read(worksheet="Introductions", ttl=0)
    except Exception:
        existing = pd.DataFrame()
    new_row = pd.DataFrame([row])
    updated = new_row if existing is None or existing.empty else pd.concat([existing, new_row], ignore_index=True)
    conn.update(worksheet="Introductions", data=updated)


def save_recommendation(entry):
    conn = st.connection("gsheets", type=GSheetsConnection)
    existing = conn.read(worksheet="Recommendations", ttl=0)
    new_row = pd.DataFrame([entry])
    updated = new_row if existing is None or existing.empty else pd.concat([existing, new_row], ignore_index=True)
    conn.update(worksheet="Recommendations", data=updated)
    load_nominations.clear()


def authenticate(username, password):
    conn = st.connection("gsheets", type=GSheetsConnection)
    users = conn.read(worksheet="Users", ttl="5m")
    users.columns = users.columns.str.strip().str.lower()
    u, p = str(username).strip(), str(password).strip()
    match = users[users["username"].astype(str) == u]
    if match.empty or str(match["password"].values[0]).strip() != p:
        return None
    r = match.iloc[0]
    return {
        "username": u,
        "role": str(r.get("role", "")).strip(),
        "assigned_type": str(r.get("assigned_type", "")).strip(),
        "assigned_value": str(r.get("assigned_value", "")).strip(),
    }


# --- LOAD ---
gj, master_df, anchors_df, tract_centers = load_assets()
ANCHOR_TYPES = sorted(anchors_df["Type"].unique().tolist())
_BOLD = px.colors.qualitative.Bold
ANCHOR_COLORS = {t: _BOLD[i % len(_BOLD)] for i, t in enumerate(ANCHOR_TYPES)}


def _lighten(rgb, amount=0.55):
    """Mix a 'rgb(r, g, b)' color with white so it stays readable on the dark page."""
    m = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", rgb)
    if not m:
        return rgb
    r, g, b = (int(v) for v in m.groups())
    return "rgb({}, {}, {})".format(*(round(c + (255 - c) * amount) for c in (r, g, b)))


# Map markers use the Bold colors on the light basemap; labels and dots on the dark page use lighter tints.
ANCHOR_UI_COLORS = {t: _lighten(c) for t, c in ANCHOR_COLORS.items()}
ID_KEY = "GEOID"
if gj and gj.get("features"):
    ID_KEY = "GEOID" if "GEOID" in gj["features"][0]["properties"] else "GEOID20"

nominations = load_nominations()
nominated = nominations.merge(master_df[["geoid_str", "Parish", "Region"]], on="geoid_str", how="inner")
nominated_ids = set(nominated["geoid_str"])
nominated_by_id = {r["geoid_str"]: r for r in nominated.to_dict("records")}


def build_region_table():
    sheet = load_regions_sheet()
    sheet_by_region = {}
    for rec in sheet.to_dict("records"):
        key = str(rec.get("region", "")).strip().lower()
        if key and key != "nan":
            sheet_by_region[key] = rec
    counts = nominated.groupby("Region").size().to_dict()
    table = []
    for region in sorted(master_df["Region"].dropna().astype(str).unique().tolist()):
        info = sheet_by_region.get(region.strip().lower(), {})
        parishes = sorted(master_df.loc[master_df["Region"] == region, "Parish"].dropna().astype(str).unique().tolist())
        partner = str(info.get("partner", "") or "").strip()
        url = str(info.get("oz_url", "") or "").strip()
        email = str(info.get("contact_email", "") or "").strip()
        table.append(
            {
                "region": region,
                "partner": "" if partner.lower() == "nan" else partner or region,
                "parishes": parishes,
                "url": safe_url(url if url.lower() != "nan" else REGION_OZ_URLS.get(region, "")),
                "email": "" if email.lower() == "nan" else email,
                "count": int(counts.get(region, 0)),
            }
        )
    return table


region_table = build_region_table()
parish_to_region = (
    master_df.dropna(subset=["Parish", "Region"]).drop_duplicates("Parish").set_index("Parish")["Region"].to_dict()
)


# --- 2. STYLES ---
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400;500;600&display=swap');
:root{--bg:#06090F;--bg2:#090E18;--panel:#0C1322;--line:#172033;--line2:#26344E;--text:#EEF2F7;--muted:#8B98AE;--soft:#B6C1D3;--accent:#4ADE80}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#06090F !important;color:#EEF2F7;font-family:'Inter',system-ui,sans-serif !important;scroll-behavior:smooth;overflow-x:hidden}
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],#MainMenu,footer{display:none !important}
[data-testid="stMainBlockContainer"],.block-container{max-width:1280px !important;padding:0 40px !important}
[data-testid="stVerticalBlock"]{gap:0 !important}
[data-testid="stHorizontalBlock"]{gap:24px !important;align-items:flex-end}
[data-testid="stElementContainer"]{width:100%}
[id]{scroll-margin-top:96px}
.g{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));column-gap:24px}
@media (max-width:900px){
.g{grid-template-columns:minmax(0,1fr);row-gap:32px}
.g>*{grid-column:1 / -1 !important;justify-self:start !important}
[data-testid="stMainBlockContainer"],.block-container{padding:0 24px !important}
.oz-nav nav{display:none}
.oz-just{padding:28px !important}
[data-testid="stHorizontalBlock"]{flex-wrap:wrap}
}

/* full-bleed section bands */
.st-key-sec-process,.st-key-sec-incentives,.st-key-sec-project{background:#06090F;box-shadow:0 0 0 100vmax #06090F;clip-path:inset(0 -100vmax)}
.st-key-sec-regions,.st-key-sec-map{background:#090E18;box-shadow:0 0 0 100vmax #090E18;clip-path:inset(0 -100vmax)}
.st-key-sec-process,.st-key-sec-regions,.st-key-sec-incentives,.st-key-sec-map,.st-key-sec-project{position:relative;padding:clamp(88px,11vw,160px) 0}
.st-key-sec-process{padding-top:clamp(120px,14vw,200px)}
.st-key-sec-regions::before,.st-key-sec-incentives::before,.st-key-sec-map::before,.st-key-sec-project::before{content:'';position:absolute;top:0;left:-100vmax;right:-100vmax;border-top:1px solid #172033}

/* nav */
.oz-nav{position:fixed;top:0;left:0;right:0;height:88px;display:flex;align-items:center;justify-content:space-between;gap:24px;padding:0 max(40px,calc((100vw - 1200px)/2));background:rgba(6,9,15,.86);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);border-bottom:1px solid #172033;z-index:999999}
.oz-brand{display:flex;align-items:center;gap:14px;color:#EEF2F7 !important;text-decoration:none !important;font-size:13px;font-weight:500;letter-spacing:.24em;text-transform:uppercase}
.oz-brand i{width:10px;height:10px;border-radius:50%;background:#4ADE80;box-shadow:0 0 16px rgba(74,222,128,.7)}
.oz-nav nav{display:flex;gap:48px}
.oz-nav nav a{color:#B6C1D3 !important;text-decoration:none !important;font-size:12px;font-weight:500;letter-spacing:.18em;text-transform:uppercase}
.oz-nav nav a:hover{color:#4ADE80 !important}
.oz-navcta{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:0 28px;border-radius:999px;border:1px solid #4ADE80;color:#4ADE80 !important;text-decoration:none !important;font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase}

/* type */
.oz-label{font-size:12px;font-weight:500;letter-spacing:.22em;text-transform:uppercase;color:#8B98AE;margin-bottom:40px}
.oz-label b{color:#4ADE80;font-weight:500}
.oz-h1{font-size:clamp(52px,7.8vw,112px) !important;line-height:1 !important;font-weight:200 !important;letter-spacing:-.055em !important;color:#EEF2F7;margin:0 0 80px !important;padding:0 !important}
.oz-h2{font-size:clamp(40px,5.6vw,80px) !important;line-height:1.02 !important;font-weight:200 !important;letter-spacing:-.05em !important;color:#EEF2F7;margin:0 0 48px !important;padding:0 !important}
.oz-h3{font-size:clamp(32px,3.9vw,56px) !important;line-height:1.05 !important;font-weight:200 !important;letter-spacing:-.045em !important;color:#EEF2F7;margin:0 !important;padding:0 !important}
.oz-intro{font-size:18px;line-height:1.75;font-weight:300;color:#8B98AE}
.oz-intro.lg{font-size:20px}
.oz-btn{display:inline-flex;align-items:center;justify-content:center;min-height:58px;padding:0 40px;border-radius:999px;background:#4ADE80;color:#06090F !important;text-decoration:none !important;font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;box-shadow:0 0 56px rgba(74,222,128,.28)}
.oz-tlink{display:inline-flex;align-items:center;gap:8px;min-height:44px;color:#EEF2F7 !important;font-size:12px;font-weight:500;letter-spacing:.16em;text-transform:uppercase;text-decoration:none !important}
.oz-tlink:hover{text-decoration:underline !important;text-underline-offset:6px}
.oz-tlink em{color:#4ADE80;font-style:normal}

/* timeline + stats */
.oz-step{position:relative;padding-top:32px;border-top:1px solid #26344E}
.oz-step i{position:absolute;top:-5px;left:0;width:9px;height:9px;border-radius:50%;background:#26344E}
.oz-step.now{border-top-color:#4ADE80}
.oz-step.now i{background:#4ADE80;box-shadow:0 0 16px rgba(74,222,128,.8)}
.oz-step-top{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:24px}
.oz-num{font-size:12px;font-weight:500;letter-spacing:.22em;color:#4ADE80}
.oz-date{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#8B98AE}
.oz-step.now .oz-date{color:#4ADE80;font-weight:600}
.oz-step-title{font-size:24px;font-weight:300;letter-spacing:-.02em;color:#EEF2F7;margin-bottom:16px}
.oz-step-text{font-size:15px;line-height:1.75;font-weight:300;color:#8B98AE}
.oz-stat b{display:block;font-size:clamp(64px,8.9vw,128px);font-weight:200;letter-spacing:-.06em;line-height:1;color:#EEF2F7}
.oz-stat.acc b{color:#4ADE80}
.oz-stat span{display:block;margin-top:24px;font-size:12px;font-weight:500;letter-spacing:.2em;text-transform:uppercase;color:#8B98AE}

/* rows */
.oz-row{padding:40px 0;border-top:1px solid #172033;align-items:center}
.oz-rows>.oz-row:last-child{border-bottom:1px solid #172033}
.oz-rname{font-size:clamp(28px,2.8vw,40px);font-weight:200;letter-spacing:-.035em;color:#EEF2F7}
.oz-row.hl .oz-rname{color:#4ADE80}
.oz-rsub{font-size:14px;font-weight:300;color:#8B98AE}
.oz-rcount{display:flex;align-items:baseline;gap:10px}
.oz-rcount b{font-size:clamp(36px,3.9vw,56px);font-weight:200;letter-spacing:-.04em;color:#4ADE80;line-height:1}
.oz-rcount span{font-size:12px;color:#8B98AE}
.oz-akind{display:flex;align-items:center;gap:10px;font-size:11px;font-weight:500;letter-spacing:.2em;text-transform:uppercase}
.oz-akind i{width:8px;height:8px;border-radius:50%}
.oz-aname{font-size:clamp(24px,2.5vw,36px);font-weight:200;letter-spacing:-.035em;color:#EEF2F7}

/* incentives */
.oz-band{padding:72px 0;border-top:1px solid #172033;align-items:start}
.oz-bands>.oz-band:last-child{border-bottom:1px solid #172033}
.oz-bhead{display:flex;align-items:center;gap:12px;margin-bottom:24px;font-size:12px;font-weight:500;letter-spacing:.2em;text-transform:uppercase}
.oz-bhead i{width:8px;height:8px;border-radius:50%}
.oz-bq{font-size:clamp(26px,2.5vw,36px);line-height:1.15;font-weight:200;letter-spacing:-.035em;color:#EEF2F7}
.oz-items{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:40px 24px}
.oz-iname{font-size:18px;font-weight:500;color:#EEF2F7}
.oz-itext{margin:12px 0 16px;font-size:15px;line-height:1.75;font-weight:300;color:#8B98AE}
.oz-ielig{font-size:12px;letter-spacing:.06em;color:#8B98AE}

/* selected tract */
.oz-kicker{font-size:11px;font-weight:500;letter-spacing:.22em;text-transform:uppercase;color:#8B98AE;margin-bottom:20px}
.oz-kicker.acc{color:#4ADE80}
.oz-chip{display:inline-flex;align-items:center;gap:8px;padding:7px 16px;border-radius:999px;border:1px solid #26344E;font-size:12px;color:#EEF2F7}
.oz-chip i{width:6px;height:6px;border-radius:50%}
.oz-chips{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.oz-ks{display:flex;gap:24px;margin-top:56px;padding:32px 0;border-top:1px solid #172033;border-bottom:1px solid #172033}
.oz-ks div{flex:1;min-width:0}
.oz-ks b{display:block;font-size:clamp(26px,2.5vw,36px);font-weight:200;letter-spacing:-.04em;line-height:1;color:#EEF2F7}
.oz-ks span{display:block;margin-top:12px;font-size:11px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:#8B98AE}
.oz-kvs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 32px}
.oz-kv{display:flex;justify-content:space-between;gap:12px;padding:18px 0;border-bottom:1px solid #172033;font-size:14px;color:#EEF2F7}
.oz-kv span{color:#8B98AE;font-weight:300}
.oz-just{padding:48px;border-radius:24px;background:#0C1322;border:1px solid #172033;display:flex;flex-direction:column;gap:24px}
.oz-just p{margin:0 !important;font-size:17px;line-height:1.85;font-weight:300;color:#D5DCE8}
.oz-just .by{padding-top:24px;border-top:1px solid #172033;font-size:13px;font-weight:300;color:#8B98AE}
.oz-key{display:flex;flex-wrap:wrap;gap:12px 28px;font-size:12px;color:#B6C1D3;padding-bottom:14px}
.oz-key span{display:inline-flex;align-items:center;gap:8px}
.oz-key i{width:14px;height:14px;border-radius:3px;display:inline-block}
.oz-empty{padding:64px 0;border-top:1px solid #172033;border-bottom:1px solid #172033;font-size:18px;font-weight:300;color:#8B98AE}
.oz-count{text-align:right;font-size:13px;font-weight:300;color:#8B98AE;padding-bottom:12px}
.oz-count b{display:block;font-size:40px;font-weight:200;letter-spacing:-.04em;line-height:1;color:#4ADE80;margin-bottom:8px}
.oz-pstep{display:flex;gap:24px;padding-top:32px;border-top:1px solid #172033;margin-bottom:48px}
.oz-pstep .n{flex:none;font-size:12px;font-weight:500;letter-spacing:.2em;color:#4ADE80;padding-top:5px}
.oz-pstep .t{font-size:20px;font-weight:300;letter-spacing:-.01em;color:#EEF2F7;margin-bottom:10px}
.oz-pstep .d{font-size:15px;line-height:1.75;font-weight:300;color:#8B98AE}
.oz-footer{padding:56px 0;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px 40px;color:#8B98AE;font-size:12px;letter-spacing:.14em;text-transform:uppercase}
.oz-footer nav{display:flex;flex-wrap:wrap;gap:0 36px}
.oz-footer a{color:#B6C1D3 !important;text-decoration:none !important;font-weight:500;letter-spacing:.16em;padding:14px 0}

.oz-th{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;padding:40px 0;border-top:1px solid #172033;border-bottom:1px solid #172033}
.oz-pop{text-align:right}
.oz-pop b{display:block;font-size:clamp(32px,3.9vw,56px);font-weight:200;letter-spacing:-.045em;line-height:1;color:#EEF2F7}
.oz-pop span{display:block;margin-top:10px;font-size:11px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:#8B98AE}
.oz-mgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));column-gap:24px;border-top:1px solid #172033;margin-top:4px}
.oz-m{padding:28px 0;border-bottom:1px solid #172033}
.oz-m b{display:block;font-size:clamp(22px,2.2vw,32px);font-weight:200;letter-spacing:-.035em;line-height:1.1;color:#EEF2F7}
.oz-m span{display:block;margin-top:12px;font-size:11px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:#8B98AE}
.oz-arows>.oz-arow:last-child{border-bottom:1px solid #172033}
.oz-arow{padding:24px 0;border-top:1px solid #172033}
.oz-aname2{font-size:22px;font-weight:200;letter-spacing:-.025em;margin:12px 0 8px;color:#EEF2F7}
.oz-arow-foot{display:flex;align-items:center;justify-content:space-between;gap:12px}

/* widgets */
[data-testid="stWidgetLabel"] p,label[data-testid="stWidgetLabel"] p{font-size:12px !important;font-weight:500 !important;letter-spacing:.18em !important;text-transform:uppercase !important;color:#8B98AE !important}
div[data-baseweb="select"]>div{background:transparent !important;border:none !important;border-bottom:1px solid #26344E !important;border-radius:0 !important;min-height:52px;box-shadow:none !important}
div[data-baseweb="select"] *{color:#EEF2F7 !important;font-family:'Inter',sans-serif !important;font-size:16px !important;font-weight:300 !important}
div[data-baseweb="select"] svg{fill:#8B98AE !important}
div[data-baseweb="popover"]>div,div[data-baseweb="popover"] ul,ul[role="listbox"]{background:#0C1322 !important;border-radius:12px}
li[role="option"]{background:#0C1322 !important;color:#EEF2F7 !important}
li[role="option"]:hover,li[aria-selected="true"]{background:#16233B !important}
span[data-baseweb="tag"]{background:transparent !important;border:1px solid #26344E !important;border-radius:999px !important;height:40px;padding-left:16px}
span[data-baseweb="tag"] span{color:#EEF2F7 !important;font-size:13px !important;font-weight:400 !important}
span[data-baseweb="tag"] svg{fill:#8B98AE !important}
div[data-baseweb="input"],div[data-baseweb="base-input"],div[data-baseweb="textarea"]{background:transparent !important;border:none !important;border-bottom:1px solid #26344E !important;border-radius:0 !important}
div[data-baseweb="input"]>div,div[data-baseweb="base-input"]>div{background:transparent !important}
div[data-baseweb="input"] input,div[data-baseweb="base-input"] input,div[data-baseweb="textarea"] textarea,textarea{background:transparent !important;color:#EEF2F7 !important;font-family:'Inter',sans-serif !important;font-size:17px !important;font-weight:300 !important;padding-left:0 !important;-webkit-text-fill-color:#EEF2F7}
input::placeholder,textarea::placeholder{color:#8B98AE !important;-webkit-text-fill-color:#8B98AE}
input:disabled{-webkit-text-fill-color:#B6C1D3 !important;opacity:1 !important}
.stButton>button,.stFormSubmitButton>button,.stDownloadButton>button{border-radius:999px !important;min-height:56px;padding:0 36px !important;font-family:'Inter',sans-serif !important;background:transparent !important;color:#EEF2F7 !important;border:1px solid #26344E !important;box-shadow:none !important}
.stButton>button *,.stFormSubmitButton>button *,.stDownloadButton>button *{color:inherit !important;font-size:12px !important;font-weight:600 !important;letter-spacing:.14em !important;text-transform:uppercase !important}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:#4ADE80 !important;color:#4ADE80 !important}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"],button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{background:#4ADE80 !important;color:#06090F !important;border:none !important;box-shadow:0 0 48px rgba(74,222,128,.25) !important}
.stButton>button[kind="primary"]:hover{color:#06090F !important}
.stButton{display:flex;justify-content:flex-start}
[data-testid="stForm"]{border:none !important;padding:0 !important}
[data-testid="stPlotlyChart"]{border-radius:24px;overflow:hidden;border:1px solid #172033;background:#E5E7EB}
[data-testid="stExpander"]{border:1px solid #172033 !important;border-radius:16px !important;background:transparent !important}
[data-testid="stExpander"] summary p{color:#B6C1D3 !important;font-size:12px !important;letter-spacing:.16em;text-transform:uppercase}
[data-testid="stAlert"]{background:#0C1322 !important;border:1px solid #26344E !important;border-radius:16px !important}
[data-testid="stAlert"] *{color:#EEF2F7 !important}
@media (max-width:900px){.oz-mgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --- 3. PARTNER SIGN-IN (optional) ---
def partner_login_form(key):
    with st.form(key):
        u = st.text_input("Username", key=f"{key}_u")
        p = st.text_input("Password", type="password", key=f"{key}_p")
        if st.form_submit_button("Sign in"):
            try:
                who = authenticate(u, p)
            except Exception as exc:
                st.error(f"Error connecting to database: {exc}")
                return
            if who:
                st.session_state["partner"] = who
                st.rerun()
            else:
                st.error("Invalid username or password")


if REQUIRE_LOGIN and not st.session_state["partner"]:
    render("<div style='height:25vh'></div>")
    left, mid, right = st.columns([1, 1, 1])
    with mid:
        render(
            """
            <div class="oz-label"><b>Secure access</b></div>
            <div class="oz-h3" style="margin-bottom:48px !important">Louisiana OZ 2.0 Portal</div>
            """
        )
        partner_login_form("gate_login")
    st.stop()


# --- 4. NAV ---
render(
    """
    <div class="oz-nav">
      <a class="oz-brand" href="#process"><i></i>Louisiana OZ 2.0</a>
      <nav>
        <a href="#process">Process</a><a href="#regions">Partners</a><a href="#incentives">Incentives</a><a href="#map">Asset map</a>
      </nav>
      <a class="oz-navcta" href="#project">Your project</a>
    </div>
    """
)

# --- SECTION 1: NOMINATION PROCESS ---
with section("process"):
    steps_html = ""
    for i, s in enumerate(CONTENT["process_steps"]):
        now = " now" if s.get("now") else ""
        steps_html += (
            f"<div class='oz-step{now}' style='grid-column:span 3'><i></i>"
            f"<div class='oz-step-top'><span class='oz-num'>{i + 1:02d}</span><span class='oz-date'>{esc(s.get('date', ''))}</span></div>"
            f"<div class='oz-step-title'>{esc(s['title'])}</div><div class='oz-step-text'>{esc(s['text'])}</div></div>"
        )
    parishes_with = int(nominated["Parish"].nunique()) if len(nominated) else 0
    render(
        f"""
        <div id="process">
          <div class="g">
            <div class="oz-label" style="grid-column:1 / span 12"><b>01</b> &nbsp;/&nbsp; Louisiana nomination process</div>
            <div role="heading" aria-level="1" class="oz-h1" style="grid-column:1 / span 11">How Louisiana nominated its Opportunity Zone 2.0 tracts.</div>
            <div class="oz-intro lg" style="grid-column:1 / span 5">{esc(CONTENT['process_intro'])}</div>
            <div style="grid-column:8 / span 5;align-self:end;display:flex;justify-content:flex-end"><a class="oz-btn" href="#map">Explore the asset map</a></div>
          </div>
          <div class="g" style="margin-top:clamp(96px,12vw,176px)">{steps_html}</div>
          <div class="g" style="margin-top:clamp(80px,10vw,144px)">
            <div class="oz-stat" style="grid-column:span 4"><b>{len(region_table)}</b><span>Regional partners</span></div>
            <div class="oz-stat" style="grid-column:span 4"><b>{parishes_with}</b><span>Parishes with nominations</span></div>
            <div class="oz-stat acc" style="grid-column:span 4"><b>{len(nominated)}</b><span>Nominated tracts</span></div>
          </div>
        </div>
        """
    )

# --- SECTION 2: REGIONAL PARTNERS ---
with section("regions"):
    render(
        """
        <div id="regions">
          <div class="oz-label"><b>02</b> &nbsp;/&nbsp; Regional partners</div>
          <div role="heading" aria-level="2" class="oz-h2" style="max-width:83%">Start with the partner in your region.</div>
        </div>
        """
    )
    c_intro, _gap, c_find = st.columns([5, 2, 5])
    with c_intro:
        render(f"<div class='oz-intro'>{esc(CONTENT['partners_intro'])}</div>")
    highlight_region = None
    with c_find:
        parish_options = ["Select a parish"] + sorted(parish_to_region.keys())
        chosen_parish = st.selectbox("Find your region by parish", parish_options, key="find_parish")
        if chosen_parish != "Select a parish":
            highlight_region = parish_to_region.get(chosen_parish)
            if highlight_region:
                render(
                    f"<div class='oz-rsub' style='margin-top:12px'>{esc(chosen_parish)} is served by "
                    f"<span style='color:#4ADE80'>{esc(highlight_region)}</span>.</div>"
                )
    spacer(112)

    rows_html = ""
    for r in region_table:
        parishes = r["parishes"]
        shown = ", ".join(parishes[:5]) + (f" +{len(parishes) - 5} more" if len(parishes) > 5 else "")
        link = (
            f"<a class='oz-tlink' href='{esc(r['url'])}' target='_blank' rel='noopener' style='grid-column:11 / span 2;justify-self:end'>OZ page <em>↗</em></a>"
            if r["url"]
            else "<span class='oz-rsub' style='grid-column:11 / span 2;justify-self:end'>OZ page soon</span>"
        )
        hl = " hl" if highlight_region and r["region"] == highlight_region else ""
        rows_html += (
            f"<div class='g oz-row{hl}'>"
            f"<div class='oz-rname' style='grid-column:1 / span 4'>{esc(r['partner'])}</div>"
            f"<div class='oz-rsub' style='grid-column:5 / span 4'>{esc(shown)}</div>"
            f"<div class='oz-rcount' style='grid-column:9 / span 2'><b>{r['count']}</b><span>nominated</span></div>"
            f"{link}</div>"
        )
    render(f"<div class='oz-rows'>{rows_html}</div>")

# --- SECTION 3: INCENTIVES ---
with section("incentives"):
    bands_html = ""
    for cat in CONTENT["incentives"]:
        items = "".join(
            f"<div><div class='oz-iname'>{esc(it['name'])}</div><div class='oz-itext'>{esc(it['text'])}</div>"
            f"<div class='oz-ielig'>Eligibility · {esc(it['eligibility'])}</div></div>"
            for it in cat["items"]
        )
        bands_html += (
            f"<div class='g oz-band'>"
            f"<div style='grid-column:1 / span 4'><div class='oz-bhead' style='color:{esc(cat['text_color'])}'>"
            f"<i style='background:{esc(cat['color'])};box-shadow:0 0 12px {esc(cat['color'])}'></i>{esc(cat['label'])}</div>"
            f"<div class='oz-bq'>{esc(cat['question'])}</div></div>"
            f"<div class='oz-items' style='grid-column:5 / span 8'>{items}</div></div>"
        )
    render(
        f"""
        <div id="incentives">
          <div class="oz-label"><b>03</b> &nbsp;/&nbsp; Development incentives</div>
          <div role="heading" aria-level="2" class="oz-h2" style="max-width:83%">Incentives that de-risk the investment.</div>
          <div class="g" style="margin-bottom:112px"><div class="oz-intro" style="grid-column:1 / span 5">{esc(CONTENT['incentives_intro'])}</div></div>
          <div class="oz-bands">{bands_html}</div>
          <div style="margin-top:64px"><a class="oz-tlink" href="#map">See which incentives apply to each tract <em>→</em></a></div>
        </div>
        """
    )


def rule_applies(rule, row, region, parish):
    if not rule:
        return True
    nm = str(row.get("NMTC_Calculated", ""))
    if rule.get("nmtc") and nm not in ("Eligible", "Deep Distress"):
        return False
    if rule.get("deep_distress") and nm != "Deep Distress":
        return False
    if rule.get("metro") and str(rule["metro"]).lower() not in str(row.get(METRO_COL, "")).lower():
        return False
    if rule.get("regions") and region not in rule["regions"]:
        return False
    if rule.get("parishes") and parish not in rule["parishes"]:
        return False
    return True


# --- MAP HELPERS ---
def get_zoom_center(geoids):
    default = {"lat": 30.9, "lon": -91.8}, 6.0
    if not geoids or not gj:
        return default
    lats, lons = [], []
    for feature in gj["features"]:
        if feature["properties"].get(ID_KEY) in geoids:
            geom = feature["geometry"]
            if geom["type"] == "Polygon":
                coords = np.array(geom["coordinates"][0])
                lons.extend(coords[:, 0]); lats.extend(coords[:, 1])
            elif geom["type"] == "MultiPolygon":
                for poly in geom["coordinates"]:
                    coords = np.array(poly[0])
                    lons.extend(coords[:, 0]); lats.extend(coords[:, 1])
    if not lats:
        return default
    center = {"lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2}
    max_diff = max(max(lats) - min(lats), max(lons) - min(lons))
    if max_diff == 0: zoom = 12.5
    elif max_diff < 0.05: zoom = 12.0
    elif max_diff < 0.1: zoom = 11.0
    elif max_diff < 0.3: zoom = 10.0
    elif max_diff < 0.8: zoom = 8.5
    elif max_diff < 1.5: zoom = 7.5
    else: zoom = 6.2
    return center, zoom


def render_map(df, active):
    """Light carto-positron basemap, hairline tract outlines, translucent grey/green fills (green =
    nominated), a navy-outlined selected tract, and the in-map 'Toggle Anchor Assets' legend."""
    map_df = df[["geoid_str", "Parish"]].copy().reset_index(drop=True)
    sel = str(active) if active else None

    def tract_cat(g):
        return 1 if g in nominated_ids else 0

    map_df["Color_Category"] = map_df["geoid_str"].map(tract_cat)
    map_df["hover"] = (
        map_df["Parish"].astype(str) + " · " + map_df["geoid_str"]
        + np.where(map_df["geoid_str"].isin(nominated_ids), " · Nominated", "")
    )
    in_view = sel is not None and sel in set(map_df["geoid_str"])
    focus = {sel} if in_view else set(map_df["geoid_str"])
    center, zoom = get_zoom_center(focus)
    revision_key = sel if in_view else f"{len(focus)}-{min(focus) if focus else ''}"

    fig = go.Figure()
    # Fills are translucent so the light basemap stays visible; one hairline outline for every tract.
    fig.add_trace(
        go.Choroplethmap(
            geojson=gj, locations=map_df["geoid_str"], z=map_df["Color_Category"],
            featureidkey=f"properties.{ID_KEY}",
            colorscale=[[0, "rgba(226,232,240,0.30)"], [1, "rgba(74,222,128,0.55)"]],
            zmin=0, zmax=1, showscale=False,
            marker=dict(opacity=1, line=dict(width=0.7, color="rgba(51,65,85,0.85)")),
            selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
            hovertext=map_df["hover"], hoverinfo="text", name="Census Tracts",
        )
    )
    if in_view:
        # selected tract: deeper fill (green if nominated, neutral otherwise) and a navy outline
        fill = "rgba(21,128,61,0.45)" if sel in nominated_ids else "rgba(15,23,42,0.22)"
        feats = [f for f in gj["features"] if f["properties"].get(ID_KEY) == sel]
        fig.add_trace(
            go.Choroplethmap(
                geojson={"type": "FeatureCollection", "features": feats}, locations=[sel], z=[1],
                featureidkey=f"properties.{ID_KEY}",
                colorscale=[[0, fill], [1, fill]], showscale=False,
                marker=dict(opacity=1, line=dict(width=2.2, color="#06090F")),
                hoverinfo="skip", name="Selected tract",
            )
        )
    for a_type in ANCHOR_TYPES:
        type_data = anchors_df[anchors_df["Type"] == a_type]
        fig.add_trace(
            go.Scattermap(
                lat=type_data["Lat"], lon=type_data["Lon"], mode="markers",
                marker=go.scattermap.Marker(size=11, color=ANCHOR_COLORS[a_type]),
                text=type_data["Name"], hoverinfo="text", name=a_type, visible="legendonly",
            )
        )
    fig.update_layout(
        map=dict(style="carto-positron", zoom=zoom, center=center),
        margin={"r": 0, "t": 0, "l": 0, "b": 0}, paper_bgcolor="rgba(0,0,0,0)", height=700,
        clickmode="event+select", uirevision=revision_key,
        hoverlabel=dict(bgcolor="#06090F", bordercolor="#26344E", font=dict(family="Inter, sans-serif", size=12, color="#EEF2F7")),
        legend=dict(
            title=dict(text="TOGGLE ANCHOR ASSETS", font=dict(size=10, color="#475569", family="Inter, sans-serif")),
            yanchor="top", y=0.97, xanchor="left", x=0.02, itemsizing="constant",
            bgcolor="rgba(255,255,255,0.94)", font=dict(size=11, color="#0F172A", family="Inter, sans-serif"),
            bordercolor="#CBD5E1", borderwidth=1,
        ),
    )
    return fig


def nearest_anchors(lon, lat, types, n=5):
    sub = anchors_df if not types else anchors_df[anchors_df["Type"].isin(types)]
    if sub.empty:
        return sub
    lon1, lat1 = np.radians(lon), np.radians(lat)
    lon2, lat2 = np.radians(sub["Lon"].values), np.radians(sub["Lat"].values)
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return sub.assign(dist=3956 * 2 * np.arcsin(np.sqrt(h))).sort_values("dist").head(n)


def add_to_shortlist(gid):
    current = list(st.session_state.get("shortlist", []))
    if gid not in current:
        current.append(gid)
    st.session_state["shortlist"] = current


def reset_view():
    st.session_state["active_tract"] = None


# --- SECTION 4: ASSET MAP ---
with section("map"):
    render(
        """
        <div id="map">
          <div class="oz-label"><b>04</b> &nbsp;/&nbsp; Asset map</div>
          <div role="heading" aria-level="2" class="oz-h2" style="max-width:83%">Nominated tracts and the assets around them.</div>
          <div class="g" style="margin-bottom:96px"><div class="oz-intro" style="grid-column:1 / span 5">Select a tract to read the regional partner’s case and see what’s nearby.</div></div>
        </div>
        """
    )

    # filters
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        regions_list = sorted(master_df["Region"].dropna().astype(str).unique().tolist())
        selected_region = st.selectbox("Region", ["All Louisiana"] + regions_list, key="f_region")
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana":
        filtered_df = filtered_df[filtered_df["Region"] == selected_region]
    with f2:
        selected_parish = st.selectbox(
            "Parish", ["All in region"] + sorted(filtered_df["Parish"].dropna().astype(str).unique().tolist()), key="f_parish"
        )
    if selected_parish != "All in region":
        filtered_df = filtered_df[filtered_df["Parish"] == selected_parish]
    nom_in_view = nominated[nominated["geoid_str"].isin(filtered_df["geoid_str"])]
    parish_by_gid = nominated.set_index("geoid_str")["Parish"].to_dict()
    with f3:
        PLACEHOLDER = "Search a nominated tract"
        search = st.selectbox(
            "Census tract", [PLACEHOLDER] + sorted(nom_in_view["geoid_str"].tolist()),
            format_func=lambda g: g if g == PLACEHOLDER else f"{g} · {parish_by_gid.get(g, '')}", key="f_tract",
        )
        if search != PLACEHOLDER and search != st.session_state["_last_search"]:
            st.session_state["_last_search"] = search
            st.session_state["active_tract"] = search
            st.rerun()
    with f4:
        scope = selected_parish if selected_parish != "All in region" else (selected_region if selected_region != "All Louisiana" else "Louisiana")
        render(f"<div class='oz-count'><b>{len(nom_in_view)}</b>nominated in {esc(scope)}</div>")

    spacer(40)

    if gj is None:
        st.warning("The tract boundary file (tl_2025_22_tract.json) was not found, so the map cannot be drawn.")
    else:
        active = st.session_state["active_tract"]

        event = plot(
            render_map(filtered_df, active), on_select="rerun", key="oz_map",
            config={"scrollZoom": True},
        )
        try:
            points = event["selection"]["points"]
        except Exception:
            points = []
        for p in points:
            loc = p.get("location") if isinstance(p, dict) else None
            if loc and str(loc) != st.session_state["active_tract"]:
                st.session_state["active_tract"] = str(loc)
                st.rerun()

        spacer(32)
        k1, k3 = st.columns([10, 2])
        with k1:
            render(
                """
                <div class="oz-key">
                  <span><i style="background:#F3F5F9;border:1px solid #94A3B8"></i>Other tracts</span>
                  <span><i style="background:#A5EFC0;border:1px solid #475569"></i>Nominated</span>
                  <span><i style="background:#96C6A8;border:2px solid #06090F"></i>Selected</span>
                  <span style="color:#8B98AE">Use the map legend to show anchor assets</span>
                </div>
                """
            )
        with k3:
            st.button("Reset", key="reset_view", on_click=reset_view)

    # selected tract: header strip, then metrics + justification (left) and nearby anchors (right),
    # the same orientation as the original portal
    spacer(96)
    active = st.session_state["active_tract"]
    match = master_df[master_df["geoid_str"] == str(active)] if active else master_df.iloc[0:0]
    if match.empty:
        render(
            "<div class='oz-empty'>Select a nominated tract on the map to read the regional partner’s case "
            "and see the assets nearby.</div>"
        )
    else:
        row = match.iloc[0]
        gid = str(active)
        parish, region = str(row["Parish"]), str(row["Region"])
        nom = nominated_by_id.get(gid)
        pop = safe_int(row.get(POP_COL, 0))
        nmtc_yes = row["NMTC_Calculated"] in ("Eligible", "Deep Distress")
        deep_yes = row["NMTC_Calculated"] == "Deep Distress"

        chips = ""
        if nom:
            if nom.get("category"):
                chips += f"<span class='oz-chip'>{esc(nom['category'])}</span>"
            chips += f"<span class='oz-chip'><i style='background:#4ADE80'></i>Nominated with {esc(region)}</span>"
        else:
            chips += "<span class='oz-chip'>Not nominated</span>"

        if nom and str(nom.get("justification", "")).strip():
            just_inner = para_html(nom["justification"]) + f"<div class='by'>Submitted by {esc(region)}</div>"
        elif nom:
            just_inner = "<p>The regional partner has not added a justification for this tract yet.</p>"
        else:
            just_inner = "<p>This tract has not been nominated.</p>"

        # header strip: parish, GEOID, population
        render(
            f"""
            <div class="oz-th">
              <div>
                <div class="oz-kicker acc">Selected tract</div>
                <div role="heading" aria-level="3" class="oz-h3">{esc(parish)} Parish</div>
                <div class="oz-rsub" style="margin-top:12px">GEOID {esc(gid)}</div>
              </div>
              <div class="oz-pop"><b>{esc(f'{pop:,}')}</b><span>Population</span></div>
            </div>
            """
        )
        spacer(64)

        col_l, _gap, col_r = st.columns([12, 1, 8])

        with col_l:
            render(
                f"""
                <div class="oz-kicker acc">Tract demographics</div>
                <div class="oz-mgrid">
                  <div class="oz-m"><b>{esc(row.get(METRO_COL, 'N/A'))}</b><span>Metro status</span></div>
                  <div class="oz-m"><b>{'Yes' if nmtc_yes else 'No'}</b><span>NMTC eligible</span></div>
                  <div class="oz-m"><b>{'Yes' if deep_yes else 'No'}</b><span>Deep distress</span></div>
                  <div class="oz-m"><b>{esc(f"{safe_float(row.get(POV_COL, 0)):.1f}%")}</b><span>Poverty</span></div>
                  <div class="oz-m"><b>{esc(f"${safe_float(row.get(MFI_COL, 0)):,.0f}")}</b><span>Median family income</span></div>
                  <div class="oz-m"><b>{esc(f"{safe_float(row.get('Unemployment Rate (%)', 0)):.1f}%")}</b><span>Unemployment</span></div>
                  <div class="oz-m"><b>{esc(f"{safe_int(row.get('Population 18 to 24', 0)):,}")}</b><span>Pop 18–24</span></div>
                  <div class="oz-m"><b>{esc(f"{safe_int(row.get('Population 65 years and over', 0)):,}")}</b><span>Pop 65+</span></div>
                  <div class="oz-m"><b>{esc(f"{safe_float(row.get('Broadband Internet (%)', 0)):.1f}%")}</b><span>Broadband</span></div>
                </div>
                <div class="oz-kicker" style="margin-top:56px">Recommendation category</div>
                <div class="oz-chips">{chips}</div>
                <div class="oz-kicker" style="margin-top:48px">Regional partner’s justification</div>
                <div class="oz-just">{just_inner}</div>
                """
            )

            applicable = [
                c for c in CONTENT["incentives"]
                if any(rule_applies(i.get("rule"), row, region, parish) for i in c["items"])
            ]
            chips_inc = "".join(
                f"<span class='oz-chip'><i style='background:{esc(c['color'])}'></i>{esc(c['label'])}</span>" for c in applicable
            )
            spacer(40)
            render(
                f"<div class='oz-chips'><span class='oz-kicker' style='margin:0 12px 0 0'>Incentives that apply</span>{chips_inc}</div>"
            )
            spacer(32)
            if nom:
                if gid in st.session_state["shortlist"]:
                    render("<div class='oz-rsub'>On your shortlist ✓</div>")
                else:
                    st.button("Add to shortlist", type="primary", key=f"add_{gid}", on_click=add_to_shortlist, args=(gid,))

        with col_r:
            render("<div class='oz-kicker acc'>Nearby anchors &amp; announcements</div>")
            anchor_pick = st.selectbox("Anchor type filter", ["All assets"] + ANCHOR_TYPES, key="anch_filt")
            spacer(24)
            rows = ""
            if gid in tract_centers:
                lon, lat = tract_centers[gid]
                near = nearest_anchors(lon, lat, [] if anchor_pick == "All assets" else [anchor_pick], n=6)
                for _, a in near.iterrows():
                    color = ANCHOR_UI_COLORS.get(a["Type"], "#CBD5E1")
                    url = safe_url(a.get("Link", ""))
                    link = (
                        f"<a class='oz-tlink' href='{esc(url)}' target='_blank' rel='noopener'>Visit site <em>↗</em></a>"
                        if url
                        else ""
                    )
                    rows += (
                        "<div class='oz-arow'>"
                        f"<div class='oz-akind' style='color:{esc(color)}'><i style='background:{esc(color)}'></i>{esc(a['Type'])}</div>"
                        f"<div class='oz-aname2'>{esc(a['Name'])}</div>"
                        f"<div class='oz-arow-foot'><span class='oz-rsub'>{a['dist']:.1f} miles</span>{link}</div></div>"
                    )
            render(
                f"""<div class="oz-arows">{rows if rows else "<div class='oz-rsub'>No anchor assets of this type were found.</div>"}</div>"""
            )

    # shortlist
    spacer(112)
    render("<div style='border-top:1px solid #172033'></div>")
    spacer(40)
    st.session_state["shortlist"] = [g for g in st.session_state["shortlist"] if g in nominated_ids]
    s1, s2 = st.columns([8, 4])
    with s1:
        st.multiselect(
            "Shortlist", sorted(nominated_ids), key="shortlist",
            format_func=lambda g: f"{g} · {parish_by_gid.get(g, '')}",
        )
    with s2:
        sl = st.session_state["shortlist"]
        export = nominated[nominated["geoid_str"].isin(sl)][["geoid_str", "Parish", "Region", "category"]].rename(
            columns={"geoid_str": "Tract", "category": "Category"}
        )
        st.download_button("Export CSV", export.to_csv(index=False).encode("utf-8"), "shortlist.csv", "text/csv", disabled=not sl)
        render("<div style='text-align:right;margin-top:8px'><a class='oz-tlink' href='#project'>Continue <em>→</em></a></div>")
    spacer(40)
    render("<div style='border-top:1px solid #172033'></div>")

# --- SECTION 5: TELL US ABOUT YOUR PROJECT ---
with section("project"):
    render(
        f"""
        <div id="project">
          <div class="oz-label"><b>05</b> &nbsp;/&nbsp; Connect with the region</div>
          <div role="heading" aria-level="2" class="oz-h2" style="max-width:83%">Tell us about your project.</div>
          <div class="g" style="margin-bottom:112px"><div class="oz-intro" style="grid-column:1 / span 5">{esc(CONTENT['project_intro'])}</div></div>
        </div>
        """
    )
    left, _g, right = st.columns([5, 1, 6])
    with left:
        render(
            "".join(
                f"<div class='oz-pstep'><div class='n'>{i + 1:02d}</div><div><div class='t'>{esc(s['title'])}</div><div class='d'>{esc(s['text'])}</div></div></div>"
                for i, s in enumerate(CONTENT["project_steps"])
            )
        )
    with right:
        shortlist_now = st.session_state["shortlist"]
        with st.form("intro_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            name = c1.text_input("Your name", placeholder="Full name")
            firm = c2.text_input("Firm or fund", placeholder="Organization")
            c3, c4 = st.columns(2)
            email = c3.text_input("Work email", placeholder="name@company.com")
            ptype = c4.selectbox("Project type", CATEGORIES)
            st.text_input(
                "Tracts of interest",
                value=", ".join(shortlist_now) if shortlist_now else "",
                placeholder="Tracts from your shortlist appear here",
                disabled=True,
            )
            summary = st.text_area("Project summary", placeholder="Capital range, timeline and what you need from the region.", height=120)
            spacer(24)
            submitted = st.form_submit_button("Send to regional partner", type="primary")
        render(f"<div class='oz-rsub' style='margin-top:16px'>{esc(CONTENT['privacy_line'])}</div>")

        if submitted:
            if not name.strip() or not firm.strip():
                st.error("Please add your name and firm.")
            elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()):
                st.error("Please enter a valid work email address.")
            else:
                regions_hit = sorted({nominated_by_id[g]["Region"] for g in shortlist_now if g in nominated_by_id})
                partners = [r for r in region_table if r["region"] in regions_hit]
                row = {
                    "Timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "Name": name.strip(), "Firm": firm.strip(), "Email": email.strip(),
                    "Project type": ptype, "Tracts": ", ".join(shortlist_now),
                    "Regions": ", ".join(regions_hit),
                    "Routed to": ", ".join(p["partner"] for p in partners),
                    "Routed emails": ", ".join(p["email"] for p in partners if p["email"]),
                    "Summary": summary.strip(),
                }
                try:
                    save_introduction(row)
                    where = ", ".join(p["partner"] for p in partners) or "the regional partners"
                    st.success(f"Thank you. Your request was sent to {where}.")
                except Exception as exc:
                    st.error(f"We could not save your request. Please try again. ({exc})")

# --- FOOTER + PARTNER TOOLS ---
render(
    f"""
    <div class="oz-footer">
      <div>© Louisiana Opportunity Zones 2.0 · {esc(CONTENT['agency'])}</div>
      <nav><a href="#process">Methodology</a><a href="#regions">Contact a partner</a><a href="#project">Your project</a></nav>
    </div>
    """
)

with st.expander("Partner sign-in"):
    partner = st.session_state["partner"]
    if not partner:
        partner_login_form("partner_login")
    else:
        st.caption(f"Signed in as {partner['username']}")
        active = st.session_state["active_tract"]
        match = master_df[master_df["geoid_str"] == str(active)] if active else master_df.iloc[0:0]
        if match.empty:
            st.write("Select a tract on the map to add or update its justification.")
        else:
            prow = match.iloc[0]
            scope_ok = (
                partner["role"].lower().endswith("admin")
                or partner["assigned_type"].lower() == "all"
                or str(prow["Region"]).strip().lower() == partner["assigned_value"].strip().lower()
                or partner["assigned_value"].strip().lower() in ("", "all")
            )
            st.write(f"**{prow['Parish']}** · {active}")
            if not scope_ok:
                st.warning("This tract is outside your assigned region.")
            else:
                existing = nominated_by_id.get(str(active), {})
                cat = st.selectbox(
                    "Category", CATEGORIES,
                    index=CATEGORIES.index(existing["category"]) if existing.get("category") in CATEGORIES else 0,
                    key="pt_cat",
                )
                text = st.text_area("Justification", value=existing.get("justification", ""), height=200, key=f"pt_just_{active}")
                if st.button("Save justification", key="pt_save"):
                    try:
                        save_recommendation(
                            {
                                "username": partner["username"], "Tract": str(active), "Parish": prow["Parish"],
                                "Category": cat, "Justification": text,
                                "Population": safe_int(prow.get(POP_COL, 0)),
                                "Poverty": f"{safe_float(prow.get(POV_COL, 0)):.1f}%",
                                "MFI": f"${safe_float(prow.get(MFI_COL, 0)):,.0f}",
                                "Broadband": f"{safe_float(prow.get('Broadband Internet (%)', 0)):.1f}%",
                                "Status": "Submitted",
                            }
                        )
                        st.success("Saved. It appears publicly once its Status is set to Published in the sheet.")
                    except Exception as exc:
                        st.error(f"Cloud save failed: {exc}")
        if st.button("Sign out", key="pt_out"):
            st.session_state["partner"] = None
            st.rerun()