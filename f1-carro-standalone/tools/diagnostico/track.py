import sys,re,math,collections; sys.path.insert(0,'.')
from props import load
from geo import cf, v3
def tris(d, prefix):
    out=[]
    for p,v in d.items():
        if p.startswith(prefix) and v['_class']=='WedgePart':
            (c,R)=cf(v['CFrame']); s=v3(v['Size'])
            X=[R[i][0] for i in range(3)]
            sgn=1 if X[1]>=0 else -1   # side face whose normal points up
            loc=[(sgn*s[0]/2,-s[1]/2,-s[2]/2),(sgn*s[0]/2,-s[1]/2,s[2]/2),(sgn*s[0]/2,s[1]/2,s[2]/2)]
            W=[tuple(c[i]+sum(R[i][k]*l[k] for k in range(3)) for i in range(3)) for l in loc]
            out.append((p,W,[sgn*x for x in X]))
    return out
