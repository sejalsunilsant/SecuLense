from pathlib import Path
from datetime import datetime, timedelta, timezone
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from secu_lense import config
from secu_lense.sources import read_table
from secu_lense.ml_pipeline import predict_filing_risk
from scripts.local_web_server import AuthStore

st.set_page_config(page_title="SecuLense Demo",page_icon="🔎",layout="wide",initial_sidebar_state="expanded")
st.markdown("""
<style>
:root { --ink:#14253d; --muted:#66758a; --teal:#087e8b; --mint:#c6f2e7; --paper:#f4f8fb; --line:#e2eaf1; }
.stApp { background:linear-gradient(145deg,#f7fafc 0%,#eff6f8 55%,#f7f8fc 100%); color:var(--ink); font-family:'Segoe UI',Arial,sans-serif; }
[data-testid="stHeader"] { background:rgba(247,250,252,.86); }
[data-testid="stMainBlockContainer"] { max-width:1480px; padding-top:1.4rem; padding-bottom:3rem; }
[data-testid="stSidebar"] { background:#eaf0f4 !important; border-right:1px solid #d5e0e7; }
[data-testid="stSidebar"] > div, [data-testid="stSidebarContent"] { background:#eaf0f4 !important; }
[data-testid="stSidebar"] * { color:#18364d; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { background:#f9fbfc; border:1px solid #dce6eb; border-radius:10px; padding:.45rem .7rem; transition:all .16s ease; }
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background:#e0f3ee; border-color:#9bd9ca; transform:translateX(2px); }
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div { background:#fff; border-color:#cbd9e1; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] * { color:#18364d !important; }
[data-testid="stSidebar"] .stButton button { background:#fff !important; border:1px solid #cbd9e1 !important; color:#18364d !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] input { accent-color:#087e8b; }
.sl-hero { position:relative; overflow:hidden; display:flex; align-items:center; justify-content:space-between; gap:1.5rem; padding:1.45rem 1.8rem; margin:.2rem 0 1.3rem; border-radius:22px; background:linear-gradient(115deg,#10283c 0%,#175365 70%,#087e8b 100%); box-shadow:0 16px 38px rgba(19,57,77,.16); }
.sl-hero:after { content:''; position:absolute; width:230px; height:230px; right:12%; top:-145px; border:1px solid rgba(198,242,231,.2); border-radius:50%; box-shadow:0 0 0 28px rgba(198,242,231,.035),0 0 0 60px rgba(198,242,231,.025); }
.sl-brand { color:#fff; font-family:'Segoe UI',Arial,sans-serif; font-size:1.72rem; font-weight:800; letter-spacing:-.045em; line-height:1.1; }
.sl-brand span { color:#8fe3d2; }
.sl-subtitle { color:#c6dce4; font-size:.91rem; margin-top:.43rem; }
.sl-hero-tag { z-index:1; white-space:nowrap; color:#c9f5e9; border:1px solid rgba(185,244,227,.34); background:rgba(255,255,255,.08); padding:.52rem .78rem; border-radius:99px; font-size:.76rem; font-weight:700; letter-spacing:.04em; }
h1,h2,h3 { color:#132c43; font-family:'Segoe UI',Arial,sans-serif !important; letter-spacing:-.035em; }
h2 { margin-top:.4rem !important; }
[data-testid="stMetric"] { background:linear-gradient(145deg,#fff,#f8fbfd); border:1px solid var(--line); border-radius:15px; padding:1rem 1.1rem; box-shadow:0 5px 18px rgba(28,57,79,.045); transition:transform .16s ease,box-shadow .16s ease; }
[data-testid="stMetric"]:hover { transform:translateY(-2px); box-shadow:0 10px 24px rgba(28,57,79,.09); }
[data-testid="stMetricLabel"] { color:#65758a; }
[data-testid="stMetricValue"] { color:#12344d; font-family:'Segoe UI',Arial,sans-serif; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--line) !important; border-radius:16px !important; background:rgba(255,255,255,.78); }
.stButton>button,.stDownloadButton>button { border-radius:10px; border:1px solid #c8dce4; color:#16465a; background:#fff; font-weight:650; transition:all .16s ease; }
.stButton>button:hover,.stDownloadButton>button:hover { border-color:#078391; color:#066e78; background:#eaf9f5; transform:translateY(-1px); }
[data-testid="stBaseButton-primary"] { background:linear-gradient(100deg,#087e8b,#13a38b); color:white; border:0; }
[data-testid="stTextInput"] input,[data-testid="stChatInput"] textarea { border-radius:11px; }
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,[data-testid="stMultiSelect"] div[data-baseweb="select"] > div { border-radius:10px; }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:13px; overflow:hidden; }
[data-testid="stPlotlyChart"] { border-radius:15px; }
[data-testid="stAlert"] { border-radius:13px; color:#18364d !important; }
[data-testid="stAlert"] * { color:#18364d !important; }
[data-testid="stBottom"], [data-testid="stBottomBlockContainer"] { background:#f4f8fb !important; }
[data-testid="stChatInput"] { background:#fff !important; border:1px solid #cbd9e1 !important; border-radius:13px !important; }
[data-testid="stChatInput"] textarea { background:#fff !important; color:#18364d !important; -webkit-text-fill-color:#18364d !important; }
[data-testid="stChatInput"] textarea::placeholder { color:#6f8191 !important; -webkit-text-fill-color:#6f8191 !important; opacity:1 !important; }
[data-testid="stChatInput"] button { color:#087e8b !important; }
.synthetic-notice { border:1px solid #e2c27b; background:#fff5d9; color:#60470e; border-radius:13px; padding:.85rem 1rem; margin:.35rem 0 .8rem; font-weight:650; line-height:1.5; }
.synthetic-notice small { display:block; font-weight:400; color:#705b2c; margin-top:.2rem; }
[data-testid="stChatMessage"] { border:1px solid var(--line); border-radius:15px; background:#fff; padding:.7rem .9rem; }
/* High-contrast dark theme for the Streamlit fallback. */
.stApp { background:#0b121a !important; color:#e4edf4 !important; }
[data-testid="stHeader"] { background:#0b121a !important; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div, [data-testid="stSidebarContent"] { background:#101b26 !important; border-color:#273846 !important; }
[data-testid="stSidebar"] * { color:#dbe7ee !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { background:#15232e !important; border-color:#2c414f !important; color:#e1eaf0 !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background:#1a3735 !important; border-color:#38776e !important; }
[data-testid="stSidebar"] .stButton button { background:#172732 !important; border-color:#39505d !important; color:#e1edf2 !important; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div { background:#172732 !important; border-color:#39505d !important; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] * { color:#e1edf2 !important; }
h1,h2,h3,h4,p,li,label { color:#e4edf4; }
[data-testid="stCaptionContainer"] *, [data-testid="stMarkdownContainer"] p { color:#c0cdd6; }
[data-testid="stMetric"] { background:#131f2b !important; border-color:#2a3d4c !important; }
[data-testid="stMetricLabel"] { color:#bac8d2 !important; }
[data-testid="stMetricValue"] { color:#f0f5f8 !important; }
div[data-testid="stVerticalBlockBorderWrapper"] { background:#121f2b !important; border-color:#2b3e4d !important; }
.stButton>button,.stDownloadButton>button { background:#172631 !important; border-color:#38505d !important; color:#e0ebf0 !important; }
.stButton>button:hover,.stDownloadButton>button:hover { background:#1b3935 !important; border-color:#398778 !important; color:#c0f2e0 !important; }
[data-testid="stBaseButton-primary"] { background:#087e8b !important; color:#fff !important; }
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,[data-testid="stDateInput"] input,[data-testid="stChatInput"] textarea { background:#101b25 !important; color:#eef4f7 !important; border-color:#3b4d5b !important; -webkit-text-fill-color:#eef4f7 !important; }
[data-testid="stTextInput"] input::placeholder,[data-testid="stChatInput"] textarea::placeholder { color:#aebdc7 !important; -webkit-text-fill-color:#aebdc7 !important; opacity:1 !important; }
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,[data-testid="stMultiSelect"] div[data-baseweb="select"] > div { background:#101b25 !important; border-color:#3b4d5b !important; }
[data-testid="stSelectbox"] div[data-baseweb="select"] *,[data-testid="stMultiSelect"] div[data-baseweb="select"] * { color:#eef4f7 !important; }
[data-testid="stDataFrame"] { border-color:#2e414f !important; }
[data-testid="stBottom"],[data-testid="stBottomBlockContainer"] { background:#0b121a !important; }
[data-testid="stChatInput"] { background:#101b25 !important; border-color:#3b4d5b !important; }
[data-testid="stChatInput"] button { color:#74ddc3 !important; }
[data-testid="stAlert"] { background:#192632 !important; border-color:#354957 !important; }
[data-testid="stAlert"] * { color:#e1ebf0 !important; }
.synthetic-notice { background:#322918 !important; border-color:#755e31 !important; color:#ffe19a !important; }
.synthetic-notice small { color:#dfc98c !important; }
[data-testid="stPlotlyChart"] { background:transparent !important; }
@media(max-width:800px) { .sl-hero { align-items:flex-start; flex-direction:column; padding:1.2rem; border-radius:16px; } .sl-brand {font-size:1.45rem;} .sl-hero-tag {font-size:.68rem;} }
</style>
<div class="sl-hero"><div><div class="sl-brand">Secu<span>Lense</span></div><div class="sl-subtitle">Corporate filing risk explorer · interactive research workspace</div></div><div class="sl-hero-tag">LOCAL DEMO · NO API KEYS</div></div>
""",unsafe_allow_html=True)
auth_store=AuthStore()
session_expiry=st.session_state.get("local_auth_expires")
if st.session_state.get("local_user") and session_expiry and datetime.now(timezone.utc)>=session_expiry:
    st.session_state.pop("local_user",None)
    st.session_state.pop("local_auth_expires",None)
