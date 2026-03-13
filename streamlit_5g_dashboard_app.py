import pandas as pd
import streamlit as st
import plotly.express as px
import calendar

st.set_page_config(page_title="5G Submission Dashboard", layout="wide")

EXPECTED_SP = [
    'PAVO', 'DIGI', 'CELCOM', 'MAXIS', 'U-MOBILE', 'YTLC',
    'REDONE', 'TUNE-TALK', 'REDTONE', 'VALYOU', 'XOX', 'TM-TECH'
]

DROP_COLS = [
    "SUBMISSION_DATE", "HOUSEHOLD_AMEND", "NON_HOUSEHOLD_AMEND",
    "CREATED_BY", "UPDATED_BY", "UPDATED", "STATUS",
    "REQUEST_REMARK", "REMARKS"
]

@st.cache_data
def load_and_prepare(uploaded_file) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()

    cols_to_drop = [c for c in DROP_COLS if c in df.columns]
    if cols_to_drop:
        df = df.drop(cols_to_drop, axis=1)

    df = df.melt(
        id_vars=['State', 'INDICATOR', 'SERVICE_PROVIDER', 'DECLARATION_MONTH', 'DECLARATION_YEAR', 'TOTAL'],
        var_name='CATEGORY',
        value_name='TOTAL_SUBS'
    )

    if 'TOTAL' in df.columns:
        df = df.drop('TOTAL', axis=1)

    df['DECLARATION_MONTH'] = pd.to_numeric(df['DECLARATION_MONTH'], errors='coerce')
    df['DECLARATION_YEAR'] = pd.to_numeric(df['DECLARATION_YEAR'], errors='coerce')
    df['TOTAL_SUBS'] = pd.to_numeric(df['TOTAL_SUBS'], errors='coerce').fillna(0)

    df = df.dropna(subset=['DECLARATION_MONTH', 'DECLARATION_YEAR'])
    df['DECLARATION_MONTH'] = df['DECLARATION_MONTH'].astype(int)
    df['DECLARATION_YEAR'] = df['DECLARATION_YEAR'].astype(int)

    df.replace({'INDICATOR': {'iMBB7': '5G Subscriptions'}}, inplace=True)
    df.replace({'SERVICE_PROVIDER': {'YTL': 'YTLC'}}, inplace=True)

    return df


def filter_period(df: pd.DataFrame, selected_month: int, selected_year: int) -> pd.DataFrame:
    return df[
        (df['DECLARATION_MONTH'] == selected_month) &
        (df['DECLARATION_YEAR'] == selected_year)
    ].copy()


st.title("5G Submission Dashboard")
st.subheader("5G Analysis & Monitoring Dashboard")

uploaded_file = st.sidebar.file_uploader("Upload raw 5G CSV", type=["csv"])

if uploaded_file is None:
    st.info("Upload the raw 5G CSV file to start.")
    st.stop()

data5G = load_and_prepare(uploaded_file)

years = sorted(
    data5G['DECLARATION_YEAR']
    .dropna()
    .unique()
    .tolist())
selected_year = st.sidebar.selectbox("Select declaration year", options=years,index=years.index(max(years)))

months = sorted(
    data5G[data5G['DECLARATION_YEAR']== selected_year]['DECLARATION_MONTH']
    .dropna()
    .unique()
    .tolist())
selected_month = st.sidebar.selectbox("Select declaration month", options=months, index=months.index(max(months)))

population = st.sidebar.number_input("Enter the current population ('000)", placeholder="34,334.4", step =0.1, format ="%.1f")

data5GDB = filter_period(data5G, selected_month, selected_year)

if data5GDB.empty:
    st.warning(f"No data found for month {selected_month} and year {selected_year}.")
    st.stop()

# Previous month logic
if selected_month == 1:
    prev_month = 12
    prev_year = selected_year - 1
else:
    prev_month = selected_month - 1
    prev_year = selected_year

prev_data = data5G[
    (data5G['DECLARATION_MONTH'] == prev_month) &
    (data5G['DECLARATION_YEAR'] == prev_year)
].copy()

# KPI section
submitted_sp = sorted(data5GDB['SERVICE_PROVIDER'].dropna().unique().tolist())
not_submitted_sp = [p for p in EXPECTED_SP if p not in submitted_sp]

total_subs = data5GDB['TOTAL_SUBS'].sum()
if population>0:
    pen_rate = (total_subs/(population*1000))*100
else:
    pen_rate = 0
state_count = data5GDB['State'].nunique() if 'State' in data5GDB.columns else 0
sp_count = data5GDB['SERVICE_PROVIDER'].nunique()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Selected month", selected_month)
c2.metric("Selected year", selected_year)
c3.metric("Total 5G subscriptions", f"{total_subs:,.0f}")
c4.metric("Penetration rate (%)", f"{pen_rate:2.1f}%")

c5, c6 = st.columns(2)
c5.metric("Service providers submitted", f"{sp_count}/{len(EXPECTED_SP)}")
c6.metric("Missing SP submissions", len(not_submitted_sp))

