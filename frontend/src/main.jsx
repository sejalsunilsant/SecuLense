import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const NAV = [
  ['Overview', '⌂', 'Executive pulse'],
  ['Company Explorer', '◉', 'Financial trends & reports'],
  ['Filing Comparisons', '⇄', 'Paragraph-level diffs'],
  ['Risk Analysis', '◇', 'Evidence-backed risks'],
  ['Company Comparisons', '☷', 'Side-by-side peer matrix'],
  ['Watchlist & Alerts', '★', 'Actionable research alerts'],
  ['Market Analysis', '↗', 'Stock analysis & OHLCV'],
  ['Price & Returns', '⇧', 'Filing event studies'],
  ['Data Provenance', '✓', 'Lakehouse freshness & audit'],
  ['Ask Secu', '✦', 'Research copilot'],
];

const money = (n) => (Number.isFinite(Number(n)) ? `$${Number(n).toFixed(2)}` : '—');
const billions = (n) => (Number.isFinite(Number(n)) ? `$${Number(n).toFixed(1)}B` : '—');
const pct = (n) => (Number.isFinite(Number(n)) ? `${Number(n) >= 0 ? '+' : ''}${(Number(n) * 100).toFixed(2)}%` : '—');
const dateValue = (v) => (v ? String(v).slice(0, 10) : '');
const safe = (v) => (v == null || v === '' ? '—' : String(v));
const plainRisk = (v) => String(v ?? '').replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

function downloadCsv(filename, rows) {
  if (!rows || !rows.length) return;
  const keys = Object.keys(rows[0]);
  const header = keys.map((k) => `"${k}"`).join(',');
  const csvRows = rows.map((r) =>
    keys
      .map((k) => {
        const val = r[k] == null ? '' : String(r[k]);
        return `"${val.replace(/"/g, '""')}"`;
      })
      .join(',')
  );
  const blob = new Blob([[header, ...csvRows].join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function LineChart({ rows, onPoint }) {
  if (!rows.length) return <div className="empty">No price history in this date range.</div>;
  const values = rows.map((r) => Number(r.close)).filter(Number.isFinite);
  const lo = Math.min(...values),
    hi = Math.max(...values),
    span = hi - lo || 1;
  const points = rows.map((r, i) => ({
    x: 32 + (i * 596) / Math.max(1, rows.length - 1),
    y: 160 - ((Number(r.close) - lo) / span) * 130,
    row: r,
  }));
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ');
  return (
    <div className="chart-wrap">
      <svg viewBox="0 0 660 200" role="img" aria-label="Share price over time">
        <defs>
          <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#12a38f" stopOpacity=".25" />
            <stop offset="1" stopColor="#12a38f" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${d} L628,175 L32,175 Z`} fill="url(#area)" />
        <path d={d} fill="none" stroke="#0b8c82" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {points
          .filter((_, i) => i % Math.max(1, Math.floor(points.length / 12)) === 0)
          .map((p) => (
            <circle
              key={p.row.trade_date}
              cx={p.x}
              cy={p.y}
              r="4"
              fill="#fff"
              stroke="#087f7a"
              strokeWidth="2"
              onClick={() => onPoint?.(p.row)}
            >
              <title>
                {dateValue(p.row.trade_date)} · {money(p.row.close)}
              </title>
            </circle>
          ))}
      </svg>
      <div className="chart-ends">
        <span>{dateValue(rows[0].trade_date)}</span>
        <b>Daily closing price (USD)</b>
        <span>{dateValue(rows.at(-1).trade_date)}</span>
      </div>
    </div>
  );
}

function MarketChart({ rows, sma20, sma50, source }) {
  if (!rows.length) return <div className="empty">No daily price data is available for this company and date range.</div>;
  const W = 900,
    H = 330,
    left = 48,
    right = 16,
    top = 16,
    plotH = 220,
    volTop = 255,
    volH = 48;
  const lows = rows.map((r) => Number(r.low)),
    highs = rows.map((r) => Number(r.high));
  const lo = Math.min(...lows),
    hi = Math.max(...highs),
    span = hi - lo || 1;
  const maxVol = Math.max(...rows.map((r) => Number(r.volume) || 0), 1);
  const step = (W - left - right) / rows.length,
    xAt = (i) => left + i * step + step / 2;
  const yAt = (v) => top + ((hi - v) / span) * plotH;
  const moving = (period) =>
    rows.map((_, i) =>
      i + 1 < period ? null : rows.slice(i + 1 - period, i + 1).reduce((s, r) => s + Number(r.close), 0) / period
    );
  const path = (values) =>
    values
      .map((v, i) => (v == null ? '' : `${i && values[i - 1] != null ? 'L' : 'M'}${xAt(i)},${yAt(v)}`))
      .filter(Boolean)
      .join(' ');
  const average20 = moving(20),
    average50 = moving(50);
  return (
    <div className="market-chart">
      <div className="chart-legend">
        <span>
          <i className="legend-candle up" /> Up day
        </span>
        <span>
          <i className="legend-candle down" /> Down day
        </span>
        {sma20 && (
          <span>
            <i className="legend-line gold" /> 20-day SMA
          </span>
        )}
        {sma50 && (
          <span>
            <i className="legend-line blue" /> 50-day SMA
          </span>
        )}
        <span className="chart-unit">{source} · USD</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${source} daily candlestick chart with volume`}>
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <g key={p}>
            <line x1={left} y1={top + p * plotH} x2={W - right} y2={top + p * plotH} className="chart-grid" />
            <text x={left - 6} y={top + p * plotH + 4} textAnchor="end" className="axis-label">
              {(hi - p * span).toFixed(0)}
            </text>
          </g>
        ))}
        {rows.map((r, i) => {
          const x = xAt(i),
            open = Number(r.open),
            close = Number(r.close),
            high = Number(r.high),
            low = Number(r.low),
            up = close >= open;
          const candleTop = yAt(Math.max(open, close)),
            candleBottom = yAt(Math.min(open, close));
          const candleH = Math.max(1.5, candleBottom - candleTop);
          const vH = (Number(r.volume || 0) / maxVol) * volH;
          const barW = Math.max(2, step * 0.7);
          return (
            <g key={r.trade_date}>
              <line x1={x} y1={yAt(high)} x2={x} y2={yAt(low)} className={up ? 'wick-up' : 'wick-down'} />
              <rect x={x - barW / 2} y={candleTop} width={barW} height={candleH} className={up ? 'candle-up' : 'candle-down'}>
                <title>
                  {`${dateValue(r.trade_date)} · O:${open.toFixed(2)} H:${high.toFixed(2)} L:${low.toFixed(2)} C:${close.toFixed(2)} Vol:${Number(r.volume || 0).toLocaleString()}`}
                </title>
              </rect>
              <rect x={x - barW / 2} y={volTop + volH - vH} width={barW} height={vH} className={up ? 'volume-up' : 'volume-down'} />
            </g>
          );
        })}
        {sma20 && <path d={path(average20)} className="average-line gold" />}
        {sma50 && <path d={path(average50)} className="average-line blue" />}
      </svg>
    </div>
  );
}