if not st.session_state.get("local_user"):
    st.markdown("## Welcome to SecuLense")
    st.caption("Sign in to open this local research dashboard.")
    if auth_store.user_count()==0:
        with st.form("first_account_setup"):
            st.write("Set up the local owner account")
            setup_username=st.text_input("Username",max_chars=32)
            setup_password=st.text_input("Password (at least 10 characters)",type="password")
            setup_confirm=st.text_input("Confirm password",type="password")
            setup_submit=st.form_submit_button("Create account",type="primary")
        if setup_submit:
            if setup_password!=setup_confirm:
                st.error("Those passwords do not match.")
            else:
                try:
                    st.session_state["local_user"]=auth_store.create_first_user(setup_username,setup_password)
                    st.session_state["local_auth_expires"]=datetime.now(timezone.utc)+timedelta(hours=12)
                    st.rerun()
                except (ValueError,RuntimeError) as exc:
                    st.error(str(exc))
    else:
        with st.form("local_sign_in"):
            login_username=st.text_input("Username",max_chars=32)
            login_password=st.text_input("Password",type="password")
            login_submit=st.form_submit_button("Sign in",type="primary")
        if login_submit:
            user=auth_store.authenticate(login_username,login_password)
            if user:
                st.session_state["local_user"]=user
                st.session_state["local_auth_expires"]=datetime.now(timezone.utc)+timedelta(hours=12)
                st.rerun()
            else:
                st.error("Username or password is incorrect.")
    st.stop()
