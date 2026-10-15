"""Stage already-validated artifacts into an explicitly chosen base directory.

The existing public tree is renamed into private development artifacts first.
Reference directories and the preserved previous-version release are untouched.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path,PurePosixPath
import shutil
import subprocess
import sys
import zipfile

from release_memora import ROOT,VERSION,scan


def extract(archive,destination,prefix):
    destination.mkdir(parents=True,exist_ok=True);destination=destination.resolve()
    count=0
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise RuntimeError('archive CRC failed')
        for info in z.infolist():
            path=PurePosixPath(info.filename)
            if not path.parts or path.parts[0]!=prefix or path.is_absolute() or '..' in path.parts or '\\' in info.filename:
                raise RuntimeError('unexpected archive path')
            if info.is_dir():continue
            target=destination.joinpath(*path.parts[1:]).resolve()
            if not target.is_relative_to(destination):raise RuntimeError('archive escaped destination')
            if (info.external_attr>>16)&0o170000==0o120000:raise RuntimeError('archive contains symbolic link')
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as source,target.open('wb') as output:shutil.copyfileobj(source,output)
            count+=1
    return count


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',required=True,help='explicit delivery parent directory');args=ap.parse_args()
    base=Path(args.base).resolve(strict=True);public=base/'public';release=base/'release'/VERSION
    if public.is_symlink() or (hasattr(public,'is_junction') and public.is_junction()):raise RuntimeError('public must not be a link')
    if public.resolve().parent!=base or release.resolve().parent.parent!=base:raise RuntimeError('delivery boundaries failed')
    validation=json.loads((ROOT/'dist/RELEASE_VALIDATION.json').read_text('utf-8'))
    if validation['version']!=VERSION or validation['privacy_findings'] or not validation.get('desktop_smoke',{}).get('rust_kernel_required'):
        raise RuntimeError('validated standalone release required')
    for asset in validation['assets']:
        if hashlib.sha256((ROOT/'dist'/asset['name']).read_bytes()).hexdigest()!=asset['sha256']:raise RuntimeError('asset checksum mismatch')
    # Same-volume native rename is reversible. Resolve both destinations before moving.
    snapshot=None
    if public.exists():
        snapshot=ROOT/'artifacts'/('private-public-before-'+VERSION+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        snapshot.parent.mkdir(exist_ok=True)
        if not snapshot.resolve().is_relative_to((ROOT/'artifacts').resolve()) or snapshot.exists():raise RuntimeError('snapshot boundary failed')
        public.rename(snapshot)
    source_zip=ROOT/'dist'/('memora-'+VERSION+'-source.zip')
    source_count=extract(source_zip,public,'memora-'+VERSION)
    release.mkdir(parents=True,exist_ok=True)
    names=[a['name'] for a in validation['assets']]+['SHA256SUMS','RELEASE_MANIFEST.json','RELEASE_VALIDATION.json','SMOKE_VALIDATION.json','BRIDGE_VALIDATION.json']
    for name in names:shutil.copyfile(ROOT/'dist'/name,release/name)
    for name in ['RELEASE_NOTES.en.md','RELEASE_NOTES.zh-CN.md']:
        guide=(ROOT/name).read_text('utf-8')
        prefix='memora-'+VERSION+'-windows-x64/'
        guide=guide.replace('](docs/',']('+prefix+'docs/').replace('](THIRD_PARTY_NOTICES.md)',']('+prefix+'THIRD_PARTY_NOTICES.md)')
        (release/name).write_text(guide,'utf-8')
    windows_zip=release/('memora-'+VERSION+'-windows-x64.zip')
    count=extract(windows_zip,release/('memora-'+VERSION+'-windows-x64'),'memora-'+VERSION+'-windows-x64')
    for folder in [public,release]:
        for p in folder.rglob('*'):
            if p.is_symlink():raise RuntimeError('link in staged delivery')
            if not p.is_file() or p.suffix=='.zip':continue
            findings=scan(p.relative_to(folder).as_posix(),p.read_bytes(),source=p.suffix.lower() in {'.js','.html','.json','.ts'})
            if findings:raise RuntimeError('staged privacy scan failed: '+json.dumps(findings))
    exe=release/('memora-'+VERSION+'-windows-x64')/'resources/backend/memora-backend.exe'
    actual=subprocess.check_output([str(exe),'--version'],text=True).strip()
    if actual!=VERSION:raise RuntimeError('staged executable version mismatch')
    # Root release landing file has no workstation paths.
    landing=f'''# memora delivery / 交付

[{VERSION} Windows zip]({VERSION}/memora-{VERSION}-windows-x64.zip) · [中文使用说明]({VERSION}/RELEASE_NOTES.zh-CN.md) · [English guide]({VERSION}/RELEASE_NOTES.en.md)

解压后运行 Memora.exe。也已提供展开目录：{VERSION}/memora-{VERSION}-windows-x64/。
旧版基线位于 1.0.0/，保持原包和校验和不变。

当前包通过无个人数据构建、已知敏感标识扫描、单元测试和冻结运行时验证；扫描边界见发行说明。
SHA256SUMS、RELEASE_VALIDATION.json、SMOKE_VALIDATION.json 位于版本目录。
公开上传前仍需用户验收；此交付没有上传 GitHub，也没有新增授权。
'''
    (base/'release/README.md').write_text(landing,'utf-8')
    report={'version':VERSION,'public_source_files':source_count,'standalone_files':count,'staged_backend_version':actual,
        'privacy_findings':[],'existing_public_preserved':snapshot is not None,'uploaded':False}
    (release/'DELIVERY_VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
