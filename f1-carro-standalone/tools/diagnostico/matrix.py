import sys; sys.path.insert(0,'.'); from sim import *
GEOS = [
 ('1 piso plano',                 flat()),
 ('2 subida suave 3° (rampa c/ transição 15)', ramp(3, 40, smooth=15)),
 ('3 descida suave 3°',           ramp(-3, 40, smooth=15)),
 ('4a mudança de inclinação: vale 2.8° (máx Spa)', kink(2.8)),
 ('4b mudança de inclinação: crista 2.8°',        kink(-2.8)),
 ('4c rampa seca 3° (sobe e volta)',               ramp(3, 30)),
 ('5a quina 0.0016 (p99 Spa)',     step(0.0016)),
 ('5b quina 0.0043 (máx Spa)',     step(0.0043)),
 ('5c quina 0.01',                 step(0.01)),
 ('6 poucos triângulos (40 studs, ±1°)',  facets(40, 1.0, 0.0, seed=3)),
 ('7 muitos triângulos (4 studs, ±0.3°, degraus 0.001)', facets(4, 0.3, 0.001, seed=3)),
]
def verdict(s):
    if s['maxAir']>0.05 or s['maxRise']>0.3: return 'PULA'
    if s['maxAir']>0.0 or s['maxRise']>0.05: return 'saltita'
    return 'ok'
def fmt(s):
    return (f"Vy_chassi {s['maxVyBody']:6.1f}  Vy_roda {s['maxWheelVy']:6.1f}  subida {s['maxRise']:5.2f}  "
            f"no_ar {s['maxAir']*1000:4.0f}ms  assoalho {s['floorHits']:2d}  asa {s['wingHits']:2d}  batente {s['stopHits']:2d}  "
            f"curso [{s['minPos']:+.2f},{s['maxPos']:+.2f}]  {verdict(s)}")
if __name__=='__main__':
    for name,ter in GEOS:
        print('==',name)
        for v in (50,150,300):
            for df in (True,False):
                s,_=run(ter,v,downforce=df)
                print(f"   v={v:3d} downforce={'sim' if df else 'não'}: {fmt(s)}")
