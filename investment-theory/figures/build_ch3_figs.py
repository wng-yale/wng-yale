"""Chapter 3 figures: iso-utility curves on a proper hyperbolic frontier (3.1),
and a smooth normal density with a VaR tail (3.2)."""
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from scipy import stats

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({'font.size':11,'font.family':'sans-serif','axes.labelsize':12,
    'axes.titlesize':13,'figure.dpi':150,'axes.spines.top':False,'axes.spines.right':False})
FIG='/Users/wng1/Dropbox/IMM/wng-yale/investment-theory/figures/'
pct=FuncFormatter(lambda x,_:f'{x:.0%}')

# ================= 3.1 ISO-UTILITY =================
# Hyperbolic frontier: sigma^2 = s0^2 + k (R - Rmv)^2  ; efficient branch R >= Rmv
Rmv, s0, k = 0.05, 0.05, 7.41
def sig(R): return np.sqrt(s0**2 + k*(R-Rmv)**2)
# Utility U = R - 0.5*lambda*sigma^2 ; on frontier optimum R* = Rmv + 1/(lambda*k)
def optimum(lam):
    Rs = Rmv + 1.0/(lam*k)
    return Rs, sig(Rs)
fig, ax = plt.subplots(figsize=(8,5))
R = np.linspace(Rmv, 0.15, 300)
ax.plot(sig(R), R, color='#00356b', lw=2.6, zorder=5, label='Efficient frontier')
# also draw the inefficient lower branch faintly for context
ax.plot(sig(R), 2*Rmv - R, color='#00356b', lw=1.0, ls=':', alpha=0.5, zorder=4)

sg = np.linspace(0, 0.30, 200)
for lam, col, name in [(5.4,'#c0392b','more risk-averse'), (2.1,'#1e8b3a','less risk-averse')]:
    Rs, ss = optimum(lam)
    Us = Rs - 0.5*lam*ss**2
    # tangent indifference curve (solid) and one lower-utility curve (dashed)
    for U, ls, a in [(Us,'-',1.0),(Us-0.018,'--',0.6)]:
        ax.plot(sg, U + 0.5*lam*sg**2, color=col, lw=1.5, ls=ls, alpha=a, zorder=3)
    ax.scatter([ss],[Rs], s=70, color=col, edgecolors='white', lw=1.5, zorder=6)
    ax.annotate(f'P*  ({name})', (ss,Rs), textcoords='offset points',
                xytext=(10,-4 if lam>3 else 8), fontsize=10, color=col, fontweight='600')

ax.annotate('higher utility', xy=(0.012,0.145), fontsize=10, color='#666')
ax.annotate('', xy=(0.01,0.15), xytext=(0.05,0.12),
            arrowprops=dict(arrowstyle='->',color='#999',lw=1))
ax.set_xlabel('Standard deviation ($\\sigma$)'); ax.set_ylabel('Expected return')
ax.set_xlim(0,0.30); ax.set_ylim(0,0.16)
ax.xaxis.set_major_formatter(pct); ax.yaxis.set_major_formatter(pct)
ax.legend(loc='lower right', fontsize=9, frameon=True)
fig.tight_layout(); fig.savefig(FIG+'iso_utility.svg', format='svg', bbox_inches='tight'); plt.close()
print("iso_utility.svg: P*_averse=(%.3f,%.3f)  P*_less=(%.3f,%.3f)"%(optimum(5.4)[1],optimum(5.4)[0],optimum(2.1)[1],optimum(2.1)[0]))

# ================= 3.2 VaR / NORMAL =================
mu, sd = 0.08, 0.15
z95 = stats.norm.ppf(0.05)          # -1.645
var = mu + z95*sd                    # 5% left-tail threshold
fig, ax = plt.subplots(figsize=(8,4.6))
x = np.linspace(mu-4*sd, mu+4*sd, 500)
y = stats.norm.pdf(x, mu, sd)
ax.plot(x, y, color='#00356b', lw=2.2)
xt = x[x<=var]
ax.fill_between(xt, stats.norm.pdf(xt,mu,sd), color='#c0392b', alpha=0.35)
ax.axvline(mu, color='#333', ls='--', lw=1)
ax.axvline(var, color='#c0392b', lw=1.6)
ax.annotate('mean = 8%', (mu, ax.get_ylim()[1]*0.96), fontsize=9, color='#333', ha='left')
ax.annotate('5% of outcomes', xy=(var-0.03, 0.35), fontsize=9.5, color='#c0392b', ha='right')
ax.annotate('$R_{VaR}$ = %.0f%%'%(var*100), xy=(var, -0.15), fontsize=10, color='#c0392b',
            ha='center', annotation_clip=False)
ax.set_xlabel('Portfolio return'); ax.set_ylabel('Probability density')
ax.set_ylim(0, None); ax.xaxis.set_major_formatter(pct)
fig.tight_layout(); fig.savefig(FIG+'var_diagram.svg', format='svg', bbox_inches='tight'); plt.close()
print("var_diagram.svg: VaR threshold = %.1f%%"%(var*100))
