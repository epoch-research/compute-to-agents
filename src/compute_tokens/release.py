"""Allowlisted, checksummed local packaging. Never uploads or commits files."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile
from .paths import ROOT

FILES = {'README.md','LICENSE','NOTICE','CITATION.md','.gitignore','pyproject.toml',
         'requirements.lock','report_manifest.json','release_status.json','release_manifest.json',
         'polished_figures/README.md','current_report_manifest.json'}
DIRS = {'src','data','reference','docs','licenses','tests','tools','.github'}
PATTERNS = {
    'private workspace path': re.compile(r'/(?:home|Users)/[A-Za-z0-9_.-]+/'),
    'private document': re.compile(r'docs\.google\.com/document/d/'),
    'provider key': re.compile(r'\bsk-(?:(?:proj-|ant-)[A-Za-z0-9_-]{24,}|[A-Za-z0-9]{32,})'),
    'github token': re.compile(r'\bgh[pousr]_[A-Za-z0-9]{25,}'),
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'signed URL': re.compile(r'(?i)(?:X-Amz-Signature|X-Goog-Signature|sig)=[A-Za-z0-9%+/]{20,}')}


def paths(root=ROOT):
    result=[]
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root)
        if rel.parts[0] not in DIRS and str(rel) not in FILES: continue
        if '__pycache__' in rel.parts or any(x.endswith('.egg-info') for x in rel.parts):continue
        if p.is_symlink():raise ValueError(f'Symlink in release allowlist: {rel}')
        if p.is_file():result.append(p)
    return result


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def scan(root=ROOT):
    failures=[]
    for p in paths(root):
        raw=p.read_bytes()
        if p.suffix=='.gz':raw=gzip.decompress(raw)
        if p.suffix=='.png':continue
        text=raw.decode('utf-8',errors='replace')
        for name,pattern in PATTERNS.items():
            if pattern.search(text):failures.append(f'{p.relative_to(root)}: {name}')
    # Row-level quick inputs are restricted to numeric accounting metadata.
    forbidden={'user','session_id','contributor_index','group_index','prompt','hashes','messages','tool_input'}
    def check_keys(value):
        if isinstance(value,dict):
            if set(value)&forbidden:raise ValueError('Identifying fields in quick inputs')
            for v in value.values():check_keys(v)
        elif isinstance(value,list):
            for v in value:check_keys(v)
    for name in ('cost_groups','token_groups'):
        check_keys(json.loads((root/'data'/f'{name}.json').read_text()))
    if failures:raise ValueError('\n'.join(failures))
    return len(paths(root))


def seal():
    scan()
    entries={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=digest(p))
             for p in paths() if p.name!='release_manifest.json'}
    (ROOT/'release_manifest.json').write_text(json.dumps(dict(files=entries),indent=2,sort_keys=True)+'\n')


def check():
    count=scan()
    expected=json.loads((ROOT/'release_manifest.json').read_text())['files']
    actual={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=digest(p))
            for p in paths() if p.name!='release_manifest.json'}
    if expected!=actual:raise ValueError('Release manifest changed; review changes before explicitly resealing.')
    # New repository starts without history. If commits are later added, scan
    # every reachable historical blob too, not just the working tree.
    if (ROOT/'.git').exists():
        refs=subprocess.run(['git','rev-list','--objects','--all'],cwd=ROOT,capture_output=True,text=True,check=True).stdout
        for line in refs.splitlines():
            oid=line.split(' ',1)[0]
            typ=subprocess.run(['git','cat-file','-t',oid],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
            if typ!='blob':continue
            raw=subprocess.run(['git','cat-file','-p',oid],cwd=ROOT,capture_output=True,check=True).stdout
            if raw.startswith(b'\x1f\x8b'):raw=gzip.decompress(raw)
            if raw.startswith(b'\x89PNG'):continue
            text=raw.decode('utf-8',errors='replace')
            if any(pattern.search(text) for pattern in PATTERNS.values()):
                raise ValueError(f'Sensitive historical content detected in blob {oid}; do not publish')
    return count


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true')
    p.add_argument('--seal',action='store_true',help='Explicitly regenerate reviewed file checksums')
    p.add_argument('--archive',action='store_true')
    p.add_argument('--public',action='store_true',help='Require all public-release gates cleared; does not publish')
    a=p.parse_args()
    if a.seal:seal()
    count=check()
    gates=json.loads((ROOT/'release_status.json').read_text())
    blocked=[k for k,v in gates['gates'].items() if not v]
    if a.public and (blocked or not gates['public_release_ready']):
        raise SystemExit('Public release blocked: '+', '.join(blocked))
    if a.archive:
        dest=ROOT/'dist';dest.mkdir(exist_ok=True)
        path=dest/('compute-to-tokens-repro-'+('release' if a.public else 'LOCAL-REVIEW')+'.zip')
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for f in paths():
                info=zipfile.ZipInfo('compute-to-tokens-repro/'+str(f.relative_to(ROOT)),date_time=(2026,9,16,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
                z.writestr(info,f.read_bytes())
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None:raise RuntimeError('Archive integrity test failed')
        print(f'Local archive: {path.name}; bytes={path.stat().st_size}; sha256={digest(path)}')
    print(json.dumps(dict(checked_files=count,privacy_scan='passed',checksums='passed',public_release_blockers=blocked)))

if __name__=='__main__':main()
