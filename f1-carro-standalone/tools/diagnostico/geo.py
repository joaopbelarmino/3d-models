import sys,re,math; sys.path.insert(0,'.'); from props import load
F=r'-?\d+(?:\.\d+)?(?:e-?\d+)?|inf'
def cf(s):
    m=re.search(r'position: Vector3 \{ x: ('+F+'), y: ('+F+'), z: ('+F+r') \}, orientation: Matrix3 \{ x: Vector3 \{ x: ('+F+'), y: ('+F+'), z: ('+F+r') \}, y: Vector3 \{ x: ('+F+'), y: ('+F+'), z: ('+F+r') \}, z: Vector3 \{ x: ('+F+'), y: ('+F+'), z: ('+F+r') \}',s)
    v=[float(x) for x in m.groups()]; return v[:3],[v[3:6],v[6:9],v[9:12]]
def v3(s):
    m=re.search(r'x: ('+F+'), y: ('+F+'), z: ('+F+')',s); return [float(m.group(i)) for i in (1,2,3)]
def inv(c):
    p,R=c; Rt=[[R[j][i] for j in range(3)] for i in range(3)]
    return [-sum(Rt[i][k]*p[k] for k in range(3)) for i in range(3)],Rt
def mul(a,b):
    p1,R1=a;p2,R2=b
    return [sum(R1[i][k]*p2[k] for k in range(3))+p1[i] for i in range(3)],[[sum(R1[i][k]*R2[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
def col(R,j): return [R[i][j] for i in range(3)]
def rot(R,v): return [sum(R[i][k]*v[k] for k in range(3)) for i in range(3)]
class Car:
    def __init__(s, dump, root):
        s.d=load(dump); s.P=root
        s.c={p[len(root)+1:]:v for p,v in s.d.items() if p.startswith(root+'/')}
        s.chassi=cf(s.c['Chassi']['CFrame']); s.ci=inv(s.chassi)
    def world(s,rel):
        v=s.c[rel]
        if v['_class']=='Attachment':
            par='/'.join(rel.split('/')[:-1]); return mul(s.world(par), cf(v['CFrame']))
        return cf(v['CFrame'])
    def local(s,rel):  # in chassis frame
        return mul(s.ci, s.world(rel))
    def ref(s,rel,key):
        m=re.match(r'Ref\((.*)\)', s.c[rel].get(key,'')); return m.group(1)[len(s.P)+1:] if m else None
