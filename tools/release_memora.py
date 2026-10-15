"""Allowlisted Memora source/desktop releases, privacy checks and integrity manifests."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='1.0.1'
DIRECTORIES={'memory_merge','native','tests','datasets','docs','bench','tools','integrations','.github','frontend','desktop','LICENSES'}
ROOT_FILES={'.gitignore','.gitattributes','.dockerignore','Dockerfile','LICENSE','NOTICE','THIRD_PARTY_NOTICES.md','LICENSE-STATUS.md',
 'PRIVACY.md','SECURITY.md','CONTRIBUTING.md','CHANGELOG.md','README.md','README.zh-CN.md','RELEASE_NOTES.en.md','RELEASE_NOTES.zh-CN.md',
 'pyproject.toml','requirements.txt','requirements-lock.txt','start-memora.ps1'}
SKIP={'node_modules','target','__pycache__','.git','.venv','venv','dist','build','release','backups','markdown','_tmp','artifacts'}
EXTENSIONS={'.py','.rs','.toml','.lock','.json','.jsonl','.md','.txt','.html','.js','.mjs','.cjs','.css','.svg','.ts','.yml','.yaml','.ps1','.png'}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def scan(name,raw,source=False):
    findings=[]
    # Exact workstation identifiers are obtained at build time, never embedded in the report.
    markers=[str(ROOT),str(Path.home()),'.'+'agent-download','007-'+'codex-workplace']
    lowered=raw.lower()
    for marker in markers:
        if not marker or marker in {'/','\\'}:continue
        if any(m in lowered for m in [marker.lower().encode(),marker.lower().replace('\\','/').encode(),marker.lower().encode('utf-16le')]):
            findings.append({'file':name,'rule':'workstation_identifier'});break
    for label,pattern in [('github_token',rb'gh[pousr]_[A-Za-z0-9]{25,}'),
                           ('api_token',rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}'),
                           ('private_key',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{100,}')]:
        if re.search(pattern,raw):findings.append({'file':name,'rule':label})
    if source:
        # Embedded WASM carries panic-source strings outside normal text scanning.
        import base64
        for match in re.finditer(rb'["\']([A-Za-z0-9+/=]{1000,})["\']',raw):
            try:decoded=base64.b64decode(match.group(1),validate=True)
            except ValueError:continue
            if decoded.startswith(b'\0asm'):
                if re.search(rb'[A-Za-z]:\\Users\\',decoded):findings.append({'file':name,'rule':'wasm_compiler_home'})
                findings.extend(scan(name+'#wasm',decoded))
    return findings


def collect():
    files={}
    for directory,dirs,names in os.walk(ROOT):
        relative=Path(directory).relative_to(ROOT)
        dirs[:]=sorted(d for d in dirs if d not in SKIP and not d.endswith('.egg-info'))
        if not relative.parts:dirs[:]=[d for d in dirs if d in DIRECTORIES]
        if len(relative.parts)>=3 and relative.parts[:2]==('frontend','vendor'):
            dirs[:]=[d for d in dirs if d!='data']
        for name in sorted(names):
            path=Path(directory)/name
            rel=path.relative_to(ROOT).as_posix()
            if not relative.parts and name not in ROOT_FILES:continue
            if path.is_symlink():raise RuntimeError('symlink in release source: '+rel)
            if path.suffix.lower() not in EXTENSIONS and name not in ROOT_FILES and name not in {'LICENSE','NOTICE'}:continue
            if name.startswith('.env') or path.suffix.lower() in {'.sqlite3','.db','.key','.pem'}:raise RuntimeError('runtime or secret file: '+rel)
            data=path.read_bytes()
            # Platform-independent source archive; upstream license text and code are not redacted.
            if path.suffix.lower()!='.png':data=data.replace(b'\r\n',b'\n')
            files[rel]=data
    return files


def check_links(files):
    for name,raw in files.items():
        if not name.endswith('.md'):continue
        for link in re.findall(r'\]\(<?([^)>#\s]+)',raw.decode('utf-8')):
            if '://' in link or link.startswith(('mailto:','#')):continue
            full=(ROOT/name).parent/link
            if not full.exists():raise RuntimeError(f'broken Markdown link: {name}: {link}')


def tests(root):
    env={k:v for k,v in os.environ.items() if not k.startswith('MM_')}
    env.update(PYTHONUTF8='1',PYTHONPATH=str(root),PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-q'],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=600)
    matched=re.search(r'Ran (\d+) tests',result.stderr)
    if result.returncode or not matched:
        # Do not publish logs containing temporary-machine paths.
        print(result.stderr[-5000:],file=sys.stderr)
        raise RuntimeError('release tests failed')
    skipped=re.search(r'skipped=(\d+)',result.stderr)
    return {'tests':int(matched.group(1)),'skipped':int(skipped.group(1)) if skipped else 0,'passed':True}


def zipped(payload,prefix):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,raw in sorted(payload.items()):
            info=zipfile.ZipInfo(prefix+'/'+name,(2026,10,15,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16;archive.writestr(info,raw)
    return output.getvalue()


def main():
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    files=collect()
    findings=[f for name,raw in files.items() for f in scan(name,raw,source=True)]
    if findings:raise RuntimeError('source privacy scan failed: '+json.dumps(findings))
    if f"__version__ = '{VERSION}'" not in files['memory_merge/__init__.py'].decode():raise RuntimeError('version mismatch')
    for path in ('frontend/package.json','desktop/package.json'):
        if json.loads(files[path])['version']!=VERSION:raise RuntimeError('package version mismatch')
    check_links(files)
    source_results=tests(ROOT)
    frontend_run=subprocess.run(['node','--test','--test-reporter=tap','tests/graphs.test.mjs'],cwd=ROOT/'frontend',capture_output=True,text=True,encoding='utf-8',timeout=90)
    frontend_count=re.search(r'# tests (\d+)',frontend_run.stdout)
    if frontend_run.returncode or not frontend_count:raise RuntimeError('frontend release tests failed')
    frontend_results={'tests':int(frontend_count.group(1)),'passed':True}
    manifest={'project':'memora','version':VERSION,'files':[{'path':name,'bytes':len(raw),'sha256':sha(raw)} for name,raw in sorted(files.items())]}
    files['RELEASE_MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    source=zipped(files,'memora-'+VERSION)
    if source!=zipped(files,'memora-'+VERSION):raise RuntimeError('source archive is not reproducible')
    with tempfile.TemporaryDirectory(prefix='memora-release-') as temp:
        with zipfile.ZipFile(io.BytesIO(source)) as archive:
            if archive.testzip():raise RuntimeError('corrupt source archive')
            archive.extractall(temp)
        unpacked_results=tests(Path(temp)/('memora-'+VERSION))
    artifacts={'memora-'+VERSION+'-source.zip':source}
    desktop=ROOT/'desktop/release/win-unpacked'
    desktop_count=0
    if desktop.is_dir():
        binary={}
        for path in desktop.rglob('*'):
            if not path.is_file():continue
            rel=path.relative_to(desktop).as_posix()
            # certifi's public CA roots are required for HTTPS; private keys remain forbidden.
            public_ca = rel == 'resources/backend/_internal/certifi/cacert.pem'
            if path.suffix.lower() in {'.log','.sqlite3','.db','.env','.key','.pem'} and not public_ca:raise RuntimeError('runtime data in desktop: '+rel)
            raw=path.read_bytes();found=scan(rel,raw,source=path.suffix.lower() in {'.js','.ts','.html','.json'})
            if found:raise RuntimeError('desktop privacy scan failed: '+json.dumps(found))
            binary[rel]=raw
        for name in ['LICENSE','NOTICE','THIRD_PARTY_NOTICES.md','RELEASE_NOTES.en.md','RELEASE_NOTES.zh-CN.md']:
            binary[name]=files[name]
        binary['README.md']=files['RELEASE_NOTES.en.md']
        binary['README.zh-CN.md']=files['RELEASE_NOTES.zh-CN.md']
        # Keep README architecture, compatibility and license links usable offline.
        for name,raw in files.items():
            if name.startswith(('docs/','LICENSES/','frontend/vendor/original-dev/licenses/')) or name == 'frontend/vendor/original-dev/THIRD_PARTY_NOTICES.md':
                binary[name]=raw
        desktop_count=len(binary)
        artifacts['memora-'+VERSION+'-windows-x64.zip']=zipped(binary,'memora-'+VERSION+'-windows-x64')
    sums=[];asset_info=[]
    for name,raw in artifacts.items():
        (dist/name).write_bytes(raw);sums.append(sha(raw)+'  '+name)
        asset_info.append({'name':name,'bytes':len(raw),'sha256':sha(raw)})
    report={'project':'memora','version':VERSION,'source_files':len(files),'desktop_files':desktop_count,
        'source_tests':source_results,'unpacked_tests':unpacked_results,'frontend_tests':frontend_results,'privacy_findings':[],
        'source_reproducible':True,'assets':asset_info,'limits':['Pattern scans cannot identify every private identifier.',
        'Live cloud and GGUF inference require operator configuration and were not exercised.',
        'Platform validation is limited to the build machine; CI is configured separately.']}
    bridge=dist/'BRIDGE_VALIDATION.json'
    if bridge.exists():report['http_bridge']=json.loads(bridge.read_text('utf-8'))
    smoke=dist/'SMOKE_VALIDATION.json'
    if smoke.exists():report['desktop_smoke']=json.loads(smoke.read_text('utf-8'))
    (dist/'SHA256SUMS').write_text('\n'.join(sums)+'\n','utf-8')
    (dist/'RELEASE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8')
    (dist/'RELEASE_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
