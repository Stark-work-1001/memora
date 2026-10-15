"""Remove development-machine identifiers from copied/generated assets, never from originals."""
import base64
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def main():
    target=ROOT/'frontend/vendor/original-dev/src/physics/generated/wasm-asset.ts'
    source=target.read_text('utf-8')
    count=0
    def scrub(match):
        nonlocal count
        raw=base64.b64decode(match.group(1))
        def replace(path):
            nonlocal count
            count+=1
            return b'BUILD_ROOT'+b'_'*(len(path.group())-len(b'BUILD_ROOT'))
        clean=re.sub(rb'[A-Za-z]:\\Users\\[^\\\x00]+',replace,raw)
        assert len(clean)==len(raw), 'WASM offsets must stay unchanged'
        return match.group(0).replace(match.group(1),base64.b64encode(clean).decode())
    clean=re.sub(r"['\"]([A-Za-z0-9+/=]{1000,})['\"]",scrub,source)
    target.write_text(clean,'utf-8')
    manifest=ROOT/'docs/graph-copy-manifest.json'
    data=json.loads(manifest.read_text('utf-8'))
    for item in data:
        copy=item['copy'].replace('\\','/')
        parts=copy.split('/')
        item['source']='upstream/'+ '/'.join(parts[2:])
        item['copy']=copy
    manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(f'Sanitized {count} embedded compiler home paths; original source trees untouched.')


if __name__=='__main__':main()
