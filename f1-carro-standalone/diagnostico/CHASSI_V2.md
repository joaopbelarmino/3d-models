# Carro_V2: chassi anti-pulo

O `Carro_V2` é o `Carro` original com o chassi refeito para não transformar irregularidades pequenas
em pulo. A arquitetura é a mesma:

- mesmas peças, nomes e hierarquia;
- mesmos `CylindricalConstraint`, molas, dobradiças de direção, `VectorForce` e câmera;
- **os mesmos scripts, sem nenhuma linha mudada:** `ScriptCar`, `ScriptCarro`, `ModuleCar` e
  `ModuleSom`.

Ele anda, troca de marcha, freia, esterça, usa DRS, vácuo, TC e quebra de asa igual ao original. O
`Carro` original continua intacto em todos os arquivos.

| arquivo | o que tem |
|---|---|
| `Laboratorio_Pulo_V2.rbxl` | Laboratório de pulo com o `Carro` (original) e o `Carro_V2` lado a lado, mais a mesma telemetria |
| `Spa_F1_Teste_V2.rbxl` | Spa com o `Carro` no GridPos01 e o `Carro_V2` no GridPos02 |
| `Carro_V2.rbxm` | Só o modelo `Carro_V2`, para arrastar para um mapa que já tenha o pacote standalone instalado |

## O que mudou e por quê

O Studio mostrou o mecanismo do pulo (seção 8 do `DIAGNOSTICO_PULO.md`):

1. uma roda pesada leva um chute de uma aresta da pista;
2. o chute vai para um chassi leve;
3. a dianteira, quase sem amortecimento, fica oscilando a ~10 Hz;
4. as rodas saem do chão uma de cada vez.

O V2 ataca esses pontos sem colar o carro no chão: não há força extra para baixo, e a rigidez, a
altura e o atrito continuam iguais.

| # | mudança | original | V2 | por quê |
|---|---|---|---|---|
| 1 | densidade das 4 rodas | 0,7 (6,87 / 7,85 de massa) | **0,2** (1,96 / 2,24) | o chute que a pista dá na roda é proporcional à massa dela |
| 2 | lastro suspenso: `LastroFD/FE` (soldados às mangas) e `LastroTD/TE` (soldados ao `EixoT`) | — | **4,91 na frente / 5,61 atrás**, cubos invisíveis no centro de cada roda, sem colisão | devolve ao carro a massa tirada das rodas, no mesmo lugar |
| 3 | `Damping` das 4 molas | 99,3 na frente / 198,6 atrás | **300 / 300** | razão de amortecimento ≈ 0,31 na frente (era 0,13) e 0,35 atrás; a roda fica com ~0,65 |
| 4 | altura das molas (`Config.MolalturaF/T`, aplicada pelo `ScriptCar` no spawn) | 1,5 / 1,5 | **1,541 / 1,544** | segura o peso do lastro: **mesma altura de rodagem** e mesma folga do assoalho |
| 5 | elasticidade das rodas | 0,3 (peso 0) | **0** (peso 1) | a roda não quica ao bater numa aresta; com peso 1, vale 0 em qualquer chão |
| 6 | elasticidade de `Corpo`, `AsaFrontal` e `aerofolio` | 0,5 | **0** (mesma densidade e atrito) | se raspar no chão, arrasta em vez de quicar |
| 7 | limites dos 4 `CylindricalConstraint` | `Lower +0.4986 / Upper −0.4986` (invertidos) | **`−0.4986 / +0.4986`** | mesmo curso que o motor já usava, agora com os valores coerentes |
| 8 | `EixoFD` e `EixoFE` `Massless` | true | **false** | com o lastro, a manga deixa de ser a raiz da montagem; isso mantém os 0,69 dela como estavam |

**Consequências do lastro no centro da roda:**
- a massa total do carro, o centro de massa e a distribuição frente/trás ficam iguais;
- a carga em cada pneu fica igual, portanto a aderência também;
- as inércias de guinada, rolagem e arfagem ficam praticamente iguais;
- na frente, o lastro gira junto com a direção (está na manga), então a inércia da direção também
  fica parecida.

