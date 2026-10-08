import sys,math,re,collections; sys.path.insert(0,'.')
from props import load; from geo import cf, v3
d=load(sys.argv[1])
parts=[]
for p,v in d.items():
    if p.startswith('Workspace/Laboratorio/') and v['_class'] in('Part','WedgePart') and v.get('CanCollide','Bool(true)')!='Bool(false)':
        c,R=cf(v['CFrame']); s=v3(v['Size'])
        m=re.search(r'"Trecho": BinaryString\(BinaryString \{ buffer: \[([0-9, ]*)\]',v.get('Attributes',''))
        tr=bytes(int(x) for x in m.group(1).split(',')).decode() if m else '-'
        parts.append((v['_class'],c,R,s,tr))
car_c,car_R=cf(d['Workspace/Carro/Chassi']['CFrame'])
fwd=[car_R[0][2],0,car_R[2][2]]; n=math.hypot(*fwd); fwd=[fwd[0]/n,0,fwd[2]/n]
lado=[fwd[2],0,-fwd[0]]
chao=d['Workspace/PistaTeste']; pc,_=cf(chao['CFrame']); y0=pc[1]+v3(chao['Size'])[1]/2
org=[car_c[0]+fwd[0]*30, y0, car_c[2]+fwd[2]*30]
def planes(kind,c,R,s):
    hx,hy,hz=s[0]/2,s[1]/2,s[2]/2; P=[]
    def add(nl,pl):
        nw=[sum(R[i][k]*nl[k] for k in range(3)) for i in range(3)]
        pw=[c[i]+sum(R[i][k]*pl[k] for k in range(3)) for i in range(3)]
        P.append((nw,pw))
    add([1,0,0],[hx,0,0]); add([-1,0,0],[-hx,0,0]); add([0,-1,0],[0,-hy,0]); add([0,0,1],[0,0,hz])
    if kind=='Part': add([0,1,0],[0,hy,0]); add([0,0,-1],[0,0,-hz])
    else:
        nl=[0,2*hz,-2*hy]; L=math.hypot(nl[1],nl[2]); add([0,nl[1]/L,nl[2]/L],[0,-hy,-hz])
    return P
# spatial index
grid=collections.defaultdict(list)
for k,c,R,s,tr in parts:
    P=planes(k,c,R,s); ms=max(s)
    for gx in range(int((c[0]-ms)//10),int((c[0]+ms)//10)+1):
        for gz in range(int((c[2]-ms)//10),int((c[2]+ms)//10)+1):
            grid[(gx,gz)].append((P,tr))
def top(x,z):
    best=None; btr=None
    for P,tr in grid.get((int(x//10),int(z//10)),[]):
        lo,hi=-1e9,1e9; ok=True
        for nw,pw in P:
            rhs=nw[0]*pw[0]+nw[1]*pw[1]+nw[2]*pw[2]-nw[0]*x-nw[2]*z
            if abs(nw[1])<1e-12:
                if rhs< -1e-7: ok=False;break
            elif nw[1]>0: hi=min(hi,rhs/nw[1])
            else: lo=max(lo,rhs/nw[1])
        if ok and hi>=lo-1e-9 and (best is None or hi>best): best=hi; btr=tr
    return best,btr
res=collections.OrderedDict(); DS=0.25; gaps=0
for lat in (-3.6,0.0,3.6):
    hist=[]; s=-5.0
    while s<2100:
        x=org[0]+fwd[0]*s+lado[0]*lat; z=org[2]+fwd[2]*s+lado[2]*lat
        h,tr=top(x,z)
        if h is None: gaps+=1; hist=[]; s+=DS; continue
        h-=y0
        r=res.setdefault(tr,dict(maxstep=0,maxkink=0,hmin=9,hmax=-9))
        r['hmin']=min(r['hmin'],h); r['hmax']=max(r['hmax'],h)
        hist.append(h)
        if len(hist)>=3:
            d1=hist[-2]-hist[-3]; d2=hist[-1]-hist[-2]
            st=abs(d2-d1)
            if st>0.0005: r['maxstep']=max(r['maxstep'],st)
            else: r['maxkink']=max(r['maxkink'],math.degrees(abs(math.atan(d2/DS)-math.atan(d1/DS))))
        s+=DS
print('samples falling into seams (no part hit):',gaps)
for tr,r in res.items():
    print(f"{tr:48s} altura {r['hmin']:+.4f}..{r['hmax']:+.4f}  maior degrau {r['maxstep']:.4f}  maior mudança de ângulo (sem degrau) {r['maxkink']:.2f}°")
