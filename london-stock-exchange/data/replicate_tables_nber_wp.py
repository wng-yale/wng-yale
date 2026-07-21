"""
FROZEN — NBER Working Paper version (do not modify).

Replicate Tables 1-4 and Table 6 from:
  "Capital Structure, Seniority, and Risk Premia:
   Evidence from the London Stock Exchange, 1870-1929"
   Goetzmann, Reyes De La Luz, and Rouwenhorst (2026)

Uses IMM_A_11_25_2025.csv (annual security-level data) and macro data.
This is the exact script used to produce the NBER WP tables.
For the updated version, see replicate_tables_v2.py.
"""

import polars as pl
from polars import col
import numpy as np
import csv
import math

# ──────────────────────────────────────────────────────────
# 0.  LOAD DATA
# ──────────────────────────────────────────────────────────

DATA_DIR = "../database/annual"
MACRO_DIR = "../database/mappings"

imm = pl.read_csv(f"{DATA_DIR}/IMM_A_11_25_2025.csv", infer_schema_length=1_000_000)

# Fix known typo in type field
imm = imm.with_columns(
    pl.when(col("type") == "Preferrred Stock")
    .then(pl.lit("Preferred Stock"))
    .otherwise(col("type"))
    .alias("type")
)

# Exclude firmid 2017 as Fernando does (but keep nulls — govt/muni bonds have no firmid)
imm = imm.filter(col("firmid").is_null() | (col("firmid") != 2017))

print(f"Loaded {imm.height} security-year observations")
print(f"Years: {imm['year'].min()} - {imm['year'].max()}")
print(f"Security types: {sorted(imm['type'].unique().to_list())}")

# ──────────────────────────────────────────────────────────
# 0b. LOAD MACRO DATA
# ──────────────────────────────────────────────────────────

# Commercial paper rate and consol yield from BoE macro
boe = pl.read_csv(f"{MACRO_DIR}/BofE-macro.csv")
# inflation and riskfree are already in IMM data per year; extract them
macro_from_imm = (
    imm.select("year", "inflation", "riskfree", "consol")
    .unique("year")
    .sort("year")
    .filter(col("year").is_between(1870, 1929))
)

