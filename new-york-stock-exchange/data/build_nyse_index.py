import pandas as pd, numpy as np, json
ICF  = "/Users/wng1/Dropbox/OLD NYSE/ICF data/NYSE Data"
OUT  = "/Users/wng1/Dropbox/OLD NYSE/site-build/out"

def parse(m):
    mon,yr = str(m).split("-"); yr=int(yr); yr = yr+1900 if yr<100 else yr
    return pd.Timestamp(f"{yr}-{mon}-01")

def load(p):
    raw = pd.read_csv(p, low_memory=False)
    meta = raw.iloc[:5].set_index(raw.columns[0]).T
    meta.columns = ["company","uid","industry","class","type"]
    px = raw.iloc[5:].set_index(raw.columns[0]).apply(pd.to_numeric, errors="coerce")
    px.index = px.index.map(parse)
    return meta, px

def pw_index(px, thin_frac=0.4):
    """Price-weighted (Dow-style) chain index on the matched sample.
    Returns across data gaps are spread geometrically over the missing months
    (matching ICF's published series). A month whose quote count falls below
    thin_frac x its +/-12-month median is bridged rather than used as an anchor,
    so an anomalously thin month cannot inject a spurious round-trip."""
    n = px.notna().sum(axis=1)
    med = n.replace(0, np.nan).rolling(25, center=True, min_periods=6).median()
    eligible = (n > 0) & ((n >= thin_frac*med) | med.isna())
    months = list(px.index); r = pd.Series(np.nan, index=months)
    prev, ppos = None, None
    for pos, d in enumerate(months):
        if not eligible.iloc[pos]: continue
        cur = px.loc[d].dropna()
        if not len(cur): continue
        if prev is not None:
            both = cur.index.intersection(prev.index)
            if len(both):
                gross = cur[both].sum()/prev[both].sum(); n = pos-ppos
                per = gross**(1.0/n)-1.0
                for k in range(ppos+1, pos+1): r.iloc[k] = per
        prev, ppos = cur, pos
    return r

meta21, px21 = load(f"{ICF}/Monthly Prices 1815-1925/nyse-monthly-price-1815-1925-updated-2021-09-04-with-labels.csv")
_,      px20 = load(f"{ICF}/Monthly Prices 1815-1925/nyse-monthly-price-1815-1925-corrected-2020-08-20.csv")

pub = pd.read_csv(f"{ICF}/Monthly Index/Price-Weighted-Index-Returns-2020-08-20.csv")
pub.columns=["month","r2015","r2020"]; pub["date"]=pub.month.map(parse); pub=pub.set_index("date").sort_index()

df = pd.DataFrame(index=px21.index)
df["r2015"] = pub.r2015
df["r2020"] = pub.r2020
df["r2021"] = pw_index(px21)          # new: built on the gap-filled 2021 data
for c in ["r2015","r2020","r2021"]:
    df["idx"+c[1:]] = 100*(1+df[c].fillna(0)).cumprod()
df["n_quoted"] = px21.notna().sum(axis=1)

# industry composition (canonical)
def norm(s):
    s=str(s).strip().lower()
    if s in ("nan","","???","unknown","m"): return "Unclassified"
    for k,v in [("transp","Transport"),("bank","Bank"),("insur","Insurance"),
                ("min","Mining"),("util","Utility"),("trust","Trust")]:
        if s.startswith(k): return v
    return "Other"
meta21["ind"] = meta21.industry.map(norm)
ind = {}
for name, cols in meta21.groupby("ind").groups.items():
    ind[name] = px21[list(cols)].notna().sum(axis=1)
ind = pd.DataFrame(ind)

df.round(6).to_csv(f"{OUT}/nyse_indexes.csv")
ind.to_csv(f"{OUT}/nyse_industry_counts.csv")

ann = df[["idx2015","idx2020","idx2021"]].resample("YS").last()
ann.index = ann.index.year; ann.round(2).to_csv(f"{OUT}/nyse_index_annual.csv")

def stats(r):
    r = r.dropna()
    return dict(months=int(len(r)), annualised_pct=round(100*((1+r).prod()**(12/len(r))-1),2),
                vol_pct=round(100*r.std()*np.sqrt(12),2),
                worst=f"{100*r.min():.1f}% ({r.idxmin():%b %Y})",
                best=f"{100*r.max():.1f}% ({r.idxmax():%b %Y})")
summary = {
    "securities": int(px21.shape[1]),
    "price_observations_2021": int(px21.notna().sum().sum()),
    "price_observations_2020": int(px20.notna().sum().sum()),
    "added_in_2021": int(px21.notna().sum().sum()-px20.notna().sum().sum()),
    "months": int(px21.shape[0]),
    "span": f"{px21.index[0]:%b %Y} – {px21.index[-1]:%b %Y}",
    "empty_months": int((px21.notna().sum(axis=1)==0).sum()),
    "index": {k: stats(df[k]) for k in ["r2015","r2020","r2021"]},
}
json.dump(summary, open(f"{OUT}/summary.json","w"), indent=2)
print(json.dumps(summary, indent=2))
print("\n=== cumulative index by decade (1815 = 100) ===")
print(df[["idx2015","idx2020","idx2021"]].resample("10YS").last().round(1).to_string())
print("\n=== 2021 vs 2020 index: annualised ===")
print("wrote:", OUT)
