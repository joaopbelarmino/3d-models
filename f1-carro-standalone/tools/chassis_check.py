import sys,re; sys.path.insert(0,'.'); from props import load
d=load('dump_ch/props.txt'); base=load('dump_spaout/props.txt')
A='Workspace/Carro'; B='Workspace/Carro_Chassi'
# 1) full car and Spa untouched
fa={p:v for p,v in base.items()}; fb={p:v for p,v in d.items() if not p.startswith(B)}
strip=lambda v:{k:x for k,x in v.items() if k!='UniqueId'}
same=set(fa)==set(fb) and all(strip(fa[p])==strip(fb[p]) for p in fa)
print('full car + Spa + services identical to previous file:', same)
if not same:
    for p in sorted(set(fa)^set(fb))[:5]: print('  only one side', p)
    for p in fa:
        if p in fb and fa[p]!=fb[p]:
            if strip(fa[p])!=strip(fb[p]): print('  diff', p, [k for k in fa[p] if fa[p].get(k)!=fb[p].get(k)][:5]); break
# 2) map chassis paths back to original names
def orig_path(p):
    parts=p[len(B):].split('/')
    out=[]; cur=B
    for seg in parts[1:]:
        cur=cur+'/'+seg
        m=re.search(r'"NomeOriginal": (?:String\("([^"]*)"\)|BinaryString\(BinaryString \{ buffer: \[([0-9, ]*)\] \}\))', d[cur].get('Attributes','')) if cur in d else None
        if m: out.append(m.group(1) if m.group(1) is not None else bytes(int(x) for x in m.group(2).split(',')).decode())
        else: out.append(seg)
    return A+('/' if out else '')+'/'.join(out)
pa={p:v for p,v in d.items() if p==A or p.startswith(A+'/')}
pb={orig_path(p):(p,v) for p,v in d.items() if p==B or p.startswith(B+'/')}
removed=sorted(set(pa)-set(pb)); added=sorted(set(pb)-set(pa))
print('removed:', [r[len(A):] for r in removed])
print('added:', [a[len(A):] for a in added])
F=r'-?\d+(?:\.\d+)?(?:e-?\d+)?'
D=None
VISUAL={'Color','Transparency','TextureContent','Attributes','Visible','UniqueId'}
from collections import Counter
cnt=Counter(); bad=0
def pos(s):
    m=re.search(r'position: Vector3 \{ x: ('+F+'), y: ('+F+'), z: ('+F+r') \}, orientation: (.*)',s)
    return [float(m.group(i)) for i in (1,2,3)], m.group(4)
for p in sorted(set(pa)&set(pb)):
    va=pa[p]; pbp,vb=pb[p]
    for k in sorted(set(va)|set(vb)):
        x,y=va.get(k),vb.get(k)
        if x==y: continue
        if k in VISUAL: cnt[('visual',k)]+=1; continue
        if k=='Source' and p.endswith('/ScriptCar'): cnt[('script',k)]+=1; continue
        if k in('CFrame','WorldPivotData','ModelMeshCFrame') and x and 'position' in x:
            (p1,o1),(p2,o2)=pos(x),pos(y)
            dd=tuple(round(p2[i]-p1[i],3) for i in range(3))
            if o1==o2 and (D is None or all(abs(dd[i]-D[i])<2e-3 for i in range(3))):
                D=D or dd; cnt[('translated',k)]+=1; continue
        if isinstance(x,str) and x.startswith('Ref('):
            # compare by original path of target
            ta=x[4:-1]; tb=y[4:-1] if y and y.startswith('Ref(') else y
            if tb and orig_path(tb)==ta: cnt[('ref same target',k)]+=1; continue
        bad+=1; print('PHYSICS-RELEVANT DIFF', p[len(A):], k, (x or '')[:90], '->', (y or '')[:90])
print(dict(cnt)); print('translation', D); print('unexpected diffs:', bad)
