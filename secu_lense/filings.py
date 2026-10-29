"""SEC filing retrieval, tolerant section extraction, and paragraph diffs."""
from __future__ import annotations
import hashlib, html, re, time
from pathlib import Path
from typing import Any
import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"

def normalize_metadata(row: dict[str, Any], ticker: str, cik: str) -> dict[str, Any]:
    return {"ticker": ticker.upper(), "cik": str(cik).zfill(10), "accession_number": row.get("accessionNumber"),
            "filing_type": row.get("form"), "filing_date": row.get("filingDate"),
            "accepted_timestamp": row.get("acceptanceDateTime"), "fiscal_period_end": row.get("reportDate"),
            "filing_url": row.get("primary_doc_url"), "is_amendment": str(row.get("form", "")).endswith("/A")}

def get_ticker_cik(ticker: str, session=requests, user_agent="SecuLense contact@example.com") -> str:
    res = session.get(SEC_TICKERS, headers={"User-Agent": user_agent}, timeout=20); res.raise_for_status()
    for item in res.json().values():
        if item.get("ticker", "").upper() == ticker.upper(): return str(item["cik_str"]).zfill(10)
    raise KeyError(f"Ticker not found in SEC mapping: {ticker}")

def fetch_filings(ticker: str, cik: str, start: str, end: str, user_agent: str, cache_dir: Path, session=requests) -> list[dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    url = SUBMISSIONS.format(cik=str(cik).zfill(10))
    response = session.get(url, headers={"User-Agent": user_agent}, timeout=30); response.raise_for_status()
    recent = response.json().get("filings", {}).get("recent", {})
    out=[]
    for i, form in enumerate(recent.get("form", [])):
        date=recent["filingDate"][i]
        if form not in ("10-K", "10-Q", "10-K/A", "10-Q/A") or not start <= date <= end: continue
        accession=recent["accessionNumber"][i]; doc=recent["primaryDocument"][i]
        acc_path=accession.replace("-", "")
        row={k: recent.get(k, [None]*len(recent["form"]))[i] for k in ("accessionNumber","form","filingDate","acceptanceDateTime","reportDate")}
        row["primary_doc_url"]=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_path}/{doc}"
        meta=normalize_metadata(row,ticker,cik)
        target=cache_dir/f"{ticker}_{accession}.html"
        meta["raw_document_path"]=str(target)
        if not target.exists():
            time.sleep(0.12)
            r=session.get(meta["filing_url"],headers={"User-Agent":user_agent},timeout=30); r.raise_for_status(); target.write_bytes(r.content)
        out.append(meta)
    return out

def clean_html(raw: str) -> str:
    if BeautifulSoup is not None:
        soup=BeautifulSoup(raw, "html.parser")
        for tag in soup(["script","style","ix:header","header","footer","nav"]): tag.decompose()
        for br in soup.find_all(["br","p","div","tr"]): br.insert_after("\n")
        text=html.unescape(soup.get_text(" ", strip=True))
    else:
        text = re.sub(r"<(script|style|ix:header|header|footer|nav)[^>]*>.*?</\1>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
    text=re.sub(r"\s+", " ", text)
    return text.strip()

def extract_sections(raw: str) -> dict[str, dict[str, Any]]:
    """Extract Item 1A / 7 with heading variants; status is never silently empty."""
    if BeautifulSoup is not None:
        soup=BeautifulSoup(raw, "html.parser")
        for tag in soup(["script","style","ix:header","header","footer","nav"]): tag.decompose()
        text=html.unescape(soup.get_text("\n", strip=True))
    else:
        text = re.sub(r"<(script|style|ix:header|header|footer|nav)[^>]*>.*?</\1>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
    text=re.sub(r"[ \t\xa0]+", " ", text)
    lines=[re.sub(r"\s+"," ",x).strip() for x in text.splitlines() if x.strip()]
    headings=[]
    for i,line in enumerate(lines):
        m=re.match(r"(?i)^item\s+(1a|7)\b[.\s:—-]*(.*)$",line)
        if m: headings.append((i,m.group(1).lower(),m.group(2)))
    result={}
    for key,label,nextkeys in (("1a","Item 1A: Risk Factors",{"7"}),("7","Item 7: MD&A",{"1a","7a"})):
        matches=[h for h in headings if h[1]==key]
        if not matches: result[label]={"text":"","status":"unavailable","warning":"Section heading not found"}; continue
        start=matches[-1][0]; body=[matches[-1][2]] if matches[-1][2] else []
        stop=len(lines)
        for idx,k,_ in headings:
            if idx>start and (k in nextkeys or (key=="1a" and k in {"1b","2"})): stop=min(stop,idx)
        body.extend(lines[start+1:stop]); content="\n".join(x for x in body if x).strip()
        result[label]={"text":content,"status":"complete" if len(content)>300 else "partial","warning":None if len(content)>300 else "Short section; verify extraction"}
    return result

def paragraphs(text: str) -> list[str]:
    return [re.sub(r"\s+"," ",p).strip() for p in re.split(r"\n\s*\n|(?<=\.)\s{2,}",text) if len(p.strip())>35]

def compare_paragraphs(old: str, new: str) -> list[dict]:
    from difflib import SequenceMatcher
    a,b=paragraphs(old),paragraphs(new); unmatched=set(range(len(a))); result=[]
    for j,nb in enumerate(b):
        scored=[(SequenceMatcher(None,a[i].lower(),nb.lower()).ratio(),i) for i in unmatched]
        score,i=max(scored,default=(0,-1))
        if i>=0 and score>=0.98: unmatched.remove(i); continue
        if i>=0 and score>=0.55:
            unmatched.remove(i); result.append({"change_type":"modified","old_text":a[i],"new_text":nb,"similarity_score":round(score,4)})
        else: result.append({"change_type":"new","old_text":None,"new_text":nb,"similarity_score":round(score,4)})
    result.extend({"change_type":"removed","old_text":a[i],"new_text":None,"similarity_score":0.0} for i in sorted(unmatched))
    return result

def paragraph_hash(text: str) -> str: return hashlib.sha256(text.encode()).hexdigest()
