"""Reproducible figure and economic-table inputs for the second native Doc tab."""
from pathlib import Path
import sys, json, os
import numpy as np
import pandas as pd
from .paths import DATA as INPUTS
from . import estimates as r
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from types import SimpleNamespace
CONFIG = json.loads((INPUTS / 'figure_config.json').read_text())
r.CONFIG = CONFIG
r.LABELS = dict(CONFIG['model_labels'], dsv41flash='DeepSeek V4.1 Flash')
OUT = None
DATA = None
MODELS=r.CONFIG['model_order']+['dsv41flash']
HARDWARE=r.CONFIG['hardware_order']
LABELS=dict(r.LABELS)
LABELS['qwen3.5']='Qwen 3.5 397B';LABELS['qwen3.8next']='Qwen 3.8 Flash Next'
ASSUMPTIONS = json.loads((INPUTS / "assumptions.json").read_text())
RENT = ASSUMPTIONS["rent_per_gpu_hour"]
PRICES = ASSUMPTIONS["open_model_prices"]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','text.parse_math':False})
TEAL='#087F8C';BLUE='#3158A5';INK='#203448'

def save(fig,name):
    for ext in ('png','svg','pdf'):fig.savefig(OUT/f'{name}.{ext}',dpi=220,facecolor='white')
    plt.close(fig)

def frontiers(metric,name):
    fig,axes=plt.subplots(4,2,figsize=(10,12),sharex=True,sharey=True)
    x='metrics.'+metric+'_intvty'
    for ax,m in zip(axes.flat,MODELS):
        for h in HARDWARE:
            g=DATA[(DATA.model==m)&(DATA.hardware==h)]
            if g.empty:continue
            c=r.CONFIG['hardware_colors'][h]; f=r.pareto_frontier(g,x)
            ax.scatter(g[x],g.concurrency_per_gpu,s=7,alpha=.12,color=c)
            ax.plot(f[x],f.concurrency_per_gpu,color=c,lw=1.8,marker='o',ms=3,label=h.upper())
        ax.set_title(LABELS[m],loc='left',fontsize=13,fontweight='bold')
        ax.set_yscale('log');ax.set_xscale('log');ax.set_xlim(1,1000);ax.set_ylim(.025,100)
        ax.set_xticks([10,50,100,200,1000],['10','50','100','200','1k'])
        ax.set_yticks([.1,1,10,100],['0.1','1','10','100']);ax.grid(alpha=.15)
        for cut in [50,100]:ax.axvline(cut,color='#8A95A2',ls=':',lw=.8,zorder=0)
    axes[-1,-1].axis('off')
    from matplotlib.lines import Line2D
    axes[-1,-1].legend([Line2D([],[],color=r.CONFIG['hardware_colors'][h],lw=2) for h in HARDWARE],[h.upper() for h in HARDWARE],loc='center',ncol=2,frameon=False)
    for ax in axes[:,0]:ax.set_ylabel('Concurrent sessions / GPU')
    for ax in [axes[-1,0],axes[-2,1]]:ax.set_xlabel(f'{metric.upper() if metric=="p90" else "Median"} output TPS/user')
    fig.suptitle('Speed versus concurrent agent sessions',x=.08,ha='left',fontsize=20,fontweight='bold',y=.985)
    fig.text(.08,.95,'Published configuration envelopes · logarithmic axes · vertical guides: 50 / 100 TPS',fontsize=11,color=INK)
    fig.text(.08,.025,'Streaming speed excludes time to first token. Lines may connect different serving deployments.',fontsize=10,color=INK)
    fig.subplots_adjust(left=.10,right=.98,top=.91,bottom=.08,hspace=.4,wspace=.18)
    save(fig,name)

