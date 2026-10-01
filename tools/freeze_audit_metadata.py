"""One-time migration of nonidentifying audit references; takes explicit paths."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd

p=argparse.ArgumentParser()
p.add_argument('source',type=Path)
p.add_argument('destination',type=Path)
a=p.parse_args()
configs=pd.read_csv(a.source/'outputs/verified_configs.csv').sort_values('artifact').to_dict('records')
occupancy=pd.read_csv(a.source/'outputs/replay_occupancy.csv').sort_values('artifact').to_dict('records')
(a.destination/'agentx_audit.json').write_text(json.dumps(dict(configs=configs,occupancy=occupancy),indent=2)+'\n')
members={}
for folder in sorted((a.source/'data').glob('artifact_*')):
    for f in sorted(folder.rglob('*')):
        if f.name in ('profile_export_aiperf.json','profile_export.jsonl','benchmark.log'):
            h=hashlib.sha256()
            with f.open('rb') as source:
                for chunk in iter(lambda: source.read(8*1024*1024),b''):h.update(chunk)
            members[str(f.relative_to(a.source/'data'))]=h.hexdigest()
(a.destination/'agentx_members.json').write_text(json.dumps(members,indent=2)+'\n')
