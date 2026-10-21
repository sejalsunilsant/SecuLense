import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const NAV = [
  ['Overview', '⌂', 'Your dashboard'], ['Company explorer', '◉', 'Companies'],
  ['Filing changes', '⇄', 'What changed'], ['Risk scores', '◇', 'Risk signals'],
  ['Market analysis', '↗', 'Stock analysis'], ['Price & returns', '⇧', 'Price changes'], ['Learn', '?', 'Simple guides'], ['Ask Secu', '✦', 'Ask a question'],
];
const money = (n) => Number.isFinite(Number(n)) ? `$${Number(n).toFixed(2)}` : '—';
const pct = (n) => Number.isFinite(Number(n)) ? `${Number(n) >= 0 ? '+' : ''}${(Number(n) * 100).toFixed(2)}%` : '—';
const dateValue = (v) => v ? String(v).slice(0, 10) : '';
const safe = (v) => v == null || v === '' ? '—' : String(v);
const plainRisk = (v) => String(v ?? '').replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

function LineChart({ rows, onPoint }) {
  if (!rows.length) return <div className="empty">No price history in this date range.</div>;
  const values = rows.map((r) => Number(r.close)).filter(Number.isFinite);
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const points = rows.map((r, i) => ({ x: 32 + i * 596 / Math.max(1, rows.length - 1), y: 160 - ((Number(r.close) - lo) / span) * 130, row: r }));
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ');
  return <div className="chart-wrap"><svg viewBox="0 0 660 200" role="img" aria-label="Share price over time"><defs><linearGradient id="area" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#12a38f" stopOpacity=".25"/><stop offset="1" stopColor="#12a38f" stopOpacity="0"/></linearGradient></defs><path d={`${d} L628,175 L32,175 Z`} fill="url(#area)"/><path d={d} fill="none" stroke="#0b8c82" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>{points.filter((_, i) => i % Math.max(1, Math.floor(points.length / 12)) === 0).map((p) => <circle key={p.row.trade_date} cx={p.x} cy={p.y} r="4" fill="#fff" stroke="#087f7a" strokeWidth="2" onClick={() => onPoint?.(p.row)}><title>{dateValue(p.row.trade_date)} · {money(p.row.close)}</title></circle>)}</svg><div className="chart-ends"><span>{dateValue(rows[0].trade_date)}</span><b>Daily closing price</b><span>{dateValue(rows.at(-1).trade_date)}</span></div></div>;
}

