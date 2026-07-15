"""Chapter 3, safety-first / shortfall figure: two tangent lines from two
y-axis thresholds (riskless rate R_f and a higher target return H) to the same
hyperbolic frontier. A higher goal -> a tangency further out = a riskier portfolio."""
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({'font.size':11,'font.family':'sans-serif','axes.labelsize':12,
    'axes.titlesize':13,'figure.dpi':150,'axes.spines.top':False,'axes.spines.right':False})
FIG='/Users/wng1/Dropbox/IMM/wng-yale/investment-theory/figures/'
pct=FuncFormatter(lambda x,_:f'{x:.0%}')

Rmv, s0, k = 0.05, 0.05, 7.41
def sig(R): return np.sqrt(s0**2 + k*(R-Rmv)**2)
def tangency(thr):
    Rt = Rmv + s0**2/(k*(Rmv-thr))   # requires thr < Rmv
    return sig(Rt), Rt

Rf, H = 0.02, 0.04
sM, RM = tangency(Rf)      # max-Sharpe tangency
sP, RP = tangency(H)       # safety-first tangency at higher goal

fig, ax = plt.subplots(figsize=(8,5.2))
R = np.linspace(Rmv, 0.15, 300)
ax.plot(sig(R), R, color='#00356b', lw=2.6, zorder=5, label='Efficient frontier')

xline = np.array([0, 0.30])
for thr, (st,Rt), col in [(Rf,(sM,RM),'#1a5276'), (H,(sP,RP),'#c0392b')]:
    slope = (Rt-thr)/st
    ax.plot(xline, thr+slope*xline, color=col, lw=1.6, ls='--', zorder=3)
    ax.scatter([st],[Rt], s=95, color=col, edgecolors='white', lw=1.6, zorder=6)

# threshold markers on the y-axis
ax.scatter([0],[Rf], s=75, marker='s', color='#d4ac0d', edgecolors='black', lw=0.6, zorder=7, clip_on=False)
ax.scatter([0],[H],  s=75, marker='s', color='#c0392b', edgecolors='black', lw=0.6, zorder=7, clip_on=False)
ax.annotate('riskless rate $R_f$', (0,Rf), xytext=(10,-14), textcoords='offset points', fontsize=10, color='#8a6d0a')
ax.annotate('target return $H$ (the goal)', (0,H), xytext=(10,9), textcoords='offset points', fontsize=10, color='#c0392b')

ax.annotate('max-Sharpe portfolio $M$', (sM,RM), xytext=(12,-16), textcoords='offset points',
            fontsize=10, color='#1a5276', fontweight='600', ha='left')
ax.annotate('higher-goal tangency', (sP,RP), xytext=(11,-3), textcoords='offset points',
            fontsize=10, color='#c0392b', fontweight='600', ha='left')

# arrow: higher goal -> riskier (arc above the points)
ax.annotate('', xy=(sP,RP), xytext=(sM,RM),
            arrowprops=dict(arrowstyle='->', color='#666', lw=1.4, connectionstyle='arc3,rad=0.28'))
ax.annotate('riskier', xy=(0.072,0.083), fontsize=10, color='#666', style='italic')

ax.set_xlabel('Standard deviation ($\\sigma$)'); ax.set_ylabel('Expected return')
ax.set_xlim(0,0.30); ax.set_ylim(0,0.15)
ax.xaxis.set_major_formatter(pct); ax.yaxis.set_major_formatter(pct)
ax.legend(loc='lower right', fontsize=9, frameon=True)
fig.tight_layout(); fig.savefig(FIG+'shortfall_tangency.svg', format='svg', bbox_inches='tight'); plt.close()
print("M=(%.3f,%.3f) slopeRf=%.2f | P_H=(%.3f,%.3f) slopeH=%.2f"%(sM,RM,(RM-Rf)/sM,sP,RP,(RP-H)/sP))