st.sidebar.caption(f"Signed in as {st.session_state['local_user']['username']}")
if st.sidebar.button("Sign out",key="auth_sign_out"):
    del st.session_state["local_user"]
    st.session_state.pop("local_auth_expires",None)
    st.rerun()
st.markdown("<div class='synthetic-notice'>SYNTHETIC DEMONSTRATION DATA<small>Company filing text, risk scores, and prices are simulated. They are not actual SEC filings or historical market data. Do not use for investment decisions.</small></div>",unsafe_allow_html=True)
st.caption("Educational research demo · analysis shows synthetic associations only, not causation or investment advice")

@st.cache_data
def load(name):
    return read_table(config.DATA_DIR/"gold"/(name+".parquet"))

if st.sidebar.button("Refresh data"):
    st.cache_data.clear(); st.rerun()
pages=["Overview","Company Explorer","Filing Comparison","Risk Scores","Price & Event Study","Model Lab","Financial Glossary","Educational Q&A","Chat Assistant","Data Quality"]
page=st.sidebar.radio("Navigate",pages)
tables={name:load(name) for name in ("companies","filings","filing_diffs","risk_scores","daily_prices","event_returns","financial_glossary","educational_qa")}
companies,filings,diffs,risks,prices,events,glossary,qa=(tables[n] for n in ("companies","filings","filing_diffs","risk_scores","daily_prices","event_returns","financial_glossary","educational_qa"))

def ticker_picker(label="Company"):
    if companies.empty: return None
    options=companies["ticker"].dropna().astype(str).sort_values().unique().tolist()
    return st.selectbox(label,options,index=options.index(global_ticker) if global_ticker in options else 0,key=f"ticker_{page}",format_func=lambda t:f"{t} — {companies.loc[companies.ticker.astype(str)==t,'company_name'].iloc[0]}")

def download_table(label, frame, key):
    if not frame.empty:
        st.download_button(label, frame.to_csv(index=False).encode("utf-8"), file_name=f"seculense_{key}.csv", mime="text/csv", key=f"download_{key}")

def within_dates(frame, column):
    if frame.empty or column not in frame or not date_window: return frame.copy()
    dates=pd.to_datetime(frame[column],errors="coerce")
    return frame.loc[dates.dt.date.between(date_window[0],date_window[1])].copy()

