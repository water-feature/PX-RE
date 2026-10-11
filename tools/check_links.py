"""Check inline repository Markdown links and heading anchors; skip external URLs."""
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def links(text):
    # Remove fenced code and inline code before finding Markdown link destinations.
    text = re.sub(r'^(```|~~~).*?^\1[^\n]*$', '', text, flags=re.M | re.S)
    text = re.sub(r'`[^`\n]*`', '', text)
    for match in re.finditer(r'\]\(', text):
        start = match.end()
        depth, end = 1, start
        while end < len(text) and depth:
            if text[end] == '(':
                depth += 1
            elif text[end] == ')':
                depth -= 1
            end += 1
        if depth == 0:
            destination = text[start:end-1].strip()
            if destination.startswith('<'):
                destination = destination[1:destination.index('>')]
            else:
                destination = re.split(r'\s+["\']', destination, maxsplit=1)[0]
            yield destination


def anchors(text):
    result, counts = set(), {}
    for line in text.splitlines():
        match = re.match(r'^#{1,6}\s+(.+?)(?:\s+#+)?\s*$', line)
        if not match:
            continue
        heading = re.sub(r'<[^>]*>', '', match[1]).lower()
        slug = re.sub(r'[^\w\- ]', '', heading).replace(' ', '-')
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        result.add(slug + (f'-{number}' if number else ''))
    result.update(re.findall(r'(?:id|name)=["\']([^"\']+)', text))
    return result


def main():
    errors = []
    for source in sorted(ROOT.rglob('*.md')):
        if '.git' in source.parts:
            continue
        for destination in links(source.read_text()):
            url = urlsplit(destination)
            if url.scheme or url.netloc:
                continue
            target = (ROOT / unquote(url.path).lstrip('/') if url.path.startswith('/') else
                      source.parent / unquote(url.path)) if url.path else source
            if not target.exists():
                errors.append(f'{source.relative_to(ROOT)}: missing {destination}')
            elif url.fragment and target.suffix.lower() == '.md' and unquote(url.fragment) not in anchors(target.read_text()):
                errors.append(f'{source.relative_to(ROOT)}: missing anchor {destination}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        raise SystemExit(1)
    print('PASS: repository Markdown links and anchors')


if __name__ == '__main__':
    main()
