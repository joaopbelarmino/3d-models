"""Variantes do chassi V2 no modelo de arfagem (sim.py).

Reconfigura as globais do sim.py: massa das rodas, lastro suspenso nos mesmos pontos
(massa total e centro de massa iguais), amortecimento por eixo, elasticidades e
compensação de FreeLength para manter a mesma altura de rodagem.
"""
import sys, statistics
sys.path.insert(0, '.')
import sim

BASE = dict(SPRUNG=list(sim.SPRUNG), M_WF=sim.M_WF, M_WR=sim.M_WR,
            SPR_F=dict(sim.SPR_F), SPR_R=dict(sim.SPR_R), E_FLOOR=sim.E_FLOOR, E_WING=sim.E_WING)


def configure(wheel_density=0.7, cF=None, cR=None, e_body=None, ballast=True):
    f = wheel_density / 0.7
    mwf, mwr = BASE['M_WF'] * f, BASE['M_WR'] * f
    sprung = list(BASE['SPRUNG'])
    dF, dR = BASE['M_WF'] - mwf, BASE['M_WR'] - mwr          # massa tirada (por eixo)
    if ballast and f < 1:
        sprung += [(dF, sim.Z_F, sim.Y_WC), (dR, sim.Z_R, sim.Y_WC)]
    sim.SPRUNG = sprung
    sim.M_WF, sim.M_WR = mwf, mwr
    sim.M_B = sum(m for m, _, _ in sprung)
    sim.ZC = sum(m * z for m, z, _ in sprung) / sim.M_B
    sim.YC = sum(m * y for m, _, y in sprung) / sim.M_B
    sim.I_B = sum(m * ((z - sim.ZC) ** 2 + (y - sim.YC) ** 2) for m, z, y in sprung) + 8.157 * 23.435 ** 2 / 12
    sim.M_TOT = sim.M_B + mwf + mwr
    sim.SPR_F = dict(BASE['SPR_F']); sim.SPR_R = dict(BASE['SPR_R'])
    if ballast and f < 1:
        # mesma altura: mais FreeLength para segurar o peso extra (por roda)
        import math
        cosF = sim.SPR_F['dy0'] / math.hypot(sim.SPR_F['dx'], sim.SPR_F['dy0'])
        sim.SPR_F['free'] += (dF / 2) * sim.G / (sim.SPR_F['k'] * cosF)
        sim.SPR_R['free'] += (dR / 2) * sim.G / sim.SPR_R['k']
    if cF is not None: sim.SPR_F['c'] = cF
    if cR is not None: sim.SPR_R['c'] = cR
    sim.E_FLOOR = BASE['E_FLOOR'] if e_body is None else e_body
    sim.E_WING = BASE['E_WING'] if e_body is None else e_body
    return sim.M_TOT, sim.M_B, sim.ZC


SCEN = [
    ('subida suave 3° @150', sim.ramp(3, 40, smooth=15), 150, {}),
    ('subida suave 3° @300', sim.ramp(3, 40, smooth=15), 300, {}),
    ('crista 2.8° @300', sim.kink(-2.8), 300, {}),
    ('vale 2.8° @300', sim.kink(2.8), 300, {}),
    ('quina 0.0016 @150', sim.step(0.0016), 150, {}),
    ('quina 0.0016 @300', sim.step(0.0016), 300, {}),
    ('quina 0.0043 @150', sim.step(0.0043), 150, {}),
    ('muitos triângulos @150', sim.facets(4, 0.3, 0.001, seed=3), 150, {}),
    ('muitos triângulos @300', sim.facets(4, 0.3, 0.001, seed=3), 300, {}),
    ('quina 0.0016 @150 freando', sim.step(0.0016), 150, {'brake': 1.0}),
    ('quina 0.0016 @150 acelerando', sim.step(0.0016), 150, {'throttle': 1.0}),
    ('quina 0.0016 @50', sim.step(0.0016), 50, {}),
]
N = 8


def jumped(s): return s['maxAir'] > 0.05 or s['maxRise'] > 0.3


def go(vname, e_wheel, quiet=False):
    tot = 0; vys = []; airs = []
    lines = []
    for name, ter, v, kw in SCEN:
        res = []
        for i in range(N):
            x0 = -120.0 - i * (v * sim.DT) / N
            s, _ = sim.run(ter, v, x0=x0, e_wheel=e_wheel, **kw); res.append(s)
        p = sum(1 for s in res if jumped(s)) / N; tot += p
        vy = [s['maxVyBody'] for s in res]; vys.append(max(vy))
        air = max(s['maxAir'] for s in res); airs.append(air)
        st = sum(s['stopHits'] for s in res)
        lines.append(f"  {name:30s} pula {p*100:4.0f}%  Vy chassi máx {max(vy):5.1f}  no ar máx {air*1000:4.0f}ms  batente {st}")
    if not quiet:
        print(f'\n######## {vname}')
        print('\n'.join(lines))
    print(f"  >>> {vname:55s} soma pulos {tot:5.2f}   média Vy máx {statistics.mean(vys):5.1f}   no ar máx {max(airs)*1000:4.0f} ms")
    return tot


if __name__ == '__main__':
    # (nome, densidade roda, cF, cR, e_roda, e_corpo)
    V = [
        ('ORIGINAL', 0.7, None, None, 0.15, None),
        ('rodas leves + lastro', 0.15, None, None, 0.15, None),
        ('rodas leves + lastro + amort 350/350', 0.15, 350, 350, 0.15, None),
        ('rodas leves + lastro + amort 350/350 + elast 0', 0.15, 350, 350, 0.0, 0.0),
        ('só amort 350/200 + elast 0 (sem mexer massa)', 0.7, 350, 200, 0.0, 0.0),
    ]
    quiet = '-q' in sys.argv
    for vn, dens, cF, cR, ew, eb in V:
        configure(dens, cF, cR, eb)
        go(vn, ew, quiet)
