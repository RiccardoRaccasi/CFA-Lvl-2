# -*- coding: utf-8 -*-
"""Extract the official CFA Level II glossary (term / definition pairs).

The glossary PDF is set in two columns; terms are MyriadPro-Bold and definitions
WarnockPro-Regular, so the pair boundary is a font change, not a layout guess.
"""
import pymupdf, re, json, sys, os

PDF = sys.argv[1] if len(sys.argv) > 1 else "cfa-program2026L2glossary.pdf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "glossary_official.json"
def column_split(page):
    """Find the gutter for this page: column x-origins move between odd and even
    pages, so a fixed midpoint misassigns whole columns."""
    xs = sorted({round(s["bbox"][0], 1)
                 for b in page.get_text("dict")["blocks"]
                 for l in b.get("lines", [])
                 for s in l["spans"]
                 if s["text"].strip()
                 and s["font"].startswith("MyriadPro-Bold")
                 and not s["font"].startswith("MyriadPro-BoldCond")})
    if len(xs) < 2:
        return page.rect.width / 2
    # The split must sit in the gutter, just left of the right column's origin —
    # not midway between the two origins, since left-column body text runs well
    # past that midpoint and would be misfiled into the right column.
    gap, right_origin = 0.0, None
    for a, b in zip(xs, xs[1:]):
        if b - a > gap:
            gap, right_origin = b - a, b
    return (right_origin - 6.0) if gap > 50 else page.rect.width / 2

def norm(t):
    for a, b in [('​',''),(' ',' '),('­',''),('ﬁ','fi'),('ﬂ','fl'),
                 ('’',"'"),('‘',"'"),('“','"'),('”','"'),(' ',' ')]:
        t = t.replace(a, b)
    return re.sub(r'[ \t]{2,}', ' ', t.replace('\t', ' '))

def dehy(t):
    t = re.sub(r'(\w)[-‐]\s*\n\s*(\w)', r'\1\2', t)
    return re.sub(r'\s{2,}', ' ', re.sub(r'\n+', ' ', t)).strip()

def spans_in_order(doc):
    """Yield (kind, text) across the glossary, left column then right, per page.

    Columns are split per SPAN, not per line: PyMuPDF sometimes merges a line
    across the gutter, which would otherwise interleave the two columns.
    """
    for p in range(doc.page_count):
        page = doc[p]
        split = column_split(page)
        cols = {0: [], 1: []}
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    f, txt = s["font"], s["text"]
                    if not txt.strip():
                        continue
                    if f.startswith("MyriadPro-BoldCond"):          # running header
                        continue
                    if re.fullmatch(r'G-\d+|Glossary', txt.strip()):
                        continue
                    x0, y0 = s["bbox"][0], s["bbox"][1]
                    col = 0 if x0 < split else 1
                    kind = "term" if (f.startswith("MyriadPro-Bold") and 8.5 <= s["size"] <= 9.4) else "def"
                    cols[col].append((round(y0, 1), round(x0, 1), kind, txt))
        for c in (0, 1):
            # bucket spans into visual rows (baselines jitter by a point or two),
            # then read each row left to right
            rows = []
            for item in sorted(cols[c]):
                if rows and abs(item[0] - rows[-1][0]) <= 2.5:
                    rows[-1][1].append(item)
                else:
                    rows.append((item[0], [item]))
            for _, items in rows:
                items.sort(key=lambda z: z[1])
                for y, x, kind, txt in items:
                    yield (kind, txt)
                yield ("nl", "\n")

def extract(path):
    doc = pymupdf.open(path)
    entries = []
    mode = None; term = []; defn = []
    def flush():
        if not term: return
        t = dehy(norm("".join(term))).strip(" .,;:")
        d = dehy(norm("".join(defn))).strip()
        d = re.sub(r'^[\s.,;:]+', '', d)
        if len(t) >= 2 and len(d) >= 3:
            entries.append({"term": t, "def": d})
    for kind, txt in spans_in_order(doc):
        if kind == "term":
            if mode == "def":            # a new bold run closes the previous entry
                flush(); term = []; defn = []
            term.append(txt); mode = "term"
        elif kind == "def":
            defn.append(txt); mode = "def"
        else:
            (term if mode == "term" else defn).append(txt)
    flush()
    doc.close()
    # merge duplicate headwords, keeping the fullest definition
    best = {}
    for e in entries:
        k = e["term"].lower()
        if k not in best or len(e["def"]) > len(best[k]["def"]):
            best[k] = e
    return [best[k] for k in sorted(best)]

if __name__ == "__main__":
    G = extract(PDF)
    json.dump(G, open(OUT, "w"), ensure_ascii=False, indent=0)
    print(f"{len(G)} terms -> {OUT}")
    lens = sorted(len(g["def"]) for g in G)
    print(f"definition length: min {lens[0]}  median {lens[len(lens)//2]}  max {lens[-1]}")
    for g in G[:4] + G[len(G)//2:len(G)//2+4]:
        print(f"  {g['term'][:38]:38s} | {g['def'][:92]}")