def matrix(cutoffs,name):
    est=r.estimates(DATA,'latest');sel=est[est.metric=='p90']
    hw=[h for h in HARDWARE if sel[(sel.hardware==h)&sel.cutoff.isin(cutoffs)&sel.model.isin(MODELS)].estimate.notna().any()]
    fig,axes=plt.subplots(len(cutoffs),1,figsize=(10,3.7*len(cutoffs)+1.5),squeeze=False)
    norm=LogNorm(.05,40);cmap=plt.get_cmap('YlGnBu').copy();cmap.set_bad('#F0F2F5')
    for ax,cut in zip(axes[:,0],cutoffs):
        mat=np.full((len(MODELS),len(hw)),np.nan); marks={}
        for i,m in enumerate(MODELS):
            for j,h in enumerate(hw):
                row=sel[(sel.model==m)&(sel.hardware==h)&(sel.cutoff==cut)]
                if len(row):
                    mat[i,j]=row.iloc[0].estimate
                    marks[i,j]='*' if row.iloc[0]['method']=='maximum_measured_frontier_starts_above_cutoff' else ''
        ax.imshow(mat,cmap=cmap,norm=norm,aspect='auto')
        for (i,j),v in np.ndenumerate(mat):
            ax.text(j,i,f'{v:.3g}'+marks.get((i,j),'') if np.isfinite(v) else '—',ha='center',va='center',fontsize=12,color='white' if np.isfinite(v) and norm(v)>.58 else INK)
        ax.set_xticks(range(len(hw)),[h.upper() for h in hw],fontsize=11)
        ax.set_yticks(range(len(MODELS)),[LABELS[m] for m in MODELS],fontsize=11)
        ax.set_title(f'P90 streaming speed ≥ {cut} TPS/user',loc='left',fontweight='bold',pad=12)
        ax.tick_params(length=0);ax.spines[:].set_visible(False)
        ax.set_xticks(np.arange(-.5,len(hw),1),minor=True);ax.set_yticks(np.arange(-.5,len(MODELS),1),minor=True)
        ax.grid(which='minor',color='white',lw=2);ax.tick_params(which='minor',length=0)
    fig.suptitle('Concurrent agent sessions per GPU',x=.04,ha='left',fontsize=20,fontweight='bold',y=.985)
    fig.text(.04,.90 if len(cutoffs)==1 else .925,'Linear interpolation of the published configuration envelopes',fontsize=12,color=INK)
    fig.text(.04,.065,'* Highest observed concurrency: sweep stays above target. — No qualifying point / no coverage.',fontsize=10,color=INK)
    fig.text(.04,.038,'Models are not quality-equivalent. Physical GPU counts include both prefill and decode pools.',fontsize=10,color=INK)
    fig.text(.04,.013,'VR200 held out pending comparability review. Hardware with no qualifying cells is omitted.',fontsize=10,color=INK)
    fig.subplots_adjust(left=.29,right=.98,top=.78 if len(cutoffs)==1 else .85,bottom=.14,hspace=.42)
    save(fig,name)

def economic_rows(df,snapshot):
    results=[]
    for tier,(model,pi,pc,po) in PRICES.items():
        for cut in [50,100]:
            for h,rent in RENT.items():
                g=df[(df.model==model)&(df.hardware==h)].copy()
                if g.empty:continue
                x='metrics.p90_intvty';f=r.pareto_frontier(g,x);e=r.estimate_at_cutoff(g,f,x,cut)
                if e.estimate is None:continue
                # Compute per-GPU billing at actual endpoints, then interpolate billing
                # at the same x weight used for the concurrency envelope.
                def bill(row):
                    row=g[g.id==row.id].iloc[0]
                    cache=row['metrics.theoretical_cache_hit_rate']
                    inp=row['input_token_throughput_per_chip'];out=row['output_token_throughput_per_chip']
                    return 3600/1e6*(inp*((1-cache)*pi+cache*pc)+out*po)
                right=f[f[x]==e.right_x].iloc[0]
                left=f[f[x]==e.left_x].iloc[0] if e.left_x is not None else right
                w=0 if e.left_x is None or e.left_x==e.right_x else (cut-e.left_x)/(e.right_x-e.left_x)
                revenue=bill(left)*(1-w)+bill(right)*w
                meas=g[g[x]>=cut].sort_values('concurrency_per_gpu',ascending=False).iloc[0]
                results.append(dict(snapshot=snapshot,tier=tier,model=model,cutoff=cut,hardware=h,c=e.estimate,
                    rent_per_gpu_hour=rent,rent_per_session_hour=rent/e.estimate,
                    revenue_per_gpu_hour=revenue,K=revenue/rent,left_id=int(left.id),right_id=int(right.id),weight=w,
                    measured_c=e.measured,measured_id=int(meas.id),measured_K=bill(meas)/rent,
                    measured_rent_per_session_hour=rent/e.measured))
    return pd.DataFrame(results)