tickers=companies["ticker"].dropna().astype(str).sort_values().unique().tolist() if not companies.empty else []
global_ticker=st.sidebar.selectbox("Company filter",["All companies"]+tickers,key="global_company")
date_source=pd.to_datetime(filings["filing_date"],errors="coerce").dropna() if not filings.empty else pd.Series(dtype="datetime64[ns]")
date_min=date_source.min().date() if not date_source.empty else pd.Timestamp.today().date()
date_max=date_source.max().date() if not date_source.empty else date_min
date_window=st.sidebar.date_input("Filing date range",value=(date_min,date_max),min_value=date_min,max_value=date_max,key="global_dates")
if not isinstance(date_window,tuple): date_window=(date_window,date_window)
company_context="All companies" if global_ticker=="All companies" else global_ticker
st.markdown(f"<div style='display:flex;gap:.55rem;align-items:center;margin:.1rem 0 1.1rem;color:#52687c;font-size:.82rem'><span style='background:#e5f3f1;border:1px solid #cce9e3;color:#176b69;padding:.28rem .65rem;border-radius:99px;font-weight:700'>{page}</span><span>Company: <b>{company_context}</b></span><span style='color:#9aacb8'>·</span><span>{date_window[0]} — {date_window[1]}</span></div>",unsafe_allow_html=True)

def answer_local_query(question):
    """Answer from the loaded demo tables with transparent, local rules."""
    q=question.lower()
    mentioned=[t for t in tickers if t.lower() in q]
    ticker=mentioned[0] if mentioned else (global_ticker if global_ticker!="All companies" else None)
    def scope(frame): return frame[frame.ticker.astype(str)==ticker] if ticker and "ticker" in frame else frame
    label=f" for {ticker}" if ticker else " across the selected dataset"
    if any(word in q for word in ("glossary","define","definition","what is")):
        matches=glossary[glossary.apply(lambda row: any(w in str(row.get("term"," ")).lower() for w in q.split()),axis=1)] if not glossary.empty else glossary
        if not matches.empty:
            return "**Glossary matches**\n\n"+"\n\n".join(f"**{r.term}:** {r.definition}" for r in matches.head(5).itertuples())+"\n\nTry asking about a specific financial term."
    if any(word in q for word in ("return","performance","price","stock","horizon")):
        view=scope(events).copy()
        if not view.empty:
            view["return_pct"]=pd.to_numeric(view.cumulative_return,errors="coerce")*100
            summary=view.groupby("horizon").return_pct.agg(["count","mean","min","max"]).reset_index().sort_values("horizon")
            lines=[f"{int(r.horizon)}-session: average {r['mean']:.2f}% (range {r['min']:.2f}% to {r['max']:.2f}%, n={int(r['count'])})" for _,r in summary.iterrows()]
            return f"**Synthetic filing-event returns{label}**\n\n"+"\n".join(f"- {x}" for x in lines)+"\n\nThese are descriptive synthetic outcomes, not forecasts or evidence that filings caused returns."
    if any(word in q for word in ("compare","change","changed","diff","filing")):
        view=scope(diffs)
        if not view.empty:
            counts=view.groupby(["change_type","risk_category"]).size().sort_values(ascending=False).head(6)
            rows=[f"{kind} · {category}: {int(count)}" for (kind,category),count in counts.items()]
            example=view.iloc[0]
            return f"**Filing comparison summary{label}**\n\nParagraph changes by type and risk theme:\n"+"\n".join(f"- {x}" for x in rows)+f"\n\nExample ({example.section_name}, {example.change_type}):\n\nPrevious: {example.old_text}\n\nCurrent: {example.new_text}\n\nOpen Filing Comparison to filter changes by filing, section, and category."
    if any(word in q for word in ("risk","severity","novelty","concern","theme")):
        view=scope(risks)
        if not view.empty:
            summary=view.groupby("risk_category").agg(records=("severity_score","size"),mean_severity=("severity_score","mean")).sort_values("mean_severity",ascending=False).head(7)
            return f"**Highest average synthetic risk scores{label}**\n\n"+"\n".join(f"- {category}: mean severity {row.mean_severity:.2f} across {int(row.records)} records" for category,row in summary.iterrows())+"\n\nThese are model-demo scores. Review the source paragraph and filing comparison before drawing conclusions."
    if any(word in q for word in ("company","companies","ticker","dataset","data")):
        return f"The loaded demo contains **{len(companies)} companies, {len(filings)} filings, {len(risks)} risk-score rows, {len(diffs)} paragraph comparisons, and {len(events)} event-return rows**. All are synthetic. Try asking for risk themes, filing changes, event returns, or a glossary definition."
    return "I can answer questions about the loaded synthetic dataset. Try: **What are the main risk themes for AAPL?**, **Summarize filing changes for MSFT**, **What were the event returns for NVDA?**, or **Define gross margin**. I only use the local demo tables; I don’t call an external AI service."

