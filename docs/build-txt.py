import re, textwrap

SRC='docs/draft-report.md'; OUT='docs/draft-report.txt'
WIDTH=88

md=open(SRC).read()
lines=md.split('\n')
out=[]; i=0

def plain(t):
    t=re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', t)
    t=re.sub(r'\*\*(.+?)\*\*', r'\1', t)
    t=re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'\1', t)
    t=re.sub(r'`([^`]+?)`', r'\1', t)
    t=re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', t)     # links -> label
    t=t.replace('—','--').replace('–','-').replace('…','...')
    t=t.replace('“','"').replace('”','"').replace('‘',"'").replace('’',"'")
    t=t.replace('·','|').replace('→','->').replace('≥','>=').replace('≤','<=')
    t=t.replace('×','x').replace('≈','~')
    return t.strip()

def rule(ch, n=WIDTH): return ch*n

while i < len(lines):
    ln=lines[i]

    if not ln.strip(): i+=1; continue
    if ln.startswith('---'): i+=1; continue

    if ln.startswith('# '):
        t=plain(ln[2:])
        out += [rule('='), *textwrap.wrap(t, WIDTH), rule('='), '']
        i+=1; continue

    if ln.startswith('## '):
        t=plain(ln[3:])
        out += ['', rule('='), t.upper(), rule('='), '']
        i+=1; continue

    if ln.startswith('### '):
        t=plain(ln[4:])
        out += ['', t, rule('-', min(len(t), WIDTH)), '']
        i+=1; continue

    if ln.startswith('#### '):
        out += ['', plain(ln[5:]).upper(), '']
        i+=1; continue

    # figure: image line then caption line
    m=re.match(r'!\[([^\]]*)\]\(([^)]+)\)', ln.strip())
    if m:
        j=i+1
        while j < len(lines) and not lines[j].strip(): j+=1
        cap = plain(lines[j]) if j < len(lines) and lines[j].startswith('***Figure') else plain(m.group(1))
        src = m.group(2)
        out += ['', f'[{cap.split(" -- ")[0]}]  (image: {src})']
        rest = cap.split(' -- ', 1)
        if len(rest) > 1:
            out += textwrap.wrap(rest[1], WIDTH, initial_indent='    ', subsequent_indent='    ')
        out += ['']
        i = j+1 if j < len(lines) and lines[j].startswith('***Figure') else i+1
        continue

    if ln.startswith('**Table'):
        out += ['', plain(ln)]
        i+=1; continue

    if ln.startswith('|'):
        rows=[]
        while i < len(lines) and lines[i].startswith('|'):
            rows.append(lines[i]); i+=1
        cells=[[plain(c) for c in r.strip().strip('|').split('|')] for r in rows]
        cells=[c for c in cells if not all(set(x) <= set('-: ') for x in c)]
        ncol=max(len(c) for c in cells)
        cells=[c+['']*(ncol-len(c)) for c in cells]
        budget=WIDTH-(3*(ncol-1))
        want=[max(len(r[k]) for r in cells) for k in range(ncol)]
        total=sum(want)
        w=[max(6, int(budget*x/total)) for x in want] if total>budget else want
        out.append('')
        for ri,row in enumerate(cells):
            wrapped=[textwrap.wrap(row[k], w[k]) or [''] for k in range(ncol)]
            for li in range(max(len(x) for x in wrapped)):
                out.append('   '.join((wrapped[k][li] if li<len(wrapped[k]) else '').ljust(w[k])
                                      for k in range(ncol)).rstrip())
            if ri==0: out.append('   '.join('-'*w[k] for k in range(ncol)))
        out.append('')
        continue

    para=[ln]; i+=1
    if re.match(r'^(\d+\. \[|   \d+\.\d )', ln):
        sub = ln.startswith('   ')
        out += textwrap.wrap(plain(ln), WIDTH,
                             initial_indent='   ' if sub else '',
                             subsequent_indent='      ' if sub else '   ')
        continue
    while (i<len(lines) and lines[i].strip()
           and not re.match(r'^(#|!\[|\||---|\*\*Table)', lines[i])
           and not re.match(r'^\d+\. \[', lines[i])          # TOC chapter entry
           and not re.match(r'^   \d+\.\d ', lines[i])       # TOC sub-entry
           and not re.match(r'^\*\*[A-Z][^*]*:?\*\*', lines[i])):  # bold metadata line
        para.append(lines[i]); i+=1
    out += textwrap.wrap(plain(' '.join(para)), WIDTH) + ['']

text='\n'.join(out)
text=re.sub(r'\n{4,}', '\n\n\n', text)
open(OUT,'w').write(text)
print(f"wrote {OUT} ({len(text.split())} words, {len(text.splitlines())} lines)")
