
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

st.set_page_config(
    page_title="ThreatStream | Security Analytics",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ ThreatStream")
st.subheader("Big Data-Based Web Traffic Analytics and Attack Detection")
st.caption("Local analytics dashboard | Synthetic demonstration data")

def load_csv(filename):
    path = OUT / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

summary = load_csv("summary.csv")
ips = load_csv("ip_summary.csv")
endpoints = load_csv("endpoint_summary.csv")
statuses = load_csv("status_summary.csv")
alerts = load_csv("alerts.csv")
timeline = load_csv("timeline_summary.csv")

if summary.empty:
    st.error("No analytics results found. Run analytics/process_logs.py first.")
    st.stop()

s = summary.iloc[0]

st.markdown("### Traffic overview")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Requests", f"{int(s['total_requests']):,}")
c2.metric("Unique IPs", int(s["unique_ips"]))
c3.metric("Error Requests", int(s["error_requests"]))
c4.metric("Suspicious IPs", len(alerts))

st.divider()

left, right = st.columns(2)

with left:
    st.markdown("### HTTP Status Distribution")
    if not statuses.empty:
        statuses["status"] = statuses["status"].astype(str)
        fig = px.pie(
            statuses,
            names="status",
            values="requests",
            hole=0.45,
            title="Requests by HTTP status code"
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.markdown("### Most Requested Endpoints")
    if not endpoints.empty:
        top_endpoints = endpoints.head(10).sort_values("requests")
        fig = px.bar(
            top_endpoints,
            x="requests",
            y="endpoint",
            orientation="h",
            title="Top endpoints by request count"
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()

left, right = st.columns(2)

with left:
    st.markdown("### Top IP Addresses")
    if not ips.empty:
        top_ips = ips.head(10).sort_values("requests")
        fig = px.bar(
            top_ips,
            x="requests",
            y="ip",
            orientation="h",
            title="Request volume by IP"
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.markdown("### Request Timeline")
    if not timeline.empty:
        timeline["time"] = pd.to_datetime(timeline["time"])
        fig = px.line(
            timeline,
            x="time",
            y="requests",
            markers=True,
            title="Requests per 5-minute window"
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()

st.markdown("### 🚨 Suspicious IP Alerts")

if alerts.empty:
    st.success("No IP addresses matched the current detection rules.")
else:
    st.warning(
        f"{len(alerts)} IP address(es) matched one or more detection rules. "
        "These are rule-based alerts, not confirmed attacks."
    )
    st.dataframe(alerts, use_container_width=True, hide_index=True)

st.markdown("### Full IP Analytics")
st.dataframe(ips, use_container_width=True, hide_index=True)

st.caption(
    "Detection is based on predefined thresholds and synthetic logs. "
    "This prototype is for educational demonstration, not production security monitoring."
)
