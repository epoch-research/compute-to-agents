"""Source clocks and illustrative replay intensity, never GPU utilization."""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def main(output, inputs, prepared):
    OUT = output
    OUT.mkdir(parents=True, exist_ok=True)
    # Same pooled source groups as the report figure; do not change eligibility or cache definitions.
    groups=json.loads((inputs/'token_groups.json').read_text())
    rates=[];clock_sensitivity=[]
    for dataset in ['TraceLab','WEKA']:
        chosen=[r for r in groups if r['dataset']==dataset]
        for cap in [30,60,300]:
            hours=sum(r[f'hours_cap{cap}'] for r in chosen)
            method='retained' if dataset=='TraceLab' else 'ideal'
            tokens={m:sum(r['tokens'][method][m] for r in chosen) for m in ['input','cached_input','nonread_input','output']}
            rr=dict(dataset=dataset,cap_seconds=cap,groups=len(chosen),hours=hours,
                    **{m+'_per_hour':t/hours for m,t in tokens.items()})
            eligible=[r for r in chosen if r['hours_primary']>=5/60]
            rr['eligible_groups']=len(eligible)
            rr.update({m+'_median_per_hour':float(np.median([r['tokens'][method][m]/r[f'hours_cap{cap}'] for r in eligible])) for m in tokens})
            clock_sensitivity.append(rr)
            if cap==300:rates.append(dict(label=dataset+' adjusted source',kind='Source',**rr))
    snapshot=pd.read_csv(prepared)
    for bid,label in [(441062,'Kimi K3 · C=56 · disagg'),(441859,'Kimi K3 · C=48 · agg'),
                      (441858,'Kimi K3 · C=4 · agg'),(441596,'GLM 5.2 · C=227'),(441367,'DeepSeek V4 Pro · C=960')]:
        r=snapshot[snapshot.id==bid].iloc[0]
        rates.append(dict(label=label,kind='Replay',benchmark_id=bid,run_url=r.run_url,
            input_per_hour=r['metrics.input_tput_tps']*3600/r.conc,
            output_per_hour=r['metrics.output_tput_tps']*3600/r.conc))
    pd.DataFrame(rates).to_csv(OUT/'source_vs_replay_rates.csv',index=False)
    pd.DataFrame(clock_sensitivity).to_csv(OUT/'source_clock_sensitivity.csv',index=False)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(12,6.3),sharey=True)
    for ax,metric,scale,label in zip(axes,['input','output'],[1e6,1e3],['Million input tokens / hour','Thousand output tokens / hour']):
        for i,r in enumerate(rates):
            value=r[metric+'_per_hour']/scale
            ax.barh(i,value,color='#187F86' if r['kind']=='Source' else '#657DB6',height=.6)
            ax.text(value+.3,i,f'{value:.1f}',va='center',fontsize=10)
        ax.set_xlim(0,max(r[metric+'_per_hour']/scale for r in rates)*1.17)
        ax.set_xlabel(label);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    axes[0].set_yticks(range(len(rates)),[r['label'] for r in rates]);axes[0].invert_yaxis()
    fig.suptitle('Similar source traces do not imply identical replay intensity',fontsize=17,fontweight='bold',x=.03,ha='left')
    fig.text(.03,.905,'Source: tokens per adjusted group-hour. Replay: measured tokens per configured client-hour.',fontsize=11,color='#46556D')
    fig.text(.03,.035,'Both source analyses use five-minute gap caps. Replays also use a 10-second global idle guard.\nDifferent models, context mixtures, warmup and sampled starts: illustrative comparisons, not matched performance tests.',fontsize=9,color='#46556D')
    fig.subplots_adjust(left=.26,right=.97,top=.84,bottom=.17,wspace=.15)
    for ext in ['png','svg','pdf']:fig.savefig(OUT/f'source_vs_replay.{ext}',dpi=180)
    plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(12,5.1))
    for ax,metric,scale,title in zip(axes,['cached_input','nonread_input','output'],[1e6,1e3,1e3],['Cached input · M tokens/h','Non-read input · k tokens/h','Output · k tokens/h']):
        for dataset,color in [('TraceLab','#187F86'),('WEKA','#B64D76')]:
            rr=[r for r in clock_sensitivity if r['dataset']==dataset]
            xs=[r['cap_seconds'] for r in rr];ys=[r[metric+'_per_hour']/scale for r in rr]
            ax.plot(xs,ys,'o-',color=color,label=dataset,lw=2)
            for x,y in zip(xs,ys):
                above=(dataset=='WEKA')
                if x==300 and metric!='output':above=not above
                ax.annotate(f'{y:.1f}',(x,y),xytext=(0,7 if above else -15),textcoords='offset points',ha='center',color=color,fontsize=9)
        ax.set_title(title,loc='left',fontweight='bold');ax.set_xscale('log');ax.set_xticks([30,60,300],['30','60','300']);ax.set_xlim(23,400)
        ax.set_ylim(0,ax.get_ylim()[1]*1.13);ax.set_xlabel('Retained gap cap (seconds)');ax.grid(alpha=.15)
    axes[0].legend(frameon=False)
    fig.suptitle('Source-corpus agreement is sensitive to the gap definition',x=.04,ha='left',fontsize=17,fontweight='bold')
    fig.text(.04,.89,'Pooled tokens per adjusted hour · same tokens and retained-cache assumptions at every cap',color='#46556D',fontsize=11)
    fig.text(.04,.035,'TraceLab preserves known model/tool work and removes identified human waits. WEKA caps gaps between parent/child model calls.\nThese are alternative accounting scenarios, not claims that shorter waits are correct or equivalent replay schedules.',color='#46556D',fontsize=9)
    fig.subplots_adjust(left=.065,right=.97,top=.77,bottom=.22,wspace=.28)
    for ext in ['png','svg','pdf']:fig.savefig(OUT/f'gap_sensitivity.{ext}',dpi=180)
    plt.close(fig)
