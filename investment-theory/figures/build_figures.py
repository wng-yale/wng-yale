"""
Build publication-quality figures for investment theory textbook
using SBBI 2024 historical returns data (1926-2024).
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
    'font.size': 11,
    'font.family': 'sans-serif',
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'figure.dpi': 150,
    'axes.spines.top': False,
    'axes.spines.right': False,
})

FIGDIR = '/Users/wng1/Dropbox/IMM/wng-yale/investment-theory/figures/'

# ── Load data ──────────────────────────────────────────────────────
df = pd.read_csv('/Users/wng1/Dropbox/History/SBBI2024.csv')
df['date'] = pd.to_datetime(df['date'], format='%m/%d/%y')
# Fix century for dates parsed as 2000s that should be 1900s
df.loc[df['date'].dt.year > 2050, 'date'] -= pd.DateOffset(years=100)
df = df.sort_values('date').reset_index(drop=True)

# Key columns
cols = {'LargeCap': 'Large Cap Stocks', 'Small': 'Small Stocks',
        'LTC': 'LT Corp Bonds', 'LTG': 'LT Gov Bonds',
        'TB30': 'T-Bills', 'INF': 'Inflation'}

for c in cols:
    df[c] = pd.to_numeric(df[c], errors='coerce')

# ── Compute annual returns ─────────────────────────────────────────
df['year'] = df['date'].dt.year
annual = df.groupby('year').apply(
    lambda g: pd.Series({c: (1 + g[c]).prod() - 1 for c in cols}),
    include_groups=False
)
# Drop first and last year if incomplete
first_yr, last_yr = df['year'].min(), df['year'].max()
if len(df[df['year'] == first_yr]) < 12:
    annual = annual.drop(first_yr, errors='ignore')
if len(df[df['year'] == last_yr]) < 12:
    annual = annual.drop(last_yr, errors='ignore')

# ================================================================
# 1. WEALTH GROWTH (log scale)
# ================================================================
print("Building wealth_growth.svg ...")
fig, ax = plt.subplots(figsize=(8, 5))

wealth_cols = ['LargeCap', 'Small', 'LTG', 'TB30', 'INF']
colors_w = {'LargeCap': '#1f77b4', 'Small': '#17becf',
            'LTG': '#ff7f0e', 'TB30': '#7f7f7f', 'INF': '#d62728'}
labels_w = {'LargeCap': 'Large Cap Stocks', 'Small': 'Small Stocks',
            'LTG': 'LT Gov Bonds', 'TB30': 'T-Bills', 'INF': 'Inflation'}

for c in wealth_cols:
    wealth = (1 + df[c]).cumprod()
    ax.plot(df['date'], wealth, label=labels_w[c], color=colors_w[c],
            linewidth=1.4 if c in ['LargeCap', 'Small'] else 1.0)

ax.set_yscale('log')
ax.set_ylabel('Growth of $1 (log scale)')
ax.set_xlabel('')
ax.set_title('Growth of $1 Invested in 1926')
ax.legend(loc='upper left', frameon=True, framealpha=0.9, fontsize=10)
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'${x:,.0f}' if x >= 1 else f'${x:.2f}'))
ax.set_xlim(df['date'].min(), df['date'].max())
fig.tight_layout()
fig.savefig(FIGDIR + 'wealth_growth.svg', format='svg', bbox_inches='tight')
plt.close()

# ================================================================
# 2. RETURN DISTRIBUTION
# ================================================================
print("Building return_distribution.svg ...")
fig, ax = plt.subplots(figsize=(8, 5))

ret = annual['LargeCap'].dropna().values
mu, sigma = ret.mean(), ret.std()

ax.hist(ret, bins=25, density=True, color='#1f77b4', alpha=0.65,
        edgecolor='white', linewidth=0.5, label='Observed')

x = np.linspace(ret.min() - 0.05, ret.max() + 0.05, 200)
ax.plot(x, stats.norm.pdf(x, mu, sigma), 'r-', linewidth=1.8,
        label=f'Normal ($\\mu$={mu:.1%}, $\\sigma$={sigma:.1%})')

ax.axvline(mu, color='#333333', linestyle='--', linewidth=1, label=f'Mean = {mu:.1%}')
ax.axvline(mu - sigma, color='#999999', linestyle=':', linewidth=1, label=f'$\\pm$1 s.d.')
ax.axvline(mu + sigma, color='#999999', linestyle=':', linewidth=1)

ax.set_xlabel('Annual Return')
ax.set_ylabel('Density')
ax.set_title('Distribution of Annual Large-Cap Stock Returns (1926–2023)')
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))
ax.legend(fontsize=9, frameon=True)
fig.tight_layout()
fig.savefig(FIGDIR + 'return_distribution.svg', format='svg', bbox_inches='tight')
plt.close()

# ================================================================
# EFFICIENT FRONTIER HELPERS
# ================================================================
# Use 5 risky asset classes for the frontier
asset_cols = ['LargeCap', 'Small', 'LTC', 'LTG', 'TB30']
asset_labels = ['Large Cap', 'Small Cap', 'LT Corp', 'LT Gov', 'T-Bills']
ann_ret = annual[asset_cols].dropna()
mu_vec = ann_ret.mean().values
cov_mat = ann_ret.cov().values
n_assets = len(asset_cols)
rf = ann_ret['TB30'].mean()  # risk-free rate

def portfolio_stats(w):
    ret = w @ mu_vec
    vol = np.sqrt(w @ cov_mat @ w)
    return ret, vol

def neg_sharpe(w):
    r, v = portfolio_stats(w)
    return -(r - rf) / v

def min_var_obj(w):
    return w @ cov_mat @ w

bounds = tuple((0, 1) for _ in range(n_assets))
constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
w0 = np.ones(n_assets) / n_assets

# Minimum variance portfolio
res_mv = optimize.minimize(min_var_obj, w0, method='SLSQP',
                           bounds=bounds, constraints=constraints)
mv_ret, mv_vol = portfolio_stats(res_mv.x)

# Tangency portfolio
res_tan = optimize.minimize(neg_sharpe, w0, method='SLSQP',
                            bounds=bounds, constraints=constraints)
tan_ret, tan_vol = portfolio_stats(res_tan.x)

# Frontier points
target_rets = np.linspace(mv_ret, mu_vec.max(), 80)
frontier_vols = []
for tr in target_rets:
    cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
            {'type': 'eq', 'fun': lambda w, t=tr: w @ mu_vec - t}]
    res = optimize.minimize(min_var_obj, res_mv.x, method='SLSQP',
                            bounds=bounds, constraints=cons)
    frontier_vols.append(np.sqrt(res.fun))
frontier_vols = np.array(frontier_vols)

asset_vols = np.sqrt(np.diag(cov_mat))
asset_rets = mu_vec

# ================================================================
# 3. EFFICIENT FRONTIER
# ================================================================
print("Building efficient_frontier.svg ...")
fig, ax = plt.subplots(figsize=(8, 5))

ax.plot(frontier_vols, target_rets, 'b-', linewidth=2, label='Efficient Frontier')

asset_colors = ['#1f77b4', '#17becf', '#ff7f0e', '#2ca02c', '#7f7f7f']
for i, lab in enumerate(asset_labels):
    ax.scatter(asset_vols[i], asset_rets[i], s=60, color=asset_colors[i],
               zorder=5, edgecolors='black', linewidth=0.5)
    offset = (8, 6) if lab != 'T-Bills' else (8, -10)
    ax.annotate(lab, (asset_vols[i], asset_rets[i]),
                textcoords='offset points', xytext=offset, fontsize=9)

ax.scatter(mv_vol, mv_ret, s=90, color='green', marker='D', zorder=6,
           edgecolors='black', linewidth=0.5, label='Min Variance')
ax.scatter(tan_vol, tan_ret, s=90, color='red', marker='*', zorder=6,
           edgecolors='black', linewidth=0.5, label='Tangency Portfolio')

ax.set_xlabel('Annual Standard Deviation')
ax.set_ylabel('Annual Mean Return')
ax.set_title('Mean-Variance Efficient Frontier (1926–2023)')
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))
ax.legend(fontsize=9, loc='lower right', frameon=True)
fig.tight_layout()
fig.savefig(FIGDIR + 'efficient_frontier.svg', format='svg', bbox_inches='tight')
plt.close()

# ================================================================
# 4. CAPITAL MARKET LINE
# ================================================================
print("Building capital_market_line.svg ...")
fig, ax = plt.subplots(figsize=(8, 5))

ax.plot(frontier_vols, target_rets, 'b-', linewidth=2, label='Efficient Frontier')

# CML
cml_x = np.linspace(0, frontier_vols.max() * 1.1, 100)
sharpe = (tan_ret - rf) / tan_vol
cml_y = rf + sharpe * cml_x
ax.plot(cml_x, cml_y, 'r--', linewidth=1.5, label='Capital Market Line')

for i, lab in enumerate(asset_labels):
    ax.scatter(asset_vols[i], asset_rets[i], s=60, color=asset_colors[i],
               zorder=5, edgecolors='black', linewidth=0.5)
    offset = (8, 6) if lab != 'T-Bills' else (8, -10)
    ax.annotate(lab, (asset_vols[i], asset_rets[i]),
                textcoords='offset points', xytext=offset, fontsize=9)

ax.scatter(0, rf, s=70, color='gold', marker='s', zorder=6,
           edgecolors='black', linewidth=0.5, label=f'Risk-Free ({rf:.1%})')
ax.scatter(tan_vol, tan_ret, s=90, color='red', marker='*', zorder=6,
           edgecolors='black', linewidth=0.5, label='Tangency Portfolio')

ax.set_xlabel('Annual Standard Deviation')
ax.set_ylabel('Annual Mean Return')
ax.set_title('Capital Market Line (1926–2023)')
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))
ax.set_xlim(-0.01, frontier_vols.max() * 1.15)
ax.set_ylim(rf - 0.02, target_rets.max() * 1.1)
ax.legend(fontsize=9, loc='lower right', frameon=True)
fig.tight_layout()
fig.savefig(FIGDIR + 'capital_market_line.svg', format='svg', bbox_inches='tight')
plt.close()

# ================================================================
# 5. CORRELATION MATRIX
# ================================================================
print("Building correlation_matrix.svg ...")
fig, ax = plt.subplots(figsize=(7, 7))

corr = ann_ret[asset_cols].corr()
corr.columns = asset_labels
corr.index = asset_labels

im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='equal')

ax.set_xticks(range(n_assets))
ax.set_xticklabels(asset_labels, rotation=45, ha='right', fontsize=10)
ax.set_yticks(range(n_assets))
ax.set_yticklabels(asset_labels, fontsize=10)

for i in range(n_assets):
    for j in range(n_assets):
        color = 'white' if abs(corr.values[i, j]) > 0.6 else 'black'
        ax.text(j, i, f'{corr.values[i, j]:.2f}', ha='center', va='center',
                fontsize=11, color=color, fontweight='bold')

ax.set_title('Asset Class Correlation Matrix (1926–2023)')
cbar = fig.colorbar(im, ax=ax, shrink=0.8, label='Correlation')
fig.tight_layout()
fig.savefig(FIGDIR + 'correlation_matrix.svg', format='svg', bbox_inches='tight')
plt.close()

# ================================================================
# 6. BETA SCATTER / SML
# ================================================================
print("Building beta_scatter.svg ...")
fig, ax = plt.subplots(figsize=(8, 5))

# Market = Large Cap, use representative sectors/styles
# Using realistic beta/return pairs for illustration
np.random.seed(42)
sectors = {
    'Utilities': (0.55, 0.095),
    'Consumer Staples': (0.65, 0.105),
    'Healthcare': (0.75, 0.115),
    'Financials': (1.05, 0.125),
    'Industrials': (1.10, 0.130),
    'Technology': (1.25, 0.145),
    'Energy': (1.15, 0.120),
    'Consumer Disc.': (1.10, 0.128),
    'Materials': (0.95, 0.112),
    'Real Estate': (0.80, 0.105),
    'Small Value': (1.30, 0.155),
    'Small Growth': (1.40, 0.135),
}

mkt_ret = annual['LargeCap'].mean()
mkt_premium = mkt_ret - rf

# SML
beta_range = np.linspace(0, 1.8, 100)
sml = rf + mkt_premium * beta_range
ax.plot(beta_range, sml, 'r-', linewidth=1.8, label='Security Market Line')

for name, (beta, ret) in sectors.items():
    ax.scatter(beta, ret, s=50, color='#1f77b4', zorder=5,
               edgecolors='black', linewidth=0.4)
    ax.annotate(name, (beta, ret), textcoords='offset points',
                xytext=(6, 4), fontsize=8)

ax.scatter(1.0, mkt_ret, s=80, color='red', marker='D', zorder=6,
           edgecolors='black', linewidth=0.5, label=f'Market ($\\beta$=1)')
ax.scatter(0, rf, s=70, color='gold', marker='s', zorder=6,
           edgecolors='black', linewidth=0.5, label=f'Risk-Free ({rf:.1%})')

ax.set_xlabel('Beta ($\\beta$)')
ax.set_ylabel('Expected Return')
ax.set_title('Security Market Line')
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))
ax.legend(fontsize=9, loc='lower right', frameon=True)
ax.set_xlim(-0.05, 1.8)
fig.tight_layout()
fig.savefig(FIGDIR + 'beta_scatter.svg', format='svg', bbox_inches='tight')
plt.close()

# ================================================================
# 7. DIVERSIFICATION BENEFIT
# ================================================================
print("Building diversification_benefit.svg ...")
fig, ax = plt.subplots(figsize=(8, 5))

# Use realistic parameters from large-cap data
# Average stock std dev ~ 40-50%, average correlation ~ 0.3
sigma_i = 0.45  # average individual stock volatility
rho = 0.30      # average pairwise correlation

n_stocks = np.arange(1, 31)
# Portfolio variance = sigma^2 * [rho + (1-rho)/n]
port_vol = sigma_i * np.sqrt(rho + (1 - rho) / n_stocks)
systematic_vol = sigma_i * np.sqrt(rho)

ax.plot(n_stocks, port_vol, 'b-', linewidth=2, marker='o', markersize=4,
        label='Portfolio Std. Dev.')
ax.axhline(systematic_vol, color='red', linestyle='--', linewidth=1.2,
           label=f'Systematic Risk ({systematic_vol:.1%})')
ax.fill_between(n_stocks, systematic_vol, port_vol, alpha=0.15, color='blue')

ax.annotate('Diversifiable\n(Unsystematic)\nRisk', xy=(15, (port_vol[14] + systematic_vol) / 2),
            fontsize=10, ha='center', color='#1f77b4')
ax.annotate('Systematic\n(Market) Risk', xy=(15, systematic_vol - 0.02),
            fontsize=10, ha='center', color='red')

ax.set_xlabel('Number of Stocks in Portfolio')
ax.set_ylabel('Portfolio Standard Deviation')
ax.set_title('Diversification and Portfolio Risk')
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))
ax.set_xlim(1, 30)
ax.set_ylim(0, 0.50)
ax.legend(fontsize=9, loc='upper right', frameon=True)
fig.tight_layout()
fig.savefig(FIGDIR + 'diversification_benefit.svg', format='svg', bbox_inches='tight')
plt.close()

print("All figures saved.")
