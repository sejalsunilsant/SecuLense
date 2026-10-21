"""Grounded retrieval, glossary, quiz, and deterministic learning assistant."""
GLOSSARY={"10-K":"A company's annual report filed with the SEC.","10-Q":"A quarterly report filed with the SEC.","Risk factors":"Disclosures describing important uncertainties that could affect a company.","MD&A":"Management's discussion of financial condition and operating results.","Revenue growth":"The percentage change in sales over a period.","Gross margin":"Revenue minus cost of revenue, expressed as a share of revenue.","Accounts receivable":"Amounts customers owe for goods or services already delivered.","Free cash flow":"Cash generated after capital spending; definitions can vary.","Volatility":"A measure of how much an asset's price varies over time.","Drawdown":"A decline from a prior peak to a later low.","Liquidity":"Ability to meet near-term cash obligations.","Alpha":"Return above a chosen benchmark, subject to the benchmark and period used."}
QUIZ={"question":"If accounts receivable rises 40% while revenue rises 5%, what might an analyst investigate?","options":["Whether collections are slowing or payment terms changed","Whether share price must fall","Whether the company has no customers"],"answer":0,"explanation":"Receivables can grow faster for several reasons. It is a signal to investigate, not a conclusion."}
def retrieve(question:str,documents:list[dict],k=4):
    import re
    def tokens(value): return {re.sub(r"ies$","y",re.sub(r"s$","",x)) for x in re.findall(r"[a-z0-9]+",value.lower())}
    q=tokens(question); scored=[]
    for d in documents:
        txt=str(d.get("text",d.get("paragraph_text",""))); overlap=len(q&tokens(txt))
        if overlap: scored.append((overlap,d))
    return [d for _,d in sorted(scored,key=lambda x:x[0],reverse=True)[:k]]
def answer(question:str,documents:list[dict])->dict:
    sources=retrieve(question,documents)
    if not sources:return {"answer":"I could not find supporting filing text in the available local data. Try a filing-specific question.","sources":[]}
    excerpts=[str(s.get("text",s.get("paragraph_text","")))[:500] for s in sources]
    return {"answer":"Based on the available filing excerpts:\n\n"+"\n\n".join(excerpts)+"\n\nEducational context, not an investment recommendation.","sources":[{k:s.get(k) for k in ("ticker","accession_number","filing_url","section_name")} for s in sources]}
