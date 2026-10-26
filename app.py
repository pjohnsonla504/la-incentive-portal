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
  CSV "Crosswalk - Towns Cities Parish RLMA and Region.csv" (repo root): towns and cities with their parish, RLMA and
        region. Drives the full parish list on each partner row and the parish-or-city search.

SECRETS (optional, .streamlit/secrets.toml)
  require_login = true     -> put the whole site behind partner sign-in (default: public)

All page copy that is still a placeholder lives in CONTENT below.
"""

import html as _html
import re
import ssl
import json
import os
from datetime import date, datetime, timezone

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

# Crosswalk of towns and cities to parish, RLMA (regional labor market area) and region.
# Column headers are matched loosely (case, spaces and punctuation are ignored). If your headers differ, add them here.
CROSSWALK_FILE = "Crosswalk - Towns Cities Parish RLMA and Region.csv"
# Also accepted, in case the file was uploaded without the "Crosswalk - " prefix. The older
# city-parish-region-crosswalk.csv is never read.
CROSSWALK_ALT_NAMES = ["Towns Cities Parish RLMA and Region.csv", "Town Cities Parish RLMA and Region.csv"]
CROSSWALK_COLUMNS = {
    "town": ["City-Town", "Town", "City", "Town/City", "Town or City", "Towns and Cities", "Towns & Cities", "Municipality", "Place"],
    "parish": ["Parish", "Parish Name"],
    "rlma": ["RLMA", "Regional Labor Market Area"],
    "region": ["Region", "REDO", "Regional Economic Development Organization", "LED Region"],
}

# Official figures from Louisiana Economic Development: display name, tracts nominated, OZ page.
# "aliases" are the other spellings the data may use for the same organization; names are compared
# ignoring case, spaces and punctuation. The master data names Louisiana's geographic regions (Southeast, Northwest,
# Capital, ...); each is listed as an alias so it merges into its REDO instead of showing as a second row.
# A link in the "Regions" sheet overrides oz_url here.
REDO_FACTS = [
    {"name": "GNO, Inc.", "nominated": 48, "oz_url": "https://gnoinc.org/",
     "aliases": ["GNO, Inc.", "GNO", "Greater New Orleans", "Southeast", "Southeast Louisiana", "Southeast Region"]},
    {"name": "NLEP", "nominated": 23, "oz_url": "https://nlep.org/",
     "aliases": ["NLEP", "North Louisiana Economic Partnership", "Northwest", "Northwest Louisiana", "Northwest Region"]},
    {"name": "One Acadiana", "nominated": 22, "oz_url": "https://www.oneacadiana.org/", "aliases": ["One Acadiana", "Acadiana", "Acadiana Region"]},
    {"name": "GBREP", "nominated": 21, "oz_url": "https://greaterbatonrouge.org/",
     "aliases": ["GBREP", "Greater Baton Rouge Economic Partnership", "Greater Baton Rouge", "Capital", "Capital Region"]},
    {"name": "Louisiana Central", "nominated": 13, "oz_url": "https://www.louisiana-central.com/home",
     "aliases": ["Louisiana Central", "Lousiana Central", "LA Central", "Central", "Central Louisiana", "Central Region"]},
    {"name": "Grow NELA", "nominated": 12, "oz_url": "https://grownela.com/", "aliases": ["Grow NELA", "GrowNELA", "Northeast", "Northeast Louisiana", "Northeast Region"]},
    {"name": "Chamber SWLA", "nominated": 9, "oz_url": "https://allianceswla.org/",
     "aliases": ["Chamber SWLA", "SWLA", "Southwest Economic Development Alliance", "SWLA Alliance", "Southwest", "Southwest Louisiana", "Southwest Region"]},
    {"name": "COLAB", "nominated": 8, "oz_url": "https://www.bayouregion.com/", "aliases": ["COLAB", "Bayou Region", "Bayou"]},
]

# Headline figure (Louisiana submitted this many tracts for OZ 2.0)
OZ2_SUBMITTED = 156

# --- PAGE COPY (replace the bracketed placeholders) ---
CONTENT = {
    # Official figures and wording (Louisiana Economic Development). Update here if they change.
    "process_lede": "Final designations are expected by the end of 2026.",
    "approach": [
        "For both rounds of Opportunity Zone nominations, Louisiana utilized a regionally focused approach, incorporating feedback and recommendations from Regional Economic Development Organizations (REDOs); local, state, and federal elected officials; business and industry leaders; site developers; nonprofits; and other community stakeholders.",
        "This collaborative process helped identify census tracts with the strongest potential to attract private investment and advance economic development priorities unique to each region.",
    ],
    "rounds": [
        {
            "name": "Opportunity Zones 1.0", "tag": "2017", "figure": "150", "acc": False,
            "unit": "Census tracts designated, in every region",
            "paras": [
                "In 2017, 150 census tracts spanning every region of Louisiana qualified and were designated as Opportunity Zones. Program benefits associated with these census tracts will sunset on December 31, 2028.",
            ],
        },
        {
            "name": "Opportunity Zones 2.0", "tag": "Designations expected by end of 2026", "figure": "156", "acc": True,
            "unit": "Census tracts submitted for federal consideration",
            "paras": [
                "For OZ 2.0, Louisiana was eligible to nominate up to 25% of qualifying census tracts for Opportunity Zone designation. Working with regional and local partners, Louisiana submitted 156 census tracts for federal consideration.",
                "Final Opportunity Zone 2.0 designations are anticipated by the end of 2026, with new federal incentives taking effect January 1, 2027.",
            ],
        },
    ],
    # Official Opportunity Zone 2.0 timeline. "end" decides when a step counts as complete; the first step
    # that is not complete is marked "We are here". Nothing else needs editing as the dates pass.
    "process_steps": [
        {"title": "Determination of eligible tracts", "when": "Jan 29 – Feb 20, 2026", "end": "2026-02-20"},
        {"title": "REDO recommendation short list", "when": "Jun 1 – Jun 12, 2026", "end": "2026-06-12"},
        {"title": "Governor’s submission deadline", "when": "Wed, Oct 28, 2026", "end": "2026-10-28"},
        {"title": "Final designations", "when": "By end of 2026", "end": "2026-12-31"},
        {"title": "New federal incentives", "when": "Jan 1, 2027", "end": "2027-01-01"},
    ],
    "partners_intro": "Each partner recommended its tracts, wrote the case for them, and can introduce you to the people on the ground.",
    "incentives_intro": "State and local incentives sit on top of the federal Opportunity Zone tax benefit, and they target the site, the workforce and the cost of doing business.",
    # "rule" decides which tracts an incentive applies to. None = every tract.
    # Supported keys: nmtc (bool), deep_distress (bool), metro ("Metropolitan" / "Rural"),
    #                 regions (list of region names), parishes (list of parish names)
    "incentives": [
        {
            "label": "Site readiness", "question": "Get the site ready.", "color": "#16A34A", "text_color": "#0B7A43",
            "items": [
                {"name": "Certified Business Site Program",
                 "text": "Certifies development-ready business sites of 10 to 25 acres after a third-party engineering review, with a 75% state match for site due diligence.",
                 "eligibility": "Sites of at least 10 and under 25 contiguous, buildable acres",
                 "url": "https://www.opportunitylouisiana.gov/why-louisiana/certified-sites/certified-business-sites", "rule": None},
                {"name": "Louisiana FastSites Program",
                 "text": "A $150 million state fund that invests in land and infrastructure to make sites project-ready, structured to be repaid as development occurs.",
                 "eligibility": "Economic development organizations, cities and towns and other public entities; some private sites qualify",
                 "url": "https://www.opportunitylouisiana.gov/fastsites", "rule": None},
            ],
        },
        {
            "label": "Workforce", "question": "Find and train the people.", "color": "#3B82F6", "text_color": "#1D4ED8",
            "items": [
                {"name": "FastStart Program",
                 "text": "Customized recruiting, screening and training for new or expanding companies, at no cost to the company.",
                 "eligibility": "Eligible new or expanding companies aligned with Louisiana’s economic development targets",
                 "url": "https://www.opportunitylouisiana.gov/incentive/led-faststart", "rule": None},
            ],
        },
        {
            "label": "Business costs", "question": "Lower the cost of doing business.", "color": "#D97706", "text_color": "#B45309",
            "items": [
                {"name": "Industrial Tax Exemption Program",
                 "text": "An 80% property tax abatement for up to 10 years on a manufacturer’s new investment.",
                 "eligibility": "Manufacturers, new to Louisiana or investing in an existing facility",
                 "url": "https://www.opportunitylouisiana.gov/incentive/industrial-tax-exemption", "rule": None},
                {"name": "Digital Interactive Media and Software Program",
                 "text": "Refundable tax credits of 18% on qualified production costs, rising to 25% on payroll for Louisiana residents, with no cap and no minimum spend.",
                 "eligibility": "Companies developing digital media or software products in Louisiana",
                 "url": "https://www.louisianaentertainment.gov/interactive/digital-interactive-media-and-software-program", "rule": None},
                {"name": "Restoration Tax Abatement Program",
                 "text": "Abates property taxes on the added value from renovating existing buildings in qualifying areas, including Opportunity Zones.",
                 "eligibility": "Existing structures in Opportunity Zones and in downtown, historic and economic development districts",
                 "url": "https://www.opportunitylouisiana.gov/incentive/restoration-tax-abatement", "rule": None},
                {"name": "High-Impact Jobs Program",
                 "text": "Reimbursable grants of 18% to 22% of wages for new jobs that pay well above the parish average.",
                 "eligibility": "New full-time jobs paying at least 125% of the parish average wage; a lower threshold applies in distressed areas",
                 "url": "https://www.opportunitylouisiana.gov/incentive/high-impact-jobs", "rule": None},
            ],
        },
    ],
    "project_intro": "Your request goes to the regional partner for the tracts you chose, and a person replies. [Add expected response time.]",
    "project_steps": [
        {"title": "Routed to the right region", "text": "[One line.]"},
        {"title": "A partner reaches out", "text": "[One line.]"},
        {"title": "Incentives are mapped to your project", "text": "[One line.]"},
    ],
    "privacy_line": "[Privacy and consent line.]",
    "agency": "[Sponsoring agency]",
}

# Basemap. "retina" = CARTO Positron drawn from high-resolution (@2x) tiles, so labels and roads stay crisp on
# high-DPI screens. "plain" = Plotly's built-in carto-positron (standard-resolution tiles; softer). Flip this
# if the map ever fails to load.
BASEMAP = "retina"


def _basemap_style():
    if BASEMAP == "plain":
        return "carto-positron"
    return {
        "version": 8,
        "sources": {
            "carto": {
                "type": "raster",
                "tiles": ["https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"],
                "tileSize": 256,
                "maxzoom": 20,
                "attribution": "© OpenStreetMap contributors © CARTO",
            }
        },
        "layers": [{"id": "carto", "type": "raster", "source": "carto"}],
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
    "find_place": "Search a parish or city",
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


def _today():
    """Today's date in Louisiana (Central time), so the timeline flips at local midnight."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Chicago")).date()
    except Exception:
        return date.today()


