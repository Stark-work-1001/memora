"""Copy selected graph sources, verifying originals are unchanged. Never runs in source trees."""
import hashlib
import json
from pathlib import Path
import shutil
import argparse

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'node_modules', 'target', 'dist', '.git', 'release', '_tmp'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    sources=parser.parse_args().source_root
    report = []
    for name in ('dictionary-graph', 'original-dev'):
        source = sources / name
        destination = ROOT / 'frontend' / 'vendor' / name
        chosen = ['src', 'standalone/src', 'standalone/styles.css', 'locales', 'licenses', 'crates',
                  'LICENSE', 'THIRD_PARTY_NOTICES.md', 'package.json', 'tsconfig.json', 'data']
        files = set()
        for relative in chosen:
            target = source / relative
            if target.is_file(): files.add(target)
            elif target.is_dir():
                files.update(p for p in target.rglob('*') if p.is_file() and not EXCLUDED.intersection(p.relative_to(source).parts))
        for path in sorted(files):
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            dest = destination / path.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'original changed'
            assert hashlib.sha256(dest.read_bytes()).hexdigest() == digest, 'copy mismatch'
            report.append({'source': 'upstream/'+name+'/'+path.relative_to(source).as_posix(), 'copy': dest.relative_to(ROOT).as_posix(), 'sha256': digest})
    (ROOT / 'docs' / 'graph-copy-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(f'Copied and verified {len(report)} files. Original trees were read only.')


if __name__ == '__main__': main()