if page=="Overview":
    selected=global_ticker
    active_filings=within_dates(filings,"filing_date")
    if selected!="All companies": active_filings=active_filings[active_filings.ticker.astype(str)==selected]
    active_risks=risks[risks.ticker.astype(str)==selected] if selected!="All companies" else risks
    active_events=events[events.ticker.astype(str)==selected] if selected!="All companies" else events
    a,b,c,d=st.columns(4)
    a.metric("Companies",companies.ticker.nunique() if selected=="All companies" and not companies.empty else int(selected!="All companies")); b.metric("Filings",len(active_filings)); c.metric("Risk records",len(active_risks)); d.metric("Event-return rows",len(active_events))
    if not active_filings.empty:
        recent=active_filings.copy(); recent["filing_date"]=pd.to_datetime(recent.filing_date,errors="coerce")
        st.subheader("Filing activity"); st.dataframe(recent.sort_values("filing_date",ascending=False),use_container_width=True,hide_index=True)
        download_table("Download filtered filings",recent,"overview_filings")
    if not active_risks.empty:
        categories=st.multiselect("Risk categories",sorted(active_risks.risk_category.dropna().astype(str).unique()),default=sorted(active_risks.risk_category.dropna().astype(str).unique()),key="overview_risk_categories")
        view=active_risks[active_risks.risk_category.astype(str).isin(categories)]
        if not view.empty: st.plotly_chart(px.histogram(view,x="risk_category",color="risk_category",title="Risk score distribution · synthetic records"),use_container_width=True)
    st.info("All displayed records are synthetic. The filing-event study is descriptive and does not establish that disclosure changes cause returns.")
elif page=="Company Explorer":
    ticker=ticker_picker()
    if ticker:
        company=companies[companies.ticker.astype(str)==ticker].iloc[0]
        st.subheader(f"{company.company_name} ({ticker})"); st.write(f"Sector: {company.get('sector','Unknown')} · CIK reference: {company.get('cik','')}")
        fp=within_dates(filings[filings.ticker.astype(str)==ticker],"filing_date"); fp["filing_date"]=pd.to_datetime(fp.filing_date,errors="coerce")
        pp=prices[prices.ticker.astype(str)==ticker].copy(); pp["trade_date"]=pd.to_datetime(pp.trade_date,errors="coerce"); pp=pp.sort_values("trade_date")
        if not pp.empty:
            price_start,price_end=st.slider("Price chart window",min_value=pp.trade_date.min().date(),max_value=pp.trade_date.max().date(),value=(pp.trade_date.min().date(),pp.trade_date.max().date()),key="price_window")
            pp=pp[pp.trade_date.dt.date.between(price_start,price_end)]
        chart_type=st.radio("Chart style",["Candlestick","Close price"],horizontal=True,key="company_chart_type")
        show_markers=st.checkbox("Show filing-date markers",value=True,key="filing_markers")
        if not pp.empty and {"open","high","low","close"}.issubset(pp.columns):
            fig=go.Figure(go.Candlestick(x=pp.trade_date,open=pp.open,high=pp.high,low=pp.low,close=pp.close,name="Synthetic OHLC") if chart_type=="Candlestick" else go.Scatter(x=pp.trade_date,y=pp.close,mode="lines",name="Synthetic close"))
            if show_markers:
                for f in fp.itertuples():
                    if pd.notna(f.filing_date): fig.add_vline(x=f.filing_date,line_dash="dot",line_color="#e08b35",opacity=.6)
            fig.update_layout(title="Synthetic daily prices with filing dates",xaxis_title="Trading date",yaxis_title="Synthetic price",xaxis_rangeslider_visible=False)
            st.plotly_chart(fig,use_container_width=True)
        st.subheader("Filing records"); st.dataframe(fp.sort_values("filing_date",ascending=False),use_container_width=True,hide_index=True); download_table("Download company filings",fp,"company_filings")
