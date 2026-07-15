import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({'font.size':12,'font.family':'sans-serif','axes.labelsize':14,'figure.dpi':150,'axes.spines.top':False,'axes.spines.right':False})
FIG='/Users/wng1/Dropbox/IMM/wng-yale/investment-theory/figures/'
si,rho=0.45,0.30
n=np.arange(1,31); port=si*np.sqrt(rho+(1-rho)/n); sysr=si*np.sqrt(rho)
fig,ax=plt.subplots(figsize=(8,5))
ax.plot(n,port,'o-',color='#00356b',lw=2.2,ms=4.5,label='Portfolio standard deviation')
ax.axhline(sysr,color='#bd5319',ls='--',lw=1.8)
ax.fill_between(n,sysr,port,alpha=0.14,color='#00356b')
ax.annotate('idiosyncratic risk\n(diversified away — the residual $e_i$)',xy=(15,(port[10]+sysr)/2+0.01),fontsize=12.5,ha='center',color='#00356b')
ax.annotate('systematic risk = beta risk\n(cannot be diversified away)',xy=(16,sysr-0.045),fontsize=12.5,ha='center',color='#bd5319')
ax.set_xlabel('Number of stocks in the portfolio'); ax.set_ylabel('Portfolio standard deviation')
ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:.0%}'))
ax.set_xlim(1,30); ax.set_ylim(0,0.5)
fig.tight_layout(); fig.savefig(FIG+'diversification_beta.svg',format='svg',bbox_inches='tight'); print("floor=%.1f%%"%(sysr*100))
