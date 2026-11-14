#!/usr/bin/env python3
"""Offline markdown link checker for T09; no network connections required."""
from pathlib import Path
import re
import sys

BASE = Path(__file__).resolve().parents[1]
DOCS = [BASE / 'README.md', *sorted((BASE / 'docs').glob('*.md'))]
NEEDED = {'setup-guide.md','architecture.md','integration-guide.md','api-guide.md','data-and-science.md','testing-and-ci.md','troubleshooting.md','release-checklist.md'}

def check():
    errors=[]
    for missing in sorted(NEEDED-{p.name for p in DOCS}): errors.append(f'missing documentation: {missing}')
    for doc in DOCS:
        if not doc.exists(): errors.append(f'missing file: {doc}'); continue
        text=doc.read_text(encoding='utf-8')
        if not text.strip(): errors.append(f'empty documentation: {doc}')
        for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)',text):
            if target.startswith(('https://','http://','#','mailto:')): continue
            path=(doc.parent / target.split('#',1)[0]).resolve()
            if not path.is_file(): errors.append(f'{doc.name}: missing relative link {target}')
    return errors

if __name__=='__main__':
    errors=check()
    for issue in errors: print('FAIL:',issue)
    print(f'Documentation: {len(DOCS)} Markdown files checked, {len(errors)} issues')
    sys.exit(1 if errors else 0)