elif page=="Filing Comparison":
    ticker=ticker_picker()
    subset=within_dates(diffs[diffs.ticker.astype(str)==ticker],"current_filing_date") if ticker and not diffs.empty and "current_filing_date" in diffs else (diffs[diffs.ticker.astype(str)==ticker] if ticker and not diffs.empty else pd.DataFrame())
    if subset.empty: st.info("No comparisons found for this company.")
    else:
        current=subset.current_accession.dropna().astype(str).unique().tolist()
        accession=st.selectbox("Current filing",current)
        selected_diffs=subset[subset.current_accession.astype(str)==accession].copy()
        change_types=st.multiselect("Change types",sorted(selected_diffs.change_type.dropna().astype(str).unique()),default=sorted(selected_diffs.change_type.dropna().astype(str).unique()),key="diff_change_types")
        categories=st.multiselect("Risk categories",sorted(selected_diffs.risk_category.dropna().astype(str).unique()),default=sorted(selected_diffs.risk_category.dropna().astype(str).unique()),key="diff_categories")
        selected_diffs=selected_diffs[selected_diffs.change_type.astype(str).isin(change_types)&selected_diffs.risk_category.astype(str).isin(categories)]
        section=st.selectbox("Section",["All sections"]+sorted(selected_diffs.section_name.dropna().astype(str).unique().tolist()),key="diff_section")
        if section!="All sections": selected_diffs=selected_diffs[selected_diffs.section_name.astype(str)==section]
        st.caption(f"Showing {len(selected_diffs)} paragraph changes")
        download_table("Download comparison rows",selected_diffs,"filing_diffs")
        for row in selected_diffs.itertuples():
            color={"added":"#e8f6ec","new":"#e8f6ec","removed":"#fdecec","modified":"#fff5dc"}.get(str(row.change_type).lower(),"#f2f4f8")
            st.markdown(f"**{row.section_name} · {row.risk_category} · {row.change_type} · similarity {row.similarity_score}**")
            left,right=st.columns(2)
            with left: st.markdown("Previous text"); st.markdown(f"<div style='background:{color};padding:10px'>{row.old_text or '—'}</div>",unsafe_allow_html=True)
            with right: st.markdown("Current text"); st.markdown(f"<div style='background:{color};padding:10px'>{row.new_text or '—'}</div>",unsafe_allow_html=True)
elif page=="Risk Scores":
    ticker=ticker_picker(); subset=within_dates(risks[risks.ticker.astype(str)==ticker],"filing_date") if ticker and not risks.empty else pd.DataFrame()
    if subset.empty: st.info("No risk records found.")
    else:
        categories=st.multiselect("Categories",sorted(subset.risk_category.dropna().astype(str).unique()),default=sorted(subset.risk_category.dropna().astype(str).unique()),key="risk_categories")
        min_severity=st.slider("Minimum severity",0.0,1.0,0.0,0.05,key="risk_min_severity")
        view=subset[subset.risk_category.astype(str).isin(categories)&(pd.to_numeric(subset.severity_score,errors="coerce")>=min_severity)]
        chart=st.radio("Visualization",["Category severity","Severity vs novelty","Score over time"],horizontal=True,key="risk_visual")
        if chart=="Category severity": fig=px.bar(view,x="risk_category",y="severity_score",color="novelty_score",hover_data=["filing_date","confidence_score"],title=f"Synthetic severity and novelty · {ticker}")
        elif chart=="Severity vs novelty": fig=px.scatter(view,x="severity_score",y="novelty_score",color="risk_category",size="confidence_score",hover_data=["filing_date","source_section","evidence"],title=f"Synthetic risk scores · {ticker}")
        else: fig=px.scatter(view,x="filing_date",y="severity_score",color="risk_category",hover_data=["source_section","evidence"],title=f"Synthetic risk over time · {ticker}")
        st.plotly_chart(fig,use_container_width=True)
        display=view[[c for c in ["filing_date","filing_type","source_section","risk_category","severity_score","novelty_score","confidence_score","evidence","model_provider"] if c in view]]
        st.dataframe(display,use_container_width=True,hide_index=True); download_table("Download filtered risk scores",display,"risk_scores")
