# -*- coding: utf-8 -*-
"""Consolidated extraction: structure, item sets with real tables, solutions with
rendered formulas, glossary. Output: curriculum2.json + mathimg2.json + glossary.json"""
import pymupdf, re, json, base64, collections, os
SP='/tmp/claude-0/-home-user-CFA-Lvl-2/80c992d8-9583-5bce-bcee-2b287a06518d/scratchpad/work'
PDF='/home/user/CFA-Lvl-2/cfa-program2026L2V{}.pdf'
VOL={1:"Quantitative Methods",2:"Economics",3:"Financial Statement Analysis",4:"Corporate Issuers",
 5:"Equity Valuation",6:"Fixed Income",7:"Derivatives",8:"Alternative Investments",9:"Portfolio Management",
 10:"Ethical and Professional Standards"}
WEIGHT={1:"5-10%",2:"5-10%",3:"10-15%",4:"5-10%",5:"10-15%",6:"10-15%",7:"5-10%",8:"5-10%",9:"10-15%",10:"5-10%"}
ZOOM=2.6
TOK=re.compile(r'\x00([TM])(\d+)\x00')

def norm(t):
    for a,b in [('​',''),(' ',' '),('­',''),('ﬁ','fi'),('ﬂ','fl'),
                ('’',"'"),('‘',"'"),('“','"'),('”','"'),(' ',' ')]:
        t=t.replace(a,b)
    return re.sub(r'[ \t]{2,}',' ',t.replace('\t',' ')).strip()
def dehy(t):
    t=re.sub(r'(\w)[-‐]\n(\w)',r'\1\2',t)
    t=re.sub(r'\n+',' ',t)
    return re.sub(r'\s{2,}',' ',t).strip()

# ---------- rows ----------
def page_rows(page):
    raw=[]
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines",[]):
            sp=l.get("spans",[])
            txt="".join(s["text"] for s in sp)
            if not txt.strip(): continue
            fonts=[s["font"] for s in sp]
            math=sum(1 for f in fonts if f.startswith('TimesNewRoman'))/max(1,len(fonts))
            raw.append({"y":l["bbox"][1],"x":l["bbox"][0],"bbox":l["bbox"],"t":txt,"math":math>=0.5})
    raw.sort(key=lambda r:(r["y"],r["x"]))
    rows=[];cur=[];cy=None
    for r in raw:
        if cy is None or abs(r["y"]-cy)<=3.0:
            cur.append(r); cy=r["y"] if cy is None else cy
        else:
            rows.append(cur); cur=[r]; cy=r["y"]
    if cur: rows.append(cur)
    out=[]
    for g in rows:
        g.sort(key=lambda z:z["x"])
        out.append({"x":round(g[0]["x"],1),"y":round(g[0]["y"],1),
                    "y1":max(z["bbox"][3] for z in g),
                    "cells":[(round(z["x"],1),norm(z["t"])) for z in g],
                    "text":norm(" ".join(z["t"] for z in g)),
                    "math":all(z["math"] for z in g),
                    "items":g})
    return out

# ---------- tables ----------
def tables_on(page):
    try: found=page.find_tables()
    except Exception: return []
    W,H=page.rect.width,page.rect.height
    out=[]
    for t in found.tables:
        b=t.bbox
        w,h=b[2]-b[0],b[3]-b[1]
        if t.row_count<2 or t.col_count<2: continue
        if w>W*0.85 or h>H*0.80: continue          # whole-page false positive
        try: cells=t.extract()
        except Exception: continue
        clean_rows=[]
        for r in cells:
            rr=[norm(c or "") for c in r]
            if any(x for x in rr): clean_rows.append(rr)
        if len(clean_rows)<2: continue
        if sum(len(x) for r in clean_rows for x in r)<12: continue
        out.append({"bbox":b,"cells":clean_rows})
    out.sort(key=lambda z:z["bbox"][1])
    return out

# ---------- running headers ----------
def header_filter(title):
    tn=re.sub(r'\s+',' ',title).strip().lower()
    LABELS={'practice problems','solutions','references','summary','introduction',tn}
    def drop(s):
        s=s.strip()
        if not s: return True
        if re.fullmatch(r'\d{1,4}',s): return True
        if re.search(r'Learning Module \d+', s): return True
        core=re.sub(r'^\d{1,4}\s+','',s); core=re.sub(r'\s+\d{1,4}$','',core)
        c=re.sub(r'\s+',' ',core).strip().lower()
        if c in LABELS: return True
        if tn.startswith(c) and len(c)>14 and len(c)<len(tn): return True
        return False
    return drop

