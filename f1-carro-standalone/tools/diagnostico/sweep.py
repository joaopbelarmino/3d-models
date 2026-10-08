import sys, statistics; sys.path.insert(0,'.'); from sim import *
SCEN = [
 ('subida suave 3° @150',      ramp(3,40,smooth=15), 150, {}),
 ('subida suave 3° @300',      ramp(3,40,smooth=15), 300, {}),
 ('crista 2.8° @300',          kink(-2.8), 300, {}),
 ('vale 2.8° @300',            kink(2.8), 300, {}),
 ('quina 0.0016 @150',         step(0.0016), 150, {}),
 ('quina 0.0016 @300',         step(0.0016), 300, {}),
 ('quina 0.0043 @150',         step(0.0043), 150, {}),
 ('muitos triângulos @150',    facets(4,0.3,0.001,seed=3), 150, {}),
 ('muitos triângulos @300',    facets(4,0.3,0.001,seed=3), 300, {}),
 ('quina 0.0016 @150 freando', step(0.0016), 150, {'brake':1.0}),
 ('quina 0.0016 @150 acelerando', step(0.0016), 150, {'throttle':1.0}),
 ('quina 0.0016 @50',          step(0.0016), 50, {}),
]
VARIANTS = [
 ('ATUAL (como no arquivo)',          {}),
 ('sem colisão do assoalho',          {'floor':False}),
 ('rodas 4x mais leves',              {'mods':{'wheel_mass':0.25}}),
 ('amortecimento x3',                 {'mods':{'damping':3.0}}),
 ('restituição da roda 0',            {'mods':{'e_wheel':0.0}}),
 ('limites TRAVANDO a suspensão',     {'limits':'locked'}),
]
N=8
def jumped(s): return s['maxAir']>0.05 or s['maxRise']>0.3
def go(vname, vkw, sel=None):
    print(f'\n######## {vname}')
    tot=0
    for name,ter,v,kw in SCEN:
        if sel and name not in sel: continue
        res=[]
        for i in range(N):
            x0=-120.0 - i*(v*DT)/N
            s,_=run(ter,v,x0=x0,**kw,**vkw); res.append(s)
        p=sum(1 for s in res if jumped(s))/N; tot+=p
        vy=[s['maxVyBody'] for s in res]; vw=[s['maxWheelVy'] for s in res]
        air=max(s['maxAir'] for s in res); fl=sum(s['floorHits'] for s in res); st=sum(s['stopHits'] for s in res)
        print(f"  {name:32s} pula {p*100:4.0f}%  Vy chassi med {statistics.median(vy):5.1f} máx {max(vy):5.1f}  Vy roda máx {max(vw):5.1f}  no ar máx {air*1000:4.0f}ms  toques assoalho {fl}  batente {st}")
    print(f"  >>> soma das probabilidades de pulo: {tot:.2f}")
if __name__=='__main__':
    for vn,vk in VARIANTS: go(vn,vk)
