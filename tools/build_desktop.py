"""Build a Windows Electron directory with a frozen, data-free Python backend."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def run(args, cwd=ROOT):
    subprocess.run(args,cwd=cwd,check=True)


def main():
    if sys.platform!='win32':raise SystemExit('This recipe currently builds Windows x64; Web is cross-platform.')
    import memory_merge_native
    if memory_merge_native.__version__!='1.0.1':raise SystemExit('Build and install ./native 1.0.1 first')
    staging=ROOT/'build'/'memora-source'
    staging.mkdir(parents=True,exist_ok=True)
    # Explicitly copy only code and distributable static assets, not the workspace or data root.
    for file in (ROOT/'memory_merge').rglob('*'):
        if not file.is_file() or '__pycache__' in file.parts:continue
        if file.suffix.lower() not in {'.py','.html','.js','.css','.svg'}:continue
        dest=staging/'memory_merge'/file.relative_to(ROOT/'memory_merge')
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
    entry=staging/'entry.py'
    entry.write_text('import multiprocessing\nif __name__=="__main__":\n    multiprocessing.freeze_support()\n    from memory_merge.__main__ import main\n    main()\n','utf-8')
    env=dict(os.environ,PYTHONPATH=str(staging),PYTHONHASHSEED='0')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir',
        '--name','memora-backend','--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build/pyinstaller'),
        '--specpath',str(ROOT/'build'),'--paths',str(staging),
        '--add-data',str(staging/'memory_merge/static')+os.pathsep+'memory_merge/static',
        '--collect-submodules','memory_merge','--collect-submodules','mcp.server','--collect-submodules','mcp.shared','--copy-metadata','mcp',
        '--hidden-import','memory_merge_native','--collect-submodules','uvicorn',
        '--exclude-module','tkinter',str(entry)],cwd=staging,env=env,check=True)
    backend=ROOT/'dist/memora-backend'
    # Attribution and both guides travel with the standalone backend and desktop binary.
    for name in ('LICENSE','NOTICE','README.md','README.zh-CN.md','THIRD_PARTY_NOTICES.md'):
        shutil.copyfile(ROOT/name,backend/name)
    shutil.copytree(ROOT/'LICENSES',backend/'LICENSES',dirs_exist_ok=True)
    shutil.copytree(ROOT/'docs',backend/'docs',dirs_exist_ok=True)
    notices=backend/'LICENSES/graphs';notices.mkdir(parents=True,exist_ok=True)
    for vendor in ('dictionary-graph','original-dev'):
        shutil.copyfile(ROOT/'frontend/vendor'/vendor/'LICENSE',notices/(vendor+'-MIT.txt'))
    shutil.copytree(ROOT/'frontend/vendor/original-dev/licenses',notices/'inherited',dirs_exist_ok=True)
    run(['npm.cmd','ci','--ignore-scripts','--no-audit','--no-fund'],ROOT/'desktop')
    run([sys.executable,str(ROOT/'tools/fetch_electron.py')])
    run(['npm.cmd','run','pack'],ROOT/'desktop')
    print('Built desktop/release/win-unpacked. Release packaging performs the final privacy scan.')


if __name__=='__main__':main()