def next_chapter(label, href):
    render(
        f"""
        <div class="oz-next"><span>Next</span><a href="{href}">{esc(label)} <em>→</em></a></div>
        """
    )


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


def _darken(rgb, amount=0.35):
    """Mix a 'rgb(r, g, b)' color with black so labels stay readable on the light page."""
    m = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", rgb)
    if not m:
        return rgb
    r, g, b = (int(v) for v in m.groups())
    return "rgb({}, {}, {})".format(*(round(c * (1 - amount)) for c in (r, g, b)))


# Map markers use the Bold colors; labels and dots on the page use darker tints.
ANCHOR_UI_COLORS = {t: _darken(c) for t, c in ANCHOR_COLORS.items()}
ID_KEY = "GEOID"
if gj and gj.get("features"):
    ID_KEY = "GEOID" if "GEOID" in gj["features"][0]["properties"] else "GEOID20"

nominations = load_nominations()
nominated = nominations.merge(master_df[["geoid_str", "Parish", "Region"]], on="geoid_str", how="inner")
nominated_ids = set(nominated["geoid_str"])
nominated_by_id = {r["geoid_str"]: r for r in nominated.to_dict("records")}


def _norm_name(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _fact_for(region):
    key = _norm_name(region)
    for f in REDO_FACTS:
        if key in {_norm_name(x) for x in f["aliases"] + [f["name"]]}:
            return f
    return None


def _clean_parish(value):
    return re.sub(r"\s+parish$", "", str(value or "").strip(), flags=re.I).strip()


def _detect_crosswalk_columns(df):
    """Map our four fields to the CSV's headers, ignoring case and punctuation. Order matters: RLMA is claimed
    before region so a header such as 'Regional Labor Market Area' is not mistaken for the region."""
    headers = {c: _norm_name(c) for c in df.columns}
    found = {}

    def pick(key, contains):
        exact = {_norm_name(x) for x in CROSSWALK_COLUMNS[key]}
        for c, n in headers.items():
            if c not in found.values() and n in exact:
                found[key] = c
                return
        for c, n in headers.items():
            if c not in found.values() and any(x in n for x in contains):
                found[key] = c
                return

    pick("parish", ["parish"])
    pick("rlma", ["rlma", "labormarket"])
    pick("region", ["region", "redo"])
    pick("town", ["town", "city", "municipal", "place"])
    return found


def _find_crosswalk_file():
    """The towns/cities crosswalk. Exact names first, then the same name ignoring case, spacing and a leading
    "Crosswalk - ", then any CSV that is clearly the towns/cities/RLMA file. The older
    city-parish-region-crosswalk.csv is deliberately never used."""
    names = [CROSSWALK_FILE] + CROSSWALK_ALT_NAMES
    for nm in names:
        if os.path.exists(nm):
            return nm

    def core(name):
        n = _norm_name(name.rsplit(".", 1)[0])
        return n[len("crosswalk"):] if n.startswith("crosswalk") else n

    wanted = {core(n) for n in names}
    files = sorted(f for f in os.listdir(".") if f.lower().endswith(".csv"))
    for f in files:
        if core(f) in wanted:
            return f
    for f in files:
        n = _norm_name(f.rsplit(".", 1)[0])
        if n == "cityparishregioncrosswalk":
            continue
        if "rlma" in n or ("town" in n and "cit" in n):
            return f
    return None


def load_crosswalk():
    """Returns (normalized DataFrame or None, detected columns). Columns: town, parish, rlma, region."""
    path = _find_crosswalk_file()
    if not path:
        return None, {}
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0
    return _read_crosswalk(path, mtime)


@st.cache_data(ttl=3600, show_spinner=False)
def _read_crosswalk(path, mtime):
    """Reads and normalizes the file. The file's modified time is part of the cache key, so a replaced file is
    picked up right away and a failed read is never cached against a newer file."""
    raw = None
    for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
        try:
            raw = pd.read_csv(path, encoding=enc, dtype=str)
            break
        except Exception:
            continue
    if raw is None or raw.empty:
        return None, {}
    raw.columns = [str(c).strip() for c in raw.columns]
    cols = _detect_crosswalk_columns(raw)
    # Layout of the file: column A = city/town, B = parish, C = region, D = RLMA. Used for any column whose header
    # was not recognized, so the file still works if a header is worded differently.
    order = list(raw.columns)
    for key, idx in {"town": 0, "parish": 1, "region": 2, "rlma": 3}.items():
        if key not in cols and idx < len(order) and order[idx] not in cols.values():
            cols[key] = order[idx]
    if "parish" not in cols or "region" not in cols:
        return None, cols
    out = pd.DataFrame(
        {
            "town": raw[cols["town"]] if "town" in cols else "",
            "parish": raw[cols["parish"]].map(_clean_parish),
            "rlma": raw[cols["rlma"]] if "rlma" in cols else "",
            "region": raw[cols["region"]],
        }
    ).fillna("")
    for c in out.columns:
        out[c] = out[c].astype(str).str.strip()
    out = out[(out["parish"] != "") & (out["region"] != "")].reset_index(drop=True)
    return out, cols


def build_region_table():
    """One row per REDO. Names, nominated counts and OZ pages come from REDO_FACTS; parishes come from the
    master data; the optional Regions sheet can override the partner name, link and contact email."""
    sheet = load_regions_sheet()
    sheet_by_name = {}
    for rec in sheet.to_dict("records"):
        key = _norm_name(rec.get("region", ""))
        if key and key != "nan":
            sheet_by_name[key] = rec

    def clean(v):
        v = str(v or "").strip()
        return "" if v.lower() == "nan" else v

    master_regions = sorted(master_df["Region"].dropna().astype(str).unique().tolist())
    computed = nominated.groupby("Region").size().to_dict()
    grouped, extras = {}, []
    for region in master_regions:
        f = _fact_for(region)
        if f:
            grouped.setdefault(f["name"], []).append(region)
        else:
            extras.append(region)

    cw, _cw_cols = load_crosswalk()
    cw_parishes = {}
    if cw is not None:
        for rec in cw.to_dict("records"):
            f_ = _fact_for(rec["region"])
            if f_:
                cw_parishes.setdefault(f_["name"], set()).add(rec["parish"])

    def parishes_of(regions):
        return sorted(master_df.loc[master_df["Region"].isin(regions), "Parish"].dropna().astype(str).map(_clean_parish).unique().tolist())

    table = []
    for f in REDO_FACTS:
        regions = grouped.get(f["name"], [])
        info = next((sheet_by_name[_norm_name(x)] for x in f["aliases"] + [f["name"]] if _norm_name(x) in sheet_by_name), {})
        table.append(
            {
                "region": regions[0] if regions else f["name"],
                "regions": regions,
                "name": f["name"],
                "partner": clean(info.get("partner")) or f["name"],
                "parishes": sorted(cw_parishes[f["name"]]) if f["name"] in cw_parishes else parishes_of(regions),
                "url": safe_url(clean(info.get("oz_url"))) or safe_url(f["oz_url"]),
                "email": clean(info.get("contact_email")),
                "count": f["nominated"],
                "mapped": sum(int(computed.get(x, 0)) for x in regions),
            }
        )
    for region in extras:  # a region in the data that is not one of the official REDOs: show it with computed numbers
        info = sheet_by_name.get(_norm_name(region), {})
        table.append(
            {
                "region": region, "regions": [region], "name": region,
                "partner": clean(info.get("partner")) or region,
                "parishes": parishes_of([region]),
                "url": safe_url(clean(info.get("oz_url"))),
                "email": clean(info.get("contact_email")),
                "count": int(computed.get(region, 0)),
                "mapped": int(computed.get(region, 0)),
            }
        )
    table.sort(key=lambda r: (-r["count"], r["partner"]))
    return table


region_table = build_region_table()


def build_place_index():
    """Every searchable place: label -> {kind, town, parish, rlma, names (the partners that serve it)}."""
    cw, _ = load_crosswalk()
    parish_names, index = {}, {}
    if cw is not None:
        for rec in cw.to_dict("records"):
            f_ = _fact_for(rec["region"])
            nm = f_["name"] if f_ else rec["region"]
            parish_names.setdefault(rec["parish"], set()).add(nm)
    for _, m in master_df.dropna(subset=["Parish", "Region"]).drop_duplicates(["Parish", "Region"]).iterrows():
        p = _clean_parish(m["Parish"])
        if p not in parish_names:  # the crosswalk wins; the master data only fills gaps
            f_ = _fact_for(m["Region"])
            parish_names.setdefault(p, set()).add(f_["name"] if f_ else str(m["Region"]))
    for p, names in parish_names.items():
        index[f"{p} Parish"] = {"kind": "parish", "town": "", "parish": p, "rlma": "", "names": sorted(names)}
    if cw is not None:
        for rec in cw.to_dict("records"):
            if not rec["town"]:
                continue
            f_ = _fact_for(rec["region"])
            nm = f_["name"] if f_ else rec["region"]
            label = f"{rec['town']} · {rec['parish']} Parish"
            item = index.setdefault(label, {"kind": "town", "town": rec["town"], "parish": rec["parish"], "rlma": "", "names": []})
            if nm not in item["names"]:
                item["names"].append(nm)
            if rec["rlma"] and not item["rlma"]:
                item["rlma"] = rec["rlma"]
    return index


place_index = build_place_index()


def render_crosswalk_check():
    """Plain-language report on the crosswalk. Open the app with ?check=1 on the end of the address to see it.
    It shows file names and column names only, nothing sensitive."""
    path = _find_crosswalk_file()
    csvs = sorted(f for f in os.listdir(".") if f.lower().endswith(".csv"))
    cw, found = load_crosswalk()
    towns = int((cw["town"] != "").sum()) if cw is not None else 0
    with st.container():
        st.markdown("**Crosswalk check**")
        st.write(f"CSV files in the repo: {', '.join(csvs) if csvs else 'none'}")
        if not path:
            st.error(f'No crosswalk file found. Expected "{CROSSWALK_FILE}" in the same folder as app.py.')
        else:
            st.write(f"File used: {path}")
            if cw is None:
                st.error(f"The file was found but could not be used. Columns recognized: {found or 'none'}. It needs at least a parish and a region column.")
            else:
                st.write(f"{len(cw)} rows · {towns} with a city or town · columns: " + ", ".join(f"{k} = {v}" for k, v in found.items()))
                if "town" not in found:
                    st.warning("No city or town column was recognized, so only parish search is available.")
                bad = sorted({x for x in cw["region"].unique() if not _fact_for(x)})
                if bad:
                    st.warning("Regions that do not match a partner: " + ", ".join(bad))
        st.write(f"Search options available: {len(place_index)} ({sum(1 for v in place_index.values() if v['kind'] == 'town')} cities and towns)")
parish_to_region = (
    master_df.dropna(subset=["Parish", "Region"]).drop_duplicates("Parish").set_index("Parish")["Region"].to_dict()
)


# --- 2. STYLES ---
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400;500;600&display=swap');
:root{color-scheme:light;--bg:#FFFFFF;--bg2:#F4F6F9;--panel:#FFFFFF;--line:#E3E7EE;--line2:#CBD3DF;--text:#0B1220;--muted:#5B6678;--soft:#3B4658;--accent:#0B7A43}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#FFFFFF !important;color:#0B1220;font-family:'Inter',system-ui,sans-serif !important;scroll-behavior:smooth;overflow-x:hidden}
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],#MainMenu,footer{display:none !important}
[data-testid="stMainBlockContainer"],.block-container{max-width:1280px !important;padding:0 40px !important}
[data-testid="stVerticalBlock"]{gap:0 !important}
[data-testid="stHorizontalBlock"]{gap:24px !important;align-items:flex-end}
[data-testid="stElementContainer"]{width:100%}
[id]{scroll-margin-top:56px}
.g{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));column-gap:24px}
@media (max-width:900px){
.g{grid-template-columns:minmax(0,1fr);row-gap:20px}
.g>*{grid-column:1 / -1 !important;justify-self:start !important}
[data-testid="stMainBlockContainer"],.block-container{padding:0 24px !important}
.oz-nav nav{display:none}
.oz-just{padding:28px !important}
[data-testid="stHorizontalBlock"]{flex-wrap:wrap}
}