**O que não mudou:**
- rigidez (25.000);
- atrito dos pneus e combinação por `FrictionWeight`;
- câmber;
- torque, marchas, freio, TC, downforce, DRS e vácuo;
- direção, colisões e collision groups;
- câmeras e HUD.

## O que deve mudar na pilotagem

- **Rodas com menos inércia de giro (≈ 30% da original):** elas ganham e perdem rotação mais rápido.
  - Na arrancada, com o TC desligado, o patinar aparece mais cedo.
  - Com o TC ligado, ele corta antes.
  - A aderência máxima é a mesma, porque a carga e o atrito são os mesmos.
- **Suspensão mais firme nas oscilações, mas não mais dura:** a rigidez é a mesma. O carro deve
  parecer mais "assentado" nas zebras e nas emendas.
- **Crista seca acima de ~200 studs/s continua tirando o carro do chão.** Isso é física: o chão desce
  mais rápido do que o carro cai. Só suavizar a pista resolve.

## Resultado no modelo numérico

Mesmos 12 cenários e mesmo critério da seção 5 do diagnóstico (8 passagens por cenário).
Saída completa em `tools/diagnostico/sim_v2_out.txt`; para rodar de novo, use
`tools/diagnostico/sim_v2.py`.

| cenário | original: pula | V2: pula | Vy máx. do chassi (orig → V2) |
|---|---|---|---|
| subida suave 3° a 150 | 25% | **0%** | 10,3 → 3,2 |
| subida suave 3° a 300 | 38% | **0%** | 17,9 → 6,1 |
| crista seca 2,8° a 300 | 100% | 100% (física) | 13,9 → 14,9 |
| vale 2,8° a 300 | 0% | 0% | 6,3 → 4,8 |
| quina 0,0016 a 300 | 12% | **0%** | 15,7 → 3,8 |
| muitos triângulos a 300 | 50% | **0%** | 20,5 → 9,6 |
| quina freando a 150 | 12% | **0%** | 8,4 → 2,7 |
| **soma das chances de pulo** | **2,38** | **1,00** (só a crista) | média 9,3 → 4,8 |

**Por que não usei rodas ainda mais leves nem amortecimento ainda maior:** no modelo, rodas de
densidade 0,1 com `Damping` ≥ 450 ficam numericamente instáveis. Uma peça leve presa a um amortecedor
forte é o tipo de combinação que também faz o solver do Roblox tremer. A escolha 0,2 / 300 tem margem
dos dois lados.

## Como testar (`Laboratorio_Pulo_V2.rbxl`)

1. Dê Play. A pista de testes é montada à frente dos dois carros. O `Carro_V2` fica 12 studs ao lado
   do original, na mesma faixa.
2. Sente no `Carro` e faça o roteiro de antes (~150, ~200 e ~250). Depois saia (pular), sente no
   `Carro_V2` e repita.
3. A telemetria funciona nos dois. O diagnóstico de partida do V2 deve mostrar:
   - **AssemblyMass do chassi ≈ 19,97** (8,75 + 2 × 5,61);
   - **rodas 1,963 / 2,243**;
   - **`CurrentPosition` em repouso parecido com o do original** (frente ≈ −0,13, trás ≈ −0,02). Se a
     altura não bater, ajuste `Carro_V2.Config.MolalturaF/T`.
4. Compare o número de pulos, a folga máxima das rodas, a rolagem e a direção. Cole o Output aqui que
   eu analiso do mesmo jeito.

## Ajuste fino sem mexer em script

| quer… | mude |
|---|---|
| ainda menos pulo | `Damping` das 4 molas (até ~350) |
| arrancada mais parecida com a original | densidade das rodas para 0,3–0,35, e o lastro correspondente para menos (a massa do lastro é a diferença de massa da roda; o atributo `Massa` de cada lastro mostra o valor atual) |
| altura | `Carro_V2.Config.MolalturaF` / `MolalturaT` |