elif page=="Price & Event Study":
    ticker=ticker_picker(); subset=within_dates(events[events.ticker.astype(str)==ticker],"filing_date") if ticker and not events.empty else pd.DataFrame()
    if subset.empty: st.info("No filing-event returns available.")
    else:
        subset["cumulative_return_pct"]=pd.to_numeric(subset.cumulative_return,errors="coerce")*100
        horizons=st.multiselect("Return horizons",sorted(subset.horizon.dropna().astype(str).unique(),key=lambda x:int(x.replace("d",""))),default=sorted(subset.horizon.dropna().astype(str).unique(),key=lambda x:int(x.replace("d",""))),key="event_horizons")
        complete_only=st.checkbox("Show only complete horizons",value=False,key="event_complete")
        view=subset[subset.horizon.astype(str).isin(horizons)]
        if complete_only: view=view[view.data_quality_status.astype(str).str.lower().isin(["complete","ok","valid"])]
        st.plotly_chart(px.box(view,x="horizon",y="cumulative_return_pct",points="all",hover_data=["accession_number","filing_date","data_quality_status"],title=f"Synthetic filing-event returns by trading-session horizon · {ticker}"),use_container_width=True)
        st.dataframe(view.sort_values(["filing_date","horizon"]),use_container_width=True,hide_index=True); download_table("Download event returns",view,"event_returns")
        st.caption("Returns use the last available close on or before a filing date as baseline and later trading sessions only. Missing horizons remain marked insufficient.")
elif page=="Model Lab":
    st.markdown("<div class='synthetic-notice'>Demo model results use simulated data.<small>They do not show that real stock prices can be predicted. Do not use them for investment decisions.</small></div>",unsafe_allow_html=True)
    ticker=ticker_picker("Company")
    model_data_path=config.DATA_DIR/"processed/ml_training_dataset.parquet"
    metadata_path=config.DATA_DIR.parent/"artifacts/models/model_metadata.json"
    if not model_data_path.exists() or not metadata_path.exists():
        st.info("Run `python scripts/run_ml_pipeline.py` to build the filing-event dataset and train the local evaluation models.")
    elif ticker:
        import json
        model_data=pd.read_parquet(model_data_path); company_events=model_data[model_data.ticker.astype(str)==ticker]
        if company_events.empty: st.info("No filing event has usable features for this company.")
        else:
            meta=json.loads(metadata_path.read_text(encoding="utf-8")); horizon=st.selectbox("Prediction horizon",["30d","60d","90d"]); target=f"negative_return_{horizon}"
            filing=st.selectbox("Filing",company_events.accession_number.astype(str).tolist(),format_func=lambda a:f"{a} · {pd.to_datetime(company_events.loc[company_events.accession_number.astype(str)==a,'filing_date'].iloc[0]).date()}")
            tmeta=meta.get("targets",{}).get(target,{})
            available=tmeta.get("trained_model_names",[]); model_name=st.selectbox("Model",available) if available else None
            prediction=predict_filing_risk(ticker,filing,horizon,data_dir=config.DATA_DIR/"gold",artifacts_dir=config.DATA_DIR.parent/"artifacts",model_name=model_name)
            event=company_events[company_events.accession_number.astype(str)==filing].iloc[0]
            a,b,c=st.columns(3); a.metric("Filing risk-change score",f"{event.weighted_risk_change_score:.1f}" if pd.notna(event.weighted_risk_change_score) else "Unavailable"); b.metric("Predicted probability",f"{prediction['predicted_probability']:.1%}" if prediction.get("predicted_probability") is not None else "Suppressed"); c.metric("Threshold",f"{config.NEGATIVE_RETURN_THRESHOLD:.1%}")
            model_features=meta.get("features",[]); available_count=sum(pd.notna(event.get(f)) for f in model_features)
            st.write(f"Data completeness for selected event: {available_count}/{len(model_features)} model features present · historical market cutoff: {event.get('feature_as_of_date') or 'unavailable'}")
            st.write("Prediction status:",prediction["status"]); st.caption("Risk-change score is filing-derived and separate from the model probability. The model probability is only returned if held-out evaluation passes minimum checks.")
            if prediction.get("warnings"): st.write("Warnings:"," · ".join(str(w) for w in prediction["warnings"] if w))
            if prediction.get("data_quality_warnings"): st.write("Data quality:"," · ".join(prediction["data_quality_warnings"]))
            model_result=tmeta.get("models",{}).get(model_name,{})
            st.subheader("Chronological held-out test evaluation")
            if model_result.get("test"):
                st.metric("Majority-class baseline accuracy",f"{tmeta.get('majority_class_test_accuracy',float('nan')):.1%}")
                st.json(model_result["test"]); cm=model_result["test"].get("confusion_matrix");
                if cm: st.dataframe(pd.DataFrame(cm,index=["Actual 0","Actual 1"],columns=["Predicted 0","Predicted 1"]))
            else: st.info("No held-out evaluation metrics are available.")
            effects=model_result.get("feature_effects",[])
            if effects: st.plotly_chart(px.bar(pd.DataFrame(effects),x="effect",y="feature",orientation="h",title="Global model feature effects · descriptive, not causal"),use_container_width=True)
            past=events[(events.ticker.astype(str)==ticker)&(events.accession_number.astype(str)==filing)] if not events.empty else pd.DataFrame()
            if not past.empty: st.subheader("Observed synthetic event-study outcomes"); st.dataframe(past,use_container_width=True,hide_index=True)
            st.write("Evaluation limitation:",tmeta.get("test_limitation") or "Synthetic held-out test only; performance is not evidence of real-market predictability.")
