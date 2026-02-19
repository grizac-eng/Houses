import io
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Greece House Sales Trends", layout="wide")

st.title("🏠 Greece House Sales Trends (Excel → Trends)")
st.caption("Upload an Excel file and explore transaction volume, traded surface, and old/new mix by month/quarter/year.")

with st.sidebar:
    st.header("1) Upload")
    uploaded = st.file_uploader("Excel file (.xlsx)", type=["xlsx"])
    st.divider()
    st.header("2) Time aggregation")
    gran = st.radio("Group by", ["Month", "Quarter", "Year"], index=0, horizontal=False)
    st.divider()
    st.header("3) Columns (auto-detect, but editable)")
    date_col_default = "Ημερομηνία Συμβολαίου"
    built_col_default = "Έτος Κατασκευής"
    area_main_default = "Eπιφάνεια Κύριων Χώρων (σε τ.μ.)"
    area_aux_default = "Επιφάνεια Βοηθητικών Χώρων (σε τ.μ.)"

    # These will be populated after load, but keep placeholders
    date_col = st.text_input("Sale date column", value=date_col_default)
    built_col = st.text_input("Year built column", value=built_col_default)
    area_main_col = st.text_input("Main area column (sqm)", value=area_main_default)
    area_aux_col = st.text_input("Aux area column (sqm) (optional)", value=area_aux_default)
    include_aux = st.checkbox("Include auxiliary area in 'Total sqm traded'", value=False)

    st.divider()
    st.header("4) Age buckets")
    pre_year = st.number_input("Old threshold (≤ year)", value=1990, step=1)
    last_n = st.number_input("New = built within last N years (relative to sale year)", value=5, min_value=1, max_value=50, step=1)

def try_parse_dates(s: pd.Series) -> pd.Series:
    # Works for datetime, excel serials, strings
    if np.issubdtype(s.dtype, np.datetime64):
        return s
    return pd.to_datetime(s, errors="coerce")

def compute_age_class(df: pd.DataFrame, date_col: str, built_col: str, pre_year: int, last_n: int) -> pd.Series:
    sale_year = df[date_col].dt.year
    built = pd.to_numeric(df[built_col], errors="coerce")
    out = np.where(built.isna(), "unknown",
          np.where(built <= pre_year, f"pre_{pre_year}",
          np.where(built >= (sale_year - last_n), f"new_last{last_n}y", "mid_age")))
    return pd.Series(out, index=df.index)

def period_key(df: pd.DataFrame, date_col: str, gran: str) -> pd.Series:
    if gran == "Month":
        return df[date_col].dt.to_period("M").astype(str)
    if gran == "Quarter":
        return df[date_col].dt.to_period("Q").astype(str)
    return df[date_col].dt.year.astype(str)

if not uploaded:
    st.info("Upload an Excel file to begin. Your example file looks compatible with the default column names shown in the sidebar.")
    st.stop()

# Load
try:
    raw = pd.read_excel(uploaded)
except Exception as e:
    st.error(f"Could not read Excel: {e}")
    st.stop()

df = raw.copy()

missing = [c for c in [date_col, built_col, area_main_col] if c not in df.columns]
if missing:
    st.error("Missing required columns: " + ", ".join(missing) + "\n\nUse the sidebar to set the correct column names.")
    st.write("Detected columns:", list(df.columns))
    st.stop()

df[date_col] = try_parse_dates(df[date_col])
df = df.dropna(subset=[date_col])

# Total sqm traded
main_area = pd.to_numeric(df[area_main_col], errors="coerce").fillna(0.0)
if include_aux and (area_aux_col in df.columns):
    aux_area = pd.to_numeric(df[area_aux_col], errors="coerce").fillna(0.0)
else:
    aux_area = 0.0
df["total_sqm"] = main_area + aux_area

# Age class
df["age_class"] = compute_age_class(df, date_col, built_col, pre_year=pre_year, last_n=last_n)

# Optional filters (auto-detect common geo columns)
geo_cols = [c for c in ["Νομαρχία", "Δήμος Καλλικράτη", "Δημοτικό ή Κοινοτικό Διαμέρισμα", "Κατηγορία Ακινήτου"] if c in df.columns]

with st.sidebar:
    st.divider()
    st.header("5) Filters (optional)")
    filters = {}
    for c in geo_cols:
        vals = ["(all)"] + sorted([v for v in df[c].dropna().unique().tolist()])
        sel = st.selectbox(c, vals, index=0)
        if sel != "(all)":
            filters[c] = sel

# Apply filters
for c, v in filters.items():
    df = df[df[c] == v]

df["period"] = period_key(df, date_col, gran)

# Aggregate core metrics
agg = df.groupby("period", as_index=False).agg(
    sales=("period", "size"),
    traded_sqm=("total_sqm", "sum"),
)

# Age mix counts
age = df.groupby(["period", "age_class"]).size().reset_index(name="count")
age_pivot = age.pivot(index="period", columns="age_class", values="count").fillna(0).astype(int).reset_index()

# Join
out = agg.merge(age_pivot, on="period", how="left").fillna(0)

# Percent mix for age classes
age_cols = [c for c in out.columns if c not in ["period", "sales", "traded_sqm"]]
if age_cols:
    pct = out[age_cols].div(out["sales"].replace(0, np.nan), axis=0) * 100
    pct = pct.fillna(0)
    pct.columns = [f"{c}_pct" for c in pct.columns]
    out_pct = pd.concat([out[["period", "sales", "traded_sqm"]], pct], axis=1)
else:
    out_pct = out[["period", "sales", "traded_sqm"]].copy()

# Layout
colA, colB = st.columns([1.2, 1])

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
        fig3 = px.area(age_long, x="period", y="count", color="age_class", title="Age mix (counts)", groupnorm=None)
        st.plotly_chart(fig3, use_container_width=True)

        pct_cols = [c for c in out_pct.columns if c.endswith("_pct")]
        pct_long = out_pct.melt(id_vars=["period"], value_vars=pct_cols, var_name="age_class", value_name="pct")
        pct_long["age_class"] = pct_long["age_class"].str.replace("_pct$", "", regex=True)
        fig4 = px.area(pct_long, x="period", y="pct", color="age_class", title="Age mix (% of sales)", groupnorm=None)
        st.plotly_chart(fig4, use_container_width=True)

st.caption("Tip: change Month/Quarter/Year in the sidebar, and use filters (Nomarchy/Municipality/Category) to drill down.")
