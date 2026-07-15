"""
Regenerate the Chapter 1 & 2 data-driven figures on the authoritative
SBBI series extended through year-end 2025 (Ibbotson, *Exponential Wealth*,
forthcoming 2026). Source: /Users/wng1/Dropbox/History/SBBI/sbbi_file.xlsx

Five risky/riskless asset classes (no LT Corporate series in this file):
Large-Cap, Small-Cap, LT Gov (20Y), IT Gov (5Y), T-Bills; plus Inflation.
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from scipy import stats, optimize

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.size': 11, 'font.family': 'sans-serif',
    'axes.labelsize': 12, 'axes.titlesize': 13, 'figure.dpi': 150,
    'axes.spines.top': False, 'axes.spines.right': False,
})

FIGDIR = '/Users/wng1/Dropbox/IMM/wng-yale/investment-theory/figures/'
SRC = '/Users/wng1/Dropbox/History/SBBI/sbbi_file.xlsx'

# ── Load monthly & annual ──────────────────────────────────────────
mo = pd.read_excel(SRC, sheet_name='monthly')
mo['date'] = pd.to_datetime(mo['date'])
an = pd.read_excel(SRC, sheet_name='annual')

MCOL = {'LargeCap': 'Large Cap Total Return', 'Small': 'Small Cap Total Return',
        'LTG': '20Y Treasury Total Return', 'ITG': '5Y Treasury Total Return',
        'TB30': '1M Treasury Total Return', 'INF': 'CPI'}
ACOL = {'LargeCap': 'Annual Large Cap Total Return', 'Small': 'Annual Small Cap Total Return',
        'LTG': 'Annual 20Y Treasury Total Return', 'ITG': 'Annual 5Y Treasury Total Return',
        'TB30': 'Annual 1M Treasury Total Return', 'INF': 'Annual CPI'}
annual = pd.DataFrame({k: an[v].astype(float).values for k, v in ACOL.items()},
                      index=an['year'].astype(int).values)

# ================================================================
# 1. WEALTH GROWTH (log scale) — Fig 1.1
# ================================================================
print("wealth_growth.svg ...")
fig, ax = plt.subplots(figsize=(8, 5))
wealth_cols = ['LargeCap', 'Small', 'LTG', 'TB30', 'INF']
colors_w = {'LargeCap': '#1f77b4', 'Small': '#17becf', 'LTG': '#ff7f0e',
            'TB30': '#7f7f7f', 'INF': '#d62728'}
labels_w = {'LargeCap': 'Large-Cap Stocks', 'Small': 'Small-Cap Stocks',
            'LTG': 'LT Gov Bonds', 'TB30': 'T-Bills', 'INF': 'Inflation'}
for c in wealth_cols:
    wealth = (1 + mo[MCOL[c]].astype(float)).cumprod()
    ax.plot(mo['date'], wealth, label=labels_w[c], color=colors_w[c],
            linewidth=1.4 if c in ['LargeCap', 'Small'] else 1.0)
ax.set_yscale('log')
ax.set_ylabel('Growth of $1 (log scale)')
ax.set_title('Growth of $1 Invested in 1926 (through 2025)')
ax.legend(loc='upper left', frameon=True, framealpha=0.9, fontsize=10)
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'${x:,.0f}' if x >= 1 else f'${x:.2f}'))
ax.set_xlim(mo['date'].min(), mo['date'].max())
fig.tight_layout(); fig.savefig(FIGDIR + 'wealth_growth.svg', format='svg', bbox_inches='tight'); plt.close()

# ================================================================
# 2. RETURN DISTRIBUTION — Fig 1.2
# ================================================================
print("return_distribution.svg ...")
fig, ax = plt.subplots(figsize=(8, 5))
ret = annual['LargeCap'].dropna().values
mu, sigma = ret.mean(), ret.std(ddof=1)
ax.hist(ret, bins=25, density=True, color='#1f77b4', alpha=0.65,
        edgecolor='white', linewidth=0.5, label='Observed')
x = np.linspace(ret.min() - 0.05, ret.max() + 0.05, 200)
ax.plot(x, stats.norm.pdf(x, mu, sigma), 'r-', linewidth=1.8,
        label=f'Normal ($\\mu$={mu:.1%}, $\\sigma$={sigma:.1%})')
ax.axvline(mu, color='#333333', linestyle='--', linewidth=1, label=f'Mean = {mu:.1%}')
ax.axvline(mu - sigma, color='#999999', linestyle=':', linewidth=1, label='$\\pm$1 s.d.')
ax.axvline(mu + sigma, color='#999999', linestyle=':', linewidth=1)
ax.set_xlabel('Annual Return'); ax.set_ylabel('Density')
ax.set_title('Distribution of Annual Large-Cap Stock Returns (1926–2025)')
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))
ax.legend(fontsize=9, frameon=True)
fig.tight_layout(); fig.savefig(FIGDIR + 'return_distribution.svg', format='svg', bbox_inches='tight'); plt.close()

# ================================================================
# EFFICIENT FRONTIER HELPERS (5 classes, long-only)
# ================================================================
asset_cols = ['LargeCap', 'Small', 'LTG', 'ITG', 'TB30']
asset_labels = ['Large Cap', 'Small Cap', 'LT Gov', 'IT Gov', 'T-Bills']
ann_ret = annual[asset_cols].dropna()
mu_vec = ann_ret.mean().values
cov_mat = ann_ret.cov().values
n_assets = len(asset_cols)
rf = ann_ret['TB30'].mean()

def pstats(w):
    return w @ mu_vec, np.sqrt(w @ cov_mat @ w)
def neg_sharpe(w):
    r, v = pstats(w); return -(r - rf) / v
def min_var_obj(w):
    return w @ cov_mat @ w

bounds = tuple((0, 1) for _ in range(n_assets))
constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
w0 = np.ones(n_assets) / n_assets
res_mv = optimize.minimize(min_var_obj, w0, method='SLSQP', bounds=bounds, constraints=constraints)
mv_ret, mv_vol = pstats(res_mv.x)
res_tan = optimize.minimize(neg_sharpe, w0, method='SLSQP', bounds=bounds, constraints=constraints)
tan_ret, tan_vol = pstats(res_tan.x)
target_rets = np.linspace(mv_ret, mu_vec.max(), 80)
frontier_vols = []
for tr in target_rets:
    cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
            {'type': 'eq', 'fun': lambda w, t=tr: w @ mu_vec - t}]
    res = optimize.minimize(min_var_obj, res_mv.x, method='SLSQP', bounds=bounds, constraints=cons)
    frontier_vols.append(np.sqrt(res.fun))
frontier_vols = np.array(frontier_vols)
asset_vols = np.sqrt(np.diag(cov_mat)); asset_rets = mu_vec

# ================================================================
# 3. EFFICIENT FRONTIER — Fig 2.3
# ================================================================
print("efficient_frontier.svg ...")
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(frontier_vols, target_rets, 'b-', linewidth=2, label='Efficient Frontier')
asset_colors = ['#1f77b4', '#17becf', '#ff7f0e', '#2ca02c', '#7f7f7f']
for i, lab in enumerate(asset_labels):
    ax.scatter(asset_vols[i], asset_rets[i], s=60, color=asset_colors[i],
               zorder=5, edgecolors='black', linewidth=0.5)
    offset = (8, 6) if lab != 'T-Bills' else (8, -10)
    ax.annotate(lab, (asset_vols[i], asset_rets[i]), textcoords='offset points', xytext=offset, fontsize=9)
ax.scatter(mv_vol, mv_ret, s=90, color='green', marker='D', zorder=6,
           edgecolors='black', linewidth=0.5, label='Min Variance')
ax.scatter(tan_vol, tan_ret, s=90, color='red', marker='*', zorder=6,
           edgecolors='black', linewidth=0.5, label='Tangency Portfolio')
ax.set_xlabel('Annual Standard Deviation'); ax.set_ylabel('Annual Mean Return')
ax.set_title('Mean-Variance Efficient Frontier (1926–2025)')
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))
ax.legend(fontsize=9, loc='lower right', frameon=True)
fig.tight_layout(); fig.savefig(FIGDIR + 'efficient_frontier.svg', format='svg', bbox_inches='tight'); plt.close()

# ================================================================
# 4. CORRELATION MATRIX — Fig 2.1b
# ================================================================
print("correlation_matrix.svg ...")
fig, ax = plt.subplots(figsize=(7, 7))
corr = ann_ret[asset_cols].corr(); corr.columns = asset_labels; corr.index = asset_labels
im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='equal')
ax.set_xticks(range(n_assets)); ax.set_xticklabels(asset_labels, rotation=45, ha='right', fontsize=10)
ax.set_yticks(range(n_assets)); ax.set_yticklabels(asset_labels, fontsize=10)
for i in range(n_assets):
    for j in range(n_assets):
        color = 'white' if abs(corr.values[i, j]) > 0.6 else 'black'
        ax.text(j, i, f'{corr.values[i, j]:.2f}', ha='center', va='center',
                fontsize=11, color=color, fontweight='bold')
ax.set_title('Asset Class Correlation Matrix (1926–2025)')
fig.colorbar(im, ax=ax, shrink=0.8, label='Correlation')
fig.tight_layout(); fig.savefig(FIGDIR + 'correlation_matrix.svg', format='svg', bbox_inches='tight'); plt.close()

print("Done. Tangency: ret=%.1f%% vol=%.1f%% | MinVar: ret=%.1f%% vol=%.1f%% | rf=%.1f%%"
      % (tan_ret*100, tan_vol*100, mv_ret*100, mv_vol*100, rf*100))
print("Tangency weights:", dict(zip(asset_labels, np.round(res_tan.x, 3))))
