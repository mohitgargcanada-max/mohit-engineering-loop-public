"""Validate this original skill without third-party packages."""
from pathlib import Path
import re
import sys
ROOT = Path(__file__).resolve().parents[1]

def validate():
    errors = []
    entry = ROOT / 'skills/mohit-engineering-loop/SKILL.md'
    text = entry.read_text(encoding='utf-8')
    if not text.startswith('---\nname: mohit-engineering-loop\ndescription: '):
        errors.append('Invalid skill metadata')
    for path in [ROOT/'README.md', ROOT/'ATTRIBUTION.md', *ROOT.rglob('skills/**/*.md')]:
        body = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', body):
            if re.match(r'https?://|#', link): continue
            if not (path.parent / link.split('#')[0]).exists():
                errors.append(str(path.relative_to(ROOT)) + ': missing ' + link)
    for path in ROOT.rglob('*.py'):
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
    if 'Copyright (c) 2026 Mohit Garg' not in (ROOT/'LICENSE').read_text():
        errors.append('Missing owner copyright')
    if 'Chase AI' not in (ROOT/'ATTRIBUTION.md').read_text():
        errors.append('Missing inspiration credit')
    return errors

if __name__ == '__main__':
    errors = validate()
    print('\n'.join(errors) if errors else 'Metadata, local links, syntax and credit passed.')
    sys.exit(bool(errors))
