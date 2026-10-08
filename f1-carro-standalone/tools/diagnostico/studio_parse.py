import re, sys
ev=[];cur=None;hdr=None
for line in open(sys.argv[1] if len(sys.argv)>1 else 'diagnostico/studio_lab_run1.txt'):
    m=re.search(r'##### PULO #(\d+)\s+trecho=(.*?)\s+vel=(\d+).*?t=([\d.]+) \(ΔVy=([\d.]+)',line)
    if m: cur={'n':int(m[1]),'tr':m[2][:30],'v':m[3],'t0':float(m[4]),'dvy':m[5],'rows':[]}; ev.append(cur); continue
    if 'TEL,t,' in line: hdr=line.split('TEL,')[1].split('  -')[0].strip().split(','); continue
    if 'TEL,' in line and cur:
        body=line.split('TEL,')[1].split('  -  Cliente')[0].strip()
        mm=re.search(r' \(x(\d+)\)$',body); rep=int(mm[1]) if mm else 1
        body=re.sub(r' \(x\d+\)$','',body)
        vals=body.split(',')
        tail=vals[-26:]; r={'t':float(vals[0]),'trecho':','.join(vals[1:-26])}
        for k,v in zip(hdr[2:],tail): r[k]=float(v)
        for _ in range(rep): cur['rows'].append(r)
W=['FD','FE','TD','TE']
for e in ev:
    R=e['rows']; t0=e['t0']
    dt=(R[-1]['t']-R[0]['t'])/(len(R)-1)
    air=[r for r in R if r['rodasNoChao']==0]
    # longest contiguous airborne
    best=cur_=0
    for r in R:
        cur_=cur_+1 if r['rodasNoChao']==0 else 0; best=max(best,cur_)
    # integrate chassis height change from vy
    z=0;zs=[]
    for r in R: z+=r['vyChassi']*dt; zs.append(z)
    def rng(k): xs=[r[k] for r in R]; return min(xs),max(xs)
    print(f"#{e['n']} {e['tr']:30s} v={e['v']} dt={dt*1000:.1f}ms  semRodas={len(air)} maiorSeq={best} ({best*dt*1000:.0f} ms)")
    print("   trechos:",sorted(set(r['trecho'][:22] for r in R)))
    print("   folga max por roda:", {w:round(rng('chao'+w)[1],3) for w in W})
    print("   pos min/max:", {w:tuple(round(x,3) for x in rng('pos'+w)) for w in W})
    print("   vy %.1f..%.1f  arf %.2f..%.2f  rol %.2f..%.2f  dir %.1f..%.1f / %.1f..%.1f  df %.0f..%.0f"%(*rng('vyChassi'),*rng('arfagem'),*rng('rolagem'),*rng('dirFD'),*rng('dirFE'),*rng('downforce')))
    print("   Δaltura chassi (integrado) %.3f..%.3f"%(min(zs),max(zs)))
