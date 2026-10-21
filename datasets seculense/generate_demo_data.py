#!/usr/bin/env python3
"""
SecuLense synthetic demonstration data generator.

ALL OUTPUT IS SYNTHETIC. Tickers are fictional, prices are simulated, filing text is
template-generated. Every row carries data_source = "SYNTHETIC_DEMO". Nothing here is
real SEC or market data and it must never be presented as such.

Usage:
    python generate_demo_data.py                         # 20 companies, 2016-2025
    python generate_demo_data.py --n-tickers 500 --out data/demo_big   # big-data scale
    python generate_demo_data.py --seed 7 --start-year 2018 --end-year 2024

Outputs (Parquet if pyarrow is installed, else CSV), under --out:
    companies, filings, filing_sections, daily_prices (partitioned by year),
    fundamentals, synthetic_risk_labels (ground truth), manifest.json
    sample_csv/  small CSV previews of every table

Built-in "signal": filings that introduce new serious risk paragraphs are followed by a
mild negative drift (~-4% over ~30 trading days on average, noisy). This lets the ML
pipeline demonstrate leakage-free training; it is an artefact of the simulator, NOT
evidence about real markets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

SOURCE = "SYNTHETIC_DEMO"
BENCH = "DEMOBENCH"

SECTORS = ["Technology", "Healthcare", "Financials", "Consumer", "Industrials", "Energy", "Utilities"]
NAME_STEMS = ["Alder", "Borealis", "Cinder", "Dunmore", "Eclipse", "Fathom", "Granite", "Helix",
              "Ironwood", "Juniper", "Kestrel", "Lumen", "Meridian", "Nimbus", "Orchid", "Pinnacle",
              "Quartz", "Redwood", "Sable", "Tundra", "Umbra", "Vertex", "Willow", "Xenon", "Yarrow", "Zenith"]
NAME_SUFFIX = ["Systems", "Holdings", "Dynamics", "Labs", "Group", "Industries", "Networks", "Partners"]

# ---------------------------------------------------------------------------
# Paragraph templates. {C} = company name. Severity: base severity of the wording.
# ---------------------------------------------------------------------------
RISK_TEMPLATES = {
    "Debt and liquidity": [
        ("We have substantial indebtedness, and our ability to refinance maturing obligations on acceptable terms may be limited by credit market conditions.", 0.5),
        ("Our credit agreement contains financial covenants; a breach could accelerate repayment and materially reduce our available liquidity.", 0.6),
    ],
    "Regulatory and legal": [
        ("{C} is subject to extensive regulation, and changes in laws or enforcement priorities could increase our compliance costs.", 0.4),
        ("We are party to legal proceedings whose outcomes are uncertain and could result in significant damages or injunctive relief.", 0.55),
    ],
    "Supply chain": [
        ("We depend on a limited number of suppliers for key components, and any interruption in their deliveries could delay our products.", 0.5),
        ("Port congestion and transportation disruptions may increase our logistics costs and extend lead times.", 0.4),
    ],
    "Customer concentration and churn": [
        ("A small number of customers account for a significant share of our revenue, and the loss of any one of them could harm our results.", 0.55),
        ("Customer churn may increase if competitors offer lower prices or if our service quality declines.", 0.45),
    ],
    "Margin compression": [
        ("Rising input and labor costs may compress our gross margin if we are unable to pass increases on to customers.", 0.5),
        ("Pricing pressure in our core markets could reduce operating margins in future periods.", 0.45),
    ],
    "Revenue recognition and receivables": [
        ("Our revenue recognition policies require significant judgment, and changes in estimates could affect reported results.", 0.4),
        ("Accounts receivable have grown faster than revenue, and delays in customer payments could adversely affect our cash flow.", 0.6),
    ],
    "Cybersecurity and data privacy": [
        ("A security breach could expose confidential customer data, lead to regulatory penalties and damage our reputation.", 0.55),
        ("Evolving data-privacy laws may require costly changes to how we collect and process personal information.", 0.4),
    ],
    "Competition and market demand": [
        ("We face intense competition from larger companies with greater resources, and demand for our offerings may decline.", 0.45),
        ("Shifts in consumer preferences could reduce demand for our existing products.", 0.4),
    ],
    "Operational disruptions": [
        ("Natural disasters, outages or labor disputes at our facilities could disrupt production and delivery.", 0.45),
        ("We rely on information systems whose failure could interrupt critical business operations.", 0.4),
    ],
    "Foreign exchange and macroeconomic exposure": [
        ("A significant portion of our sales is denominated in foreign currencies, and exchange-rate movements may reduce reported revenue.", 0.45),
        ("Inflation, interest-rate increases and slower economic growth could reduce customer spending.", 0.45),
    ],
    "Capital expenditure and investment": [
        ("We plan substantial capital expenditures, and returns on these investments may be lower or slower than expected.", 0.4),
        ("Acquisitions may not deliver anticipated benefits and could strain management and financial resources.", 0.45),
    ],
}

# Serious "shock" wording used when a filing introduces a new material risk.
SHOCK_TEMPLATES = {
    "Debt and liquidity": "Substantial doubt exists regarding our ability to meet near-term debt maturities, and we may need to seek covenant waivers or restructure our obligations.",
    "Regulatory and legal": "A government agency has opened an investigation into {C}'s practices, and an adverse outcome could result in material fines and operating restrictions.",
    "Supply chain": "Our sole-source supplier has notified us of a prolonged production shutdown, which is expected to materially disrupt our ability to fulfil orders.",
    "Customer concentration and churn": "Our largest customer, representing a major share of revenue, has indicated it may not renew its agreement with {C}.",
    "Margin compression": "Sharp cost inflation and contract repricing are expected to significantly reduce our gross margin over the coming periods.",
    "Revenue recognition and receivables": "We identified a material weakness in internal control over revenue recognition and observed a marked increase in overdue receivables.",
    "Cybersecurity and data privacy": "{C} experienced a cybersecurity incident involving unauthorized access to customer data; the full scope and financial impact remain uncertain.",
    "Operational disruptions": "A fire at a principal facility halted production, and the timeline and cost of restoring operations are uncertain.",
}

MDNA_TEMPLATES = [
    "Revenue for the period was ${rev:,.0f} million, a change of {g:+.1f}% compared with the prior-year period.",
    "Gross margin was {gm:.1f}% for the period, compared with {gm_prev:.1f}% in the prior-year period, reflecting product mix and input costs.",
    "Operating margin was {om:.1f}%; operating expenses are discussed below by category.",
    "Accounts receivable were ${ar:,.0f} million at period end, representing {dso:.0f} days of sales outstanding.",
    "Total debt outstanding was ${debt:,.0f} million, and we believe cash on hand and operating cash flow are sufficient for the next twelve months.",
    "Capital expenditures were ${capex:,.0f} million as we continued investment in capacity and technology.",
]

FILLER_RISK = [
    "Our results may fluctuate from quarter to quarter due to factors outside our control.",
    "Our success depends on our ability to attract and retain key personnel.",
    "We may be unable to protect our intellectual property rights adequately.",
    "Our stock price may be volatile, and investors could lose part of their investment.",
]

INTENSIFY = [("may ", "is likely to "), ("could ", "has begun to "), ("uncertain", "increasingly uncertain"),
             ("significant", "substantial and growing"), ("potential", "material")]
SOFTEN = [("is likely to ", "may "), ("substantial and growing", "significant"), ("increasingly uncertain", "uncertain")]


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def trading_calendar(start: str, end: str) -> pd.DatetimeIndex:
    # Approximation: US federal holidays. NOT the exact NYSE calendar (documented limitation).
    cbd = CustomBusinessDay(calendar=USFederalHolidayCalendar())
    return pd.date_range(start, end, freq=cbd)


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------
def make_companies(n: int, rng: np.random.Generator) -> pd.DataFrame:
    rows, used = [], set()
    for i in range(n):
        while True:
            stem = NAME_STEMS[rng.integers(len(NAME_STEMS))]
            suf = NAME_SUFFIX[rng.integers(len(NAME_SUFFIX))]
            name = f"{stem} {suf} (Synthetic)"
            if name not in used or len(used) >= len(NAME_STEMS) * len(NAME_SUFFIX):
                break
        used.add(name)
        ticker = f"Z{stem[:2].upper()}{i:03d}"[:6]
        rows.append(dict(
            ticker=ticker, cik=f"{9_000_000 + i:010d}", company_name=name.replace(" (Synthetic)", f" {i:03d} (Synthetic)"),
            sector=SECTORS[rng.integers(len(SECTORS))],
            annual_vol=float(rng.uniform(0.18, 0.55)), annual_drift=float(rng.uniform(0.0, 0.14)),
            beta=float(rng.uniform(0.6, 1.5)), base_revenue_musd=float(rng.uniform(400, 40_000)),
            data_source=SOURCE))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Filings, sections, fundamentals
# ---------------------------------------------------------------------------
def next_bday(d: pd.Timestamp, cal: pd.DatetimeIndex) -> pd.Timestamp:
    i = cal.searchsorted(d)
    return cal[min(i, len(cal) - 1)]


def make_paragraph(cat: str, rng, company: str):
    tpl, sev = RISK_TEMPLATES[cat][rng.integers(len(RISK_TEMPLATES[cat]))]
    return tpl.replace("{C}", company), sev


def modify_text(text: str, rng, intensify: bool) -> str:
    pairs = INTENSIFY if intensify else SOFTEN
    rng.shuffle(pairs := list(pairs))
    for a, b in pairs:
        if a in text:
            return text.replace(a, b, 1)
    return text + (" This exposure has increased in the current period." if intensify else "")


def generate_filings(companies: pd.DataFrame, cal: pd.DatetimeIndex, start_year: int, end_year: int, rng):
    filings, sections, funds, labels = [], [], [], []
    acc_counter = 0
    for _, co in companies.iterrows():
        t, name = co.ticker, co.company_name
        # initial risk register
        cats = list(RISK_TEMPLATES)
        reg = []  # list of dict(text, cat, sev, section)
        for c in rng.choice(cats, size=int(rng.integers(6, 10)), replace=False):
            txt, sev = make_paragraph(c, rng, name)
            reg.append(dict(text=txt, cat=c, sev=sev, sec="Item 1A"))
        for f in rng.choice(FILLER_RISK, size=2, replace=False):
            reg.append(dict(text=f, cat="Other or uncertain", sev=0.2, sec="Item 1A"))
        rev, ar_ratio, debt, gm = co.base_revenue_musd, 0.15, co.base_revenue_musd * 0.4, rng.uniform(25, 55)
        prev_by_type = {}
        periods = []
        for y in range(start_year, end_year + 1):
            periods += [(y, "10-K", pd.Timestamp(y, 2, 15) + pd.Timedelta(days=int(rng.integers(0, 14))), pd.Timestamp(y - 1, 12, 31), "FY"),
                        (y, "10-Q", pd.Timestamp(y, 5, 3) + pd.Timedelta(days=int(rng.integers(0, 7))), pd.Timestamp(y, 3, 31), "Q1"),
                        (y, "10-Q", pd.Timestamp(y, 8, 3) + pd.Timedelta(days=int(rng.integers(0, 7))), pd.Timestamp(y, 6, 30), "Q2"),
                        (y, "10-Q", pd.Timestamp(y, 11, 3) + pd.Timedelta(days=int(rng.integers(0, 7))), pd.Timestamp(y, 9, 30), "Q3")]
        for y, ftype, fdate_raw, pend, fq in periods:
            fdate = next_bday(fdate_raw, cal)
            if fdate > cal[-1]:
                continue
            acc_counter += 1
            acc = f"{int(co.cik) % 10**10:010d}-{fdate.year % 100:02d}-{acc_counter:06d}"
            # evolve register
            gen_events = []
            new_reg = []
            for p in reg:
                r = rng.random()
                if r < 0.03:
                    gen_events.append(("removed", p)); continue
                if r < 0.11:  # material modification
                    intens = rng.random() < 0.65
                    p = dict(p, text=modify_text(p["text"], rng, intens), sev=min(1, p["sev"] + (0.1 if intens else -0.1)))
                    gen_events.append(("modified", p))
                new_reg.append(p)
            reg = new_reg
            shock = rng.random() < 0.22
            shock_cats = []
            if shock:
                for c in rng.choice(list(SHOCK_TEMPLATES), size=int(rng.integers(1, 3)), replace=False):
                    p = dict(text=SHOCK_TEMPLATES[c].replace("{C}", name), cat=c, sev=float(rng.uniform(0.75, 0.95)), sec="Item 1A")
                    reg.append(p); shock_cats.append(c)
                    gen_events.append(("added", p))
            elif rng.random() < 0.25:  # benign new paragraph
                c = rng.choice(cats); txt, sev = make_paragraph(c, rng, name)
                if txt not in [q["text"] for q in reg]:
                    p = dict(text=txt, cat=c, sev=sev, sec="Item 1A"); reg.append(p); gen_events.append(("added", p))
            # fundamentals evolve
            g = float(rng.normal(0.015, 0.04) - (0.05 if shock else 0))
            rev *= (1 + g)
            ar_ratio *= (1 + (0.25 if shock and "Revenue recognition and receivables" in shock_cats else rng.normal(0.0, 0.03)))
            debt *= (1 + (0.3 if "Debt and liquidity" in shock_cats else rng.normal(0.0, 0.04)))
            gm_prev = gm; gm += rng.normal(0, 1.0) - (3 if "Margin compression" in shock_cats else 0)
            om = gm - rng.uniform(15, 25)
            ar = rev * ar_ratio; dso = ar / rev * 90
            funds.append(dict(ticker=t, accession_number=acc, fiscal_period_end=pend, fiscal_year=int(pend.year if ftype == "10-Q" else y - 1),
                              fiscal_quarter=fq, revenue_musd=round(rev, 1), revenue_growth_pct=round(g * 100, 2),
                              gross_margin_pct=round(gm, 2), operating_margin_pct=round(om, 2), receivables_musd=round(ar, 1),
                              dso_days=round(dso, 1), total_debt_musd=round(debt, 1),
                              capex_musd=round(rev * rng.uniform(0.03, 0.08), 1), data_source=SOURCE))
            md = [tpl.format(rev=rev, g=g * 100, gm=gm, gm_prev=gm_prev, om=om, ar=ar, dso=dso, debt=debt,
                             capex=rev * 0.05) for tpl in MDNA_TEMPLATES]
            # acceptance timestamp (Eastern; stored with offset)
            hour = float(rng.choice([6.5, 7.5, 8.5, 16.5, 17.5, 18.5, 20.0], p=[.1, .1, .1, .3, .2, .1, .1]))
            accepted = (fdate + pd.Timedelta(hours=hour)).tz_localize("America/New_York")
            ext_status = "complete"
            if rng.random() < 0.03: ext_status = "partial"
            if rng.random() < 0.015: ext_status = "unavailable"
            filings.append(dict(
                ticker=t, cik=co.cik, company_name=name, accession_number=acc, filing_type=ftype,
                is_amendment=False, amends_accession=None, filing_date=fdate, accepted_timestamp=accepted,
                fiscal_period_end=pend, fiscal_year=int(pend.year if ftype == "10-Q" else y - 1), fiscal_quarter=fq,
                filing_url=f"https://synthetic.invalid/{t}/{acc}", raw_document_path=f"data/bronze/sec/{t}/{acc}.html",
                extraction_status=ext_status, data_source=SOURCE))
            para_rows = []
            if ext_status != "unavailable":
                body = reg if ext_status == "complete" else reg[: max(1, len(reg) // 2)]
                for i, p in enumerate(body):
                    txt = p["text"]
                    if rng.random() < 0.04:  # cosmetic whitespace-only variation; should diff as UNCHANGED
                        txt = "  " + txt.replace(". ", ".  ") + " "
                    para_rows.append((("Item 1A"), i, txt, p["cat"], p["sev"]))
                for i, txt in enumerate(md):
                    para_rows.append(("Item 7", i, txt, None, None))
            for sec, i, txt, _, _ in para_rows:
                sections.append(dict(ticker=t, accession_number=acc, section_name=sec, paragraph_id=f"{acc}:{sec.replace(' ', '')}:{i:03d}",
                                     paragraph_index=i, paragraph_text=txt,
                                     paragraph_hash=md5(re.sub(r"\s+", " ", txt).strip().lower()),
                                     extraction_status=ext_status, data_source=SOURCE))
            for kind, p in gen_events:
                labels.append(dict(ticker=t, accession_number=acc, filing_date=fdate, change_type=kind, risk_category=p["cat"],
                                   true_severity=round(float(p["sev"]), 3), is_shock=bool(kind == "added" and p["cat"] in shock_cats and p["sev"] >= 0.75),
                                   paragraph_text=p["text"], data_source=SOURCE))
            # occasional amendment (10-K/A) with a trivial edit
            if ftype == "10-K" and rng.random() < 0.05:
                acc_counter += 1
                aacc = f"{int(co.cik) % 10**10:010d}-{fdate.year % 100:02d}-{acc_counter:06d}"
                adate = next_bday(fdate + pd.Timedelta(days=int(rng.integers(20, 50))), cal)
                if adate <= cal[-1]:
                    filings.append(dict(**{**filings[-1], "accession_number": aacc, "filing_type": "10-K/A", "is_amendment": True,
                                           "amends_accession": acc, "filing_date": adate,
                                           "accepted_timestamp": (adate + pd.Timedelta(hours=17)).tz_localize("America/New_York"),
                                           "filing_url": f"https://synthetic.invalid/{t}/{aacc}", "raw_document_path": f"data/bronze/sec/{t}/{aacc}.html"}))
                    for r in [s for s in sections if s["accession_number"] == acc][:3]:
                        sections.append({**r, "accession_number": aacc, "paragraph_id": r["paragraph_id"].replace(acc, aacc)})
    return (pd.DataFrame(filings), pd.DataFrame(sections), pd.DataFrame(funds), pd.DataFrame(labels))


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------
def anchor_index(cal: pd.DatetimeIndex, accepted: pd.Timestamp) -> int:
    """First eligible session: same day if accepted before 16:00 ET, else next session."""
    d = accepted.tz_localize(None).normalize() if accepted.tzinfo is None else accepted.tz_convert("America/New_York").tz_localize(None)
    day = d.normalize()
    i = cal.searchsorted(day)
    if i < len(cal) and cal[i] == day and d.hour + d.minute / 60 >= 16:
        i += 1
    return min(i, len(cal) - 1)


def generate_prices(companies, filings, labels, cal, rng):
    n = len(cal)
    mkt_ret = rng.normal(0.08 / 252, 0.16 / np.sqrt(252), n)
    # regime shock (synthetic crash) for realism
    k = int(n * 0.55); mkt_ret[k:k + 25] += rng.normal(-0.006, 0.01, 25)
    bench_close = 100 * np.exp(np.cumsum(mkt_ret))
    frames = []

    def to_frame(tkr, close_adj, vol_scale, split=None):
        o = close_adj * (1 + rng.normal(0, 0.003, n)); c = close_adj
        hi = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.006, n))); lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.006, n)))
        v = (vol_scale * np.exp(rng.normal(0, 0.35, n))).astype("int64")
        adj = close_adj.copy(); raw = close_adj.copy()
        if split:
            si, ratio = split
            factor = np.ones(n); factor[:si] = ratio  # prices before split were ratio x higher in raw terms
            raw = close_adj * factor; o = o * factor; hi = hi * factor; lo = lo * factor; v = (v / factor).astype("int64")
        return pd.DataFrame(dict(ticker=tkr, trade_date=cal, open=o.round(4), high=hi.round(4), low=lo.round(4), close=raw.round(4),
                                 adjusted_close=adj.round(4), volume=v, data_source=SOURCE))

    frames.append(to_frame(BENCH, bench_close, 8e7))
    shock_filings = labels[labels.is_shock][["ticker", "accession_number"]].drop_duplicates() if len(labels) else pd.DataFrame(columns=["ticker", "accession_number"])
    shock_set = set(map(tuple, shock_filings.values))
    fil_by_t = {t: g for t, g in filings.groupby("ticker")}
    for _, co in companies.iterrows():
        idio = rng.normal(co.annual_drift / 252, co.annual_vol / np.sqrt(252), n)
        r = co.beta * (mkt_ret - 0.08 / 252) + idio * 0.9
        for _, f in fil_by_t[co.ticker].iterrows():
            ai = anchor_index(cal, f.accepted_timestamp)
            if (f.ticker, f.accession_number) in shock_set:
                L = min(30, n - ai)
                r[ai:ai + L] += rng.normal(-0.0015, 0.0005, L)      # mild negative drift after serious new risks
                if ai < n: r[ai] += rng.normal(-0.01, 0.01)            # day-0 reaction
            elif ai < n:
                r[ai] += rng.normal(0, 0.015)                           # earnings-day noise
        close = 50 * rng.uniform(0.5, 4) * np.exp(np.cumsum(r))
        split = (int(n * rng.uniform(0.3, 0.7)), 4.0) if rng.random() < 0.08 else None  # 4-for-1 split, raw close shows the break
        frames.append(to_frame(co.ticker, close, rng.uniform(5e5, 4e7), split))
    df = pd.concat(frames, ignore_index=True)
    # missing observations: drop ~0.15% of rows (never benchmark) to exercise gap handling
    drop = (rng.random(len(df)) < 0.0015) & (df.ticker != BENCH)
    df = df[~drop].copy()
    df["retrieved_at"] = datetime.now(timezone.utc).isoformat()
    df["year"] = df.trade_date.dt.year
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
def write_table(df: pd.DataFrame, name: str, out: Path, parquet_ok: bool, partition=None):
    if parquet_ok:
        p = out / name
        df.to_parquet(p, partition_cols=partition, index=False) if partition else df.to_parquet(str(p) + ".parquet", index=False)
    else:
        df.to_csv(out / f"{name}.csv", index=False)
    (out / "sample_csv").mkdir(exist_ok=True)
    df.head(200).to_csv(out / "sample_csv" / f"{name}_head.csv", index=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-tickers", type=int, default=20)
    ap.add_argument("--start-year", type=int, default=2016)
    ap.add_argument("--end-year", type=int, default=2025)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/demo")
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    try:
        import pyarrow  # noqa: F401
        parquet_ok = True
    except ImportError:
        parquet_ok = False

    cal = trading_calendar(f"{a.start_year - 1}-06-01", f"{a.end_year + 1}-03-31")
    companies = make_companies(a.n_tickers, rng)
    filings, sections, funds, labels = generate_filings(companies, cal, a.start_year, a.end_year, rng)
    filings = filings[filings.filing_date <= cal[-1] - pd.Timedelta(days=120)].reset_index(drop=True)
    sections = sections[sections.accession_number.isin(filings.accession_number)]
    funds = funds[funds.accession_number.isin(filings.accession_number)]
    labels = labels[labels.accession_number.isin(filings.accession_number)]
    prices = generate_prices(companies, filings, labels, cal, rng)

    filings["accepted_timestamp"] = filings["accepted_timestamp"].dt.tz_convert("UTC")
    filings["year"] = pd.to_datetime(filings.filing_date).dt.year
    companies_out = companies.drop(columns=["annual_vol", "annual_drift", "beta", "base_revenue_musd"])

    write_table(companies_out, "companies", out, parquet_ok)
    write_table(filings, "filings", out, parquet_ok, partition=["year", "filing_type"] if parquet_ok else None)
    write_table(sections, "filing_sections", out, parquet_ok)
    write_table(prices, "daily_prices", out, parquet_ok, partition=["year"] if parquet_ok else None)
    write_table(funds, "fundamentals", out, parquet_ok)
    write_table(labels, "synthetic_risk_labels", out, parquet_ok)

    manifest = dict(
        label="SYNTHETIC DEMONSTRATION DATA - NOT REAL SEC OR MARKET DATA", data_source=SOURCE,
        generated_at=datetime.now(timezone.utc).isoformat(), seed=a.seed, format="parquet" if parquet_ok else "csv",
        benchmark_ticker=BENCH, calendar_note="US federal-holiday approximation, not the exact NYSE calendar",
        embedded_signal="Filings introducing serious new risk paragraphs are followed by mild negative drift (simulator artefact).",
        counts=dict(companies=len(companies), filings=len(filings), amendments=int(filings.is_amendment.sum()),
                    filing_sections=len(sections), daily_prices=len(prices), fundamentals=len(funds), risk_labels=len(labels),
                    shock_events=int(labels.is_shock.sum())),
        date_range=[str(prices.trade_date.min().date()), str(prices.trade_date.max().date())])
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
