# -*- coding: utf-8 -*-
import pymupdf, re, json
SP='/tmp/claude-0/-home-user-CFA-Lvl-2/80c992d8-9583-5bce-bcee-2b287a06518d/scratchpad/work'
PDF='/home/user/CFA-Lvl-2/cfa-program2026L2V{}.pdf'
VOL={1:"Quantitative Methods",2:"Economics",3:"Financial Statement Analysis",4:"Corporate Issuers",
 5:"Equity Valuation",6:"Fixed Income",7:"Derivatives",8:"Alternative Investments",9:"Portfolio Management",
 10:"Ethical and Professional Standards"}
def norm(t):
    for a,b in [('​',''),(' ',' '),('­',''),('ﬁ','fi'),('ﬂ','fl'),
                ('’',"'"),('‘',"'"),('“','"'),('”','"'),(' ',' ')]:
        t=t.replace(a,b)
    return re.sub(r'[ \t]{2,}',' ',t.replace('\t',' ')).strip()
def dehy(t):
    t=re.sub(r'(\w)[-‐]\s*\n\s*(\w)',r'\1\2',t)
    return re.sub(r'\s{2,}',' ',re.sub(r'\n+',' ',t)).strip()

STOP={'exhibit','panel','solution','example','summary','introduction','learning module','practice problems'}
BADSUF=re.compile(r'\b(is|are|the|of|in|and|for|to|a|an|that|which|with|by|as|or)$',re.I)

def blocks(page):
    out=[]
    for b in page.get_text("dict")["blocks"]:
        lines=b.get("lines",[])
        if not lines: continue
        txt=[]; bolds=[]
        for l in lines:
            run=[]
            for s in l["spans"]:
                txt.append(s["text"])
                if s["font"].startswith('MyriadPro-Bold') and 9.0<=s["size"]<=10.6: run.append(s["text"])
                else:
                    if run: bolds.append("".join(run)); run=[]
            if run: bolds.append("".join(run))
            txt.append("\n")
        out.append((dehy(norm("".join(txt))), [norm(x) for x in bolds],
                    any(s["font"].startswith('WarnockPro-Regular') for l in lines for s in l["spans"])))
    return out

def sentence_for(body, term):
    i=body.find(term)
    if i<0: return None
    start=body.rfind('. ', 0, i)
    start=0 if start<0 else start+2
    end=body.find('. ', i)
    end=len(body) if end<0 else end+1
    s=body[start:end].strip()
    if len(s)<40:
        nxt=body.find('. ', end)
        s=body[start:(len(body) if nxt<0 else nxt+1)].strip()
    return s[:420]

out={}; 
for v in range(1,11):
    doc=pymupdf.open(PDF.format(v))
    starts=[i for i in range(doc.page_count) if 'L E A R N I N G M O D U L E' in doc[i].get_text().replace(' ',' ')]
    for p in range(doc.page_count):
        lm=sum(1 for s in starts if s<=p)
        for body, bolds, isbody in blocks(doc[p]):
            if not isbody or len(body)<80: continue
            for term in bolds:
                t=term.strip(" .,;:()")
                if not (3<len(t)<58): continue
                if not re.match(r"^[A-Za-z][A-Za-z0-9 '–\-/(),\.]+$",t): continue
                if t.lower() in STOP or BADSUF.search(t): continue
                if sum(c.isdigit() for c in t)>2: continue
                key=t.lower()
                sent=sentence_for(body,term)
                if not sent or len(sent)<45: continue
                if key not in out or len(out[key]['def'])<len(sent)<400:
                    out[key]={"term":t,"def":sent,"topic":VOL[v],"vol":v,"lm":lm}
    doc.close()
    print(f"V{v}: {len(out)} cumulative")
G=sorted(out.values(), key=lambda g:g['term'].lower())
json.dump(G,open(f"{SP}/glossary.json","w"),ensure_ascii=False)
print("\nfinal terms:",len(G))
for g in G[:6]+G[len(G)//2:len(G)//2+6]:
    print(f"  {g['term'][:34]:34s} [{g['topic'][:12]}] {g['def'][:95]}")
