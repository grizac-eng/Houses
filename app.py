import os
import glob
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Greece House Sales Trends", layout="wide")
st.title("🏠 Greece House Sales Trends")
st.caption("Transaction activity analytics: number of sales, traded surface (sqm), and old/new mix over time.")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ---------- Helpers ----------
def try_parse_dates(s: pd.Series) -> pd.Series:
    if np.issubdtype(s.dtype, np.datetime64):
        return s
    return pd.to_datetime(s, errors="coerce")

def compute_age_class(df: pd.DataFrame, date_col: str, built_col: str, pre_year: int, last_n: int) -> pd.Series:
    sale_year = df[date_col].dt.year
    built = pd.to_numeric(df[built_col], errors="coerce")
    out = np.where(
        built.isna(), "unknown",
        np.where(
            built <= pre_year, f"pre_{pre_year}",
            np.where(built >= (sale_year - last_n), f"new_last{last_n}y", "mid_age"),
        ),
    )
    return pd.Series(out, index=df.index)

def period_key(df: pd.DataFrame, date_col: str, gran: str) -> pd.Series:
    if gran == "Month":
        return df[date_col].dt.to_period("M").astype(str)
    if gran == "Quarter":
        return df[date_col].dt.to_period("Q").astype(str)
    return df[date_col].dt.year.astype(str)

@st.cache_data(show_spinner=False)
def load_excel(path_or_bytes) -> pd.DataFrame:
    return pd.read_excel(path_or_bytes)

def discover_built_in_files():
    paths = sorted(glob.glob(os.path.join(DATA_DIR, "*.xlsx")))
    file_by_year = {}
    for p in paths:
        name = os.path.basename(p)
        year = None
        # Extract any 4-digit token in the filename
        for token in name.replace(".xlsx", "").split("-"):
            if token.isdigit() and len(token) == 4:
                year = int(token)
        if year is not None:
            file_by_year[year] = p
    years = sorted(file_by_year.keys())
    return years, file_by_year

# ---------- Sidebar ----------
with st.sidebar:
    st.header("1) Data")
    mode = st.radio("Source", ["Built-in years (no upload)", "Upload Excel"], index=0)

    years, file_by_year = discover_built_in_files()

    uploaded = None
    years_selected = None

    if mode == "Built-in years (no upload)":
        if not years:
            st.warning("No built-in Excel files found. Add .xlsx files under ./data in the repo.")
        default_years = years[-3:] if len(years) >= 3 else years
        years_selected = st.multiselect("Select years", years, default=default_years)
    else:
        uploaded = st.file_uploader("Excel file (.xlsx)", type=["xlsx"])

    st.divider()

    st.header("2) Time aggregation")
    gran = st.radio("Group by", ["Month", "Quarter", "Year"], index=0)

    st.divider()

    st.header("3) Columns (editable)")
    date_col = st.text_input("Sale date column", value="Ημερομηνία Συμβολαίου")
    built_col = st.text_input("Year built column", value="Έτος Κατασκευής")
    area_main_col = st.text_input("Main area (sqm)", value="Eπιφάνεια Κύριων Χώρων (σε τ.μ.)")
    area_aux_col = st.text_input("Aux area (sqm) (optional)", value="Επιφάνεια Βοηθητικών Χώρων (σε τ.μ.)")
    include_aux = st.checkbox("Include auxiliary area in total sqm", value=False)

    st.divider()

    st.header("4) Age buckets")
    pre_year = st.number_input("Old threshold (≤ year)", value=1990, step=1)
    last_n = st.number_input("New = within last N years (relative to sale year)", value=5, min_value=1, max_value=50, step=1)

# ---------- Load data ----------
dfs = []

if mode == "Built-in years (no upload)":
    if not years_selected:
        st.info("Select at least one year from the sidebar.")
        st.stop()
    for y in years_selected:
        p = file_by_year.get(y)
        if not p:
            continue
        d = load_excel(p)
        d["_source_year_file"] = y
        dfs.append(d)
else:
    if not uploaded:
        st.info("Upload an Excel file to begin.")
        st.stop()
    d = load_excel(uploaded)
    dfs.append(d)

raw = pd.concat(dfs, ignore_index=True)

