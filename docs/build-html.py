import base64, html, re, os, pathlib

SRC = 'docs/draft-report.md'
OUT = 'docs/draft-report.html'
FIGDIR = 'docs'

md = open(SRC).read()
body_md = md.split('\n', 1)[1]  # drop the H1, handled in the masthead

def data_uri(rel):
    p = os.path.join(FIGDIR, rel)
    b = pathlib.Path(p).read_bytes()
    return f"data:image/png;base64,{base64.b64encode(b).decode()}"

def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', t)
    t = re.sub(r'`([^`]+?)`', r'<code>\1</code>', t)
    t = re.sub(r'\[([^\]]+)\]\((#[^)]+)\)', r'<a href="\2">\1</a>', t)
    t = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2" rel="noreferrer">\1</a>', t)
    t = re.sub(r'(?<!href=")(?<!">)(https?://[^\s<)]+)', r'<a href="\1" rel="noreferrer">\1</a>', t)
    return t

out, i = [], 0
lines = body_md.split('\n')
fig_n = 0

while i < len(lines):
    ln = lines[i]

    if not ln.strip():
        i += 1; continue

    if ln.startswith('---'):
        i += 1; continue

    # image + its caption on the following non-blank line
    m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', ln.strip())
    if m:
        alt, src = m.group(1), m.group(2)
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        cap = ''
        if j < len(lines) and lines[j].startswith('***Figure'):
            raw = lines[j].strip()
            # Escape FIRST, then wrap the figure number — doing it the other way
            # round escapes the span itself and prints the markup verbatim.
            m2 = re.match(r'^\*\*\*(Figure \d+)\*\*(.*?)\*$', raw)
            if m2:
                cap = f'<span class="fignum">{m2.group(1)}</span>' + inline(m2.group(2))
            else:
                cap = inline(raw)
            i = j
        fig_n += 1
        out.append(
            f'<figure class="plate">'
            f'<img src="{data_uri(src)}" alt="{html.escape(alt)}" loading="lazy">'
            f'<figcaption>{cap}</figcaption></figure>'
        )
        i += 1; continue

    if ln.startswith('#### '):
        out.append(f'<h4>{inline(ln[5:])}</h4>'); i += 1; continue
    if ln.startswith('### '):
        t = ln[4:]
        num = re.match(r'([\d.]+)\s+(.*)', t)
        sid = 's' + num.group(1).replace('.', '-') if num else ''
        inner = (f'<span class="secnum">{num.group(1)}</span>{inline(num.group(2))}'
                 if num else inline(t))
        out.append(f'<h3 id="{sid}">{inner}</h3>'); i += 1; continue
    if ln.startswith('## '):
        t = ln[3:]
        num = re.match(r'(\d+)\.\s+(.*)', t)
        if num:
            cid = 'c' + num.group(1)
            out.append(f'<h2 id="{cid}"><span class="chapnum">Chapter {num.group(1)}</span>'
                       f'<span class="chaptitle">{inline(num.group(2))}</span></h2>')
        else:
            out.append(f'<h2 id="toc">{inline(t)}</h2>')
        i += 1; continue

    # table caption
    if ln.startswith('**Table'):
        out.append(f'<p class="tabcap">{inline(ln)}</p>'); i += 1; continue

    # table
    if ln.startswith('|'):
        rows = []
        while i < len(lines) and lines[i].startswith('|'):
            rows.append(lines[i]); i += 1
        cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows]
        head, data = cells[0], cells[2:] if len(cells) > 2 else []
        th = ''.join(f'<th>{inline(c)}</th>' for c in head)
        tb = ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in data)
        out.append(f'<div class="tablewrap"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>')
        continue

    # paragraph
    para = [ln]
    i += 1
    while i < len(lines) and lines[i].strip() and not re.match(r'^(#|!\[|\||---|\*\*Table)', lines[i]):
        para.append(lines[i]); i += 1
    text = ' '.join(para).strip()
    cls = ' class="lede"' if text.startswith('**Figures:**') or text.startswith('**Tables:**') else ''
    out.append(f'<p{cls}>{inline(text)}</p>')

BODY = '\n'.join(out)

CHAPTERS = [('c1','Introduction'),('c2','Literature Review'),('c3','Design'),
            ('c4','Implementation'),('c5','Evaluation'),('c6','Conclusion'),('c7','References')]
RAIL = ''.join(f'<a href="#{cid}"><span>{n}</span>{name}</a>'
               for n,(cid,name) in enumerate(CHAPTERS, 1))

TPL = open('/tmp/report_tpl.html').read()
open(OUT,'w').write(TPL.replace('{{BODY}}', BODY).replace('{{RAIL}}', RAIL))
print(f"wrote {OUT}  ({os.path.getsize(OUT)/1e6:.1f} MB, {fig_n} figures inlined)")