# ---------- section grab with table placeholders ----------
def grab(doc,a,b,header,stops,title):
    drop=header_filter(title)
    toks=[]; active=False; tables={}; ti=[0]
    for p in range(a,b):
        page=doc[p]; rows=page_rows(page); tbs=tables_on(page)
        used=set()
        for r in rows:
            s=r["text"]
            if not active:
                if s==header: active=True
                continue
            if s in stops: return toks,tables
            hit=None
            yc=(r["y"]+r["y1"])/2
            if r["math"]: tbs_scan=[]          # formulas render as images, never as tables
            else: tbs_scan=tbs
            for i,tb in enumerate(tbs_scan):
                x0,y0,x1,y1=tb["bbox"]
                if y0-2<=yc<=y1+2 and r["x"]>=x0-25 and r["x"]<=x1+25: hit=i; break
            if hit is not None:
                if hit not in used:
                    used.add(hit); ti[0]+=1; k=ti[0]
                    tables[k]=tbs[hit]["cells"]
                    toks.append({"k":"tbl","v":k})
                continue
            if drop(s): continue
            toks.append({"k":"row","x":r["x"],"t":s,"math":r["math"],"items":r["items"],"page":p})
    return toks,tables

# ---------- math rendering ----------
BAR=re.compile(r'^[_—–\-\s]+$')
def render_math(doc,group,store):
    pg=doc[group[0]["page"]]
    xs=[z["bbox"][0] for r in group for z in r["items"]]
    x1s=[z["bbox"][2] for r in group for z in r["items"]]
    ys=[z["bbox"][1] for r in group for z in r["items"]]
    y1s=[z["bbox"][3] for r in group for z in r["items"]]
    rect=pymupdf.Rect(min(xs)-5,min(ys)-4,min(max(x1s)+5,pg.rect.x1),max(y1s)+4)
    if rect.width<5 or rect.height<5: return None
    pm=pg.get_pixmap(matrix=pymupdf.Matrix(ZOOM,ZOOM),clip=rect,alpha=True)
    k="m%d"%(len(store)+1)
    store[k]=base64.b64encode(pm.tobytes("png")).decode()
    return k

def toks_to_text(doc,toks,store,do_math):
    """Build a single string with \x00T<n>\x00 / \x00M<n>\x00 placeholders."""
    parts=[]; i=0; mmap={}
    while i<len(toks):
        t=toks[i]
        if t["k"]=="tbl":
            parts.append("\n\x00T%d\x00\n"%t["v"]); i+=1; continue
        if do_math and t.get("math"):
            j=i; grp=[t]
            while j+1<len(toks) and toks[j+1]["k"]=="row" and toks[j+1].get("math") \
                  and toks[j+1]["page"]==t["page"]:
                j+=1; grp.append(toks[j])
            its=[z for g in grp for z in g["items"]]
            complex_=any(BAR.fullmatch(norm(z["t"])) for z in its) or \
                     len({round(z["bbox"][1]) for z in its})<len(its)
            if complex_ and len(its)>=2:
                k=render_math(doc,grp,store)
                if k:
                    n=len(mmap)+1; mmap[n]=k
                    parts.append("\n\x00M%d\x00\n"%n); i=j+1; continue
            for g in grp:
                if not BAR.fullmatch(g["t"]): parts.append(g["t"])
            i=j+1; continue
        parts.append(t["t"]); i+=1
    return "\n".join(parts), mmap

def chunkify(text,tables,mmap,store):
    """Split placeholder text into ordered chunks."""
    out=[]; pos=0
    for m in TOK.finditer(text):
        pre=text[pos:m.start()]
        if pre.strip(): out.append({"t":"x","v":dehy(pre)})
        if m.group(1)=="T":
            cells=tables.get(int(m.group(2)))
            if cells: out.append({"t":"b","v":cells})
        else:
            k=mmap.get(int(m.group(2)))
            if k: out.append({"t":"i","v":k})
        pos=m.end()
    tail=text[pos:]
    if tail.strip(): out.append({"t":"x","v":dehy(tail)})
    return [c for c in out if c["t"]!="x" or c["v"]]

def plain(text):
    return dehy(TOK.sub(" ",text))

# ---------- question segmentation ----------
VIGRE=re.compile(r'^The following information relates to questions?\s*(.*)$',re.M|re.I)
def opt_split(body):
    pos={}
    for L in 'ABC':
        m=re.search(r'^'+L+r'\.\s',body,re.M)
        if not m: break
        if pos and m.start()<max(pos.values()): break
        pos[L]=m.start()
    if len(pos)<3: return body.strip(),{}
    order=['A','B','C']
    if sorted(pos,key=lambda k:pos[k])!=order: return body.strip(),{}
    stem=body[:pos['A']]
    opts={}
    for i,k in enumerate(order):
        st=pos[k]+3
        en=pos[order[i+1]] if i+1<len(order) else len(body)
        opts[k]=body[st:en].strip()
    return stem.strip(),opts