# GDP from JST dataset (Jorda-Schularick-Taylor)
jst_rows = []
with open(f"{MACRO_DIR}/JSTdataset.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["iso"] == "GBR":
            try:
                yr = int(row["year"])
                gdp = float(row["gdp"]) if row["gdp"] else None
                rgdp = float(row["rgdpmad"]) if row["rgdpmad"] else None
                cpi_val = float(row["cpi"]) if row["cpi"] else None
                jst_rows.append({"year": yr, "gdp_nominal": gdp, "rgdp": rgdp, "cpi": cpi_val})
            except (ValueError, KeyError):
                pass

jst = pl.DataFrame(jst_rows).filter(col("year").is_between(1869, 1929))
# GDP growth as pct change in real GDP
jst = jst.sort("year").with_columns(
    (col("rgdp") / col("rgdp").shift(1) - 1.0).alias("gdp_growth")
)

# ──────────────────────────────────────────────────────────
# 1.  IDENTIFY TOP 100 FIRMS BY EQUITY MARKET CAP (lagged)
# ──────────────────────────────────────────────────────────

equity_by_year = (
    imm.filter(
        (col("type") == "Common Stock") & col("marketvalueGBP_lag").is_not_null()
    )
    .group_by(["year", "firmid"])
    .agg(
        mkt_cap_lag=pl.sum("marketvalueGBP_lag"),
        iso=col("iso").first(),
        sic=col("sic").first(),
    )
)

top100_uk = equity_by_year.filter(col("iso") == "GBR").filter(
    col("mkt_cap_lag").rank("average", descending=True).over("year") <= 100
)

top100_wxuk = equity_by_year.filter(col("iso") != "GBR").filter(
    col("mkt_cap_lag").rank("average", descending=True).over("year") <= 100
)

top100_wrld = equity_by_year.filter(col("iso").is_not_null()).filter(
    col("mkt_cap_lag").rank("average", descending=True).over("year") <= 100
)

# ──────────────────────────────────────────────────────────
# 2.  BUILD CAP-WEIGHTED RETURN INDEXES BY ASSET CLASS
# ──────────────────────────────────────────────────────────

CORP_TYPES = ["Common Stock", "Preferred Stock", "Corporate Bond"]
ALL_TYPES = ["Common Stock", "Preferred Stock", "Corporate Bond",
             "Municipal Bond", "Government Bond"]


def build_indexes(top100_df, label, types=ALL_TYPES):
    """
    Build cap-weighted annual return indexes for given top-100 firm set.
    For Municipal and Government bonds, we include ALL such securities
    (not just those matched to top-100 firms), since these are not firm-specific.
    """
    # Corporate securities: join to top-100 firms
    corp = (
        imm.filter(
            col("totreturn").is_not_null()
            & col("marketvalueGBP_lag").is_not_null()
            & col("type").is_in(CORP_TYPES)
        )
        .join(top100_df.select("year", "firmid"), on=["year", "firmid"], how="inner")
        .group_by(["year", "type"])
        .agg(
            ret=(col("totreturn") * col("marketvalueGBP_lag")).sum()
            / pl.sum("marketvalueGBP_lag"),
            n_securities=pl.len(),
        )
    )

    # For Municipal and Government bonds — use all securities in the relevant geography
    if label == "UK":
        geo_filter = col("iso") == "GBR"
    elif label == "WXUK":
        geo_filter = col("iso") != "GBR"
    else:
        geo_filter = col("iso").is_not_null()

    non_corp = (
        imm.filter(
            col("totreturn").is_not_null()
            & col("marketvalueGBP_lag").is_not_null()
            & col("type").is_in(["Municipal Bond", "Government Bond"])
            & geo_filter
        )
        .group_by(["year", "type"])
        .agg(
            ret=(col("totreturn") * col("marketvalueGBP_lag")).sum()
            / pl.sum("marketvalueGBP_lag"),
            n_securities=pl.len(),
        )
    )

    combined = pl.concat([corp, non_corp]).sort("year")
    return combined


results = {}
for top_df, label in [(top100_uk, "UK"), (top100_wxuk, "WXUK"), (top100_wrld, "WRLD")]:
    results[label] = build_indexes(top_df, label)

# ──────────────────────────────────────────────────────────
# 3.  COMPUTE SUMMARY STATISTICS (TABLE 1)
# ──────────────────────────────────────────────────────────


def summary_stats(returns_series, rf_series=None):
    """Compute GM, AM, SD, SR, t-stat for a return series."""
    r = np.array(returns_series, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    if n == 0:
        return {"GM": np.nan, "AM": np.nan, "SD": np.nan, "SR": np.nan,
                "t_stat": np.nan, "N": 0}
    am = np.mean(r)
    sd = np.std(r, ddof=1)
    gm = np.exp(np.mean(np.log(1 + r))) - 1 if np.all(1 + r > 0) else np.nan
    t_stat = am / (sd / np.sqrt(n)) if sd > 0 else np.nan

    sr = np.nan
    if rf_series is not None:
        rf = np.array(rf_series, dtype=float)
        rf = rf[~np.isnan(rf)]
        if len(rf) == n:
            excess = r - rf
            sr = np.mean(excess) / np.std(excess, ddof=1) if np.std(excess, ddof=1) > 0 else np.nan

    return {"GM": gm, "AM": am, "SD": sd, "SR": sr, "t_stat": t_stat, "N": n}


def print_table1(label, index_df, macro_df):
    """Print Table 1 for a given geography."""
    print(f"\n{'='*80}")
    print(f"TABLE 1 — Summary Statistics — Nominal Returns ({label})")
    print(f"{'='*80}")
    print(f"{'Asset Class':<25s} {'GM':>8s} {'AM':>8s} {'SD':>8s} {'SR':>8s} {'t-stat':>8s} {'N':>5s}")
    print("-" * 80)

    # Get commercial paper rates for Sharpe ratio (UK only)
    rf_by_year = dict(
        zip(macro_df["year"].to_list(), macro_df["riskfree"].to_list())
    )

    type_order = ["Common Stock", "Preferred Stock", "Corporate Bond",
                  "Municipal Bond", "Government Bond"]

    for sec_type in type_order:
        sub = index_df.filter(col("type") == sec_type).sort("year")
        if sub.height == 0:
            continue
        years = sub["year"].to_list()
        rets = sub["ret"].to_list()

        rf_vals = [rf_by_year.get(y, np.nan) for y in years]
        has_rf = not all(np.isnan(v) for v in rf_vals)

        stats = summary_stats(rets, rf_vals if has_rf else None)
        n_sec_avg = sub["n_securities"].mean()
        print(
            f"{sec_type:<25s} {stats['GM']*100:>8.2f} {stats['AM']*100:>8.2f} "
            f"{stats['SD']*100:>8.2f} {stats['SR']:>8.2f} {stats['t_stat']:>8.2f} "
            f"{n_sec_avg:>5.0f}"
        )

    # Commercial paper rate (UK only)
    if label == "UK":
        cp_vals = macro_df.sort("year")["riskfree"].to_list()
        cp_years = macro_df.sort("year")["year"].to_list()
        cp_arr = np.array(cp_vals, dtype=float)
        cp_arr = cp_arr[~np.isnan(cp_arr)]
        if len(cp_arr) > 0:
            am_cp = np.mean(cp_arr)
            sd_cp = np.std(cp_arr, ddof=1)
            gm_cp = np.exp(np.mean(np.log(1 + cp_arr))) - 1
            t_cp = am_cp / (sd_cp / np.sqrt(len(cp_arr)))
            print(
                f"{'Commercial Paper':<25s} {gm_cp*100:>8.2f} {am_cp*100:>8.2f} "
                f"{sd_cp*100:>8.2f} {'—':>8s} {t_cp:>8.2f} {'—':>5s}"
            )

        # Inflation
        inf_vals = macro_df.sort("year")["inflation"].to_list()
        inf_arr = np.array(inf_vals, dtype=float)
        inf_arr = inf_arr[~np.isnan(inf_arr)]
        if len(inf_arr) > 0:
            am_inf = np.mean(inf_arr)
            sd_inf = np.std(inf_arr, ddof=1)
            gm_inf = np.exp(np.mean(np.log(1 + inf_arr))) - 1 if np.all(1 + inf_arr > 0) else np.nan
            print(
                f"{'Inflation':<25s} {gm_inf*100:>8.2f} {am_inf*100:>8.2f} "
                f"{sd_inf*100:>8.2f} {'—':>8s} {'—':>8s} {'—':>5s}"
            )


for label in ["UK", "WXUK", "WRLD"]:
    print_table1(label, results[label], macro_from_imm)


# ──────────────────────────────────────────────────────────
# 4.  TABLE 2 — REAL RETURNS (UK only)
# ──────────────────────────────────────────────────────────

print(f"\n{'='*80}")
print(f"TABLE 2 — Real Returns — UK Asset Classes (Inflation-Adjusted)")
print(f"{'='*80}")

inf_arr = np.array(macro_from_imm.sort("year")["inflation"].to_list(), dtype=float)
inf_arr = inf_arr[~np.isnan(inf_arr)]
mean_inflation = np.mean(inf_arr) if len(inf_arr) > 0 else 0.0
print(f"Mean inflation rate: {mean_inflation*100:.2f}%\n")

uk_idx = results["UK"]
type_order = ["Common Stock", "Preferred Stock", "Corporate Bond",
              "Municipal Bond", "Government Bond"]

# Get government bond AM for computing real premium
gov_sub = uk_idx.filter(col("type") == "Government Bond").sort("year")
gov_am = np.mean(gov_sub["ret"].to_numpy()) if gov_sub.height > 0 else np.nan
gov_real = gov_am - mean_inflation

print(f"{'Asset Class':<25s} {'Nominal AM':>12s} {'Real AM':>10s} {'Real Prem':>10s}")
print("-" * 60)

for sec_type in type_order:
    sub = uk_idx.filter(col("type") == sec_type).sort("year")
    if sub.height == 0:
        continue
    am = np.mean(sub["ret"].to_numpy())
    real_am = am - mean_inflation
    real_prem = real_am - gov_real
    print(
        f"{sec_type:<25s} {am*100:>12.2f} {real_am*100:>10.2f} {real_prem*100:>10.2f}"
    )

# Commercial paper
cp_arr = np.array(macro_from_imm.sort("year")["riskfree"].to_list(), dtype=float)
cp_arr = cp_arr[~np.isnan(cp_arr)]
if len(cp_arr) > 0:
    am_cp = np.mean(cp_arr)
    real_cp = am_cp - mean_inflation
    real_prem_cp = real_cp - gov_real
    print(
        f"{'Commercial Paper':<25s} {am_cp*100:>12.2f} {real_cp*100:>10.2f} {real_prem_cp*100:>10.2f}"
    )


# ──────────────────────────────────────────────────────────
# 5.  TABLE 3 — CORRELATION MATRIX (UK)
# ──────────────────────────────────────────────────────────

print(f"\n{'='*80}")
print(f"TABLE 3 — Correlation Matrix of Capital-Weighted Indexes (UK)")
print(f"{'='*80}")

# Pivot to wide format
uk_wide = (
    uk_idx.select("year", "type", "ret")
    .pivot(values="ret", index="year", on="type")
    .sort("year")
)

# Add commercial paper and inflation
uk_wide = uk_wide.join(
    macro_from_imm.select("year", col("riskfree").alias("Comm. Paper"),
                          col("inflation").alias("Inflation")),
    on="year",
    how="left",
)

corr_cols = ["Common Stock", "Preferred Stock", "Corporate Bond",
             "Municipal Bond", "Government Bond", "Comm. Paper", "Inflation"]
short_names = ["UK Eq", "UK Prf", "UK Corp", "UK Muni", "UK Gov", "CP", "Infl"]

# Build numpy matrix
available_cols = [c for c in corr_cols if c in uk_wide.columns]
available_short = [short_names[corr_cols.index(c)] for c in available_cols]

mat = uk_wide.select(available_cols).to_numpy()
# Drop rows with any NaN
mask = ~np.isnan(mat).any(axis=1)
mat_clean = mat[mask]

corr = np.corrcoef(mat_clean, rowvar=False)

# Print
header = f"{'':>10s}" + "".join(f"{s:>10s}" for s in available_short)
print(header)
for i, name in enumerate(available_short):
    row_str = f"{name:>10s}"
    for j in range(len(available_short)):
        if j <= i:
            row_str += f"{corr[i, j]:>10.2f}"
        else:
            row_str += f"{'':>10s}"
    print(row_str)


# ──────────────────────────────────────────────────────────
# 6.  TABLE 4 — RISK PREMIA
# ──────────────────────────────────────────────────────────

def get_return_series(index_df, sec_type=None, macro_df=None, macro_col=None):
    """Get a year/ret dataframe from either an index or macro source."""
    if macro_col is not None:
        return macro_df.select("year", col(macro_col).alias("ret")).sort("year")
    return (
        index_df.filter(col("type") == sec_type)
        .select("year", "ret")
        .sort("year")
    )


def compute_premium_from_series(series_a, series_b):
    """Compute premium = series_a - series_b, return stats dict."""
    merged = (
        series_a.rename({"ret": "ret_a"})
        .join(series_b.rename({"ret": "ret_b"}), on="year", how="inner")
        .drop_nulls()
    )
    if merged.height == 0:
        return None

    prem = (merged["ret_a"] - merged["ret_b"]).to_numpy()
    prem = prem[~np.isnan(prem)]
    n = len(prem)
    if n == 0:
        return None

    am = np.mean(prem)
    sd = np.std(prem, ddof=1)
    gm = np.exp(np.mean(np.log(1 + prem))) - 1 if np.all(1 + prem > 0) else np.nan
    t_stat = am / (sd / np.sqrt(n)) if sd > 0 else np.nan

    sig = ""
    if abs(t_stat) > 2.576:
        sig = "***"
    elif abs(t_stat) > 1.96:
        sig = "**"
    elif abs(t_stat) > 1.645:
        sig = "*"

    return {"GM": gm, "AM": am, "SD": sd, "t_stat": t_stat, "N": n, "sig": sig}


def print_premium_row(name, result):
    if result:
        print(
            f"{name:<40s} {result['GM']*100:>8.2f} {result['AM']*100:>8.2f} "
            f"{result['SD']*100:>8.2f} {result['t_stat']:>7.2f}{result['sig']:<1s} "
            f"{result['N']:>5d}"
        )
    else:
        print(f"{name:<40s} {'N/A':>8s}")


def print_table4(label, index_df, macro_df):
    print(f"\n--- {label} ---")
    print(f"{'Premium':<40s} {'GM':>8s} {'AM':>8s} {'SD':>8s} {'t-stat':>8s} {'N':>5s}")
    print("-" * 75)

    eq = get_return_series(index_df, "Common Stock")
    prf = get_return_series(index_df, "Preferred Stock")
    cb = get_return_series(index_df, "Corporate Bond")
    muni = get_return_series(index_df, "Municipal Bond")
    gov = get_return_series(index_df, "Government Bond")
    cp = get_return_series(None, macro_col="riskfree", macro_df=macro_df)

    # Equity - Commercial Paper
    print_premium_row("Equity - Comm. Paper", compute_premium_from_series(eq, cp))

    # Equity - LT Govt Bond
    print_premium_row("Equity - LT Govt Bond", compute_premium_from_series(eq, gov))

    # Equity - All Other Corporate (avg of preferred + corporate bond)
    merged3 = (
        eq.rename({"ret": "eq_ret"})
        .join(prf.rename({"ret": "prf_ret"}), on="year", how="inner")
        .join(cb.rename({"ret": "cb_ret"}), on="year", how="inner")
    )
    if merged3.height > 0:
        other = (merged3["prf_ret"].to_numpy() + merged3["cb_ret"].to_numpy()) / 2
        prem_arr = merged3["eq_ret"].to_numpy() - other
        prem_arr = prem_arr[~np.isnan(prem_arr)]
        n = len(prem_arr)
        am = np.mean(prem_arr)
        sd = np.std(prem_arr, ddof=1)
        gm = np.exp(np.mean(np.log(1 + prem_arr))) - 1 if np.all(1 + prem_arr > 0) else np.nan
        t_stat = am / (sd / np.sqrt(n)) if sd > 0 else np.nan
        sig = "***" if abs(t_stat) > 2.576 else "**" if abs(t_stat) > 1.96 else "*" if abs(t_stat) > 1.645 else ""
        print_premium_row("Equity - All Corp Secs",
                          {"GM": gm, "AM": am, "SD": sd, "t_stat": t_stat, "N": n, "sig": sig})
    else:
        print_premium_row("Equity - All Corp Secs", None)

    # Priority premium (Preferred - Corporate Bond)
    print_premium_row("Priority (Pref - Corp Bond)", compute_premium_from_series(prf, cb))

    # Default premium (Corporate Bond - Govt Bond)
    print_premium_row("Default (Corp Bond - Govt Bond)", compute_premium_from_series(cb, gov))

    # Municipal - Govt Bond
    print_premium_row("Municipal - Govt Bond", compute_premium_from_series(muni, gov))

    # Horizon premium (Govt Bond - Commercial Paper)
    print_premium_row("Horizon (Govt Bond - Comm. Paper)", compute_premium_from_series(gov, cp))


print(f"\n{'='*80}")
print(f"TABLE 4 — Risk Premium Estimates")
print(f"{'='*80}")

for label in ["UK", "WXUK", "WRLD"]:
    print_table4(label, results[label], macro_from_imm)


# ──────────────────────────────────────────────────────────
# 7.  TABLE 6 — REGRESSION: EQUITY PREMIUM ON GDP GROWTH
# ──────────────────────────────────────────────────────────

print(f"\n{'='*80}")
print(f"TABLE 6 — Equity Risk Premium and GDP Growth (UK)")
print(f"{'='*80}")

# Get annual equity excess return over govt bonds
eq_uk = (
    results["UK"]
    .filter(col("type") == "Common Stock")
    .select("year", col("ret").alias("eq_ret"))
    .sort("year")
)
gov_uk = (
    results["UK"]
    .filter(col("type") == "Government Bond")
    .select("year", col("ret").alias("gov_ret"))
    .sort("year")
)

eq_prem_df = eq_uk.join(gov_uk, on="year", how="inner").with_columns(
    (col("eq_ret") - col("gov_ret")).alias("eq_premium")
)

# Merge with GDP growth
reg_df = eq_prem_df.join(jst.select("year", "gdp_growth"), on="year", how="inner").drop_nulls()

y = reg_df["eq_premium"].to_numpy()
x = reg_df["gdp_growth"].to_numpy()
n = len(y)

# OLS regression: y = a + b*x + e
x_mat = np.column_stack([np.ones(n), x])
beta = np.linalg.lstsq(x_mat, y, rcond=None)[0]
y_hat = x_mat @ beta
resid = y - y_hat
sse = np.sum(resid**2)
sst = np.sum((y - np.mean(y))**2)
r_sq = 1 - sse / sst

# Standard errors (OLS)
s2 = sse / (n - 2)
var_beta = s2 * np.linalg.inv(x_mat.T @ x_mat)
se = np.sqrt(np.diag(var_beta))
t_stats = beta / se

# Newey-West standard errors (1 lag)
def newey_west_se(X, resid, n_lags=1):
    k = X.shape[1]
    n = len(resid)
    # S0
    S = np.zeros((k, k))
    for t in range(n):
        S += resid[t]**2 * np.outer(X[t], X[t])
    # Add lag terms
    for lag in range(1, n_lags + 1):
        w = 1 - lag / (n_lags + 1)  # Bartlett kernel
        for t in range(lag, n):
            cross = resid[t] * resid[t - lag] * (np.outer(X[t], X[t - lag]) + np.outer(X[t - lag], X[t]))
            S += w * cross
    S /= n
    XtX_inv = np.linalg.inv(X.T @ X / n)
    V = XtX_inv @ S @ XtX_inv / n
    return np.sqrt(np.diag(V))

nw_se = newey_west_se(x_mat, resid, n_lags=1)
nw_t = beta / nw_se

print(f"\nDependent variable: Annual UK equity excess return over LT Govt Bonds")
print(f"Independent variable: Annual UK real GDP growth")
print(f"Sample: {int(reg_df['year'].min())} - {int(reg_df['year'].max())}, N = {n}\n")
print(f"{'':>15s} {'Coef':>10s} {'OLS SE':>10s} {'OLS t':>8s} {'NW SE':>10s} {'NW t':>8s}")
print("-" * 60)
print(f"{'Intercept':>15s} {beta[0]*100:>10.3f} {se[0]*100:>10.3f} {t_stats[0]:>8.2f} {nw_se[0]*100:>10.3f} {nw_t[0]:>8.2f}")
print(f"{'GDP Growth':>15s} {beta[1]*100:>10.3f} {se[1]*100:>10.3f} {t_stats[1]:>8.2f} {nw_se[1]*100:>10.3f} {nw_t[1]:>8.2f}")
print(f"\nR-squared: {r_sq:.4f}")
print(f"Note: Coefficients and SEs multiplied by 100 for readability.")

print("\n\nDone.")
