import os

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="DeployGuard | Command Center", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="expanded")

API_URL = os.getenv("DEPLOYGUARD_API_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TOKEN = os.getenv("DEPLOYGUARD_ADMIN_TOKEN", "")
ADMIN_HEADERS = {"X-Admin-Token": ADMIN_TOKEN}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
:root { --bg:#080d18; --border:#243147; --muted:#91a0b8; --text:#edf4ff; }
.stApp { background: radial-gradient(ellipse at 85% 0%, #142746 0%, transparent 38%), var(--bg); color: var(--text); font-family:'DM Sans',sans-serif; }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1500px; padding: 2rem 2.5rem 3rem; }
h1,h2,h3 { font-family:'Space Grotesk',sans-serif !important; letter-spacing:-0.5px; color: var(--text) !important; }
p, label, [data-testid="stCaptionContainer"] { color: var(--muted); }
[data-testid="stSidebar"] { background:#0b1220; border-right:1px solid var(--border); }
[data-testid="stMetric"] { background: linear-gradient(145deg,#141f32,#0f1726); border:1px solid var(--border); padding:20px 22px; border-radius:16px; min-height:115px; }
[data-testid="stMetricLabel"] { color:#9aabc4 !important; }
[data-testid="stMetricValue"] { color:#f2f7ff !important; font-family:'Space Grotesk',sans-serif; }
.stButton > button { background: linear-gradient(100deg,#3478f6,#6559ef); color:white; border:0; border-radius:10px; padding:.65rem 1rem; font-weight:700; min-height:45px; transition:.2s ease; }
.stButton > button:hover { border:1px solid #8bb8ff; box-shadow:0 0 24px #3979f640; color:white; }
.stTabs [data-baseweb="tab-list"] { gap:6px; border-bottom:1px solid var(--border); }
.stTabs [data-baseweb="tab"] { background:transparent; border-radius:10px 10px 0 0; padding:10px 18px; color:#9aabc4; font-weight:600; }
.stTabs [aria-selected="true"] { color:#fff !important; background:#14223a; }
.dg-hero { background: linear-gradient(115deg,#15243b,#101827 62%,#172344); border:1px solid #304361; border-radius:22px; padding:30px; margin:8px 0 24px; }
.dg-eyebrow { color:#80b7ff; font-size:11px; font-weight:700; letter-spacing:2px; text-transform:uppercase; }
.dg-title { font-family:'Space Grotesk',sans-serif; font-size:clamp(28px,4vw,42px); font-weight:700; letter-spacing:-1.7px; color:#f4f8ff; margin:10px 0 8px; }
.dg-subtitle { color:#a8bad4; font-size:14px; line-height:1.8; max-width:620px; }
.dg-chip { display:inline-block; background:#1b3553; color:#9ccaff; border:1px solid #355578; padding:6px 11px; border-radius:30px; font-size:11px; margin:14px 5px 0 0; }
.dg-panel { background: linear-gradient(145deg,#121d2d,#0e1624); border:1px solid #26354a; border-radius:17px; padding:22px; margin:8px 0 18px; }
.dg-section { font-family:'Space Grotesk',sans-serif; font-size:18px; font-weight:600; color:#eef4ff; margin-bottom:5px; }
.dg-muted { color:#92a3bd; font-size:12px; line-height:1.7; }
.dg-pill { display:inline-block; padding:6px 12px; border-radius:7px; font-size:11px; font-weight:700; letter-spacing:1px; }
.dg-ring-wrap { display:flex; align-items:center; gap:24px; }
.dg-ring-num { font-family:'Space Grotesk',sans-serif; font-size:34px; font-weight:700; fill:#f2f7ff; }
.dg-badge { display:inline-flex; align-items:center; gap:8px; font-size:12px; font-weight:600; padding:6px 12px; border-radius:20px; }
.dg-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
.dg-ai { background: linear-gradient(145deg,#131f35,#0f1829); border:1px solid #2e4468; border-left:4px solid #6559ef; border-radius:14px; padding:22px 24px; }
.dg-footer { text-align:center; color:#64748b; font-size:11px; padding:22px 0 4px; }
</style>
""", unsafe_allow_html=True)


def api_get(path, **kw):
    return requests.get(f"{API_URL}{path}", timeout=kw.pop("timeout", 10), **kw)


try:
    api_online = api_get("/health", timeout=2).ok
except requests.RequestException:
    api_online = False

# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("## 🛡️ DeployGuard")
    st.caption("DEPLOYMENT COMMAND CENTER")
    c = "#36d399" if api_online else "#ff647c"
    bg = "#12382f" if api_online else "#421f2b"
    st.markdown(f'<span class="dg-badge" style="background:{bg};color:{c}"><span class="dg-dot" '
                f'style="background:{c}"></span>{"Backend online" if api_online else "Backend offline"}</span>',
                unsafe_allow_html=True)
    st.divider()
    st.markdown("### Control Panel")
    scenario = st.selectbox("Quick scenario", ["Custom metrics", "Healthy release", "Slow application",
                                               "Error spike", "Unhealthy deployment"])
    presets = {"Healthy release": (0.5, 120, "healthy"), "Slow application": (2.0, 850, "healthy"),
               "Error spike": (12.0, 300, "healthy"), "Unhealthy deployment": (15.0, 1200, "unhealthy"),
               "Custom metrics": (2.0, 150, "healthy")}
    d_er, d_lat, d_hs = presets[scenario]
    # key includes scenario so presets actually update the widgets
    error_rate = st.slider("Error rate (%)", 0.0, 100.0, float(d_er), 0.5, key=f"er_{scenario}")
    latency = st.number_input("Response latency (ms)", 0, 120000, int(d_lat), 50, key=f"lat_{scenario}")
    health = st.selectbox("Application health", ["healthy", "unhealthy"],
                          index=0 if d_hs == "healthy" else 1, key=f"hs_{scenario}")
    st.divider()
    analyze = st.button("⚡ Analyze Deployment", type="primary", use_container_width=True)
    st.caption("Risk score: deterministic rules. Explanation: AI (advisory).")
    st.caption("Sidebar metrics are manual input. Live metrics: see the CloudWatch tab.")

# ---------------- Hero ----------------
st.markdown("""
<div class="dg-hero">
  <div class="dg-eyebrow">INFRASTRUCTURE INTELLIGENCE / 01</div>
  <div class="dg-title">Deployment Command Center</div>
  <div class="dg-subtitle">Understand deployment health, identify release risks, and make safer recovery decisions from one workspace.</div>
  <span class="dg-chip">● RISK ENGINE</span><span class="dg-chip">AI DIAGNOSIS</span>
  <span class="dg-chip">FASTAPI BACKEND</span><span class="dg-chip">AWS-READY</span>
</div>
""", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("API Status", "ONLINE" if api_online else "OFFLINE")
m2.metric("Risk Engine", "READY" if api_online else "UNAVAILABLE")
m3.metric("AI Diagnosis", "READY" if api_online else "UNAVAILABLE")
m4.metric("Monitoring Mode", "MANUAL INPUT")

if analyze:
    if not api_online:
        st.error("Backend unavailable. Start it with: uvicorn app.main:app --reload")
    else:
        try:
            r = api_get("/analyze", params={"error_rate": error_rate, "latency_ms": latency,
                                            "health_status": health})
            r.raise_for_status()
            st.session_state["last_analysis"] = r.json()
            st.session_state.pop("ai_diagnosis", None)
        except (requests.RequestException, ValueError) as exc:
            st.error(f"Analysis failed: {exc}")

result = st.session_state.get("last_analysis")
tab_risk, tab_ai, tab_cw, tab_hist = st.tabs(["📊 Risk Analysis", "🤖 AI Diagnosis", "☁️ CloudWatch & Rollback", "🕘 History"])

# ---------------- Risk ----------------
with tab_risk:
    if not result:
        st.markdown('<div class="dg-panel"><div class="dg-section">Your next deployment insight starts here.</div>'
                    '<div class="dg-muted">Pick a scenario in the sidebar and click <b>Analyze Deployment</b>.</div></div>',
                    unsafe_allow_html=True)
    else:
        score, level, mt = result["risk_score"], result["risk_level"], result["metrics"]
        colors = {"LOW": ("#36d399", "#12382f"), "MEDIUM": ("#ffc46b", "#3d2e19"), "HIGH": ("#ff647c", "#421f2b")}
        color, pill_bg = colors.get(level, ("#64a8ff", "#1b3553"))
        circ = 326.7
        offset = circ * (1 - min(max(score, 0), 100) / 100)
        note = {"HIGH": "Immediate investigation recommended.",
                "MEDIUM": "Review signals and continue monitoring."}.get(level, "Signals are within the low-risk range.")
        left, right = st.columns([1, 1.4], gap="large")
        with left:
            st.markdown(f"""
<div class="dg-panel"><div class="dg-muted">DEPLOYMENT RISK SCORE</div>
<div class="dg-ring-wrap" style="margin-top:14px">
<svg width="130" height="130" viewBox="0 0 130 130">
<circle cx="65" cy="65" r="52" fill="none" stroke="#253247" stroke-width="11"/>
<circle cx="65" cy="65" r="52" fill="none" stroke="{color}" stroke-width="11" stroke-linecap="round"
 stroke-dasharray="{circ}" stroke-dashoffset="{offset}" transform="rotate(-90 65 65)"/>
<text x="65" y="73" text-anchor="middle" class="dg-ring-num">{score}</text></svg>
<div><span class="dg-pill" style="color:{color};background:{pill_bg}">{level} RISK</span>
<div class="dg-muted" style="margin-top:12px">{note}</div></div></div></div>""", unsafe_allow_html=True)
        with right:
            st.markdown('<div class="dg-section">Signal Breakdown</div>', unsafe_allow_html=True)
            a, b = st.columns(2)
            a.metric("Error Rate", f"{mt['error_rate_percent']}%")
            b.metric("Latency", f"{mt['latency_ms']} ms")
            a.metric("Health Status", mt["health_status"].upper())
            b.metric("Risk Level", level)
        st.markdown("### Recommended Action")
        {"HIGH": st.error, "MEDIUM": st.warning}.get(level, st.success)(result["recommendation"])
        with st.expander("View raw analysis response"):
            st.json(result)

# ---------------- AI ----------------
with tab_ai:
    if not result:
        st.info("Run **Analyze Deployment** first. The AI explains the metrics you analyzed.")
    else:
        mt = result["metrics"]
        if st.button("🤖 Run AI Diagnosis", key="ai_btn"):
            with st.spinner("Asking the model..."):
                try:
                    r = requests.post(f"{API_URL}/diagnose", timeout=60, json={
                        "error_rate": mt["error_rate_percent"], "latency_ms": mt["latency_ms"],
                        "health_status": mt["health_status"]})
                    if r.ok:
                        st.session_state["ai_diagnosis"] = r.json()
                    else:
                        try:
                            detail = r.json().get("detail", r.text)
                        except ValueError:
                            detail = r.text
                        st.error(f"Diagnosis failed ({r.status_code}): {detail}")
                except requests.RequestException as e:
                    st.error(f"Backend not reachable: {e}")
        ai = st.session_state.get("ai_diagnosis")
        if ai:
            st.markdown('<div class="dg-ai">', unsafe_allow_html=True)
            st.markdown(ai["diagnosis"])
            st.markdown("</div>", unsafe_allow_html=True)
            st.caption(f"Model: {ai.get('model','unknown')} · Advisory only. No rollback has been performed.")

# ---------------- CloudWatch & Rollback ----------------
with tab_cw:
    st.markdown("#### Live metrics (AWS CloudWatch)")
    st.caption("Works only after an Elastic Beanstalk environment exists and has traffic.")
    if st.button("Fetch live metrics", key="cw_btn"):
        try:
            r = api_get("/metrics/live", timeout=20)
            if r.ok:
                st.session_state["live"] = r.json()
            else:
                st.session_state.pop("live", None)
                st.error(f"({r.status_code}) {r.json().get('detail', r.text)}")
        except requests.RequestException as e:
            st.error(f"Backend not reachable: {e}")
    live = st.session_state.get("live")
    if live:
        st.json(live)
        if None not in (live["error_rate"], live["latency_ms"], live["health_status"]):
            if st.button("Analyze these live metrics", key="cw_an"):
                r = api_get("/analyze", params={"error_rate": live["error_rate"],
                                                "latency_ms": live["latency_ms"],
                                                "health_status": live["health_status"]})
                if r.ok:
                    st.session_state["last_analysis"] = r.json()
                    st.session_state.pop("ai_diagnosis", None)
                    st.success("Done. Open the Risk Analysis tab.")
        else:
            st.warning("Some metrics are missing (no datapoints), so analysis is disabled.")

    st.divider()
    st.markdown("#### Rollback")
    if not ADMIN_TOKEN:
        st.info("Production rollback is done from GitHub: **Actions → Rollback → Run workflow**. "
                "It lists versions first, then redeploys the one you choose (with approval).")
    else:
        st.warning("Rollback needs DEPLOYGUARD_ADMIN_TOKEN set on the server and in this dashboard's environment. It only runs after you tick the confirmation box.")
        if st.button("List versions", key="rb_list"):
            try:
                r = api_get("/rollback/versions", timeout=20, headers=ADMIN_HEADERS)
                if r.ok:
                    st.session_state["versions"] = r.json()
                else:
                    st.error(f"({r.status_code}) {r.json().get('detail', r.text)}")
            except requests.RequestException as e:
                st.error(f"Backend not reachable: {e}")
        v = st.session_state.get("versions")
        if v:
            st.caption(f"Current version: {v['current_version']}")
            target = st.selectbox("Roll back to", v["available_versions"], key="rb_target")
            sure = st.checkbox(f"I understand this will redeploy **{target}** to the environment.", key="rb_sure")
            if st.button("Roll back now", key="rb_go", disabled=not sure):
                r = requests.post(f"{API_URL}/rollback", json={"version_label": target, "confirm": True}, headers=ADMIN_HEADERS, timeout=30)
                (st.success if r.ok else st.error)(r.json().get("message") or r.json().get("detail", r.text))


# ---------------- History ----------------
with tab_hist:
    if not api_online:
        st.info("Backend offline.")
    else:
        try:
            recs = api_get("/history", timeout=5).json()
            if not recs:
                st.info("No analyses saved yet.")
            else:
                st.dataframe(pd.json_normalize(recs[-20:][::-1]), use_container_width=True, hide_index=True)
                st.caption(f"Latest {min(len(recs), 20)} of {len(recs)} saved analyses.")
        except Exception as e:
            st.error(f"Could not load history: {type(e).__name__}: {e}")

st.markdown('<div class="dg-footer">DEPLOYGUARD • HACKATHON MVP • AI DIAGNOSIS IS ADVISORY • ROLLBACK IS MANUAL AND CONFIRMED</div>',
            unsafe_allow_html=True)
