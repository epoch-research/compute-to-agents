"""Opt-in range downloads for the pinned audit artifacts; gh auth stays in memory."""
import io
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
import httpx
from .paths import REFERENCE

IDS = [9160764634,9845132453,9964947783,9961723604,10139171704,10136761323,
       9903217672,9876160116,10315131697,10314379718,9459261150,10274478370,9715184025]
REQUEST_IDS = {9964947783,10139171704,9876160116,10315131697,10314379718}


class Remote(io.RawIOBase):
    def __init__(self,url,size):
        self.url, self.size, self.pos = url, size, 0
        self.client = httpx.Client(timeout=60)
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos = offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def read(self,n=-1):
        n = self.size-self.pos if n<0 else min(n,self.size-self.pos)
        if n<=0: return b''
        if n>=100_000_000: raise ValueError('Refusing unexpectedly large range')
        # Do not expose signed URLs in exception messages.
        try:
            r=self.client.get(self.url,headers={'Range':f'bytes={self.pos}-{self.pos+n-1}'})
        except httpx.HTTPError:
            raise RuntimeError('Artifact range request failed; rerun to refresh authorization') from None
        if r.status_code!=206 or len(r.content)!=n:
            raise RuntimeError(f'Invalid artifact range response: HTTP {r.status_code}')
        if not r.headers.get('Content-Range','').startswith(f'bytes {self.pos}-'):
            raise RuntimeError('Artifact range offset mismatch')
        self.pos+=n
        return r.content
    def close(self):
        self.client.close()
        super().close()


def fetch_all(directory, requests=False):
    directory.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(directory).free < (600_000_000 if requests else 50_000_000):
        raise OSError('Insufficient space for artifact extraction')
    result=subprocess.run(['gh','auth','token'],text=True,capture_output=True)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError('Artifact retrieval needs GitHub CLI authentication; run gh auth login separately.')
    token=result.stdout.strip()
    pins=json.loads((REFERENCE/'agentx_pins.json').read_text())
    with httpx.Client(timeout=60) as client:
        for expected in pins:
            r=client.get('https://api.github.com/repos/SemiAnalysisAI/InferenceX/contents/utils/aiperf',
                params={'ref':expected['head_sha']},headers={'Authorization':'Bearer '+token})
            if r.status_code!=200 or r.json().get('sha')!=expected['aiperf_sha']:
                raise RuntimeError(f'Historical harness pin verification failed for run {expected["run"]}')
    (directory/'pins.json').write_text(json.dumps(pins,indent=2)+'\n')
    hashes=json.loads((REFERENCE/'agentx_members.json').read_text())
    from .sources import sha256
    for aid in IDS:
        dest=directory/f'artifact_{aid}'
        suffixes=('profile_export_aiperf.json','benchmark.log')
        if requests and aid in REQUEST_IDS: suffixes+=('profile_export.jsonl',)
        with httpx.Client(timeout=60) as client:
            base=f'https://api.github.com/repos/SemiAnalysisAI/InferenceX/actions/artifacts/{aid}'
            response=client.get(base,headers={'Authorization':'Bearer '+token})
            if response.status_code != 200:
                raise RuntimeError(f'Artifact {aid} unavailable: HTTP {response.status_code}; do not substitute a newer run.')
            meta=response.json()
            if meta.get('expired'):
                raise RuntimeError(f'Pinned artifact {aid} expired. Supply the archived original locally; no live substitution allowed.')
            r=client.get(base+'/zip',headers={'Authorization':'Bearer '+token},follow_redirects=False)
            if r.status_code!=302: raise RuntimeError(f'Artifact {aid}: download authorization failed')
        with Remote(r.headers['location'],meta['size_in_bytes']) as remote, zipfile.ZipFile(remote) as archive:
            members=[m for m in archive.infolist() if m.filename.endswith(suffixes)]
            if not members: raise ValueError(f'Artifact {aid}: expected members absent')
            for member in members:
                rel=f'artifact_{aid}/'+member.filename
                expected=hashes.get(rel)
                if expected is None: raise ValueError('Unrecognized artifact member; aborting')
                target=dest/member.filename
                if not target.resolve().is_relative_to(directory.resolve()):
                    raise ValueError('Unsafe ZIP member path')
                if target.exists():
                    if sha256(target)!=expected: raise ValueError(f'Existing artifact {aid} failed checksum')
                    continue
                if member.file_size>500_000_000: raise ValueError('Unexpectedly large extracted member')
                target.parent.mkdir(parents=True,exist_ok=True)
                part=target.with_suffix(target.suffix+'.part')
                with archive.open(member) as source, part.open('wb') as output:
                    shutil.copyfileobj(source,output,1024*1024)
                if sha256(part)!=expected: raise ValueError(f'Artifact {aid} member checksum failed')
                part.rename(target)
        # Save only fields consumed by the analysis; never signed download URLs.
        (dest/'inventory.json').write_text(json.dumps({'metadata':{'workflow_run':{'id':meta['workflow_run']['id']}}})+'\n')
        print(f'Artifact {aid}: verified selected members',flush=True)
