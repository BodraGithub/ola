"""OLA Ride Insights: Streamlit app.

Run:  python clean_data.py OLA_DataSet.xlsx   (once, builds data/ola.db)
      streamlit run app.py
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).parent
DB = BASE / "data" / "ola.db"
SQL_FILE = BASE / "queries.sql"
PALETTE = ["#1B1F23", "#8FB400", "#2F6F5E", "#E8A33D", "#6C7A89", "#C0392B", "#4C9F70"]

st.set_page_config(page_title="OLA Ride Insights", page_icon="🚖", layout="wide")

if not DB.exists():
    st.error("data/ola.db not found. Run `python clean_data.py OLA_DataSet.xlsx` first.")
    st.stop()


# ---------- data access ----------
def run_sql(sql: str, params=()) -> pd.DataFrame:
    with sqlite3.connect(DB) as con:
        return pd.read_sql(sql, con, params=params)


@st.cache_data(show_spinner=False)
def load_rides() -> pd.DataFrame:
    df = run_sql("SELECT * FROM rides")
    df["booking_date"] = pd.to_datetime(df["booking_date"])
    return df


@st.cache_data(show_spinner=False)
def load_queries() -> dict:
    """Parse queries.sql into {'Q1: title': 'SELECT ...'}."""
    parts = re.split(r"(?m)^-- (Q\d+): (.*)$", SQL_FILE.read_text())
    out = {}
    for i in range(1, len(parts), 3):
        body = "\n".join(l for l in parts[i + 2].splitlines() if not l.startswith("--")).strip()
        out[f"{parts[i]}: {parts[i + 1]}"] = body
    return out


rides = load_rides()

# ---------- sidebar filters ----------
st.sidebar.title("🚖 OLA Ride Insights")
page = st.sidebar.radio("Page", ["Dashboard", "SQL explorer", "Power BI", "Key insights"])

st.sidebar.divider()
st.sidebar.subheader("Filters")
dmin, dmax = rides["booking_date"].min().date(), rides["booking_date"].max().date()
date_range = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
vehicles = st.sidebar.multiselect("Vehicle type", sorted(rides["vehicle_type"].unique()))
statuses = st.sidebar.multiselect("Booking status", sorted(rides["booking_status"].unique()))
payments = st.sidebar.multiselect(
    "Payment method", sorted(p for p in rides["payment_method"].unique() if p != "Not Applicable")
)

f = rides
if isinstance(date_range, tuple) and len(date_range) == 2:
    f = f[(f["booking_date"].dt.date >= date_range[0]) & (f["booking_date"].dt.date <= date_range[1])]
if vehicles:
    f = f[f["vehicle_type"].isin(vehicles)]
if statuses:
    f = f[f["booking_status"].isin(statuses)]
if payments:
    f = f[f["payment_method"].isin(payments)]
done = f[f["booking_status"] == "Success"]


def style(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=50, b=10), legend_title_text="")
    return fig


def bar(df, x, y, title, **kw):
    return style(px.bar(df, x=x, y=y, title=title, color_discrete_sequence=PALETTE, **kw))


# ---------- pages ----------
if page == "Dashboard":
    st.title("OLA Ride Insights Dashboard")
    if f.empty:
        st.warning("No rides match the current filters.")
        st.stop()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Bookings", f"{len(f):,}")
    k2.metric("Success rate", f"{len(done) / len(f):.1%}")
    k3.metric("Revenue (completed)", f"₹{done['booking_value'].sum():,.0f}")
    k4.metric("Avg distance (completed)", f"{done['ride_distance'].mean():.1f} km" if len(done) else "n/a")
    k5.metric("Avg ratings (driver / customer)",
              f"{done['driver_rating'].mean():.2f} / {done['customer_rating'].mean():.2f}" if len(done) else "n/a")

    t_over, t_veh, t_rev, t_can, t_rate = st.tabs(["Overall", "Vehicle type", "Revenue", "Cancellation", "Ratings"])

    with t_over:
        daily = f.groupby([f["booking_date"].dt.date.rename("date"), "booking_status"]).size().reset_index(name="rides")
        c1, c2 = st.columns([3, 2])
        c1.plotly_chart(style(px.line(daily, x="date", y="rides", color="booking_status",
                                      title="Ride volume over time", color_discrete_sequence=PALETTE)),
                        use_container_width=True)
        status = f["booking_status"].value_counts().reset_index()
        status.columns = ["booking_status", "rides"]
        c2.plotly_chart(style(px.pie(status, names="booking_status", values="rides", hole=0.5,
                                     title="Booking status breakdown", color_discrete_sequence=PALETTE)),
                        use_container_width=True)
        hourly = f.groupby("hour").size().reset_index(name="bookings")
        st.plotly_chart(bar(hourly, "hour", "bookings", "Bookings by hour of day (peak demand)"),
                        use_container_width=True)

    with t_veh:
        c1, c2 = st.columns(2)
        dist = done.groupby("vehicle_type")["ride_distance"].sum().nlargest(5).reset_index()
        c1.plotly_chart(bar(dist, "vehicle_type", "ride_distance", "Top 5 vehicle types by total ride distance (km)"),
                        use_container_width=True)
        avg = done.groupby("vehicle_type")[["driver_rating", "customer_rating"]].mean().round(2).reset_index()
        avg = avg.melt("vehicle_type", var_name="rating_by", value_name="avg_rating")
        c2.plotly_chart(style(px.bar(avg, x="vehicle_type", y="avg_rating", color="rating_by", barmode="group",
                                     title="Average rating by vehicle type", range_y=[3.5, 4.5],
                                     color_discrete_sequence=PALETTE)), use_container_width=True)

    with t_rev:
        c1, c2 = st.columns(2)
        pay = done.groupby("payment_method")["booking_value"].sum().reset_index()
        c1.plotly_chart(style(px.pie(pay, names="payment_method", values="booking_value", hole=0.5,
                                     title="Revenue by payment method", color_discrete_sequence=PALETTE)),
                        use_container_width=True)
        top = (f.groupby("customer_id")["booking_value"].sum().nlargest(5).reset_index())
        c2.plotly_chart(bar(top, "customer_id", "booking_value", "Top 5 customers by total booking value"),
                        use_container_width=True)
        per_day = done.groupby(done["booking_date"].dt.date.rename("date"))["ride_distance"].sum().reset_index()
        st.plotly_chart(bar(per_day, "date", "ride_distance", "Ride distance per day (km, completed rides)"),
                        use_container_width=True)
        st.plotly_chart(style(px.box(done, x="vehicle_type", y="ride_distance",
                                     title="Ride distance distribution by vehicle type",
                                     color_discrete_sequence=PALETTE)), use_container_width=True)

    with t_can:
        c1, c2 = st.columns(2)
        cu = f[f["cancel_reason_customer"] != "Not Applicable"]["cancel_reason_customer"].value_counts().reset_index()
        cu.columns = ["reason", "rides"]
        c1.plotly_chart(bar(cu, "rides", "reason", "Cancelled by customers: reasons", orientation="h"),
                        use_container_width=True)
        dr = f[f["cancel_reason_driver"] != "Not Applicable"]["cancel_reason_driver"].value_counts().reset_index()
        dr.columns = ["reason", "rides"]
        c2.plotly_chart(bar(dr, "rides", "reason", "Cancelled by drivers: reasons", orientation="h"),
                        use_container_width=True)
        inc = f[f["incomplete_ride"] == "Yes"]["incomplete_reason"].value_counts().reset_index()
        inc.columns = ["reason", "rides"]
        st.plotly_chart(bar(inc, "reason", "rides", "Incomplete rides: reasons"), use_container_width=True)

    with t_rate:
        c1, c2 = st.columns(2)
        c1.plotly_chart(style(px.histogram(done, x="driver_rating", nbins=20, title="Driver ratings distribution",
                                           color_discrete_sequence=PALETTE)), use_container_width=True)
        c2.plotly_chart(style(px.histogram(done, x="customer_rating", nbins=20, title="Customer ratings distribution",
                                           color_discrete_sequence=[PALETTE[1]])), use_container_width=True)
        st.plotly_chart(style(px.density_heatmap(done, x="customer_rating", y="driver_rating", nbinsx=20, nbinsy=20,
                                                 title="Customer vs driver ratings (ride count)",
                                                 color_continuous_scale="Greens")), use_container_width=True)

elif page == "SQL explorer":
    st.title("SQL explorer")
    st.caption("Queries come from queries.sql and run against data/ola.db (SQLite). Sidebar filters do not apply here.")
    queries = load_queries()
    choice = st.selectbox("Question", list(queries))
    sql = st.text_area("SQL (editable, read-only SELECT statements)", queries[choice], height=200)
    if st.button("Run query", type="primary"):
        if not re.match(r"(?is)^\s*(select|with)\b", sql) or re.search(r"(?i)\b(insert|update|delete|drop|alter|create|attach|pragma)\b", sql):
            st.error("Only read-only SELECT queries are allowed.")
        else:
            try:
                res = run_sql(sql)
                st.success(f"{len(res):,} rows")
                search = st.text_input("Search within results")
                if search:
                    mask = res.astype(str).apply(lambda c: c.str.contains(search, case=False, na=False)).any(axis=1)
                    res = res[mask]
                st.dataframe(res, use_container_width=True, height=420)
                st.download_button("Download CSV", res.to_csv(index=False), "query_result.csv", "text/csv")
            except Exception as e:  # show SQL errors to the user
                st.error(f"Query failed: {e}")

elif page == "Power BI":
    st.title("Power BI dashboard")
    st.caption("Publish the dashboard (see powerbi_guide.md), then use File > Embed report > Publish to web "
               "and paste the link below, or set POWERBI_URL in .streamlit/secrets.toml.")
    default = st.secrets.get("POWERBI_URL", "") if hasattr(st, "secrets") else ""
    url = st.text_input("Power BI embed URL", default)
    if url.startswith("https://app.powerbi.com/"):
        st.components.v1.iframe(url, height=650, scrolling=True)
    elif url:
        st.error("Enter a link that starts with https://app.powerbi.com/")
    else:
        st.info("No Power BI link yet.")

else:
    st.title("Key insights")
    s = rides
    ok = s[s["booking_status"] == "Success"]
    n = len(s)
    st.markdown(f"""