def economics():
    rows=economic_rows(DATA,'latest')
    rows.to_csv(OUT/'economic_candidates.csv',index=False)
    selected=rows.sort_values('rent_per_session_hour').groupby(['snapshot','tier','cutoff'],as_index=False).first()
    selected.to_csv(OUT/'economic_selected.csv',index=False)
    print(selected[['snapshot','tier','cutoff','hardware','K','c']].to_string(index=False))
    (OUT/'pricing_assumptions.json').write_text(json.dumps({'prices_per_million_input_cached_output':PRICES,'rental_usd_per_gpu_hour':RENT,
        'sources':['https://api-docs.deepseek.com/quick_start/pricing/','https://docs.z.ai/guides/overview/pricing','https://platform.kimi.ai/','https://platform.minimax.io/docs/guides/pricing-paygo','https://github.com/SemiAnalysisAI/InferenceX-app/blob/master/packages/constants/src/gpu-keys.ts'],
        'note':'Current pricing applied to both snapshots for a like-priced benchmark comparison; MiniMax uses <=512k standard lower tariff. VR200 excluded.'},indent=2))

H3 = {int(y): v for y, v in ASSUMPTIONS["cumulative_hbm3e_billion_gb"].items()}
H4 = {int(y): v for y, v in ASSUMPTIONS["cumulative_hbm4_billion_gb"].items()}
def capacity(year,S=30,K=5,u=2,c=None):
    return (H3[year]+u*H4[year])*1e3/288*(5*K/S if c is None else c)