def segment(text,maxn):
    vigs=[]
    for m in VIGRE.finditer(text):
        tail=m.group(1).strip()
        src=tail if re.search(r'\d',tail) else text[m.end():m.end()+40]
        mm=re.search(r'(\d+)\s*[-‒–]\s*(\d+)',src)
        lo,hi=(int(mm.group(1)),int(mm.group(2))) if mm else (None,None)
        vigs.append({"id":len(vigs)+1,"lo":lo,"hi":hi,"start":m.start(),"he":m.end()})
    starts={}; pos=0
    for n in range(1,maxn+1):
        cands=[mo.start() for mo in re.finditer(r'^'+str(n)+r'\.\s',text[pos:],re.M)]
        if not cands: continue
        pick=None
        for c in cands:
            if re.search(r'^A\.\s',text[pos+c:pos+c+2600],re.M): pick=pos+c; break
        if pick is None: pick=pos+cands[0]
        starts[n]=pick; pos=pick+2
    qs=[]; order=sorted(starts)
    for i,n in enumerate(order):
        st=starts[n]; en=starts[order[i+1]] if i+1<len(order) else len(text)
        for v in vigs:
            if st<v["start"]<en: en=min(en,v["start"])
        body=re.sub(r'^'+str(n)+r'\.\s*','',text[st:en])
        stem,opts=opt_split(body)
        qs.append({"num":n,"stem":stem,"opts":opts,"vig":None})
    for j,v in enumerate(vigs):
        nxt=vigs[j+1]["start"] if j+1<len(vigs) else len(text)
        f=starts.get(v["lo"]) if v["lo"] else None
        end=f if (f and v["he"]<f<=nxt) else nxt
        raw=text[v["he"]:end]
        raw=re.sub(r'^\s*\d+\s*[-‒–]\s*\d+\s*','',raw)
        v["raw"]=raw
    for q in qs:
        for v in vigs:
            if v["lo"] and v["hi"] and v["lo"]<=q["num"]<=v["hi"]: q["vig"]=v["id"]; break
    return vigs,qs

ANS=re.compile(r'^(?:The correct answer is\s+([ABC])|Answer\s+([ABC])\s+is\s+correct|([ABC])\s+is\s+(?:correct|the correct))\b',re.I)
def segment_sol(text,):
    sols={}; cur=None; pos=0
    marks=[]
    for m in re.finditer(r'^(\d{1,3})\.\s*',text,re.M):
        n=int(m.group(1)); rest=text[m.end():m.end()+60]
        if ANS.match(rest) or (marks and n==marks[-1][0]+1) or (not marks and n==1):
            marks.append((n,m.start(),m.end()))
    for i,(n,st,he) in enumerate(marks):
        en=marks[i+1][1] if i+1<len(marks) else len(text)
        body=text[he:en]
        m=ANS.match(plain(body)[:60])
        sols[n]={"a":(m.group(1) or m.group(2) or m.group(3)).upper() if m else None,"raw":body}
    return sols

# ---------- TOC / LOS (proven) ----------
def toc_cells(doc):
    cells=[];started=False
    for p in range(0,min(14,doc.page_count)):
        rows=page_rows(doc[p])
        if not started:
            if any(r["text"]=="CONTENTS" for r in rows): started=True
            else: continue
        if cells and any(re.match(r'^How to Use the CFA',r["text"]) and r["x"]<140 for r in rows): break
        for r in rows:
            for x,t in r["cells"]:
                if t: cells.append((x,t))
    return cells
SKIP={'practice problems','solutions','references','summary','appendix','glossary'}
def parse_toc(doc):
    mods=[];cur=None;buf=[];bx=None
    def flush(page):
        nonlocal buf,bx
        title=re.sub(r'\s+',' ',' '.join(buf)).strip(); x=bx; buf=[];bx=None
        if not title or cur is None: return
        if cur["title"] is None: cur["title"]=title; cur["page"]=page; return
        if title.lower() in SKIP: return
        lvl=1 if x is None or x<255 else (2 if x<281 else 3)
        cur["sections"].append({"t":title,"p":page,"l":lvl})
    for x,t in toc_cells(doc):
        m=re.fullmatch(r'Learning Module (\d+)',t)
        if m:
            buf=[];bx=None
            cur={"num":int(m.group(1)),"title":None,"page":None,"sections":[]}
            mods.append(cur); continue
        if cur is None: continue
        if re.fullmatch(r'\d{1,4}',t) and x>460: flush(int(t)); continue
        if re.fullmatch(r'[ivxlIVXL]{1,6}',t) and x>460: buf=[];bx=None; continue
        m2=re.match(r'^(.*?)[\s\t]+(\d{1,4})$',t)
        if m2 and len(m2.group(1).strip())>2:
            if bx is None: bx=x
            buf.append(m2.group(1).strip()); flush(int(m2.group(2))); continue
        if bx is None: bx=x
        buf.append(t)
    mods=[m for m in mods if m["title"]]
    for m in mods:
        seen=set();keep=[]
        for s in m["sections"]:
            k=(s["t"].lower(),s["p"])
            if k in seen: continue
            seen.add(k);keep.append(s)
        m["sections"]=keep
    best={}
    for m in mods:
        c=best.get(m["num"])
        if c is None or len(m["sections"])>len(c["sections"]): best[m["num"]]=m
    return [best[k] for k in sorted(best)]