# Provider submission checklist
st.subheader("Service provider submission checklist")
checklist = pd.DataFrame({
    'SERVICE_PROVIDER': EXPECTED_SP,
    'SUBMITTED': [p in submitted_sp for p in EXPECTED_SP]
})
st.dataframe(checklist, use_container_width=True, hide_index=True)

if not_submitted_sp:
    st.warning("Not submitted: " + ", ".join(not_submitted_sp), icon="⚠️")
else:
    st.success("All expected service providers have submitted data.", icon="✅")

# Aggregations
latest_by_sp = (
    data5GDB.groupby('SERVICE_PROVIDER', as_index=False)
    .agg(TOTAL_SUBS=('TOTAL_SUBS', 'sum'))
    .sort_values('TOTAL_SUBS', ascending=False)
)

latest_by_state = (
    data5GDB.groupby('State', as_index=False)
    .agg(TOTAL_SUBS=('TOTAL_SUBS', 'sum'))
    .sort_values('TOTAL_SUBS', ascending=False)
)

latest_by_cat = (
    data5GDB.groupby('CATEGORY', as_index=False)
    .agg(TOTAL_SUBS=('TOTAL_SUBS', 'sum'))
    .sort_values('TOTAL_SUBS', ascending=False)
)

latest_by_sp_cat = (
    data5GDB.groupby(['SERVICE_PROVIDER', 'CATEGORY'], as_index=False)
    .agg(TOTAL_SUBS=('TOTAL_SUBS', 'sum'))
)

# Comparison with previous month
if not prev_data.empty:
    prev_by_sp = (
        prev_data.groupby('SERVICE_PROVIDER', as_index=False)
        .agg(TOTAL_SUBS=('TOTAL_SUBS', 'sum'))
    )

    comparison = pd.merge(
        latest_by_sp,
        prev_by_sp,
        on='SERVICE_PROVIDER',
        how='left',
        suffixes=('_LATEST', '_PREV')
    )

    comparison['TOTAL_SUBS_PREV'] = comparison['TOTAL_SUBS_PREV'].fillna(0)
    comparison['DIFFERENCE'] = comparison['TOTAL_SUBS_LATEST'] - comparison['TOTAL_SUBS_PREV']
    comparison['GROWTH_%'] = comparison.apply(
        lambda r: ((r['DIFFERENCE'] / r['TOTAL_SUBS_PREV']) * 100) if r['TOTAL_SUBS_PREV'] > 0 else None,
        axis=1
    )
else:
    comparison = latest_by_sp.copy().rename(columns={'TOTAL_SUBS': 'TOTAL_SUBS_LATEST'})
    comparison['TOTAL_SUBS_PREV'] = 0
    comparison['DIFFERENCE'] = comparison['TOTAL_SUBS_LATEST']
    comparison['GROWTH_%'] = None

# Overview
st.subheader("Overview")

col1, col2 = st.columns(2)

table_sp = latest_by_sp.copy()
table_sp['TOTAL_SUBS'] = table_sp['TOTAL_SUBS'].map('{:,.0f}'.format)
col1.markdown(f"**Subscriptions by Service Provider ({selected_month}/{selected_year})**")
col1.dataframe(table_sp, use_container_width=True, hide_index=True)

fig_cat = px.pie(
    latest_by_cat,
    names='CATEGORY',
    values='TOTAL_SUBS',
    title='Category split (HH vs NHH)'
)
col2.plotly_chart(fig_cat, use_container_width=True)

col3, col4 = st.columns(2)

table_state = latest_by_state.copy()
table_state['TOTAL_SUBS'] = table_state['TOTAL_SUBS'].map('{:,.0f}'.format)
col3.markdown(f"**Subscriptions by State ({selected_month}/{selected_year})**")
col3.dataframe(table_state, use_container_width=True, hide_index=True)

fig_sp_cat = px.bar(
    latest_by_sp_cat,
    x='SERVICE_PROVIDER',
    y='TOTAL_SUBS',
    color='CATEGORY',
    barmode='stack',
    title='HH/NHH split by Service Provider'
)
fig_sp_cat.update_yaxes(tickformat=',.0f')
col4.plotly_chart(fig_sp_cat, use_container_width=True)

st.subheader("Latest vs previous month")
display_comparison = comparison.copy()
display_comparison['TOTAL_SUBS_LATEST'] = display_comparison['TOTAL_SUBS_LATEST'].map(lambda x: f"{x:,.0f}")
display_comparison['TOTAL_SUBS_PREV'] = display_comparison['TOTAL_SUBS_PREV'].map(lambda x: f"{x:,.0f}")
display_comparison['DIFFERENCE'] = display_comparison['DIFFERENCE'].map(lambda x: f"{x:,.0f}")
display_comparison['GROWTH_%'] = display_comparison['GROWTH_%'].map(lambda x: f"{x:.2f}%" if pd.notnull(x) else "-")

st.dataframe(display_comparison, use_container_width=True, hide_index=True)

month_name = calendar.month_name[selected_month]

csv_bytes = data5GDB.to_csv(index=False).encode('utf-8-sig')
st.download_button(
    label=f'Download {month_name} {selected_year} data as CSV',
    data=csv_bytes,
    file_name=f'5GDB_{selected_year}_{selected_month}.csv',
    mime='text/csv'
)