def projections():
    rows=[dict(year=y,u=u,K=k,S=s,capacity_millions=capacity(y,s,k,u)) for y in [2026,2027] for u in [1,2,4] for k in [5,10,20,40] for s in [10,20,30,50,75,100]]
    pd.DataFrame(rows).to_csv(OUT/'capacity_scenarios.csv',index=False)
    fig,ax=plt.subplots(figsize=(9,4.5))
    for pos,y in enumerate([2026,2027]):
        lo,hi=capacity(y,u=1),capacity(y,K=10,u=4);cl,ch=capacity(y),capacity(y,K=10)
        ax.plot([lo,hi],[pos,pos],color='#D6E5EB',lw=20,solid_capstyle='butt')
        ax.plot([cl,ch],[pos,pos],color=TEAL,lw=10,solid_capstyle='butt')
        ax.text((cl+ch)/2,pos+.17,f'{cl:.0f}–{ch:.0f} million',ha='center',color=TEAL,fontweight='bold',fontsize=13)
        ax.text(hi+3,pos,f'{lo:.0f}–{hi:.0f}',va='center',fontsize=11,color='#647785')
    ax.set_yticks([0,1],['Supply through 2026','Supply through 2027']);ax.invert_yaxis();ax.set_ylim(1.5,-.55)
    ax.set_xlim(0,210);ax.set_xlabel('Potential concurrent agent sessions (millions)');ax.grid(axis='x',alpha=.15);ax.spines[['left','top','right']].set_visible(False)
    ax.tick_params(axis='y',length=0)
    from matplotlib.lines import Line2D
    ax.legend([Line2D([],[],color=TEAL,lw=7),Line2D([],[],color='#D6E5EB',lw=10)],['Central uplift: u = 2×','Broader uplift: u = 1–4×'],loc='lower right',frameon=False,fontsize=10)
    fig.suptitle('How much continuous agent capacity?',x=.04,ha='left',fontsize=20,fontweight='bold')
    fig.text(.04,.88,'$30/session-hour · K = 5–10× · $5/GB300-hour · full allocation (f = 100%)',fontsize=11,color=INK)
    fig.text(.04,.025,'Scenario envelopes, not confidence intervals or forecasts of agents online at year-end.',fontsize=10,color=INK)
    fig.subplots_adjust(left=.24,right=.98,top=.8,bottom=.2);save(fig,'figure_5_capacity_envelope')
    fig,axes=plt.subplots(1,2,figsize=(10,4.9),sharey=True)
    s=np.linspace(10,100,181)
    pd.DataFrame([dict(year=y,hourly_cost=float(v),
        outer_low=capacity(y,v,u=1),outer_high=capacity(y,v,K=10,u=4),
        central_low=capacity(y,v),central_high=capacity(y,v,K=10))
        for y in (2026,2027) for v in s]).to_csv(OUT/'cost_sensitivity_curve.csv',index=False)
    for ax,y in zip(axes,[2026,2027]):
        ax.fill_between(s,capacity(y,s,u=1),capacity(y,s,K=10,u=4),color='#D6E5EB',label='u = 1–4×')
        ax.fill_between(s,capacity(y,s),capacity(y,s,K=10),color=TEAL,alpha=.75,label='u = 2×')
        ax.axvline(30,color=INK,ls='--',lw=1);ax.text(32,400,'$30 reference',fontsize=10)
        ax.set_title(f'Supply through {y}',loc='left',fontweight='bold');ax.set_yscale('log');ax.set_xlim(10,100);ax.set_ylim(4,600)
        ax.set_xticks([10,30,50,75,100],['$10','$30','$50','$75','$100']);ax.set_yticks([5,10,25,50,100,250,500],['5','10','25','50','100','250','500'])
        ax.grid(axis='y',alpha=.15);ax.set_xlabel('API-equivalent cost / session-hour')
    axes[0].set_ylabel('Potential concurrent sessions (millions)');axes[1].legend(frameon=False,loc='lower left',fontsize=10)
    fig.suptitle('Hourly workload cost changes the capacity estimate',x=.06,ha='left',fontsize=19,fontweight='bold')
    fig.text(.06,.875,'K stays within 5–10×; G = $5/GPU-hour and allocation f = 100%.',fontsize=11,color=INK)
    fig.text(.06,.025,'Not the effect of an API price rise alone: a pure repricing changes both S and K, not physical capacity.',fontsize=10,color=INK)
    fig.subplots_adjust(left=.10,right=.98,top=.78,bottom=.19,wspace=.15);save(fig,'figure_6_cost_sensitivity')
    cuts=r.estimates(DATA, 'latest')
    g=cuts[(cuts.snapshot=='latest')&(cuts.model=='dsv4')&(cuts.hardware=='gb300')&(cuts.metric=='p90')].set_index('cutoff')
    fig,axes=plt.subplots(1,2,figsize=(9,4.1),sharex=True,sharey=True);openrows=[]
    for ax,y in zip(axes,[2026,2027]):
        for pos,cut in enumerate([50,100]):
            c=g.loc[cut,'estimate'];lo=capacity(y,u=1,c=c);hi=capacity(y,u=4,c=c);central=capacity(y,u=2,c=c)
            ax.plot([lo,hi],[pos,pos],color=BLUE,lw=7);ax.plot(central,pos,'o',color='white',mec=BLUE,ms=8)
            ax.text((lo+hi)/2,pos+.22,f'{lo:,.0f}–{hi:,.0f}',ha='center',fontsize=11)
            openrows.append(dict(year=y,cutoff=cut,c=c,low_millions=lo,central_millions=central,high_millions=hi))
        ax.set_title(f'Supply through {y}',loc='left',fontweight='bold');ax.set_yticks([0,1],['50 TPS/user','100 TPS/user']);ax.set_ylim(1.5,-.5);ax.set_xlim(0,3500);ax.grid(axis='x',alpha=.15);ax.set_xlabel('Concurrent sessions (millions)')
    fig.suptitle('Separate benchmark scenario: DeepSeek V4 Pro',x=.05,ha='left',fontsize=18,fontweight='bold')
    fig.text(.05,.025,'Range: u = 1–4×; white marker: u = 2×. No K assumption. Not capability-equivalent to closed models.',fontsize=10,color=INK)
    fig.subplots_adjust(left=.15,right=.97,top=.78,bottom=.22,wspace=.15);save(fig,'figure_7_deepseek_sensitivity')
    pd.DataFrame(openrows).to_csv(OUT/'deepseek_capacity_scenarios.csv',index=False)

def main(output, prepared):
    global OUT, DATA
    plt.rcdefaults()
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','text.parse_math':False})
    OUT = output
    OUT.mkdir(parents=True, exist_ok=True)
    DATA = pd.read_csv(prepared)
    economics()
    projections()
    frontiers('p90', 'figure_1_p90_frontiers')
    frontiers('median', 'figure_a1_median_frontiers')
    matrix([50,100], 'figure_2_capacity_matrix')
    matrix([200], 'figure_a2_200tps')
    r.estimates(DATA, 'latest').to_csv(OUT / 'all_cutoff_estimates.csv', index=False)