/* full-bleed section bands */
.st-key-sec-process,.st-key-sec-incentives,.st-key-sec-project{background:#FFFFFF;box-shadow:0 0 0 100vmax #FFFFFF;clip-path:inset(0 -100vmax)}
.st-key-sec-regions,.st-key-sec-map{background:#F4F6F9;box-shadow:0 0 0 100vmax #F4F6F9;clip-path:inset(0 -100vmax)}
.st-key-sec-process,.st-key-sec-regions,.st-key-sec-incentives,.st-key-sec-map,.st-key-sec-project{position:relative;padding:clamp(56px,6.9vw,100px) 0}
.st-key-sec-process{padding-top:clamp(72px,8.3vw,120px)}
.st-key-sec-regions::before,.st-key-sec-incentives::before,.st-key-sec-map::before,.st-key-sec-project::before{content:'';position:absolute;top:0;left:-100vmax;right:-100vmax;border-top:1px solid #E3E7EE}

/* nav */
.oz-nav{position:fixed;top:0;left:0;right:0;height:88px;display:flex;align-items:center;justify-content:space-between;gap:24px;padding:0 max(40px,calc((100vw - 1200px)/2));background:rgba(255,255,255,.92);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);border-bottom:1px solid #E3E7EE;z-index:999999}
.oz-brand{display:flex;align-items:center;gap:14px;color:#0B1220 !important;text-decoration:none !important;font-size:13px;font-weight:500;letter-spacing:.24em;text-transform:uppercase}
.oz-brand i{width:10px;height:10px;border-radius:50%;background:#16A34A;box-shadow:none}
.oz-nav nav{display:flex;gap:28px}
.oz-nav nav a{color:#3B4658 !important;text-decoration:none !important;font-size:12px;font-weight:500;letter-spacing:.18em;text-transform:uppercase}
.oz-nav nav a:hover{color:#0B7A43 !important}
.oz-navcta{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:0 28px;border-radius:999px;border:1px solid #0B7A43;color:#0B7A43 !important;text-decoration:none !important;font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase}

/* type */
.oz-label{font-size:12px;font-weight:500;letter-spacing:.22em;text-transform:uppercase;color:#5B6678;margin-bottom:24px}
.oz-label b{color:#0B7A43;font-weight:500}
.oz-h1{font-size:clamp(44px,6.1vw,88px) !important;line-height:1 !important;font-weight:200 !important;letter-spacing:-.055em !important;color:#0B1220;margin:0 0 48px !important;padding:0 !important}
.oz-h2{font-size:clamp(34px,3.9vw,56px) !important;line-height:1.02 !important;font-weight:200 !important;letter-spacing:-.05em !important;color:#0B1220;margin:0 0 28px !important;padding:0 !important}
.oz-h3{font-size:clamp(28px,3vw,44px) !important;line-height:1.05 !important;font-weight:200 !important;letter-spacing:-.045em !important;color:#0B1220;margin:0 !important;padding:0 !important}
.oz-intro{font-size:18px;line-height:1.75;font-weight:300;color:#5B6678}
.oz-intro.lg{font-size:20px}
.oz-btn{display:inline-flex;align-items:center;justify-content:center;min-height:58px;padding:0 40px;border-radius:999px;background:#4ADE80;color:#06090F !important;text-decoration:none !important;font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;box-shadow:none}

/* timeline + stats */
.oz-stat b{display:block;font-size:clamp(52px,6.7vw,96px);font-weight:200;letter-spacing:-.06em;line-height:1;color:#0B1220}
.oz-stat.acc b{color:#0B7A43}
.oz-stat span{display:block;margin-top:24px;font-size:12px;font-weight:500;letter-spacing:.2em;text-transform:uppercase;color:#5B6678}

/* rows */
.oz-row{padding:24px 0;border-top:1px solid #E3E7EE;align-items:center}
.oz-rows>.oz-row:last-child{border-bottom:1px solid #E3E7EE}
.oz-rname{font-size:clamp(24px,2.2vw,32px);font-weight:200;letter-spacing:-.035em;color:#0B1220}
.oz-row.hl .oz-rname{color:#0B7A43}
.oz-rsub{font-size:14px;font-weight:300;color:#5B6678}
.oz-rcount{display:flex;align-items:baseline;gap:10px}
.oz-rcount b{font-size:clamp(30px,3vw,44px);font-weight:200;letter-spacing:-.04em;color:#0B7A43;line-height:1}
.oz-rcount span{font-size:12px;color:#5B6678}
.oz-akind{display:flex;align-items:center;gap:10px;font-size:11px;font-weight:500;letter-spacing:.2em;text-transform:uppercase}
.oz-akind i{width:8px;height:8px;border-radius:50%}
.oz-aname{font-size:clamp(22px,2vw,28px);font-weight:200;letter-spacing:-.035em;color:#0B1220}

/* incentives */
.oz-band{padding:44px 0;border-top:1px solid #E3E7EE;align-items:start}
.oz-bands>.oz-band:last-child{border-bottom:1px solid #E3E7EE}
.oz-bhead{display:flex;align-items:center;gap:12px;margin-bottom:24px;font-size:12px;font-weight:500;letter-spacing:.2em;text-transform:uppercase}
.oz-bhead i{width:8px;height:8px;border-radius:50%}
.oz-bq{font-size:clamp(22px,2vw,28px);line-height:1.15;font-weight:200;letter-spacing:-.035em;color:#0B1220}
.oz-items{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px 24px}
.oz-iname{font-size:18px;font-weight:500;color:#0B1220}
.oz-itext{margin:12px 0 16px;font-size:15px;line-height:1.75;font-weight:300;color:#5B6678}
.oz-ielig{font-size:12px;letter-spacing:.06em;color:#5B6678}

/* selected tract */
.oz-kicker{font-size:11px;font-weight:500;letter-spacing:.22em;text-transform:uppercase;color:#5B6678;margin-bottom:20px}
.oz-kicker.acc{color:#0B7A43}
.oz-chip{display:inline-flex;align-items:center;gap:8px;padding:7px 16px;border-radius:999px;border:1px solid #CBD3DF;font-size:12px;color:#0B1220}
.oz-chip i{width:6px;height:6px;border-radius:50%}
.oz-chips{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.oz-ks{display:flex;gap:24px;margin-top:32px;padding:20px 0;border-top:1px solid #E3E7EE;border-bottom:1px solid #E3E7EE}
.oz-ks div{flex:1;min-width:0}
.oz-ks b{display:block;font-size:clamp(22px,2vw,28px);font-weight:200;letter-spacing:-.04em;line-height:1;color:#0B1220}
.oz-ks span{display:block;margin-top:12px;font-size:11px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:#5B6678}
.oz-kvs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 32px}
.oz-kv{display:flex;justify-content:space-between;gap:12px;padding:18px 0;border-bottom:1px solid #E3E7EE;font-size:14px;color:#0B1220}
.oz-kv span{color:#5B6678;font-weight:300}
.oz-just{padding:28px;border-radius:24px;background:#FFFFFF;border:1px solid #E3E7EE;display:flex;flex-direction:column;gap:24px}
.oz-just p{margin:0 !important;font-size:17px;line-height:1.85;font-weight:300;color:#1F2937}
.oz-just .by{padding-top:24px;border-top:1px solid #E3E7EE;font-size:13px;font-weight:300;color:#5B6678}
.oz-key{display:flex;flex-wrap:wrap;gap:12px 28px;font-size:12px;color:#3B4658;padding-bottom:14px}
.oz-key span{display:inline-flex;align-items:center;gap:8px}
.oz-key i{width:14px;height:14px;border-radius:3px;display:inline-block}
.oz-empty{padding:40px 0;border-top:1px solid #E3E7EE;border-bottom:1px solid #E3E7EE;font-size:18px;font-weight:300;color:#5B6678}
.oz-count{text-align:right;font-size:13px;font-weight:300;color:#5B6678;padding-bottom:12px}
.oz-count b{display:block;font-size:40px;font-weight:200;letter-spacing:-.04em;line-height:1;color:#0B7A43;margin-bottom:8px}
.oz-pstep{display:flex;gap:24px;padding-top:20px;border-top:1px solid #E3E7EE;margin-bottom:28px}
.oz-pstep .n{flex:none;font-size:12px;font-weight:500;letter-spacing:.2em;color:#0B7A43;padding-top:5px}
.oz-pstep .t{font-size:20px;font-weight:300;letter-spacing:-.01em;color:#0B1220;margin-bottom:10px}
.oz-pstep .d{font-size:15px;line-height:1.75;font-weight:300;color:#5B6678}
.oz-footer{padding:32px 0;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px 40px;color:#5B6678;font-size:12px;letter-spacing:.14em;text-transform:uppercase}
.oz-footer nav{display:flex;flex-wrap:wrap;gap:0 36px}
.oz-footer a{color:#3B4658 !important;text-decoration:none !important;font-weight:500;letter-spacing:.16em;padding:14px 0}

.oz-th{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;padding:24px 0;border-top:1px solid #E3E7EE;border-bottom:1px solid #E3E7EE}
.oz-pop{text-align:right}
.oz-pop b{display:block;font-size:clamp(28px,3vw,44px);font-weight:200;letter-spacing:-.045em;line-height:1;color:#0B1220}
.oz-pop span{display:block;margin-top:10px;font-size:11px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:#5B6678}
.oz-mgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));column-gap:24px;border-top:1px solid #E3E7EE;margin-top:4px}
.oz-m{padding:28px 0;border-bottom:1px solid #E3E7EE}
.oz-m b{display:block;font-size:clamp(20px,1.8vw,26px);font-weight:200;letter-spacing:-.035em;line-height:1.1;color:#0B1220}
.oz-m span{display:block;margin-top:12px;font-size:11px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:#5B6678}
.oz-arows>.oz-arow:last-child{border-bottom:1px solid #E3E7EE}
.oz-arow{padding:24px 0;border-top:1px solid #E3E7EE}
.oz-aname2{font-size:22px;font-weight:200;letter-spacing:-.025em;margin:12px 0 8px;color:#0B1220}
.oz-arow-foot{display:flex;align-items:center;justify-content:space-between;gap:12px}

.oz-h1 .acc{color:#0B7A43}
.oz-kick2{font-size:12px;font-weight:500;letter-spacing:.22em;text-transform:uppercase;color:#5B6678;padding-top:6px}
.oz-approach{align-items:start;padding-top:20px;border-top:1px solid #E3E7EE}
.oz-lead{font-size:20px;line-height:1.7;font-weight:300;color:#5B6678}
.oz-lead.dark{color:#0B1220}
.oz-round{padding-top:20px;border-top:1px solid #CBD3DF}
.oz-round.acc{border-top-color:#0B7A43}
.oz-roundlbl{font-size:12px;font-weight:500;letter-spacing:.22em;text-transform:uppercase;color:#5B6678}
.oz-roundlbl.acc{color:#0B7A43}
.oz-bignum{margin-top:28px;font-size:clamp(52px,6.7vw,96px);font-weight:200;letter-spacing:-.06em;line-height:1;color:#0B1220}
.oz-bignum.acc{color:#0B7A43}
.oz-unit{margin-top:16px;font-size:12px;font-weight:500;letter-spacing:.2em;text-transform:uppercase;color:#5B6678}
.oz-rtext{margin-top:20px;font-size:16px;line-height:1.75;font-weight:300;color:#5B6678;max-width:520px}
.oz-rtext:first-of-type{margin-top:28px}
.oz-next{margin-top:32px;padding-top:20px;border-top:1px solid #E3E7EE;display:flex;align-items:center;justify-content:space-between;gap:24px}
.oz-next span{font-size:12px;font-weight:500;letter-spacing:.2em;text-transform:uppercase;color:#5B6678}
.oz-next a{display:inline-flex;align-items:center;gap:14px;min-height:48px;font-size:clamp(20px,1.8vw,26px);font-weight:200;letter-spacing:-.02em;color:#0B1220 !important;text-decoration:none !important}
.oz-next em{color:#0B7A43;font-style:normal}


.oz-tlink{display:inline-flex;align-items:center;gap:8px;min-height:44px;color:#0B1220 !important;font-size:12px;font-weight:500;letter-spacing:.16em;text-transform:uppercase;text-decoration:none !important}
.oz-tlink:hover{text-decoration:underline !important;text-underline-offset:6px}
.oz-tlink em{color:#0B7A43;font-style:normal}
.oz-rwhen{font-size:14px;font-weight:400;letter-spacing:.02em;color:#5B6678}
.oz-row.done .oz-rname{color:#5B6678}
.oz-row.now .oz-rname{color:#0B7A43}
.oz-rstat{display:inline-flex;align-items:center;gap:10px;font-size:12px;font-weight:500;letter-spacing:.16em;text-transform:uppercase;color:#5B6678}
.oz-rstat.now{color:#0B7A43;font-weight:600}
.oz-rstat i{width:8px;height:8px;border-radius:50%;background:#16A34A}

.oz-iname a{color:#0B1220 !important;text-decoration:none !important}
.oz-iname a:hover{text-decoration:underline !important;text-underline-offset:5px}
.oz-iname em{color:#0B7A43;font-style:normal;margin-left:6px}

[data-testid="stPlotlyChart"] .maplibregl-canvas,[data-testid="stPlotlyChart"] .maplibregl-canvas-container,[data-testid="stPlotlyChart"] .maplibregl-canvas-container.maplibregl-interactive,[data-testid="stPlotlyChart"] .maplibregl-canvas-container.maplibregl-interactive:active,[data-testid="stPlotlyChart"] .maplibregl-canvas-container.maplibregl-track-pointer,[data-testid="stPlotlyChart"] .nsewdrag,[data-testid="stPlotlyChart"] [class*="cursor-"]{cursor:url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18'%3E%3Ccircle cx='9' cy='9' r='5' fill='%230B1220' stroke='white' stroke-width='1.5'/%3E%3C/svg%3E") 9 9,crosshair !important}

/* widgets */
[data-testid="stWidgetLabel"] p,label[data-testid="stWidgetLabel"] p{font-size:12px !important;font-weight:500 !important;letter-spacing:.18em !important;text-transform:uppercase !important;color:#5B6678 !important}
div[data-baseweb="select"]>div{background:transparent !important;border:none !important;border-bottom:1px solid #CBD3DF !important;border-radius:0 !important;min-height:52px;box-shadow:none !important}
div[data-baseweb="select"] *{color:#0B1220 !important;font-family:'Inter',sans-serif !important;font-size:16px !important;font-weight:300 !important}
div[data-baseweb="select"] svg{fill:#5B6678 !important}
div[data-baseweb="popover"]>div,div[data-baseweb="popover"] ul,ul[role="listbox"]{background:#FFFFFF !important;border-radius:12px}
li[role="option"]{background:#FFFFFF !important;color:#0B1220 !important}
li[role="option"]:hover,li[aria-selected="true"]{background:#F1F4F8 !important}
span[data-baseweb="tag"]{background:transparent !important;border:1px solid #CBD3DF !important;border-radius:999px !important;height:40px;padding-left:16px}
span[data-baseweb="tag"] span{color:#0B1220 !important;font-size:13px !important;font-weight:400 !important}
span[data-baseweb="tag"] svg{fill:#5B6678 !important}
div[data-baseweb="input"],div[data-baseweb="base-input"],div[data-baseweb="textarea"]{background:transparent !important;border:none !important;border-bottom:1px solid #CBD3DF !important;border-radius:0 !important}
div[data-baseweb="input"]>div,div[data-baseweb="base-input"]>div{background:transparent !important}
div[data-baseweb="input"] input,div[data-baseweb="base-input"] input,div[data-baseweb="textarea"] textarea,textarea{background:transparent !important;color:#0B1220 !important;font-family:'Inter',sans-serif !important;font-size:17px !important;font-weight:300 !important;padding-left:0 !important;-webkit-text-fill-color:#0B1220}
input::placeholder,textarea::placeholder{color:#5B6678 !important;-webkit-text-fill-color:#5B6678}
input:disabled{-webkit-text-fill-color:#3B4658 !important;opacity:1 !important}
.stButton>button,.stFormSubmitButton>button,.stDownloadButton>button{border-radius:999px !important;min-height:56px;padding:0 36px !important;font-family:'Inter',sans-serif !important;background:transparent !important;color:#0B1220 !important;border:1px solid #CBD3DF !important;box-shadow:none !important}
.stButton>button *,.stFormSubmitButton>button *,.stDownloadButton>button *{color:inherit !important;font-size:12px !important;font-weight:600 !important;letter-spacing:.14em !important;text-transform:uppercase !important}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:#0B7A43 !important;color:#0B7A43 !important}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"],button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{background:#4ADE80 !important;color:#06090F !important;border:none !important;box-shadow:none !important}
.stButton>button[kind="primary"]:hover{color:#06090F !important}
.stButton{display:flex;justify-content:flex-start}
[data-testid="stForm"]{border:none !important;padding:0 !important}
[data-testid="stPlotlyChart"]{border-radius:24px;overflow:hidden;border:1px solid #E3E7EE;background:#EEF1F5}
[data-testid="stExpander"]{border:1px solid #E3E7EE !important;border-radius:16px !important;background:transparent !important}
[data-testid="stExpander"] summary p{color:#3B4658 !important;font-size:12px !important;letter-spacing:.16em;text-transform:uppercase}
[data-testid="stAlert"]{background:#FFFFFF !important;border:1px solid #CBD3DF !important;border-radius:16px !important}
[data-testid="stAlert"] *{color:#0B1220 !important}
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
            <div class="oz-h3" style="margin-bottom:28px !important">Louisiana OZ 2.0 Portal</div>
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
        <a href="#process">How</a><a href="#regions">Who</a><a href="#incentives">What</a><a href="#map">Where</a>
      </nav>
      <a class="oz-navcta" href="#project">Your project</a>
    </div>
    """
)

# --- SECTION 1: NOMINATION PROCESS ---
with section("process"):
    today = _today()
    done_flags = [today > date.fromisoformat(st_["end"]) for st_ in CONTENT["process_steps"]]
    now_idx = next((i for i, d in enumerate(done_flags) if not d), None)
    steps_html = ""
    for i, st_ in enumerate(CONTENT["process_steps"]):
        state = "done" if done_flags[i] else ("now" if i == now_idx else "todo")
        if state == "now":
            status = "<span class='oz-rstat now'><i></i>We are here</span>"
        else:
            status = f"<span class='oz-rstat'>{'Complete' if state == 'done' else 'Upcoming'}</span>"
        steps_html += (
            f"<div class='g oz-row {state}'>"
            f"<div class='oz-rwhen' style='grid-column:1 / span 3'>{esc(st_['when'])}</div>"
            f"<div class='oz-rname' style='grid-column:4 / span 6'>{esc(st_['title'])}</div>"
            f"<div style='grid-column:10 / span 3;justify-self:end'>{status}</div></div>"
        )
    rounds_html = ""
    for r in CONTENT["rounds"]:
        acc = " acc" if r.get("acc") else ""
        paras = "".join(f"<div class='oz-rtext'>{esc(p)}</div>" for p in r["paras"])
        rounds_html += (
            f"<div class='oz-round{acc}' style='grid-column:span 6'>"
            f"<div class='oz-roundlbl{acc}'>{esc(r['name'])} &nbsp;·&nbsp; {esc(r['tag'])}</div>"
            f"<div class='oz-bignum{acc}'>{esc(r['figure'])}</div><div class='oz-unit'>{esc(r['unit'])}</div>{paras}</div>"
        )
    approach = CONTENT["approach"]
    approach_html = f"<div class='oz-lead dark'>{esc(approach[0])}</div><div class='oz-lead'>{esc(approach[1])}</div>"
    render(
        f"""
        <div id="process">
          <div class="g">
            <div class="oz-label" style="grid-column:1 / span 12"><b>01</b> &nbsp;/&nbsp; How it happened</div>
            <div role="heading" aria-level="1" class="oz-h1" style="grid-column:1 / span 11">Louisiana nominated <span class="acc">{OZ2_SUBMITTED}</span> tracts for Opportunity Zone 2.0.</div>
            <div class="oz-intro lg" style="grid-column:1 / span 6">{esc(CONTENT['process_lede'])}</div>
            <div style="grid-column:8 / span 5;align-self:end;display:flex;justify-content:flex-end"><a class="oz-btn" href="#map">Explore the asset map</a></div>
          </div>
          <div class="g oz-approach" style="margin-top:clamp(56px,6.7vw,96px)">
            <div class="oz-kick2" style="grid-column:1 / span 3">Our approach</div>
            <div style="grid-column:4 / span 7;display:flex;flex-direction:column;gap:20px">{approach_html}</div>
          </div>
          <div class="g" style="margin-top:clamp(56px,6.7vw,96px);align-items:start">{rounds_html}</div>
          <div class="oz-kick2" style="margin:clamp(56px,6.7vw,96px) 0 28px">Opportunity Zones 2.0 timeline</div>
          <div class="oz-rows">{steps_html}</div>
        </div>
        """
    )
    next_chapter("Who stands behind it", "#regions")

# --- SECTION 2: REGIONAL PARTNERS ---
with section("regions"):
    render(
        """
        <div id="regions">
          <div class="oz-label"><b>02</b> &nbsp;/&nbsp; Who stands behind it</div>
          <div role="heading" aria-level="2" class="oz-h2" style="max-width:83%">Regional partners stand behind every nomination.</div>
        </div>
        """
    )
    c_intro, _gap, c_find = st.columns([5, 2, 5])
    with c_intro:
        render(f"<div class='oz-intro'>{esc(CONTENT['partners_intro'])}</div>")
    highlight_names = set()
    with c_find:
        PLACE_PLACEHOLDER = "Search a parish or city"
        options = [PLACE_PLACEHOLDER] + sorted(place_index.keys(), key=lambda x: x.lower())
        choice = st.selectbox("Search by parish or city", options, key="find_place")
        if choice != PLACE_PLACEHOLDER and choice in place_index:
            info = place_index[choice]
            highlight_names = set(info["names"])
            where = f"{info['town']}, {info['parish']} Parish" if info["town"] else f"{info['parish']} Parish"
            served = " and ".join(f"<span style='color:#0B7A43'>{esc(n)}</span>" for n in info["names"])
            rl = info["rlma"]
            rlma = (f" · RLMA {esc(rl)}" if rl.isdigit() else f" · RLMA: {esc(rl)}") if rl else ""
            render(f"<div class='oz-rsub' style='margin-top:12px'>{esc(where)} is served by {served}{rlma}.</div>")
    try:
        check_mode = str(st.query_params.get("check", "")).strip().lower() in ("1", "true", "yes")
    except Exception:
        check_mode = False
    if check_mode:
        render_crosswalk_check()
    spacer(64)

    rows_html = ""
    for r in region_table:
        shown = ", ".join(r["parishes"])  # the full list of parishes in the region
        link = (
            f"<a class='oz-tlink' href='{esc(r['url'])}' target='_blank' rel='noopener' style='grid-column:11 / span 2;justify-self:end'>OZ page <em>↗</em></a>"
            if r["url"]
            else "<span class='oz-rsub' style='grid-column:11 / span 2;justify-self:end'>OZ page soon</span>"
        )
        hl = " hl" if r["name"] in highlight_names else ""
        rows_html += (
            f"<div class='g oz-row{hl}'>"
            f"<div class='oz-rname' style='grid-column:1 / span 4'>{esc(r['partner'])}</div>"
            f"<div class='oz-rsub' style='grid-column:5 / span 4'>{esc(shown)}</div>"
            f"<div class='oz-rcount' style='grid-column:9 / span 2'><b>{r['count']}</b><span>nominated</span></div>"
            f"{link}</div>"
        )
    render(f"<div class='oz-rows'>{rows_html}</div>")
    next_chapter("What makes it investable", "#incentives")

# --- SECTION 3: INCENTIVES ---
with section("incentives"):
    bands_html = ""
    for cat in CONTENT["incentives"]:
        def _name(it):
            u = safe_url(it.get("url", ""))
            if u:
                return f"<a href='{esc(u)}' target='_blank' rel='noopener'>{esc(it['name'])} <em>↗</em></a>"
            return esc(it["name"])

        items = "".join(
            f"<div><div class='oz-iname'>{_name(it)}</div><div class='oz-itext'>{esc(it['text'])}</div>"
            f"<div class='oz-ielig'>Eligibility · {esc(it['eligibility'])}</div></div>"
            for it in cat["items"]
        )
        bands_html += (
            f"<div class='g oz-band'>"
            f"<div style='grid-column:1 / span 4'><div class='oz-bhead' style='color:{esc(cat['text_color'])}'>"
            f"<i style='background:{esc(cat['color'])}'></i>{esc(cat['label'])}</div>"
            f"<div class='oz-bq'>{esc(cat['question'])}</div></div>"
            f"<div class='oz-items' style='grid-column:5 / span 8'>{items}</div></div>"
        )
    render(
        f"""
        <div id="incentives">
          <div class="oz-label"><b>03</b> &nbsp;/&nbsp; What makes it investable</div>
          <div role="heading" aria-level="2" class="oz-h2" style="max-width:83%">Three kinds of risk. Three kinds of help.</div>
          <div class="g" style="margin-bottom:64px"><div class="oz-intro" style="grid-column:1 / span 5">{esc(CONTENT['incentives_intro'])}</div></div>
          <div class="oz-bands">{bands_html}</div>
          <div style="margin-top:40px"><a class="oz-tlink" href="#map">Find the tracts these apply to <em>→</em></a></div>
        </div>
        """
    )


    next_chapter("Where it is", "#map")


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
    """Light map on CARTO Positron vector tiles (built into Plotly, no API token). The basemap adds
    highways, streets, water and place names by itself as the visitor zooms in, from the whole state
    down to single streets. Tracts sit on top with translucent fills so that detail always shows through."""
    map_df = df[["geoid_str", "Parish"]].copy().reset_index(drop=True)
    sel = str(active) if active else None
    view_ids = set(map_df["geoid_str"])
    is_nom = map_df["geoid_str"].isin(nominated_ids)
    other_df, nom_df = map_df[~is_nom], map_df[is_nom]
    in_view = sel is not None and sel in view_ids
    focus = {sel} if in_view else view_ids
    center, zoom = get_zoom_center(focus)
    revision_key = sel if in_view else f"{len(focus)}-{min(focus) if focus else ''}"
    fid = f"properties.{ID_KEY}"
    keep_opacity = dict(selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)))

    fig = go.Figure()
    if len(other_df):
        # almost-transparent fill (still clickable) with a hairline outline
        fig.add_trace(
            go.Choroplethmap(
                geojson=gj, locations=other_df["geoid_str"], z=[0] * len(other_df), featureidkey=fid,
                colorscale=[[0, "rgba(100,116,139,0.06)"], [1, "rgba(100,116,139,0.06)"]], showscale=False,
                marker=dict(opacity=1, line=dict(width=0.6, color="rgba(71,85,105,0.6)")),
                hovertext=other_df["Parish"].astype(str) + " · " + other_df["geoid_str"], hoverinfo="text",
                name="Other tracts", **keep_opacity,
            )
        )
    if len(nom_df):
        ids = set(nom_df["geoid_str"])
        nom_geo = {"type": "FeatureCollection", "features": [f for f in gj["features"] if f["properties"].get(ID_KEY) in ids]}
        fig.add_trace(
            go.Choroplethmap(
                geojson=nom_geo, locations=nom_df["geoid_str"], z=[1] * len(nom_df), featureidkey=fid,
                colorscale=[[0, "rgba(34,197,94,0.45)"], [1, "rgba(34,197,94,0.45)"]], showscale=False,
                marker=dict(opacity=1, line=dict(width=1.2, color="#15803D")),
                hovertext=nom_df["Parish"].astype(str) + " · " + nom_df["geoid_str"] + " · Nominated", hoverinfo="text",
                name="Nominated", **keep_opacity,
            )
        )
    if in_view:
        sel_geo = {"type": "FeatureCollection", "features": [f for f in gj["features"] if f["properties"].get(ID_KEY) == sel]}
        fig.add_trace(
            go.Choroplethmap(
                geojson=sel_geo, locations=[sel], z=[1], featureidkey=fid,
                colorscale=[[0, "rgba(11,18,32,0.22)"], [1, "rgba(11,18,32,0.22)"]], showscale=False,
                marker=dict(opacity=1, line=dict(width=2.4, color="#0B1220")),
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
        map=dict(style=_basemap_style(), zoom=zoom, center=center),
        margin={"r": 0, "t": 0, "l": 0, "b": 0}, paper_bgcolor="#FFFFFF", height=620,
        clickmode="event+select", uirevision=revision_key,
        hoverlabel=dict(bgcolor="#0B1220", bordercolor="#0B1220", font=dict(family="Inter, sans-serif", size=12, color="#FFFFFF")),
        legend=dict(
            title=dict(text="TOGGLE ANCHOR ASSETS", font=dict(size=10, color="#5B6678", family="Inter, sans-serif")),
            yanchor="top", y=0.97, xanchor="left", x=0.02, itemsizing="constant",
            bgcolor="rgba(255,255,255,0.94)", font=dict(size=11, color="#0B1220", family="Inter, sans-serif"),
            bordercolor="#CBD3DF", borderwidth=1,
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
          <div class="oz-label"><b>04</b> &nbsp;/&nbsp; Where it is</div>
          <div role="heading" aria-level="2" class="oz-h2" style="max-width:83%">See each tract, and everything around it.</div>
          <div class="g" style="margin-bottom:56px"><div class="oz-intro" style="grid-column:1 / span 5">Select a tract to read the partner’s case. Zoom in and the streets, sites and clinics around it appear.</div></div>
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
        # Official numbers for the state and for a region; a single parish can only be counted from the sheet.
        if selected_parish != "All in region":
            shown = len(nom_in_view)
        elif selected_region != "All Louisiana":
            shown = (_fact_for(selected_region) or {}).get("nominated", len(nom_in_view))
        else:
            shown = OZ2_SUBMITTED
        render(f"<div class='oz-count'><b>{shown}</b>nominated in {esc(scope)}</div>")

    spacer(24)

    if gj is None:
        st.warning("The tract boundary file (tl_2025_22_tract.json) was not found, so the map cannot be drawn.")
    else:
        active = st.session_state["active_tract"]

        event = plot(
            render_map(filtered_df, active), on_select="rerun", key="oz_map",
            config={"scrollZoom": True, "displayModeBar": False},
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

        spacer(20)
        k1, k3 = st.columns([10, 2])
        with k1:
            render(
                """
                <div class="oz-key">
                  <span><i style="background:rgba(100,116,139,0.10);border:1px solid #64748B"></i>Other tracts</span>
                  <span><i style="background:rgba(34,197,94,0.45);border:1px solid #15803D"></i>Nominated</span>
                  <span><i style="background:rgba(11,18,32,0.22);border:2px solid #0B1220"></i>Selected</span>
                </div>
                """
            )
        with k3:
            st.button("Reset", key="reset_view", on_click=reset_view)

    # selected tract: header strip, then metrics + justification (left) and nearby anchors (right),
    # the same orientation as the original portal
    spacer(56)
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
        redo_name = (_fact_for(region) or {}).get("name", region)
        nom = nominated_by_id.get(gid)
        pop = safe_int(row.get(POP_COL, 0))
        nmtc_yes = row["NMTC_Calculated"] in ("Eligible", "Deep Distress")
        deep_yes = row["NMTC_Calculated"] == "Deep Distress"

        chips = ""
        if nom:
            if nom.get("category"):
                chips += f"<span class='oz-chip'>{esc(nom['category'])}</span>"
            chips += f"<span class='oz-chip'><i style='background:#16A34A'></i>Nominated with {esc(redo_name)}</span>"
        else:
            chips += "<span class='oz-chip'>Not nominated</span>"

        if nom and str(nom.get("justification", "")).strip():
            just_inner = para_html(nom["justification"]) + f"<div class='by'>Submitted by {esc(redo_name)}</div>"
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
        spacer(40)

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
                <div class="oz-kicker" style="margin-top:32px">Recommendation category</div>
                <div class="oz-chips">{chips}</div>
                <div class="oz-kicker" style="margin-top:28px">Regional partner’s justification</div>
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
            spacer(24)
            render(
                f"<div class='oz-chips'><span class='oz-kicker' style='margin:0 12px 0 0'>Incentives that apply</span>{chips_inc}</div>"
            )
            spacer(20)
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
    spacer(64)
    render("<div style='border-top:1px solid #E3E7EE'></div>")
    spacer(24)
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
    spacer(24)
    render("<div style='border-top:1px solid #E3E7EE'></div>")

    next_chapter("What happens next", "#project")

# --- SECTION 5: TELL US ABOUT YOUR PROJECT ---
with section("project"):
    render(
        f"""
        <div id="project">
          <div class="oz-label"><b>05</b> &nbsp;/&nbsp; What happens next</div>
          <div role="heading" aria-level="2" class="oz-h2" style="max-width:83%">Ready to build? Tell us about your project.</div>
          <div class="g" style="margin-bottom:64px"><div class="oz-intro" style="grid-column:1 / span 5">{esc(CONTENT['project_intro'])}</div></div>
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
                partners = [r for r in region_table if any(x in regions_hit for x in r["regions"])]
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
        st.markdown("**Data check: crosswalk**")
        with st.container():
            cw_df, cw_found = load_crosswalk()
            if cw_df is None:
                st.info(
                    f"The crosswalk file (expected: \"{CROSSWALK_FILE}\") was not found, is empty, or its columns were not recognized "
                    f"(detected: {cw_found or 'none'}). Parishes come from the master data instead."
                )
            else:
                st.write(
                    f"{len(cw_df)} rows · columns detected: "
                    + ", ".join(f"{k} = {v}" for k, v in cw_found.items())
                )
                unmatched = sorted({x for x in cw_df["region"].unique() if not _fact_for(x)})
                if unmatched:
                    st.warning("These regions in the crosswalk do not match any partner: " + ", ".join(unmatched))
                else:
                    st.success("Every region in the crosswalk matches a partner.")
                st.dataframe(
                    pd.DataFrame([{"Partner": r["partner"], "Parishes": len(r["parishes"])} for r in region_table]),
                    hide_index=True,
                )
        st.markdown("**Data check: nominated tracts on the map**")
        with st.container():
            check = pd.DataFrame(
                [
                    {"Partner": r["partner"], "Official": r["count"], "On the map": r["mapped"],
                     "Missing": max(r["count"] - r["mapped"], 0)}
                    for r in region_table
                ]
            )
            st.dataframe(check, hide_index=True)
            total_official = int(check["Official"].sum())
            total_mapped = int(check["On the map"].sum())
            if total_mapped < total_official:
                st.warning(
                    f"{total_mapped} of {total_official} nominated tracts have a record in the Recommendations sheet, "
                    f"so {total_official - total_mapped} are not shown on the map yet."
                )
            else:
                st.success("Every nominated tract has a record in the Recommendations sheet.")
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