# ---------- Validate columns ----------
required = [date_col, built_col, area_main_col]
missing = [c for c in required if c not in raw.columns]
if missing:
    st.error("Missing required columns: " + ", ".join(missing))
    st.write("Detected columns:", list(raw.columns))
    st.stop()

df = raw.copy()
df[date_col] = try_parse_dates(df[date_col])
df = df.dropna(subset=[date_col])

main_area = pd.to_numeric(df[area_main_col], errors="coerce").fillna(0.0)
aux_area = 0.0
if include_aux and (area_aux_col in df.columns):
    aux_area = pd.to_numeric(df[area_aux_col], errors="coerce").fillna(0.0)
df["total_sqm"] = main_area + aux_area

df["age_class"] = compute_age_class(df, date_col, built_col, pre_year=pre_year, last_n=last_n)
df["period"] = period_key(df, date_col, gran)

# ---------- Optional filters ----------
geo_candidates = ["Νομαρχία", "Δήμος Καλλικράτη", "Δημοτικό ή Κοινοτικό Διαμέρισμα", "Κατηγορία Ακινήτου"]
geo_cols = [c for c in geo_candidates if c in df.columns]

with st.sidebar:
    st.divider()
    st.header("5) Filters (optional)")
    filters = {}
    for c in geo_cols:
        vals = ["(all)"] + sorted([v for v in df[c].dropna().unique().tolist()])
        sel = st.selectbox(c, vals, index=0)
        if sel != "(all)":
            filters[c] = sel

for c, v in filters.items():
    df = df[df[c] == v]

# ---------- Aggregations ----------
agg = df.groupby("period", as_index=False).agg(
    sales=("period", "size"),
    traded_sqm=("total_sqm", "sum"),
)

age = df.groupby(["period", "age_class"]).size().reset_index(name="count")
age_pivot = age.pivot(index="period", columns="age_class", values="count").fillna(0).astype(int).reset_index()

out = agg.merge(age_pivot, on="period", how="left").fillna(0)

age_cols = [c for c in out.columns if c not in ["period", "sales", "traded_sqm"]]
pct_long = None
if age_cols:
    out_pct = out.copy()
    for c in age_cols:
        out_pct[c] = (out_pct[c] / out_pct["sales"].replace(0, np.nan) * 100).fillna(0)

    pct_long = out_pct.melt(id_vars=["period"], value_vars=age_cols, var_name="age_class", value_name="pct")

# ---------- UI ----------
k1, k2, k3 = st.columns(3)
k1.metric("Rows loaded", f"{len(df):,}")
k2.metric("Total sales", f"{int(df.shape[0]):,}")
k3.metric("Total traded sqm", f"{df['total_sqm'].sum():,.0f}")

colA, colB = st.columns([1.25, 1])

with colA:
    st.subheader("📌 Aggregated table")
    st.dataframe(out, use_container_width=True)

    csv = out.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Download aggregated CSV", data=csv, file_name="aggregated_trends.csv", mime="text/csv")

with colB:
    st.subheader("📈 Charts")

    fig1 = px.line(agg, x="period", y="sales", markers=True, title=f"Number of sales per {gran.lower()}")
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.line(agg, x="period", y="traded_sqm", markers=True, title=f"Total sqm traded per {gran.lower()}")
    st.plotly_chart(fig2, use_container_width=True)

    if age_cols:
        age_long = out.melt(id_vars=["period"], value_vars=age_cols, var_name="age_class", value_name="count")
        fig3 = px.area(age_long, x="period", y="count", color="age_class", title="Age mix (counts)")
        st.plotly_chart(fig3, use_container_width=True)

        fig4 = px.area(pct_long, x="period", y="pct", color="age_class", title="Age mix (% of sales)")
        st.plotly_chart(fig4, use_container_width=True)

with st.expander("Data notes / assumptions", expanded=False):
    st.markdown(
        f"""
- **Age buckets** are dynamic relative to the sale year:
  - `pre_{int(pre_year)}`: built year ≤ {int(pre_year)}
  - `new_last{int(last_n)}y`: built year ≥ sale_year − {int(last_n)}
  - `mid_age`: everything in between
  - `unknown`: missing/invalid build year
- **Total sqm traded** = main area + (optional) auxiliary area (controlled in sidebar).
"""
    )

st.caption("Tip: If you deploy this to Streamlit Cloud, the built-in yearly files live in the repo under `data/`.")