def parse_los(doc,a,b):
    los=[];buf=[];active=False;prev=None
    for p in range(a,min(a+3,b)):
        for r in page_rows(doc[p]):
            t=r["text"]
            if not active:
                if 'The candidate should be able to' in t: active=True;prev=r["y"]
                continue
            if re.match(r'^(INTRODUCTION|L E A R N I N G)',t) or re.fullmatch(r'\d{1,4}',t):
                if buf: los.append(' '.join(buf));buf=[]
                active=False;break
            if prev is not None and r["y"]-prev>14 and buf: los.append(' '.join(buf));buf=[]
            buf.append(t);prev=r["y"]
        if not active: break
    if buf: los.append(' '.join(buf))
    return [re.sub(r'\s+',' ',x).strip() for x in los if len(x)>12 and not re.match(r'^(Mastery|LEARNING)',x)]

def lm_starts(doc):
    return [i for i in range(doc.page_count) if 'L E A R N I N G M O D U L E' in doc[i].get_text().replace(' ',' ')]

# ================= MAIN =================
DATA={"topics":[]}; MATH={}; st=collections.Counter()
for v in range(1,11):
    doc=pymupdf.open(PDF.format(v)); mods=parse_toc(doc); starts=lm_starts(doc)
    mods=mods[:len(starts)]; bounds=starts+[doc.page_count]
    topic={"id":"T%d"%v,"vol":v,"name":VOL[v],"w":WEIGHT[v],"mods":[]}
    for k,m in enumerate(mods):
        a,b=bounds[k],bounds[k+1]
        los=parse_los(doc,a,b)
        ptok,ptab=grab(doc,a,b,'PRACTICE PROBLEMS',{'SOLUTIONS'},m['title'])
        stok,stab=grab(doc,a,b,'SOLUTIONS',{'PRACTICE PROBLEMS'},m['title'])
        ptext,pmm=toks_to_text(doc,ptok,MATH,False)
        stext,smm=toks_to_text(doc,stok,MATH,True)
        sols=segment_sol(stext)
        vigs,qs=segment(ptext,max(sols) if sols else 0)
        MC=[];CR=[]
        for q in qs:
            s=sols.get(q['num'])
            if not s: continue
            expl=chunkify(s['raw'],stab,smm,MATH)
            if len(q['opts'])==3 and s['a'] and len(plain(q['stem']))>15:
                MC.append({"n":q['num'],"s":plain(q['stem']),
                           "o":[plain(q['opts'][c]) for c in 'ABC'],
                           "a":"ABC".index(s['a']),"v":q['vig'],"e":expl})
            elif len(q['opts'])==0 and len(plain(q['stem']))>25:
                CR.append({"n":q['num'],"s":plain(q['stem']),"e":expl})
        VG=[]
        for vg in vigs:
            ch=chunkify(vg['raw'],ptab,pmm,MATH)
            if sum(len(c['v']) for c in ch if c['t']=='x')>60 or any(c['t']=='b' for c in ch):
                VG.append({"id":vg['id'],"r":("%s-%s"%(vg['lo'],vg['hi'])) if vg['lo'] else "","c":ch})
        keep={x['id'] for x in VG}
        for q in MC:
            if q['v'] not in keep: q['v']=None
        topic["mods"].append({"n":m['num'],"t":m['title'],"p":m['page'],
            "sec":[[s['t'],s['p'],s['l']] for s in m['sections']],"los":los,
            "vig":VG,"q":MC,"cr":CR})
        st['mc']+=len(MC); st['cr']+=len(CR); st['vig']+=len(VG); st['los']+=len(los)
        st['tbl']+=sum(1 for x in VG for c in x['c'] if c['t']=='b')
        st['etbl']+=sum(1 for q in MC for c in q['e'] if c['t']=='b')
        st['img']+=sum(1 for q in MC for c in q['e'] if c['t']=='i')
    DATA["topics"].append(topic); doc.close()
    print(f"V{v} done  mc={st['mc']} vigtables={st['tbl']}")
print("\nTOTALS",dict(st),"math images",len(MATH))
json.dump(DATA,open(f"{SP}/curriculum2.json","w"),ensure_ascii=False)
json.dump(MATH,open(f"{SP}/mathimg2.json","w"))
print("curriculum2.json",round(os.path.getsize(f"{SP}/curriculum2.json")/1e6,2),"MB")
