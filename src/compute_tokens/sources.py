"""Explicit, resumable source downloads; no mutable latest endpoints."""
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

from .paths import DATA


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify(path, spec):
    if path.stat().st_size != spec['bytes'] or sha256(path) != spec['sha256']:
        raise ValueError(f'Checksum/size mismatch: {path.name}; original retained, no replacement.')


def acquire(directory, allow_download=False):
    directory.mkdir(parents=True, exist_ok=True)
    sources = json.loads((DATA / 'sources.json').read_text())
    for spec in sources.values():
        dest = directory / spec['filename']
        if dest.exists():
            verify(dest, spec)
            continue
        if not allow_download:
            raise FileNotFoundError(f'{dest.name} missing; supply --download or place pinned file in --data-dir.')
        part = dest.with_suffix(dest.suffix + '.part')
        offset = part.stat().st_size if part.exists() else 0
        if offset > spec['bytes']:
            raise ValueError(f'Oversized partial download: {part.name}; retained for inspection.')
        if shutil.disk_usage(directory).free < max(0, spec['bytes']-offset) + 2_000_000_000:
            raise OSError('Insufficient free space: need remaining download plus 2 GB working reserve.')
        if offset == spec['bytes']:
            verify(part, spec)
            part.rename(dest)
            continue
        request = urllib.request.Request(spec['url'], headers={'Range': f'bytes={offset}-'} if offset else {})
        with urllib.request.urlopen(request, timeout=60) as response:
            if offset and response.status != 206:
                raise RuntimeError('Server refused resume. Preserve .part; move it aside to explicitly restart.')
            if offset and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                raise RuntimeError('Incorrect resume offset')
            with part.open('ab' if offset else 'wb') as f:
                shutil.copyfileobj(response, f, 8 * 1024 * 1024)
        verify(part, spec)
        part.rename(dest)
    return {k: directory / s['filename'] for k, s in sources.items()}


def main():
    import argparse
    from .paths import ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT/'raw')
    parser.add_argument('--download', action='store_true', help='Download missing pinned files (~2.01 GB); otherwise verify existing files only')
    args = parser.parse_args()
    paths = acquire(args.data_dir.resolve(), args.download)
    print(json.dumps({key: {'filename': path.name, 'bytes': path.stat().st_size,
                           'verified': True} for key, path in paths.items()}, indent=2))


if __name__ == '__main__':
    main()