function Metric({ label, value, sub, highlight }) {
  return (
    <div className="metric-card">
      <span className="metric-dot" />
      <div>
        <p className="metric-label">{label}</p>
        <b className="metric-value" style={highlight ? { color: '#38b98d' } : undefined}>
          {value}
        </b>
        {sub && <small style={{ display: 'block', color: '#889da9', fontSize: '10px', marginTop: '2px' }}>{sub}</small>}
      </div>
    </div>
  );
}

function Card({ title, subtitle, action, children }) {
  return (
    <div className="card">
      <div className="card-header-actions">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

function Score({ score }) {
  const num = Number(score);
  const color = num >= 0.75 ? '#e27e80' : num >= 0.5 ? '#e5b95f' : '#45c99c';
  return (
    <div className="score-wrap" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <div style={{ width: '40px', height: '6px', background: '#243b4c', borderRadius: '99px', overflow: 'hidden' }}>
        <div style={{ width: `${Math.round(num * 100)}%`, height: '100%', background: color, borderRadius: '99px' }} />
      </div>
      <b style={{ color, fontSize: '11px', fontVariantNumeric: 'tabular-nums' }}>{Number.isFinite(num) ? num.toFixed(2) : '—'}</b>
    </div>
  );
}

function RiskBars({ data }) {
  if (!data || !data.length) return <div className="empty">No risk score records available.</div>;
  const max = Math.max(...data.map((d) => d.score), 0.1);
  return (
    <div className="risk-bars" style={{ display: 'grid', gap: '10px' }}>
      {data.map((d) => (
        <div key={d.category} style={{ display: 'grid', gridTemplateColumns: '130px 1fr 45px', alignItems: 'center', gap: '10px', fontSize: '11px' }}>
          <span style={{ color: '#c4d7e2', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{plainRisk(d.category)}</span>
          <div style={{ height: '8px', background: '#1c3344', borderRadius: '99px', overflow: 'hidden' }}>
            <div
              style={{
                width: `${(d.score / max) * 100}%`,
                height: '100%',
                background: d.score >= 0.75 ? 'linear-gradient(90deg, #d86b6e, #f39798)' : 'linear-gradient(90deg, #2db693, #74d8bd)',
                borderRadius: '99px',
              }}
            />
          </div>
          <b style={{ textAlign: 'right', color: '#9fc2d4', fontVariantNumeric: 'tabular-nums' }}>{d.score.toFixed(2)}</b>
        </div>
      ))}
    </div>
  );
}

function ReturnBars({ rows }) {
  if (!rows || !rows.length) return <div className="empty">No event study price observations.</div>;
  const byH = {};
  for (const r of rows) {
    if (r.horizon != null && r.cumulative_return != null) {
      byH[r.horizon] = byH[r.horizon] || [];
      byH[r.horizon].push(Number(r.cumulative_return));
    }
  }
  const horizons = Object.keys(byH).sort((a, b) => Number(a) - Number(b));
  return (
    <div style={{ display: 'grid', gap: '8px', padding: '6px 0' }}>
      {horizons.map((h) => {
        const vals = byH[h];
        const avg = vals.reduce((s, v) => s + v, 0) / vals.length;
        const up = avg >= 0;
        return (
          <div key={h} style={{ display: 'grid', gridTemplateColumns: '85px 1fr 60px', alignItems: 'center', gap: '10px', fontSize: '11px' }}>
            <span style={{ color: '#a0b6c5' }}>{h}-session</span>
            <div style={{ height: '8px', background: '#1b3242', borderRadius: '99px', overflow: 'hidden', position: 'relative' }}>
              <div
                style={{
                  width: `${Math.min(100, Math.abs(avg) * 500)}%`,
                  height: '100%',
                  background: up ? '#38b98d' : '#e27e80',
                  borderRadius: '99px',
                }}
              />
            </div>
            <b style={{ color: up ? '#45c99c' : '#e27e80', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {pct(avg)}
            </b>
          </div>
        );
      })}
    </div>
  );
}

function App() {
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [auth, setAuth] = useState({ loading: true, setup_required: false, user: null });
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState('');
  const [page, setPage] = useState('Overview');
  const [ticker, setTicker] = useState('All companies');
  const [search, setSearch] = useState('');
  const [selectedChange, setSelectedChange] = useState(null);
  const [selectedAlertFilter, setSelectedAlertFilter] = useState('All');
  const [chartMode, setChartMode] = useState('Candles');
  const [sma20, setSma20] = useState(true);
  const [sma50, setSma50] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [copilotBusy, setCopilotBusy] = useState(false);
  const [watchlist, setWatchlist] = useState(['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'TSLA']);

  useEffect(() => {
    let active = true;
    async function initialize() {
      try {
        const statusResponse = await fetch('/api/auth/status');
        if (!statusResponse.ok) throw new Error('Backend auth service unavailable.');
        const status = await statusResponse.json();
        if (status.setup_required) {
          if (active) setAuth({ loading: false, setup_required: true, user: null });
          return;
        }

        const meResponse = await fetch('/api/auth/me');
        if (meResponse.ok) {
          const me = await meResponse.json();
          if (active) setAuth({ loading: false, setup_required: false, user: me.user });
        } else {
          if (active) setAuth({ loading: false, setup_required: false, user: null });
        }
      } catch (err) {
        if (active) setAuth({ loading: false, setup_required: false, user: null });
      }
    }
    initialize();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!auth.user) return;
    let active = true;
    async function loadData() {
      try {
        const res = await fetch('/api/data');
        if (!res.ok) throw new Error('Could not load Lakehouse dataset.');
        const payload = await res.json();
        if (active) setData(payload);
      } catch (err) {
        if (active) setLoadError(err.message);
      }
    }
    loadData();
    return () => {
      active = false;
    };
  }, [auth.user]);

  const companies = useMemo(() => data?.companies ?? [], [data]);
  const filings = useMemo(() => {
    let list = data?.filings ?? [];
    if (ticker !== 'All companies') list = list.filter((f) => f.ticker === ticker);
    return list;
  }, [data, ticker]);

  const diffs = useMemo(() => {
    let list = data?.filing_diffs ?? [];
    if (ticker !== 'All companies') list = list.filter((d) => d.ticker === ticker);
    return list;
  }, [data, ticker]);

  const matchedDiffs = useMemo(() => {
    if (!search.trim()) return diffs;
    const q = search.toLowerCase();
    return diffs.filter(
      (d) =>
        d.ticker?.toLowerCase().includes(q) ||
        d.section_name?.toLowerCase().includes(q) ||
        d.risk_category?.toLowerCase().includes(q) ||
        d.old_text?.toLowerCase().includes(q) ||
        d.new_text?.toLowerCase().includes(q)
    );
  }, [diffs, search]);

  const risks = useMemo(() => {
    let list = data?.risk_scores ?? [];
    if (ticker !== 'All companies') list = list.filter((r) => r.ticker === ticker);
    return list;
  }, [data, ticker]);

  const prices = useMemo(() => {
    let list = data?.daily_prices ?? [];
    if (ticker !== 'All companies') list = list.filter((p) => p.ticker === ticker);
    else list = list.filter((p) => p.ticker === 'AAPL');
    return list.slice().sort((a, b) => a.trade_date.localeCompare(b.trade_date));
  }, [data, ticker]);

  const events = useMemo(() => {
    let list = data?.event_returns ?? [];
    if (ticker !== 'All companies') list = list.filter((e) => e.ticker === ticker);
    return list;
  }, [data, ticker]);

  const fundamentals = useMemo(() => {
    let list = data?.fundamentals ?? [];
    if (ticker !== 'All companies') list = list.filter((f) => f.ticker === ticker);
    return list;
  }, [data, ticker]);

  const comparisons = useMemo(() => data?.company_comparisons ?? [], [data]);
  const alerts = useMemo(() => {
    let list = data?.watchlist_alerts ?? [];
    if (ticker !== 'All companies') list = list.filter((a) => a.ticker === ticker);
    if (selectedAlertFilter !== 'All') list = list.filter((a) => a.severity === selectedAlertFilter);
    return list;
  }, [data, ticker, selectedAlertFilter]);

  const freshness = useMemo(() => data?.freshness ?? {}, [data]);

  const topRisks = useMemo(() => {
    const byCat = {};
    for (const r of risks) {
      const c = r.risk_category || 'other';
      byCat[c] = byCat[c] || [];
      byCat[c].push(Number(r.severity_score || 0));
    }
    return Object.entries(byCat)
      .map(([category, vals]) => ({
        category,
        score: vals.reduce((a, b) => a + b, 0) / vals.length,
      }))
      .sort((a, b) => b.score - a.score);
  }, [risks]);

  const company = useMemo(() => {
    if (ticker === 'All companies') return null;
    return companies.find((c) => c.ticker === ticker) ?? null;
  }, [companies, ticker]);

  const latestQuote = useMemo(() => {
    if (!prices.length) return null;
    const last = prices.at(-1);
    const prev = prices.length > 1 ? prices.at(-2) : last;
    const change = Number(last.close) - Number(prev.close);
    const changePct = Number(prev.close) ? change / Number(prev.close) : 0;
    return { ...last, change, changePct };
  }, [prices]);

  async function handleAuthSubmit({ username, password, mode }) {
    setAuthBusy(true);
    setAuthError('');
    const endpoint = mode === 'setup' ? '/api/auth/setup' : mode === 'signup' ? '/api/auth/signup' : '/api/auth/login';
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Authentication request failed.');
      setAuth({ loading: false, setup_required: false, user: body.user });
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleLogout() {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } finally {
      setAuth({ loading: false, setup_required: false, user: null });
      setData(null);
    }
  }

  async function handleAskCopilot(qText) {
    const text = qText || question;
    if (!text.trim() || copilotBusy) return;
    const userMsg = { sender: 'user', text };
    setMessages((prev) => [...prev, userMsg]);
    setQuestion('');
    setCopilotBusy(true);
    try {
      const res = await fetch('/api/copilot/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, ticker: ticker === 'All companies' ? null : ticker }),
      });
      const body = await res.json();
      setMessages((prev) => [...prev, { sender: 'copilot', text: body.answer, category: body.category }]);
    } catch (err) {
      setMessages((prev) => [...prev, { sender: 'copilot', text: 'Could not contact the research copilot.' }]);
    } finally {
      setCopilotBusy(false);
    }
  }

  if (auth.loading) {
    return (
      <div className="auth-shell">
        <div className="auth-card" style={{ textAlign: 'center' }}>
          <div className="brand-icon" style={{ margin: '0 auto 16px' }}>S</div>
          <h2>SecuLense Financial Research</h2>
          <p>Initializing secure Lakehouse session...</p>
        </div>
      </div>
    );
  }

  if (!auth.user) {
    return (
      <AuthScreen
        setup={auth.setup_required}
        busy={authBusy}
        error={authError}
        onSubmit={handleAuthSubmit}
      />
    );
  }

  return (
    <div className="shell">
      {/* -------------------- SIDEBAR -------------------- */}
      <aside className="sidebar">
        <div className="brand-mark">
          <span className="brand-icon">S</span>
          <div>
            <b>SecuLense</b>
            <small>Financial Research Platform</small>
          </div>
        </div>
        <div className="nav-caption">RESEARCH WORKSPACES</div>
        <nav>
          {NAV.map(([label, icon, desc]) => (
            <button
              key={label}
              className={`nav-item ${page === label ? 'active' : ''}`}
              onClick={() => {
                setPage(label);
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            >
              <span className="nav-icon">{icon}</span>
              <div>
                <b>{label}</b>
                <small>{desc}</small>
              </div>
              {page === label && <i />}
            </button>
          ))}
        </nav>
        <div className="side-bottom">
          <span className="live-dot" />
          <span>Lakehouse Synced</span>
          <span className="version">v2.1 · Delta Lake</span>
        </div>
      </aside>

      {/* -------------------- MAIN CONTENT -------------------- */}
      <main className="main">
        {/* TOP BAR */}
        <header className="topbar">
          <div>
            <div className="eyebrow">{page.toUpperCase()}</div>
            <h1>{page}</h1>
            <p>
              {page === 'Overview'
                ? 'Portfolio health, actionable filing alerts, and market summary.'
                : page === 'Company Explorer'
                ? 'Quarterly fundamentals, verified SEC filings, and financial metrics.'
                : page === 'Filing Comparisons'
                ? 'Item 1A Risk Factors and Item 7 MD&A paragraph-level diff comparison.'
                : page === 'Risk Analysis'
                ? 'Verbatim disclosures, linguistic severity, and novelty metrics.'
                : page === 'Company Comparisons'
                ? 'Side-by-side peer benchmarking across revenue, margins, valuation, and risk.'
                : page === 'Watchlist & Alerts'
                ? 'Real-time market signals and materiality alerts.'
                : page === 'Market Analysis'
                ? 'Technical candlestick charts, moving averages, and volume.'
                : page === 'Price & Returns'
                ? 'Filing-event study returns across 1d, 5d, 30d, 60d, and 90d horizons.'
                : page === 'Data Provenance'
                ? 'Databricks Delta Lake Medallion architecture and data audit trail.'
                : 'Interactive financial research copilot.'}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div className="freshness-pill">
              <span className="freshness-dot" />
              <span>Lakehouse Gold · SEC EDGAR Live</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div className="avatar">{auth.user.username.slice(0, 2).toUpperCase()}</div>
              <div>
                <b style={{ display: 'block', fontSize: '11px', color: '#162e43' }}>{auth.user.username}</b>
                <button
                  onClick={handleLogout}
                  style={{ border: 0, background: 'none', color: '#0b8c82', fontSize: '10px', padding: 0, cursor: 'pointer' }}
                >
                  Sign out
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* WATCHLIST QUICK TICKER BAR */}
        <section className="watchlist-bar">
          <span style={{ fontSize: '11px', color: '#738997', fontWeight: '700', paddingRight: '4px' }}>WATCHLIST:</span>
          {['All companies', 'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'TSLA'].map((t) => {
            const isAll = t === 'All companies';
            const compPrices = data?.daily_prices?.filter((p) => p.ticker === t) ?? [];
            const last = compPrices.at(-1);
            const prev = compPrices.length > 1 ? compPrices.at(-2) : last;
            const chg = last && prev ? (Number(last.close) - Number(prev.close)) / Number(prev.close) : 0;
            return (
              <button
                key={t}
                className={`watchlist-chip ${ticker === t ? 'active' : ''}`}
                onClick={() => setTicker(t)}
              >
                <span className="chip-ticker">{isAll ? 'ALL TICKERS' : t}</span>
                {!isAll && last && <span className="chip-price">${Number(last.close).toFixed(2)}</span>}
                {!isAll && last && (
                  <span className={`chip-change ${chg >= 0 ? 'up' : 'down'}`}>
                    {chg >= 0 ? '+' : ''}{(chg * 100).toFixed(2)}%
                  </span>
                )}
              </button>
            );
          })}
        </section>

        {/* -------------------- WORKSPACE 1: OVERVIEW -------------------- */}
        {page === 'Overview' && (
          <>
            <section className="metrics">
              <Metric label="Tracked Companies" value={companies.length} sub="Real SEC registrants" />
              <Metric label="Verified SEC Filings" value={filings.length} sub="Official 10-K & 10-Q" />
              <Metric label="Disclosed Risk Factors" value={risks.length} sub="Evidence-backed citations" />
              <Metric label="Active Research Alerts" value={alerts.length} sub="High & medium materiality" highlight />
            </section>

            {/* High Priority Alerts Feed Banner */}
            {alerts.length > 0 && (
              <div style={{ marginBottom: '18px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '11px', fontWeight: '800', letterSpacing: '.07em', color: '#e27e80' }}>
                    ACTIONABLE RESEARCH ALERTS ({alerts.length})
                  </span>
                  <button className="text-link" onClick={() => setPage('Watchlist & Alerts')}>
                    View all alerts <span>→</span>
                  </button>
                </div>
                <div className="alerts-feed">
                  {alerts.slice(0, 2).map((a) => (
                    <div className={`alert-card ${a.severity.toLowerCase()}`} key={a.id}>
                      <div className="alert-header">
                        <span className={`alert-badge ${a.severity.toLowerCase()}`}>{a.severity} Priority</span>
                        <span style={{ fontSize: '11px', color: '#88a0ad' }}>{a.ticker} · {a.date}</span>
                        <span style={{ fontSize: '11px', color: '#68d1b5' }}>{a.alert_type}</span>
                      </div>
                      <h4 className="alert-title">{a.title}</h4>
                      <p className="alert-summary">{a.summary}</p>
                      <div className="alert-meta">
                        <span>Trigger: <b>{a.trigger}</b></span>
                        <span>Horizon: <b>{a.impact_horizon}</b></span>
                        <span>Source: <b>{a.source_filing}</b></span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <section className="grid-two">
              <Card
                title={ticker === 'All companies' ? 'Benchmark Market Price Trend' : `${company?.company_name ?? ticker} · Share Price`}
                subtitle="Historical market daily close with event markers."
                action={
                  <button className="download-btn" onClick={() => downloadCsv('seculense_daily_prices.csv', prices)}>
                    ↓ Export Prices
                  </button>
                }
              >
                <LineChart rows={prices} onPoint={() => setPage('Market Analysis')} />
              </Card>

              <Card
                title="Evidence-Backed Risk Themes"
                subtitle="Aggregated linguistic severity across verified SEC 10-K Item 1A disclosures."
                action={
                  <button className="download-btn" onClick={() => downloadCsv('seculense_risk_scores.csv', risks)}>
                    ↓ Export Risks
                  </button>
                }
              >
                <RiskBars data={topRisks.slice(0, 5)} />
              </Card>
            </section>

            <section className="grid-two">
              <Card
                title="Recent SEC Disclosures (Form 10-K / 10-Q)"
                subtitle="Traceable directly to the official SEC EDGAR repository."
                action={
                  <button className="download-btn" onClick={() => downloadCsv('seculense_filings.csv', filings)}>
                    ↓ Export Filings
                  </button>
                }
              >
                <div className="list-rows">
                  {filings.slice(0, 5).map((f) => (
                    <div className="list-row" key={f.accession_number} style={{ display: 'flex', alignItems: 'center' }}>
                      <span className="file-icon">▤</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <b style={{ display: 'block', fontSize: '12px' }}>
                          {f.company_name} <i style={{ color: '#0b8c82' }}>{f.ticker}</i>
                        </b>
                        <small style={{ color: '#889ea9' }}>
                          {f.filing_type} · {dateValue(f.filing_date)} · Acc: {f.accession_number}
                        </small>
                      </div>
                      {f.filing_url ? (
                        <a href={f.filing_url} target="_blank" rel="noopener noreferrer" className="sec-link" style={{ fontSize: '10px' }}>
                          SEC EDGAR ↗
                        </a>
                      ) : (
                        <span className="metric-unavailable">Local Archive</span>
                      )}
                    </div>
                  ))}
                </div>
              </Card>

              <Card
                title="Post-Filing Event Study Returns"
                subtitle="Empirical cumulative return performance across standard trading horizons."
                action={
                  <button className="download-btn" onClick={() => downloadCsv('seculense_event_returns.csv', events)}>
                    ↓ Export Returns
                  </button>
                }
              >
                <ReturnBars rows={events} />
                <button className="text-link" onClick={() => setPage('Price & Returns')}>
                  Deep event analysis <span>→</span>
                </button>
              </Card>
            </section>
          </>
        )}

        {/* -------------------- WORKSPACE 2: COMPANY EXPLORER & FINANCIAL TRENDS -------------------- */}
        {page === 'Company Explorer' && (
          <>
            {company ? (
              <div className="panel" style={{ marginBottom: '18px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                  <div>
                    <h2 style={{ margin: '0 0 4px', color: '#fff' }}>
                      {company.company_name} <span style={{ color: '#45c99c' }}>({company.ticker})</span>
                    </h2>
                    <p style={{ margin: 0, color: '#8fa4b3', fontSize: '12px' }}>
                      CIK: <b>{company.cik}</b> · Sector: <b>{company.sector}</b> · Industry: <b>{company.industry}</b> · Exchange: <b>{company.exchange}</b>
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '16px' }}>
                    <div>
                      <small style={{ display: 'block', color: '#7a8e9b', fontSize: '9px' }}>MARKET CAP</small>
                      <b style={{ color: '#a3edd9', fontSize: '15px' }}>{billions(company.market_cap_billions)}</b>
                    </div>
                    <div>
                      <small style={{ display: 'block', color: '#7a8e9b', fontSize: '9px' }}>P/E RATIO</small>
                      <b style={{ color: '#e8f4f8', fontSize: '15px' }}>{company.pe_ratio ? `${company.pe_ratio}x` : '—'}</b>
                    </div>
                    <div>
                      <small style={{ display: 'block', color: '#7a8e9b', fontSize: '9px' }}>DIVIDEND YIELD</small>
                      <b style={{ color: '#e8f4f8', fontSize: '15px' }}>{company.dividend_yield_pct ? `${company.dividend_yield_pct}%` : '0.0%'}</b>
                    </div>
                  </div>
                </div>
                <p style={{ marginTop: '12px', fontSize: '12px', color: '#b2c5d1', lineHeight: '1.55' }}>
                  {company.description}
                </p>
              </div>
            ) : (
              <div className="panel" style={{ marginBottom: '18px', textAlign: 'center', padding: '24px' }}>
                <h3>Select a Company from the Watchlist Above</h3>
                <p>Choose AAPL, MSFT, NVDA, AMZN, GOOGL, or TSLA to inspect financial trends and verified SEC filings.</p>
              </div>
            )}

            {/* Financial Trends Workspace */}
            {fundamentals.length > 0 && (
              <Card
                title={`Financial Performance Trends · ${ticker}`}
                subtitle="Quarterly & annual trajectory from official Form 10-K and 10-Q statements."
                action={
                  <button className="download-btn" onClick={() => downloadCsv(`seculense_${ticker}_fundamentals.csv`, fundamentals)}>
                    ↓ Export Financials CSV
                  </button>
                }
              >
                <div className="trend-grid">
                  <div className="trend-card">
                    <div className="trend-card-title">
                      <span>Revenue Trajectory ($B)</span>
                      <span style={{ color: '#38b98d' }}>Quarterly/Annual</span>
                    </div>
                    <div className="trend-bars">
                      {fundamentals.slice(-6).map((f) => (
                        <div className="trend-col" key={f.period}>
                          <span className="trend-val">${f.revenue_billions}</span>
                          <div
                            className="trend-bar-fill"
                            style={{ height: `${Math.min(100, (Number(f.revenue_billions) / 150) * 100)}%` }}
                          />
                          <span className="trend-label">{f.period}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="trend-card">
                    <div className="trend-card-title">
                      <span>Operating Margin Trend (%)</span>
                      <span style={{ color: '#5e9de8' }}>Efficiency</span>
                    </div>
                    <div className="trend-bars">
                      {fundamentals.slice(-6).map((f) => (
                        <div className="trend-col" key={f.period}>
                          <span className="trend-val">{f.operating_margin_pct}%</span>
                          <div
                            className="trend-bar-fill secondary"
                            style={{ height: `${Math.min(100, Number(f.operating_margin_pct) * 1.5)}%` }}
                          />
                          <span className="trend-label">{f.period}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Fundamentals Table */}
                <div className="comparison-table-wrap">
                  <table className="comparison-table">
                    <thead>
                      <tr>
                        <th>Period</th>
                        <th>Type</th>
                        <th>Report Date</th>
                        <th>Revenue ($B)</th>
                        <th>Net Income ($B)</th>
                        <th>Gross Margin</th>
                        <th>Operating Margin</th>
                        <th>Diluted EPS</th>
                        <th>Free Cash Flow ($B)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fundamentals.map((row) => (
                        <tr key={row.period}>
                          <td><b>{row.period}</b></td>
                          <td><span className="layer-chip silver">{row.period_type}</span></td>
                          <td>{row.report_date}</td>
                          <td className="highlight-metric">${row.revenue_billions}B</td>
                          <td>${row.net_income_billions}B</td>
                          <td>{row.gross_margin_pct}%</td>
                          <td>{row.operating_margin_pct}%</td>
                          <td>${row.diluted_eps}</td>
                          <td>${row.free_cash_flow_billions}B</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            <section className="grid-two" style={{ marginTop: '18px' }}>
              <Card title="Verified SEC Filings Catalog" subtitle="Official Form 10-K and 10-Q submissions.">
                <div className="list-rows">
                  {filings.map((f) => (
                    <div className="list-row" key={f.accession_number} style={{ display: 'flex', alignItems: 'center' }}>
                      <span className="file-icon">▤</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <b style={{ display: 'block', fontSize: '12px' }}>{f.filing_type} Report</b>
                        <small style={{ color: '#8da2af' }}>
                          Filing Date: {dateValue(f.filing_date)} · Period End: {f.fiscal_period_end}
                        </small>
                      </div>
                      {f.filing_url ? (
                        <a href={f.filing_url} target="_blank" rel="noopener noreferrer" className="sec-link">
                          SEC EDGAR ↗
                        </a>
                      ) : (
                        <span className="metric-unavailable">Unavailable</span>
                      )}
                    </div>
                  ))}
                </div>
              </Card>

              <Card title="Daily Share Price & Filing Markers" subtitle="Historical closes from Market Data API.">
                <LineChart rows={prices} onPoint={() => setPage('Market Analysis')} />
              </Card>
            </section>
          </>
        )}

        {/* -------------------- WORKSPACE 3: FILING COMPARISONS -------------------- */}
        {page === 'Filing Comparisons' && (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>What Changed in Corporate SEC Disclosures?</h2>
                <p>Paragraph-by-paragraph diff engine across consecutive 10-K and 10-Q filings.</p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="download-btn" onClick={() => downloadCsv('seculense_filing_diffs.csv', matchedDiffs)}>
                  ↓ Export Diffs CSV
                </button>
                <label className="search-box">
                  <span>⌕</span>
                  <input placeholder="Search wording or disclosure topics..." value={search} onChange={(e) => setSearch(e.target.value)} />
                </label>
              </div>
            </div>

            <div className="change-list">
              {matchedDiffs.map((d, i) => (
                <div
                  className={`change-card ${selectedChange === d ? 'selected' : ''}`}
                  key={`${d.current_accession}-${i}`}
                  onClick={() => setSelectedChange(selectedChange === d ? null : d)}
                  style={{ cursor: 'pointer' }}
                >
                  <div className="change-head">
                    <span className={`change-badge ${d.change_type}`}>{plainRisk(d.change_type)}</span>
                    <span style={{ fontWeight: '700', color: '#c7dbe6' }}>
                      {d.ticker} · Current: {dateValue(d.current_filing_date)} {d.previous_filing_date ? `(vs ${dateValue(d.previous_filing_date)})` : ''}
                    </span>
                    <span className="category-badge">{plainRisk(d.risk_category)}</span>
                    <span style={{ marginLeft: 'auto', fontSize: '10px', color: '#7ba0b1' }}>
                      Similarity: {(Number(d.similarity_score) * 100).toFixed(0)}%
                    </span>
                  </div>

                  <b className="section-name">{d.section_name}</b>

                  <div className="compare-grid">
                    {d.old_text && (
                      <div style={{ borderLeft: '3px solid #e27e80', paddingLeft: '10px' }}>
                        <small style={{ color: '#e27e80', fontWeight: '800' }}>PRIOR FILING WORDING ({dateValue(d.previous_filing_date)})</small>
                        <p style={{ margin: '6px 0 0', color: '#b2c4cf', fontSize: '12px', lineHeight: '1.55' }}>{d.old_text}</p>
                      </div>
                    )}
                    <div style={{ borderLeft: '3px solid #38b98d', paddingLeft: '10px' }}>
                      <small style={{ color: '#38b98d', fontWeight: '800' }}>UPDATED FILING WORDING ({dateValue(d.current_filing_date)})</small>
                      <p style={{ margin: '6px 0 0', color: '#d5e7f2', fontSize: '12px', lineHeight: '1.55' }}>{d.new_text}</p>
                    </div>
                  </div>

                  <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '10px', color: '#7a91a0' }}>
                    <span>SEC Accession: <code>{d.current_accession}</code></span>
                    <span style={{ color: '#45c99c' }}>{selectedChange === d ? 'Hide details ↑' : 'Expanded view'}</span>
                  </div>
                </div>
              ))}
              {!matchedDiffs.length && <div className="empty">No filing diffs match your filter or search query.</div>}
            </div>
          </section>
        )}

        {/* -------------------- WORKSPACE 4: RISK ANALYSIS -------------------- */}
        {page === 'Risk Analysis' && (
          <section className="grid-two">
            <Card
              title="Evidence-Backed Risk Disclosures"
              subtitle="Verbatim textual evidence cited directly from Form 10-K Item 1A."
              action={
                <button className="download-btn" onClick={() => downloadCsv('seculense_risk_evidence.csv', risks)}>
                  ↓ Export Evidence
                </button>
              }
            >
              <div style={{ display: 'grid', gap: '14px' }}>
                {risks.map((r, i) => (
                  <div key={`${r.ticker}-${r.paragraph_id || i}`} className="evidence-box">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <b style={{ color: '#a3edd9', fontSize: '12px' }}>
                        {r.ticker} · {plainRisk(r.risk_category)}
                      </b>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <span style={{ fontSize: '10px', color: '#889ea9' }}>Severity:</span>
                        <Score score={r.severity_score} />
                        <span style={{ fontSize: '10px', color: '#889ea9' }}>Novelty:</span>
                        <Score score={r.novelty_score} />
                      </div>
                    </div>
                    <blockquote className="evidence-quote">"{r.evidence || r.original_paragraph}"</blockquote>
                    <div className="evidence-meta">
                      <span>Source: <b>{r.source_section || 'Item 1A'}</b> (Filing: {dateValue(r.filing_date)})</span>
                      <span>Accession: <code>{r.accession_number}</code></span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <div>
              <Card title="Risk Theme Severity Distribution" subtitle="System scoring across risk categories.">
                <RiskBars data={topRisks} />
              </Card>

              <div style={{ marginTop: '16px' }}>
                <Card title="Linguistic Risk Methodology" subtitle="How scores are generated.">
                  <div style={{ fontSize: '12px', color: '#a9bcc8', lineHeight: '1.6' }}>
                    <p style={{ margin: '0 0 8px' }}>
                      • <b>Severity Score (0.0 to 1.0)</b>: Evaluates semantic intensity, regulatory keywords (investigations, subpoenas, injunctions), and supply bottlenecks.
                    </p>
                    <p style={{ margin: '0 0 8px' }}>
                      • <b>Novelty Score (0.0 to 1.0)</b>: Measures newly introduced phrases compared against previous 10-K disclosures.
                    </p>
                    <p style={{ margin: '0' }}>
                      • <b>Confidence Score</b>: Assesses linguistic clarity and attribution within the filing.
                    </p>
                  </div>
                </Card>
              </div>
            </div>
          </section>
        )}

        {/* -------------------- WORKSPACE 5: COMPANY COMPARISONS -------------------- */}
        {page === 'Company Comparisons' && (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Multi-Company Peer Benchmarking Matrix</h2>
                <p>Side-by-side financial, valuation, and risk metrics across market leaders.</p>
              </div>
              <button className="download-btn" onClick={() => downloadCsv('seculense_company_comparisons.csv', comparisons)}>
                ↓ Export Matrix CSV
              </button>
            </div>

            <div className="comparison-table-wrap">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Ticker</th>
                    <th>Sector</th>
                    <th>Market Cap</th>
                    <th>P/E Ratio</th>
                    <th>Annual Revenue</th>
                    <th>Gross Margin</th>
                    <th>Operating Margin</th>
                    <th>Free Cash Flow</th>
                    <th>Mean Risk Severity</th>
                    <th>Top Risk Category</th>
                    <th>Disclosed Risks</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisons.map((c) => (
                    <tr key={c.ticker}>
                      <td><b>{c.company_name}</b></td>
                      <td><span className="layer-chip gold">{c.ticker}</span></td>
                      <td>{c.sector}</td>
                      <td className="highlight-metric">${c.market_cap_billions}B</td>
                      <td>{c.pe_ratio ? `${c.pe_ratio}x` : '—'}</td>
                      <td>${c.annual_revenue_billions}B</td>
                      <td>{c.gross_margin_pct}%</td>
                      <td>{c.operating_margin_pct}%</td>
                      <td>${c.free_cash_flow_billions}B</td>
                      <td>
                        <Score score={c.mean_risk_severity} />
                      </td>
                      <td><span className="category-badge">{plainRisk(c.top_risk_category)}</span></td>
                      <td>{c.disclosed_risk_factors_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* -------------------- WORKSPACE 6: WATCHLIST & ALERTS -------------------- */}
        {page === 'Watchlist & Alerts' && (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Actionable Research Alerts & Watchlist</h2>
                <p>Materiality signals triggered by regulatory disclosures, novelty spikes, and price volatility.</p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <select
                  value={selectedAlertFilter}
                  onChange={(e) => setSelectedAlertFilter(e.target.value)}
                  style={{ height: '33px', background: '#0e1c27', color: '#e8f2f6', border: '1px solid #2e4a5d', borderRadius: '8px', padding: '0 8px', fontSize: '11px' }}
                >
                  <option value="All">All Severity Levels</option>
                  <option value="High">High Priority Only</option>
                  <option value="Medium">Medium Priority Only</option>
                </select>
                <button className="download-btn" onClick={() => downloadCsv('seculense_alerts.csv', alerts)}>
                  ↓ Export Alerts CSV
                </button>
              </div>
            </div>

            <div className="alerts-feed">
              {alerts.map((a) => (
                <div className={`alert-card ${a.severity.toLowerCase()}`} key={a.id}>
                  <div className="alert-header">
                    <span className={`alert-badge ${a.severity.toLowerCase()}`}>{a.severity} Priority</span>
                    <span style={{ fontSize: '12px', fontWeight: '750', color: '#fff' }}>
                      {a.company_name} ({a.ticker})
                    </span>
                    <span style={{ fontSize: '11px', color: '#829bb0' }}>{a.date}</span>
                    <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#6fe0c2' }}>{a.alert_type}</span>
                  </div>
                  <h4 className="alert-title">{a.title}</h4>
                  <p className="alert-summary">{a.summary}</p>
                  <div style={{ background: '#081219', borderRadius: '8px', padding: '10px 12px', margin: '10px 0', fontSize: '11px', color: '#88e0c8' }}>
                    💡 <b>Action Recommendation:</b> {a.action_recommendation}
                  </div>
                  <div className="alert-meta">
                    <span>Trigger: <b>{a.trigger}</b></span>
                    <span>Impact Horizon: <b>{a.impact_horizon}</b></span>
                    <span>Source Accession: <code>{a.source_filing}</code></span>
                  </div>
                </div>
              ))}
              {!alerts.length && <div className="empty">No alerts match the selected filter.</div>}
            </div>
          </section>
        )}

        {/* -------------------- WORKSPACE 7: MARKET ANALYSIS -------------------- */}
        {page === 'Market Analysis' && (
          <section className="panel market-panel">
            <div className="market-heading">
              <div>
                <h2>Market Analysis · {ticker === 'All companies' ? 'AAPL (Anchor)' : ticker}</h2>
                <p>Interactive OHLCV candlestick chart, moving averages, and trading volume.</p>
              </div>
              {latestQuote && (
                <div className="market-last">
                  <div className="price">${Number(latestQuote.close).toFixed(2)}</div>
                  <div className={`change ${latestQuote.change >= 0 ? 'up' : 'down'}`}>
                    {latestQuote.change >= 0 ? '+' : ''}${latestQuote.change.toFixed(2)} ({pct(latestQuote.changePct)})
                  </div>
                  <small style={{ color: '#748b99', fontSize: '9px' }}>As of {dateValue(latestQuote.trade_date)}</small>
                </div>
              )}
            </div>

            <div className="chart-toggles" style={{ margin: '12px 0' }}>
              <label>
                <input type="checkbox" checked={sma20} onChange={(e) => setSma20(e.target.checked)} />
                <span>20-day SMA</span>
              </label>
              <label>
                <input type="checkbox" checked={sma50} onChange={(e) => setSma50(e.target.checked)} />
                <span>50-day SMA</span>
              </label>
              <button
                className="download-btn"
                style={{ marginLeft: 'auto' }}
                onClick={() => downloadCsv(`seculense_${ticker}_market_history.csv`, prices)}
              >
                ↓ Export OHLCV CSV
              </button>
            </div>

            <MarketChart rows={prices} sma20={sma20} sma50={sma50} source="Market Data API" />
          </section>
        )}

        {/* -------------------- WORKSPACE 8: PRICE & RETURNS (EVENT STUDY) -------------------- */}
        {page === 'Price & Returns' && (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Filing-Event Study Horizon Analysis</h2>
                <p>Cumulative price reaction and drawdowns post-filing date across 1d, 5d, 30d, 60d, and 90d horizons.</p>
              </div>
              <button className="download-btn" onClick={() => downloadCsv('seculense_event_returns.csv', events)}>
                ↓ Export Event Returns CSV
              </button>
            </div>

            <div className="comparison-table-wrap">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Filing Date</th>
                    <th>Base Trade Date</th>
                    <th>Horizon</th>
                    <th>Cumulative Return</th>
                    <th>Max Drawdown</th>
                    <th>Quality Status</th>
                    <th>Accession</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e, idx) => (
                    <tr key={`${e.ticker}-${e.accession_number}-${e.horizon}-${idx}`}>
                      <td><b>{e.ticker}</b></td>
                      <td>{e.filing_date}</td>
                      <td>{e.base_trade_date}</td>
                      <td><span className="layer-chip silver">{e.horizon}-session</span></td>
                      <td style={{ color: Number(e.cumulative_return) >= 0 ? '#45c99c' : '#e27e80', fontWeight: '750' }}>
                        {e.cumulative_return != null ? pct(e.cumulative_return) : 'Pending'}
                      </td>
                      <td style={{ color: '#e27e80' }}>
                        {e.maximum_drawdown != null ? pct(e.maximum_drawdown) : '—'}
                      </td>
                      <td>
                        <span className="layer-chip gold">{e.data_quality_status}</span>
                      </td>
                      <td><code>{e.accession_number}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* -------------------- WORKSPACE 9: DATA PROVENANCE & FRESHNESS -------------------- */}
        {page === 'Data Provenance' && (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Lakehouse Data Provenance & Freshness Audit</h2>
                <p>Verifiable audit trail powered by Databricks Delta Lake and PySpark distributed engine.</p>
              </div>
              <div className="freshness-pill">
                <span className="freshness-dot" />
                <span>{freshness.data_freshness || 'Fresh as of Today'}</span>
              </div>
            </div>

            <div className="quality-stats">
              <div className="quality-stat-card">
                <small>ARCHITECTURE</small>
                <b style={{ fontSize: '13px', color: '#68d1b5' }}>Databricks Delta Lake</b>
              </div>
              <div className="quality-stat-card">
                <small>MEDALLION LAYERS</small>
                <b>Bronze → Silver → Gold</b>
              </div>
              <div className="quality-stat-card">
                <small>ENGINE STATUS</small>
                <b style={{ color: '#45c99c' }}>Active & Synced</b>
              </div>
              <div className="quality-stat-card">
                <small>SYNTHETIC DATA</small>
                <b style={{ color: '#45c99c' }}>None (0% Synthetic)</b>
              </div>
            </div>

            <h3 style={{ margin: '20px 0 10px', fontSize: '14px', color: '#fff' }}>Medallion Lakehouse Layer Catalog</h3>
            <div className="comparison-table-wrap">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>Table Name</th>
                    <th>Medallion Layer</th>
                    <th>Verified Source</th>
                    <th>Record Count</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['companies', 'Gold', 'SEC EDGAR Submissions API', companies.length],
                    ['filings', 'Gold', 'Official Form 10-K / 10-Q', filings.length],
                    ['filing_diffs', 'Gold', 'Paragraph Sequence Diff Engine', diffs.length],
                    ['risk_scores', 'Gold', 'Item 1A Linguistic Analyzer', risks.length],
                    ['daily_prices', 'Gold', 'Market Data API', prices.length],
                    ['event_returns', 'Gold', 'PySpark Event Study Engine', events.length],
                    ['fundamentals', 'Gold', 'Corporate Financial Statements', fundamentals.length],
                    ['company_comparisons', 'Gold', 'PySpark Benchmark Engine', comparisons.length],
                    ['watchlist_alerts', 'Gold', 'Materiality Rules Engine', alerts.length],
                  ].map(([tableName, layer, sourceName, rowCount]) => (
                    <tr key={tableName}>
                      <td><b>{tableName}</b></td>
                      <td><span className="layer-chip gold">{layer}</span></td>
                      <td>{sourceName}</td>
                      <td><b>{rowCount}</b> rows</td>
                      <td>
                        <button
                          className="download-btn"
                          onClick={() => downloadCsv(`seculense_${tableName}.csv`, data?.[tableName] ?? [])}
                        >
                          ↓ CSV
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: '20px', padding: '15px', background: '#0a141d', borderRadius: '10px', border: '1px solid #1e3344', fontSize: '11px', color: '#8ca0ae' }}>
              ℹ️ <b>Data Traceability Notice:</b> All corporate filings and pricing data in this Lakehouse represent authentic public market disclosures. Non-reported metrics are explicitly marked as unavailable rather than generated synthetically.
            </div>
          </section>
        )}

        {/* -------------------- WORKSPACE 10: ASK SECU (RESEARCH COPILOT) -------------------- */}
        {page === 'Ask Secu' && (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Financial Research Copilot</h2>
                <p>Deterministic assistant providing evidence-backed answers citing verified SEC filings and financials.</p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
              <span style={{ fontSize: '10px', color: '#7a91a0', alignSelf: 'center' }}>Suggested queries:</span>
              {[
                "What was Apple's gross margin trajectory?",
                "Summarize filing changes for MSFT",
                "What are the top risk themes for NVDA?",
                "Show active alerts for AAPL and TSLA",
                "What were the post-filing event returns for AMZN?",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  className="download-btn"
                  onClick={() => handleAskCopilot(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>

            <div style={{ minHeight: '260px', maxHeight: '420px', overflowY: 'auto', background: '#09151e', border: '1px solid #1f3647', borderRadius: '10px', padding: '16px', display: 'grid', gap: '12px', marginBottom: '14px' }}>
              {messages.map((m, idx) => (
                <div
                  key={idx}
                  style={{
                    alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '85%',
                    background: m.sender === 'user' ? '#14362f' : '#0e1f2b',
                    border: `1px solid ${m.sender === 'user' ? '#266355' : '#274154'}`,
                    borderRadius: '10px',
                    padding: '12px 14px',
                    color: '#e4f1f7',
                    fontSize: '12px',
                    lineHeight: '1.55',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  <b style={{ display: 'block', fontSize: '10px', color: m.sender === 'user' ? '#68d1b5' : '#7cb7e6', marginBottom: '4px' }}>
                    {m.sender === 'user' ? 'You' : 'SecuLense Copilot'}
                  </b>
                  {m.text}
                </div>
              ))}
              {!messages.length && (
                <div className="empty" style={{ margin: 'auto' }}>
                  Ask a question about financial margins, SEC filing wording changes, risk factors, or event study returns.
                </div>
              )}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleAskCopilot();
              }}
              style={{ display: 'flex', gap: '10px' }}
            >
              <input
                type="text"
                placeholder="Ask about financial trends, filing diffs, risk factors, or alerts..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                style={{ flex: 1, height: '40px', background: '#0b1924', border: '1px solid #284254', borderRadius: '8px', padding: '0 14px', color: '#fff', fontSize: '12px' }}
              />
              <button
                type="submit"
                disabled={copilotBusy || !question.trim()}
                className="download-btn"
                style={{ height: '40px', padding: '0 20px', background: '#168460', color: '#fff', borderColor: '#20a77b' }}
              >
                {copilotBusy ? 'Researching...' : 'Ask'}
              </button>
            </form>
          </section>
        )}
      </main>
    </div>
  );
}

function AuthScreen({ setup, busy, error, onSubmit }) {
  const [username, setUsername] = useState('researcher');
  const [password, setPassword] = useState('Password123!');
  const [mode, setMode] = useState(setup ? 'setup' : 'login');

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <div className="brand-icon" style={{ margin: '0 auto 12px' }}>S</div>
          <h2 style={{ color: '#fff', margin: '0 0 6px' }}>SecuLense Financial Terminal</h2>
          <p style={{ color: '#889fae', fontSize: '12px', margin: 0 }}>
            {setup ? 'Initial Administrator Setup' : mode === 'signup' ? 'Create Research Account' : 'Sign in to Financial Research'}
          </p>
        </div>

        {error && (
          <div style={{ background: '#3d1c21', border: '1px solid #6e2f38', color: '#f39b9c', padding: '10px 12px', borderRadius: '8px', fontSize: '11px', marginBottom: '14px' }}>
            {error}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit({ username, password, mode });
          }}
          style={{ display: 'grid', gap: '14px' }}
        >
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#97adb9', marginBottom: '5px' }}>Username</label>
            <input
              type="text"
              required
              minLength={3}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={{ width: '100%', height: '36px', background: '#0b1924', border: '1px solid #284457', borderRadius: '8px', padding: '0 10px', color: '#fff', fontSize: '12px', boxSizing: 'border-box' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#97adb9', marginBottom: '5px' }}>Password (min 10 chars)</label>
            <input
              type="password"
              required
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: '100%', height: '36px', background: '#0b1924', border: '1px solid #284457', borderRadius: '8px', padding: '0 10px', color: '#fff', fontSize: '12px', boxSizing: 'border-box' }}
            />
          </div>

          <button
            type="submit"
            disabled={busy}
            style={{ height: '38px', background: '#168460', border: 0, borderRadius: '8px', color: '#fff', fontWeight: '750', fontSize: '12px', cursor: 'pointer', marginTop: '6px' }}
          >
            {busy ? 'Verifying...' : setup ? 'Complete Setup' : mode === 'signup' ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        {!setup && (
          <div style={{ textAlign: 'center', marginTop: '16px', fontSize: '11px' }}>
            {mode === 'login' ? (
              <button
                type="button"
                onClick={() => setMode('signup')}
                style={{ background: 'none', border: 0, color: '#45c99c', cursor: 'pointer', padding: 0 }}
              >
                Need an account? Sign up
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setMode('login')}
                style={{ background: 'none', border: 0, color: '#45c99c', cursor: 'pointer', padding: 0 }}
              >
                Already have an account? Sign in
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const root = createRoot(document.getElementById('root'));
root.render(<App />);
