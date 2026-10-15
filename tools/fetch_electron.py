"""Fetch the official Electron runtime and verify its npm-distributed SHA-256 checksum."""
import hashlib
import json
from pathlib import Path
import urllib.request
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    pkg=json.loads((ROOT/'desktop/package.json').read_text('utf-8'))
    version=pkg['devDependencies']['electron']
    name=f'electron-v{version}-win32-x64.zip'
    cache=ROOT/'artifacts/cache';cache.mkdir(parents=True,exist_ok=True)
    archive=cache/name
    expected=json.loads((ROOT/'desktop/node_modules/electron/checksums.json').read_text('utf-8'))[name]
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
        request=urllib.request.Request(f'https://github.com/electron/electron/releases/download/v{version}/{name}?build={uuid.uuid4().hex}',headers={'User-Agent':'Memora-release-build'})
        with urllib.request.urlopen(request,timeout=45) as response,archive.open('wb') as output:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                output.write(chunk)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:raise RuntimeError('Electron checksum mismatch')
    destination=ROOT/'desktop/node_modules/electron/dist';destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:z.extractall(destination)
    (destination.parent/'path.txt').write_text('electron.exe','utf-8')
    print('Official Electron runtime verified and ready.')


if __name__=='__main__':main()