elif page=="Financial Glossary":
    if glossary.empty: st.info("Glossary is not loaded.")
    else:
        query=st.text_input("Search terms").strip().lower(); view=glossary
        if query: view=view[view.term.astype(str).str.lower().str.contains(query,na=False)|view.definition.astype(str).str.lower().str.contains(query,na=False)]
        st.caption(f"{len(view)} of {len(glossary)} glossary entries")
        st.dataframe(view,use_container_width=True,hide_index=True); download_table("Download glossary",view,"glossary")
elif page=="Educational Q&A":
    if qa.empty: st.info("Educational Q&A is not loaded.")
    else:
        categories=["All"]+sorted(qa.category.dropna().astype(str).unique().tolist()); category=st.selectbox("Topic",categories)
        view=qa if category=="All" else qa[qa.category==category]
        difficulty=st.multiselect("Difficulty",sorted(view.difficulty.dropna().astype(str).unique()),default=sorted(view.difficulty.dropna().astype(str).unique()),key="qa_difficulty")
        query=st.text_input("Search questions and answers",key="qa_search").strip().lower()
        view=view[view.difficulty.astype(str).isin(difficulty)]
        if query: view=view[view.question.astype(str).str.lower().str.contains(query,na=False)|view.answer.astype(str).str.lower().str.contains(query,na=False)]
        st.caption(f"{len(view)} matching learning items")
        for row in view.itertuples():
            with st.expander(f"{row.question} · {row.difficulty}"):
                st.write(row.answer); st.caption(f"Educational content · {row.category}")
        download_table("Download filtered Q&A",view,"educational_qa")
elif page=="Chat Assistant":
    st.subheader("Ask the local dataset assistant")
    st.write("Ask about filing risk themes, paragraph changes, event returns, company coverage, or glossary terms. Answers are generated locally from the loaded tables; no API key or external AI service is used.")
    st.markdown("<div class='synthetic-notice'>This assistant summarizes simulated demo records.<small>It does not provide investment advice or real-world predictions.</small></div>",unsafe_allow_html=True)
    selected_ticker=global_ticker if global_ticker!="All companies" else (tickers[0] if tickers else "AAPL")
    suggestions=[f"What are the main risk themes for {selected_ticker}?",f"Summarize filing changes for {selected_ticker}",f"What were the event returns for {selected_ticker}?","Define gross margin"]
    st.markdown("**Try asking**")
    suggestion_cols=st.columns(4)
    if "chat_messages" not in st.session_state: st.session_state.chat_messages=[]
    for col,suggestion,index in zip(suggestion_cols,suggestions,range(len(suggestions))):
        if col.button(suggestion,key=f"chat_suggestion_{index}"):
            st.session_state.chat_messages.extend([{"role":"user","content":suggestion},{"role":"assistant","content":answer_local_query(suggestion)}])
    prompt=st.chat_input("Ask about this synthetic dataset…")
    if prompt:
        st.session_state.chat_messages.extend([{"role":"user","content":prompt},{"role":"assistant","content":answer_local_query(prompt)}])
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    if st.session_state.chat_messages:
        if st.button("Clear conversation",key="clear_chat"):
            st.session_state.chat_messages=[]; st.rerun()
    st.markdown("**Suggested next steps**")
    st.markdown("- Compare risk themes across two synthetic filings in **Filing Comparison**.\n- Inspect subsequent trading-session outcomes in **Price & Event Study**.\n- Look up unfamiliar accounting and market terms in **Financial Glossary**.")
elif page=="Data Quality":
    report_path=config.DATA_DIR/"gold/validation_report.json"
    if report_path.exists():
        import json
        report=json.loads(report_path.read_text(encoding="utf-8")); st.json(report)
    else: st.info("No validation report found. Run the demo dataset loader.")
    st.write("Loaded table counts")
    counts=pd.DataFrame([{"table":n,"rows":len(df),"columns":len(df.columns)} for n,df in tables.items()])
    st.dataframe(counts,hide_index=True)
    chosen=st.selectbox("Preview a loaded table",list(tables),key="quality_table")
    preview=tables[chosen]
    st.dataframe(preview.head(100),use_container_width=True,hide_index=True)
    download_table(f"Download {chosen}",preview,f"quality_{chosen}")