**Scope:** {n:,} bookings from {s['booking_date'].min():%d %b} to {s['booking_date'].max():%d %b %Y}.

- **Only {len(ok) / n:.1%} of bookings complete.** {(s.booking_status == 'Canceled by Driver').mean():.1%} are cancelled by drivers, {(s.booking_status == 'Canceled by Customer').mean():.1%} by customers and {(s.booking_status == 'Driver Not Found').mean():.1%} end with no driver found.
- **Completed rides brought in ₹{ok['booking_value'].sum():,.0f}.** Cash is the largest share ({ok[ok.payment_method == 'Cash'].booking_value.sum() / ok.booking_value.sum():.0%}), then UPI ({ok[ok.payment_method == 'UPI'].booking_value.sum() / ok.booking_value.sum():.0%}).
- **Ratings are uniform.** Driver and customer averages are {ok['driver_rating'].mean():.2f} and {ok['customer_rating'].mean():.2f}, and barely differ across vehicle types.
- **Autos run short trips:** about {ok[ok.vehicle_type == 'Auto'].ride_distance.mean():.0f} km versus {ok[ok.vehicle_type != 'Auto'].ride_distance.mean():.0f} km for other vehicle types.
""")
    c = s[s["cancel_reason_driver"] != "Not Applicable"]["cancel_reason_driver"].value_counts()
    u = s[s["cancel_reason_customer"] != "Not Applicable"]["cancel_reason_customer"].value_counts()
    st.markdown(f"- **Top driver cancellation reason:** {c.index[0]} ({c.iloc[0]:,} rides). "
                f"**Top customer reason:** {u.index[0]} ({u.iloc[0]:,} rides).")
    st.markdown("**Recommendations:** reduce driver cancellations with pickup-distance and incentive rules, "
                "shift driver supply toward peak hours, and promote UPI to cut cash handling.")
