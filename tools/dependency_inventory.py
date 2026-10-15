"""Record public dependency names, versions, repository URLs and licenses, never install paths."""
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import tomllib

ROOT=Path(__file__).resolve().parents[1]


def safe_url(value):
    if isinstance(value,str) and value.startswith(('https://','http://','git+https://','git://')):
        return value.replace('git+https://','https://').replace('git://','https://')
    return ''


def main():
    records=[];licenses=[]
    for dist in sorted(metadata.distributions(),key=lambda d:d.metadata['Name'].lower()):
        name=dist.metadata['Name']
        if name.lower() in {'memora','memory-merge-local'}: continue
        meta=dist.metadata
        urls=[safe_url(v.split(', ',1)[-1]) for v in meta.get_all('Project-URL',[])]
        home=safe_url(meta.get('Home-page',''))
        license_=meta.get('License-Expression') or meta.get('License','').splitlines()[0:1]
        if isinstance(license_,list):license_=license_[0] if license_ else 'see distribution license'
        urls=[u for u in urls if u]
        records.append(dict(ecosystem='Python',name=name,version=dist.version,license=str(license_)[:160],
                            project=home or (urls[0] if urls else 'https://pypi.org/project/'+name+'/'),links=urls))
        texts=[]
        for entry in dist.files or []:
            if any(x in Path(str(entry)).name.lower() for x in ('license','copying','notice')):
                try:
                    file=dist.locate_file(entry)
                    if file.is_file() and file.stat().st_size<1_000_000:texts.append(file.read_text('utf-8'))
                except (OSError,UnicodeError):pass
        if texts:licenses.append(f'\n===== {name} {dist.version} =====\n'+'\n'.join(texts))
    for package in ('frontend','desktop'):
        lock=json.loads((ROOT/package/'package-lock.json').read_text('utf-8'))
        for key,p in lock.get('packages',{}).items():
            if not key or '/node_modules/' in key: continue
            installed=ROOT/package/key/'package.json'
            data=json.loads(installed.read_text('utf-8')) if installed.is_file() else {}
            name=data.get('name') or key.removeprefix('node_modules/')
            repo=data.get('repository','')
            if isinstance(repo,dict):repo=repo.get('url','')
            url=safe_url(repo) or safe_url(data.get('homepage','')) or 'https://www.npmjs.com/package/'+name
            if url.endswith('.git'):url=url[:-4]
            records.append(dict(ecosystem='npm/'+package,name=name,version=p.get('version',''),license=str(p.get('license') or data.get('license','see package license')),
                                project=url,links=['https://www.npmjs.com/package/'+name]))
    for cargo in [ROOT/'native/Cargo.lock',ROOT/'frontend/vendor/original-dev/crates/graph-physics/Cargo.lock']:
        if not cargo.is_file():continue
        for p in tomllib.loads(cargo.read_text('utf-8')).get('package',[]):
            if p.get('source','').startswith('registry+'):
                records.append(dict(ecosystem='Rust',name=p['name'],version=p['version'],license='see bundled crate notices / crates.io',
                    project='https://crates.io/crates/'+p['name'],links=['https://docs.rs/'+p['name']]))
    lines=['# Complete dependency inventory / 完整依赖与项目链接','',
        'Generated from installed distribution metadata and package/Cargo locks. Includes runtime and build dependencies; optional uninstalled model backends are listed in the READMEs. No local install paths or credentials are recorded.','',
        '| Ecosystem | Project / repository | Version | License |','| --- | --- | --- | --- |']
    for r in records:
        lines.append(f"| {r['ecosystem']} | [{r['name']}]({r['project']}) | {r['version']} | {r['license'].replace('|',' / ')} |")
    lines+=['','Python full license texts: [THIRD_PARTY_LICENSES.txt](../LICENSES/THIRD_PARTY_LICENSES.txt). Rust/WASM full notices: [rust-crates.txt](../frontend/vendor/original-dev/licenses/rust-crates.txt). Electron distribution includes Chromium and Electron notices.']
    (ROOT/'docs/DEPENDENCIES.md').write_text('\n'.join(lines)+'\n','utf-8')
    (ROOT/'docs/DEPENDENCIES.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n','utf-8')
    (ROOT/'LICENSES/THIRD_PARTY_LICENSES.txt').write_text('\n'.join(licenses),'utf-8')
    print(f'Inventoried {len(records)} dependency records with public project links.')


if __name__=='__main__':main()
