from dataclasses import asdict
import pandas as pd
from .frontier import pareto_frontier, estimate_at_cutoff
def estimates(df, snapshot):
    rows=[]
    for (model, hardware), group in df.groupby(['model','hardware']):
        for metric in ['p90','median']:
            x='metrics.'+metric+'_intvty'
            front=pareto_frontier(group,x)
            for cutoff in [50,100,200]:
                r=dict(snapshot=snapshot,model=model,hardware=hardware,metric=metric,cutoff=cutoff,
                       **asdict(estimate_at_cutoff(group,front,x,cutoff)))
                for side in ['left','right']:
                    xx=r[side+'_x']
                    sel=front[front[x]==xx] if xx is not None else front.iloc[:0]
                    r[side+'_id']=int(sel.iloc[0]['id']) if len(sel) else None
                measured=group[group[x]>=cutoff].sort_values(['concurrency_per_gpu',x],ascending=False)
                r['measured_id']=int(measured.iloc[0].id) if len(measured) else None
                rows.append(r)
    return pd.DataFrame(rows)