function MarketChart({ rows, mode, sma20, sma50, source }) {
  if (!rows.length) return <div className="empty">No daily price data is available for this company and date range.</div>;
  const W = 900, H = 330, left = 48, right = 16, top = 16, plotH = 220, volTop = 255, volH = 48;
  const lows = rows.map((r) => Number(r.low)), highs = rows.map((r) => Number(r.high));
  const lo = Math.min(...lows), hi = Math.max(...highs), span = hi - lo || 1;
  const maxVol = Math.max(...rows.map((r) => Number(r.volume) || 0), 1);
  const step = (W - left - right) / rows.length, xAt = (i) => left + i * step + step / 2;
  const yAt = (v) => top + (hi - v) / span * plotH;
  const moving = (period) => rows.map((_, i) => i + 1 < period ? null : rows.slice(i + 1 - period, i + 1).reduce((s, r) => s + Number(r.close), 0) / period);
  const path = (values) => values.map((v, i) => v == null ? '' : `${i && values[i - 1] != null ? 'L' : 'M'}${xAt(i)},${yAt(v)}`).filter(Boolean).join(' ');
  const average20 = moving(20), average50 = moving(50);
  return <div className="market-chart"><div className="chart-legend"><span><i className="legend-candle up"/> Up day</span><span><i className="legend-candle down"/> Down day</span>{sma20 && <span><i className="legend-line gold"/> 20 day average</span>}{sma50 && <span><i className="legend-line blue"/> 50 day average</span>}<span className="chart-unit">{source} · USD</span></div><svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${source} daily candlestick chart with volume`}>
    {[0, .25, .5, .75, 1].map((p) => <g key={p}><line x1={left} x2={W-right} y1={top+p*plotH} y2={top+p*plotH} className="chart-grid"/><text x={left-8} y={top+p*plotH+4} textAnchor="end" className="axis-label">${(hi-p*span).toFixed(0)}</text></g>)}
    {rows.map((r,i) => {const x=xAt(i), o=Number(r.open), c=Number(r.close), rising=c>=o, bodyY=Math.min(yAt(o),yAt(c)), bodyH=Math.max(1.5,Math.abs(yAt(o)-yAt(c))), candleW=Math.max(2,Math.min(11,step*.56));return <g key={`${r.trade_date}-${i}`} className="candle"><line x1={x} x2={x} y1={yAt(Number(r.high))} y2={yAt(Number(r.low))} className={rising?'wick-up':'wick-down'}/><rect x={x-candleW/2} y={bodyY} width={candleW} height={bodyH} rx="1" className={rising?'candle-up':'candle-down'}><title>{dateValue(r.trade_date)} · Open ${o.toFixed(2)} · High ${Number(r.high).toFixed(2)} · Low ${Number(r.low).toFixed(2)} · Close ${c.toFixed(2)} · Volume {Number(r.volume).toLocaleString()}</title></rect><rect x={x-step/2} y={top} width={step} height={plotH} fill="transparent"><title>{dateValue(r.trade_date)} · Open ${o.toFixed(2)} · High ${Number(r.high).toFixed(2)} · Low ${Number(r.low).toFixed(2)} · Close ${c.toFixed(2)} · Volume {Number(r.volume).toLocaleString()}</title></rect><rect x={x-step*.28} y={volTop+volH-(Number(r.volume)||0)/maxVol*volH} width={Math.max(1,step*.56)} height={(Number(r.volume)||0)/maxVol*volH} className={rising?'volume-up':'volume-down'}/></g>})}
    {mode==='Close' && <path d={path(rows.map((r)=>Number(r.close)))} className="close-line"/>}{sma20 && <path d={path(average20)} className="average-line gold"/>}{sma50 && <path d={path(average50)} className="average-line blue"/>}
    <text x={left} y={H-4} className="axis-label">{dateValue(rows[0].trade_date)}</text><text x={W-right} y={H-4} textAnchor="end" className="axis-label">{dateValue(rows.at(-1).trade_date)}</text><text x={left} y={volTop-7} className="axis-label">DAILY VOLUME</text>
  </svg></div>;
}

function App() {
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [auth, setAuth] = useState({ loading: true, setup_required: false, user: null });
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState('');
  const [page, setPage] = useState('Overview');
  const [ticker, setTicker] = useState('All companies');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [search, setSearch] = useState('');
  const [horizon, setHorizon] = useState('All');
  const [marketRange, setMarketRange] = useState('3M');
  const [marketFeed, setMarketFeed] = useState(null);
  const [marketLoading, setMarketLoading] = useState(false);
  const [chartMode, setChartMode] = useState('Candles');
  const [sma20, setSma20] = useState(true);
  const [sma50, setSma50] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [selectedChange, setSelectedChange] = useState(null);
  const [selectedTerm, setSelectedTerm] = useState(null);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    let active = true;
    async function initialize() {
      try {
        const statusResponse = await fetch('/api/auth/status');
        if (!statusResponse.ok) throw new Error('The local sign-in service is unavailable. Restart the dashboard with npm run dashboard.');
        const status = await statusResponse.json();
        if (status.setup_required) { if (active) setAuth({ loading: false, setup_required: true, user: null }); return; }
        const sessionResponse = await fetch('/api/auth/me');
        if (!sessionResponse.ok) { if (active) setAuth({ loading: false, setup_required: false, user: null }); return; }
        const session = await sessionResponse.json();
        const dataResponse = await fetch('/api/data');
        const payload = await dataResponse.json();
        if (!dataResponse.ok) throw new Error(payload.error || 'Could not load the dashboard data.');
        if (active) { setAuth({ loading: false, setup_required: false, user: session.user }); setData(payload); }
      } catch (error) { if (active) { setLoadError(error.message); setAuth((a) => ({ ...a, loading: false })); } }
    }
    initialize();
    return () => { active = false; };
  }, []);
  useEffect(() => { const timer = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(timer); }, []);

  async function handleAuth(credentials, authMode) {
    setAuthBusy(true); setAuthError('');
    let authenticated = false;
    try {
      const route = authMode === 'signup' ? '/api/auth/signup' : authMode === 'setup' ? '/api/auth/setup' : '/api/auth/login';
      const response = await fetch(route, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(credentials) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Could not sign in.');
      setAuth({ loading: false, setup_required: false, user: payload.user });
      authenticated = true;
      const dataResponse = await fetch('/api/data');
      const dataPayload = await dataResponse.json();
      if (!dataResponse.ok) { setLoadError(dataPayload.error || 'Could not load dashboard data.'); return; }
      setData(dataPayload); setLoadError('');
    } catch (error) { if (authenticated) setLoadError(error.message); else setAuthError(error.message); }
    finally { setAuthBusy(false); }
  }

  async function signOut() {
    await fetch('/api/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => {});
    setData(null); setAuth({ loading: false, setup_required: false, user: null }); setMessages([]); setPage('Overview');
  }

  const companies = data?.companies ?? [];
  const tickers = [...new Set(companies.map((c) => c.ticker).filter(Boolean))].sort();
  const filterTicker = (rows) => ticker === 'All companies' ? rows : rows.filter((r) => r.ticker === ticker);
  const filterDate = (rows, field) => rows.filter((r) => { const d = dateValue(r[field]); return (!startDate || d >= startDate) && (!endDate || d <= endDate); });
  const filings = useMemo(() => filterDate(filterTicker(data?.filings ?? []), 'filing_date'), [data, ticker, startDate, endDate]);
  const risks = useMemo(() => filterDate(filterTicker(data?.risk_scores ?? []), 'filing_date'), [data, ticker, startDate, endDate]);
  const diffs = useMemo(() => filterDate(filterTicker(data?.filing_diffs ?? []), 'current_filing_date'), [data, ticker, startDate, endDate]);
  const events = useMemo(() => filterDate(filterTicker(data?.event_returns ?? []), 'filing_date'), [data, ticker, startDate, endDate]);
  const prices = useMemo(() => filterDate(filterTicker(data?.daily_prices ?? []), 'trade_date').sort((a, b) => dateValue(a.trade_date).localeCompare(dateValue(b.trade_date))), [data, ticker, startDate, endDate]);
  const marketTicker = ticker === 'All companies' ? tickers[0] : ticker;
  const marketHistory = useMemo(() => (data?.daily_prices ?? []).filter((r) => r.ticker === marketTicker).sort((a,b) => dateValue(a.trade_date).localeCompare(dateValue(b.trade_date))), [data, marketTicker]);
  useEffect(() => {
    if (page !== 'Market analysis' || !marketTicker) return;
    const controller = new AbortController();
    setMarketLoading(true);
    fetch(`/api/market-data?ticker=${encodeURIComponent(marketTicker)}`, { signal: controller.signal })
      .then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.error || 'The live price request failed.'); return payload; })
      .then(setMarketFeed)
      .catch((error) => { if (error.name !== 'AbortError') setMarketFeed({ provider_configured: false, error: error.message, results: [] }); })
      .finally(() => { if (!controller.signal.aborted) setMarketLoading(false); });
    return () => controller.abort();
  }, [page, marketTicker]);
  const liveBarsAvailable = Boolean(marketFeed?.results?.length);
  const marketSourceRows = liveBarsAvailable ? marketFeed.results : marketHistory;
  const marketPrices = useMemo(() => {
    const days = {'1M': 21, '3M': 63, '6M': 126, '1Y': 252, All: Infinity}[marketRange] ?? 63;
    return marketSourceRows.slice(-days).filter((r) => (!startDate || dateValue(r.trade_date) >= startDate) && (!endDate || dateValue(r.trade_date) <= endDate));
  }, [marketSourceRows, marketRange, startDate, endDate]);
  const marketMetrics = useMemo(() => {
    const closes = marketPrices.map((r) => Number(r.close)).filter(Number.isFinite), returns = closes.slice(1).map((v,i)=>v/closes[i]-1), last=closes.at(-1), prior=closes.at(-2);
    const change=(n)=>closes.length>n?last/closes[closes.length-1-n]-1:null;
    const recent=returns.slice(-14), up=recent.reduce((a,r)=>a+Math.max(r,0),0)/Math.max(recent.length,1), down=recent.reduce((a,r)=>a+Math.max(-r,0),0)/Math.max(recent.length,1);
    let peak=-Infinity, drawdown=0; for(const v of closes){peak=Math.max(peak,v);drawdown=Math.min(drawdown,v/peak-1);}
    const volatility=returns.slice(-20), avg=volatility.reduce((a,b)=>a+b,0)/Math.max(volatility.length,1), vol=volatility.length>1?Math.sqrt(volatility.reduce((a,b)=>a+(b-avg)**2,0)/(volatility.length-1))*Math.sqrt(252)*100:null;
    return {last, daily:last&&prior?last/prior-1:null, week:change(5), month:change(21), quarter:change(63), high:marketPrices.length?Math.max(...marketPrices.map(r=>Number(r.high))):null, low:marketPrices.length?Math.min(...marketPrices.map(r=>Number(r.low))):null, avgVolume:marketPrices.length?marketPrices.slice(-20).reduce((a,r)=>a+Number(r.volume||0),0)/Math.min(20,marketPrices.length):null, rsi:down===0?(up===0?50:100):100-100/(1+up/down), vol, drawdown};
  }, [marketPrices]);
  const company = companies.find((c) => c.ticker === ticker);
  const tapeQuotes = tickers.map((t, index) => {
    const latest = (data?.daily_prices ?? []).filter((r) => r.ticker === t).sort((a, b) => dateValue(b.trade_date).localeCompare(dateValue(a.trade_date)))[0];
    const base = Number(latest?.close ?? 0);
    const move = Math.sin(now.getTime() / 3500 + index * 1.7) * 0.0007;
    return { ticker: t, price: base * (1 + move), move };
  });
  const allRisks = [...new Set(risks.map((r) => r.risk_category))];
  const topRisks = Object.entries(risks.reduce((acc, r) => { const k = r.risk_category; (acc[k] ??= []).push(Number(r.severity_score)); return acc; }, {})).map(([name, values]) => ({ name, average: values.reduce((a, b) => a + b, 0) / values.length, count: values.length })).sort((a, b) => b.average - a.average);
  const matchedDiffs = diffs.filter((r) => `${r.section_name} ${r.risk_category} ${r.change_type} ${r.old_text} ${r.new_text}`.toLowerCase().includes(search.toLowerCase()));
  const glossary = (data?.financial_glossary ?? []).filter((r) => `${r.term} ${r.definition}`.toLowerCase().includes(search.toLowerCase()));
  const shownEvents = events.filter((r) => horizon === 'All' || String(r.horizon) === horizon).sort((a, b) => dateValue(a.filing_date).localeCompare(dateValue(b.filing_date)));

  function answer(q) {
    const normalized = q.toLowerCase();
    const matchTicker = tickers.find((t) => normalized.includes(t.toLowerCase()));
    const rows = matchTicker ? (data.risk_scores ?? []).filter((r) => r.ticker === matchTicker) : risks;
    const label = matchTicker || (ticker !== 'All companies' ? ticker : 'all companies');
    if (/define|definition|what is|meaning/.test(normalized)) {
      const found = (data.financial_glossary ?? []).find((r) => normalized.includes(r.term.toLowerCase()));
      if (found) return `${found.term}, in simple terms: ${found.definition}`;
      return 'I could not find that exact term in the glossary. Try “gross margin”, “cash flow”, “risk factors”, or “volatility”.';
    }
    if (/return|price|share|stock|performance/.test(normalized)) {
      const selected = matchTicker ? (data.event_returns ?? []).filter((r) => r.ticker === matchTicker) : events;
      if (!selected.length) return 'There are no filing-related price changes for that selection yet. Try another company or widen the date range.';
      const means = Object.entries(selected.reduce((a, r) => { (a[r.horizon] ??= []).push(Number(r.cumulative_return)); return a; }, {})).sort((a, b) => Number(a[0]) - Number(b[0]));
      return `For ${label}, these are average price changes after a filing in the synthetic sample: ${means.map(([h, xs]) => `${h} sessions: ${pct(xs.reduce((a, b) => a + b, 0) / xs.length)} (based on ${xs.length} events)`).join('; ')}. This describes the demo data; it does not predict future prices.`;
    }
    if (/change|compare|different|filing/.test(normalized)) {
      const selected = (data.filing_diffs ?? []).filter((r) => matchTicker ? r.ticker === matchTicker : ticker !== 'All companies' ? r.ticker === ticker : true);
      if (!selected.length) return 'No filing text changes match this selection. Try another company or widen the date range.';
      const types = selected.reduce((a, r) => { a[r.change_type] = (a[r.change_type] ?? 0) + 1; return a; }, {});
      return `I found ${selected.length} paragraph changes for ${label}: ${Object.entries(types).map(([k, v]) => `${plainRisk(k)}: ${v}`).join(', ')}. Open “Filing changes” to read the earlier and newer wording side by side.`;
    }
    if (/risk|concern|theme|severity/.test(normalized)) {
      if (!rows.length) return 'There are no risk notes for this selection. Try another company or widen the date range.';
      const grouped = Object.entries(rows.reduce((a, r) => { const k = r.risk_category; (a[k] ??= []).push(Number(r.severity_score)); return a; }, {})).map(([k, v]) => [k, v.reduce((a, b) => a + b, 0) / v.length, v.length]).sort((a, b) => b[1] - a[1]).slice(0, 4);
      return `The highest average risk scores for ${label} are ${grouped.map(([k, v, n]) => `${plainRisk(k)} (${v.toFixed(2)} out of 1, ${n} notes)`).join('; ')}. These are simulated scores, so read the example wording before interpreting them.`;
    }
    return `I can summarize risk notes, filing changes, price changes after filings, and glossary terms. Try “What risks stand out for ${ticker === 'All companies' ? 'AAPL' : ticker}?”, “What changed in ${ticker === 'All companies' ? 'MSFT' : ticker}?”, or “What does gross margin mean?”`;
  }
  function submit(q) { if (!q.trim() || !data) return; setMessages((m) => [...m, { role: 'you', text: q.trim() }, { role: 'assistant', text: answer(q.trim()) }]); setQuestion(''); }
  const quickPrompts = [`What risks stand out for ${ticker === 'All companies' ? 'AAPL' : ticker}?`, `What changed in ${ticker === 'All companies' ? 'MSFT' : ticker}?`, 'What does gross margin mean?'];

  if (loadError && !auth.user) return <div className="load-error"><h1>SecuLense</h1><p>{loadError}</p><p>Run <code>npm run dashboard</code> in the frontend directory after setting up dependencies.</p></div>;
  if (auth.loading) return <div className="loading"><span className="spinner"/> Securing your local session…</div>;
  if (!auth.user) return <AuthScreen setup={auth.setup_required} busy={authBusy} error={authError} onSubmit={handleAuth}/>;
  if (loadError) return <div className="load-error"><h1>SecuLense</h1><p>{loadError}</p><button onClick={signOut}>Sign out</button></div>;
  if (!data) return <div className="loading"><span className="spinner"/> Loading your local demo data…</div>;

  return <div className="shell">
    <aside className="sidebar"><div className="brand-mark"><span className="brand-icon">S</span><div><b>SecuLense</b><small>Filing explorer</small></div></div><div className="nav-caption">EXPLORE</div><nav>{NAV.map(([label, icon, sub]) => <button key={label} className={`nav-item ${page === label ? 'active' : ''}`} onClick={() => setPage(label)}><span className="nav-icon">{icon}</span><span><b>{label}</b><small>{sub}</small></span>{page === label && <i/>}</button>)}</nav><div className="side-bottom"><span className="live-dot"/> Local demo data <span className="version">v1.0</span></div></aside>
    <main className="main">
      <header className="topbar"><div><div className="eyebrow">SIMPLE COMPANY RESEARCH</div><h1>{page}</h1><p>{page === 'Overview' ? 'A clear view of company filings, risk signals, and example price moves.' : page === 'Filing changes' ? 'See how a company’s own words changed between reports.' : page === 'Risk scores' ? 'Explore possible concerns mentioned in the sample filings.' : page === 'Price & returns' ? 'See example share-price moves after filing dates.' : page === 'Ask Secu' ? 'Ask questions about the demo data in everyday language.' : 'Explore company reports and learn the basic ideas behind them.'}</p></div><div className="user-actions"><div className="clock-card"><span className="live-dot"/><div><b>LIVE DEMO</b><small>{now.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'})}</small></div></div><span className="user-name">{auth.user.username}</span><button className="logout-button" onClick={signOut}>Sign out</button></div></header>
      <div className="demo-alert"><span>ⓘ</span><div><b>{page === 'Market analysis' && liveBarsAvailable ? 'Provider-sourced market prices are shown for this chart.' : 'Practice data, not real-world records.'}</b><small>{page === 'Market analysis' && liveBarsAvailable ? 'The price chart uses US daily bars from Massive. Plan access can be delayed. Company metadata, filings, filing changes, and risk scores in this demo remain synthetic.' : 'Company names, filing text, risk scores, and prices in this demo are simulated. They are not actual SEC filings or stock-market history.'}</small></div><span className="demo-pill">{page === 'Market analysis' && liveBarsAvailable ? 'MASSIVE DATA' : 'SYNTHETIC'}</span></div>
      <section className="live-tape"><div className="tape-label"><span className="pulse-dot"/> SIMULATED LIVE TAPE <small>demo animation · not market data</small></div><div className="tape-quotes">{tapeQuotes.map((q) => <div className="tape-quote" key={q.ticker}><b>{q.ticker}</b><span>${q.price.toFixed(2)}</span><i className={q.move >= 0 ? 'positive' : 'negative'}>{q.move >= 0 ? '+' : ''}{(q.move * 100).toFixed(3)}%</i></div>)}</div></section>
      <section className="filterbar"><label><span>Company</span><select value={ticker} onChange={(e) => setTicker(e.target.value)}><option>All companies</option>{tickers.map((t) => <option key={t} value={t}>{t} · {companies.find((c) => c.ticker === t)?.company_name}</option>)}</select></label><label><span>From</span><input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}/></label><label><span>To</span><input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}/></label><button className="clear-filters" onClick={() => { setTicker('All companies'); setStartDate(''); setEndDate(''); }}>Reset</button><div className="filter-note">{ticker === 'All companies' ? 'Showing every company' : `Showing ${ticker}`}</div></section>
      {page === 'Overview' && <>
        <section className="metrics"><Metric label="Companies" value={companies.length}/><Metric label="Company reports" value={filings.length}/><Metric label="Possible risk notes" value={risks.length}/><Metric label="Price-change examples" value={events.length}/></section>
        <section className="grid-two"><Card title={ticker === 'All companies' ? 'Example share prices' : `${company?.company_name ?? ticker} · share price`} subtitle="Each point shows a simulated daily closing price."><LineChart rows={prices} onPoint={(r) => setPage('Price & returns')}/></Card><Card title="Common risk topics" subtitle="Higher scores mean the system marked the wording as more concerning."><RiskBars data={topRisks.slice(0, 5)}/></Card></section>
        <section className="grid-two"><Card title="Recent company reports" subtitle="Select a report to view related wording changes."><div className="list-rows">{filings.slice().sort((a,b) => dateValue(b.filing_date).localeCompare(dateValue(a.filing_date))).slice(0,6).map((f) => <button className="list-row" key={f.accession_number} onClick={() => {setTicker(f.ticker);setPage('Filing changes');}}><span className="file-icon">▤</span><span className="row-main"><b>{f.company_name} <i>{f.ticker}</i></b><small>{f.filing_type} · {dateValue(f.filing_date)}</small></span><span className="arrow">↗</span></button>)}</div></Card><Card title="Price changes after reports" subtitle="Average movement across the example companies."><ReturnBars rows={events}/><button className="text-link" onClick={() => setPage('Price & returns')}>See all price-change examples <span>→</span></button></Card></section>
        <section className="tip-card"><span className="tip-icon">✦</span><div><b>Start with a question</b><p>Try “What changed in the latest report?” or “What is gross margin?” in the Ask Secu section.</p></div><button onClick={() => setPage('Ask Secu')}>Ask Secu <span>→</span></button></section>
      </>}
      {page === 'Company explorer' && <section className="grid-two"><Card title={company ? company.company_name : 'Companies in this demo'} subtitle={company ? `${ticker} · ${company.sector ?? 'Sector not listed'}` : 'Choose a company above to focus the dashboard.'}><LineChart rows={prices} onPoint={() => setPage('Price & returns')}/></Card><Card title="Reports from this company" subtitle="Select a report to explore its changes."><div className="list-rows">{filings.map((f) => <button className="list-row" key={f.accession_number} onClick={() => {setSelectedChange(diffs.find((d) => d.current_accession === f.accession_number) ?? null);setPage('Filing changes');}}><span className="file-icon">▤</span><span className="row-main"><b>{f.filing_type} report</b><small>{dateValue(f.filing_date)} · {f.accession_number}</small></span><span className="arrow">→</span></button>)}</div></Card><Card title="Risk topics" subtitle="Average example score by topic."><RiskBars data={topRisks}/></Card></section>}
      {page === 'Filing changes' && <section className="panel"><div className="panel-head"><div><h2>What changed in the reports?</h2><p>Compare earlier and newer wording. This is simulated filing text.</p></div><label className="search-box"><span>⌕</span><input placeholder="Search topics or wording" value={search} onChange={(e) => setSearch(e.target.value)}/></label></div><div className="change-list">{matchedDiffs.map((d, i) => <button className={`change-card ${selectedChange === d ? 'selected' : ''}`} key={`${d.current_accession}-${i}`} onClick={() => setSelectedChange(selectedChange === d ? null : d)}><div className="change-head"><span className={`change-badge ${d.change_type}`}>{plainRisk(d.change_type)}</span><span>{d.ticker} · {dateValue(d.current_filing_date)}</span><span className="category-badge">{plainRisk(d.risk_category)}</span></div><b className="section-name">{d.section_name}</b>{selectedChange === d && <div className="compare-grid"><div><small>EARLIER WORDING</small><p>{safe(d.old_text)}</p></div><div><small>LATER WORDING</small><p>{safe(d.new_text)}</p></div></div>}<div className="expand-hint">{selectedChange === d ? 'Click to hide wording ↑' : 'Click to compare wording ↓'}</div></button>)}{!matchedDiffs.length && <div className="empty">No changes match your search and filters.</div>}</div></section>}
      {page === 'Risk scores' && <section className="grid-two"><Card title="Which topics scored highest?" subtitle="Score goes from 0 (low) to 1 (high). It is a computer-generated signal, not a conclusion."><RiskBars data={topRisks}/></Card><Card title="Example wording" subtitle="Read the text behind each score for context."><div className="list-rows">{risks.slice().sort((a,b) => Number(b.severity_score)-Number(a.severity_score)).map((r, i) => <div className="risk-row" key={`${r.paragraph_id}-${i}`}><div className="risk-row-head"><b>{plainRisk(r.risk_category)}</b><Score score={r.severity_score}/></div><p>{r.evidence || r.original_paragraph}</p><small>{r.ticker} · {dateValue(r.filing_date)} · sample text</small></div>)}</div></Card></section>}
      {page === 'Market analysis' && <>
        <section className="market-heading"><div><span className="market-symbol">{marketTicker || '—'}</span><span className="market-company">{companies.find(c=>c.ticker===marketTicker)?.company_name || 'Select a company above'}</span><span className={liveBarsAvailable?'market-provider-tag':'synthetic-tag'}>{marketLoading?'CHECKING PRICE SOURCE':liveBarsAvailable?'MASSIVE · MARKET DATA':'SYNTHETIC SAMPLE'}</span></div><div className="market-last">{money(marketMetrics.last)} <span className={marketMetrics.daily>=0?'positive':'negative'}>{pct(marketMetrics.daily)}</span><small>latest {liveBarsAvailable?'provider':'sample'} close · {dateValue(marketPrices.at(-1)?.trade_date)}</small></div></section>
        <section className="metrics market-metrics"><MarketMetric label="1 day" value={pct(marketMetrics.daily)} sub="since previous session"/><MarketMetric label="1 week" value={pct(marketMetrics.week)} sub="5 trading days"/><MarketMetric label="1 month" value={pct(marketMetrics.month)} sub="21 trading days"/><MarketMetric label="3 months" value={pct(marketMetrics.quarter)} sub="63 trading days"/><MarketMetric label="Avg. daily volume" value={marketMetrics.avgVolume?Math.round(marketMetrics.avgVolume).toLocaleString():'—'} sub="last 20 sessions"/><MarketMetric label="RSI · 14 sessions" value={Number.isFinite(marketMetrics.rsi)?marketMetrics.rsi.toFixed(0):'—'} sub="momentum indicator · 0–100"/><MarketMetric label="Price range" value={marketMetrics.high?`${money(marketMetrics.low)}–${money(marketMetrics.high)}`:'—'} sub="within selected period"/><MarketMetric label="Largest drop" value={pct(marketMetrics.drawdown)} sub="peak to later low"/></section>
        <section className="panel market-panel"><div className="panel-head"><div><h2>Price chart</h2><p>{liveBarsAvailable?'Each candle shows a real US trading session.':'Each candle summarizes one synthetic trading day.'} Hover a candle for open, high, low, close, and volume.</p></div><div className="market-controls"><div className="segmented">{['1M','3M','6M','1Y','All'].map(r=><button key={r} className={marketRange===r?'selected':''} onClick={()=>setMarketRange(r)}>{r}</button>)}</div><select value={chartMode} onChange={e=>setChartMode(e.target.value)}><option>Candles</option><option>Close</option></select></div></div><div className="chart-toggles"><label><input type="checkbox" checked={sma20} onChange={e=>setSma20(e.target.checked)}/> 20 day average</label><label><input type="checkbox" checked={sma50} onChange={e=>setSma50(e.target.checked)}/> 50 day average</label><span>Annualized 20-session volatility: {Number.isFinite(marketMetrics.vol)?`${marketMetrics.vol.toFixed(1)}%`:'—'}</span></div><MarketChart rows={marketPrices} mode={chartMode} sma20={sma20} sma50={sma50} source={liveBarsAvailable?'Massive market data':'Synthetic sample data'}/><div className="market-footnote">{marketFeed?.error ? `${marketFeed.error} Showing the synthetic practice sample instead. ` : marketFeed?.provider_configured===false?'Massive is not connected yet. Add MASSIVE_API_KEY to the local .env file to load actual US market bars. ':''}These prices are {liveBarsAvailable?'provider-sourced US market data':'simulated demo data'}. RSI and volatility are descriptive indicators, not buy or sell advice.{liveBarsAvailable && marketFeed?.updated_at ? ` Retrieved ${new Date(marketFeed.updated_at).toLocaleString()}.` : ''}</div></section>
      </>}
      {page === 'Price & returns' && <section className="grid-two"><Card title="Share price over time" subtitle="Move your mouse over chart points for date and price. Click a point to explore the period."><LineChart rows={prices} onPoint={(r) => setSelectedChange(r)}/></Card><Card title="Average price move after a report" subtitle="Average change after the report date, by number of trading days."><ReturnBars rows={events}/></Card><div className="panel full-width"><div className="panel-head"><div><h2>Example price changes by report</h2><p>Choose a time window to narrow the list. A session is a day when markets are open.</p></div><select value={horizon} onChange={(e) => setHorizon(e.target.value)}><option>All</option>{[...new Set(events.map((r) => String(r.horizon)))].sort((a,b)=>Number(a)-Number(b)).map((h) => <option key={h} value={h}>{h} trading days</option>)}</select></div><div className="table-scroll"><table><thead><tr><th>Company</th><th>Report date</th><th>Time window</th><th>Price change</th><th>Data note</th></tr></thead><tbody>{shownEvents.map((r, i) => <tr key={`${r.accession_number}-${r.horizon}-${i}`}><td><b>{r.ticker}</b></td><td>{dateValue(r.filing_date)}</td><td>{r.horizon} trading days</td><td className={Number(r.cumulative_return) >= 0 ? 'positive' : 'negative'}>{pct(r.cumulative_return)}</td><td><span className="status-pill">{r.data_quality_status}</span></td></tr>)}</tbody></table></div></div></section>}
      {page === 'Learn' && <section className="grid-two"><Card title="Money and market words, in plain English" subtitle="Search and select a term to see a short explanation."><div className="search-box glossary-search"><span>⌕</span><input placeholder="Search words" value={search} onChange={(e) => setSearch(e.target.value)}/></div><div className="term-list">{glossary.map((g) => <button className={selectedTerm === g.term ? 'selected' : ''} key={g.term} onClick={() => setSelectedTerm(g.term)}>{g.term}<span>→</span></button>)}</div>{selectedTerm && <div className="definition"><small>IN PLAIN ENGLISH</small><h3>{selectedTerm}</h3><p>{glossary.find((g) => g.term === selectedTerm)?.definition}</p></div>}</Card><Card title="Quick learning cards" subtitle="Short answers to common finance questions."><div className="list-rows">{(data.educational_qa ?? []).map((q, i) => <details className="qa-card" key={i}><summary>{q.question}<span>{q.difficulty}</span></summary><p>{q.answer}</p></details>)}</div></Card></section>}
      {page === 'Ask Secu' && <section className="chat-panel"><div className="chat-heading"><div className="assistant-avatar">✦</div><div><h2>Ask Secu</h2><p>A simple guide to the data in this practice dashboard.</p></div><span className="local-label">LOCAL · NO API</span></div><div className="suggestions"><span>TRY ASKING</span>{quickPrompts.map((p) => <button key={p} onClick={() => submit(p)}>{p}</button>)}</div><div className="chat-history">{!messages.length && <div className="welcome-chat"><div className="sparkle">✧</div><h3>What would you like to understand?</h3><p>Ask about report changes, possible risks, price moves, or a finance word.</p></div>}{messages.map((m, i) => <div className={`bubble-row ${m.role}`} key={i}><div className="bubble-avatar">{m.role === 'you' ? 'Y' : 'S'}</div><div className="bubble"><small>{m.role === 'you' ? 'YOU' : 'SECU'}</small><p>{m.text}</p></div></div>)}</div><form className="chat-form" onSubmit={(e) => {e.preventDefault();submit(question);}}><input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask in everyday language…"/><button disabled={!question.trim()}>Send <span>↑</span></button></form><div className="chat-disclaimer">Secu uses simple local rules and the demo data. It can misunderstand broad questions. Check the tables and wording yourself.</div></section>}
      <footer className="footer"><span>SecuLense · Learning and research demo</span><span>All records shown here are simulated</span></footer>
    </main>
  </div>;
}

function AuthScreen({ setup, busy, error, onSubmit }) {
  const [mode, setMode] = useState(setup ? 'setup' : 'login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [localError, setLocalError] = useState('');
  function submit(event) {
    event.preventDefault(); setLocalError('');
    if (mode !== 'login' && password !== confirm) { setLocalError('Those passwords do not match.'); return; }
    onSubmit({ username, password }, mode);
  }
  const creating = mode !== 'login';
  return <main className="auth-page"><div className="auth-grid"/><section className="auth-card"><div className="auth-brand"><span className="brand-icon">S</span><div><b>SecuLense</b><small>Private research workspace</small></div></div><div className="auth-eyebrow">{mode === 'setup' ? 'FIRST-TIME SETUP' : creating ? 'LOCAL ACCOUNT' : 'SECURE SIGN IN'}</div><h1>{creating ? 'Create your account' : 'Welcome back'}</h1><p className="auth-copy">{mode === 'setup' ? 'Create the first account for this local dashboard.' : creating ? 'Create an account to access this local research dashboard.' : 'Sign in to view the local company research dashboard.'}</p><form onSubmit={submit} className="auth-form"><label>Username<input autoComplete="username" minLength={3} maxLength={32} value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Your username" required/></label><label>Password<input type="password" autoComplete={creating ? 'new-password' : 'current-password'} minLength={creating ? 10 : undefined} value={password} onChange={(e) => setPassword(e.target.value)} placeholder={creating ? 'At least 10 characters' : 'Your password'} required/></label>{creating && <label>Confirm password<input type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Enter your password again" required/></label>}{(localError || error) && <div className="auth-error">{localError || error}</div>}<button type="submit" disabled={busy}>{busy ? 'Please wait…' : creating ? 'Create account' : 'Sign in'} <span>→</span></button></form>{!setup && <div className="auth-switch">{mode === 'login' ? <>New to SecuLense? <button type="button" onClick={() => { setLocalError(''); setMode('signup'); }}>Create an account</button></> : <>Already have an account? <button type="button" onClick={() => { setLocalError(''); setMode('login'); }}>Sign in</button></>}</div>}<div className="auth-security"><span>▣</span><div><b>Local account protection</b><small>Your password is stored as a one-way hash. Sessions are private to this browser and expire after 12 hours.</small></div></div><div className="auth-demo-note">Synthetic educational data · Local use only · No market feed</div></section></main>;
}

function Metric({ label, value }) { return <div className="metric-card"><span className="metric-dot"/><div><small>{label}</small><b>{Number(value).toLocaleString()}</b></div><span className="metric-arrow">↗</span></div>; }
function MarketMetric({ label, value, sub }) { const state=String(value).startsWith('-')?'negative':String(value).startsWith('+')?'positive':''; return <div className="metric-card market-metric"><span className="metric-dot"/><div><small>{label}</small><b className={state}>{value}</b><em>{sub}</em></div></div>; }
function Card({ title, subtitle, children }) { return <section className="card"><div className="card-title"><div><h2>{title}</h2><p>{subtitle}</p></div><span className="more-dot">···</span></div>{children}</section>; }
function Score({ score }) { const n = Number(score); return <span className={`score ${n >= .7 ? 'high' : n >= .4 ? 'medium' : 'low'}`}><i/>{Number.isFinite(n) ? `${Math.round(n * 100)} / 100` : '—'}</span>; }
function RiskBars({ data }) { if (!data.length) return <div className="empty">No risk notes for these filters.</div>; const max = Math.max(...data.map((r) => r.average), 1); return <div className="risk-bars">{data.map((r) => <div className="risk-bar" key={r.name}><div className="bar-label"><span>{plainRisk(r.name)}</span><b>{Math.round(r.average * 100)}</b></div><div className="bar-track"><span style={{ width: `${Math.max(3, r.average / max * 100)}%` }}/></div><small>{r.count} example {r.count === 1 ? 'note' : 'notes'}</small></div>)}</div>; }
function ReturnBars({ rows }) { if (!rows.length) return <div className="empty">No price-change examples for these filters.</div>; const horizons = [...new Set(rows.map((r) => Number(r.horizon)))].sort((a,b) => a-b); const avgs = horizons.map((h) => {const xs = rows.filter((r) => Number(r.horizon) === h).map((r) => Number(r.cumulative_return));return { h, avg: xs.reduce((a,b) => a+b,0)/xs.length };}); const max = Math.max(...avgs.map((x) => Math.abs(x.avg)),.01); return <div className="return-bars">{avgs.map(({h,avg}) => <div className="return-bar" key={h}><div className="return-track"><span className={avg >= 0 ? 'gain' : 'loss'} style={{height:`${Math.max(6,Math.abs(avg)/max*100)}%`}}><i>{pct(avg)}</i></span></div><small>{h} days</small></div>)}</div>; }

createRoot(document.getElementById('root')).render(<App/>);
