# Diagnóstico: por que o carro dá um pulo em pequenas irregularidades

**Nada da física do carro foi alterado.** Este documento diz o que foi medido, o que foi simulado e o
que ainda precisa ser confirmado no Studio. O laboratório para essa confirmação está em
`Laboratorio_Pulo.rbxl`.

## 1. Resposta curta

**Causa mais provável:** é a interação entre a roda e a pista, e o carro amplifica o efeito.

1. **A roda do Roblox é um cilindro rígido, sem pneu que deforme.** Qualquer quina, emenda ou
   mudança de inclinação vira, num único frame, uma velocidade vertical na roda de mais ou menos
   `velocidade × ângulo`:
   - mudança de inclinação de 2,8° a 300 studs/s: ≈ 15 studs/s para cima;
   - degrau de 0,0016 stud a 300 studs/s: até ≈ 24 studs/s, conforme o ponto do frame em que a roda
     cruza a aresta.

   Isso cresce com a velocidade e depende do instante exato, e é por isso que o pulo acontece
   "às vezes".
2. **A suspensão do carro não consegue absorver esse impulso:**
   - **Limites de curso invertidos** (`LowerLimit = +0.4986 > UpperLimit = −0.4986`) nos 4
     `CylindricalConstraint`. Se o Roblox aplicar esses limites como estão, ou ajustar um ao outro,
     a suspensão fica **travada**. Nesse caso, no modelo, o carro pula **3 vezes mais** (chassi a
     até 49 studs/s), e até uma quina de 0,0016 stud a 150 studs/s faz o carro pular em metade das
     passagens. **Este é o primeiro item a confirmar no Studio.**
   - **Massa invertida:** as rodas somam **29,4** de massa, contra **13,8** do que fica sobre as
     molas. Num carro real as rodas são 10–15% da massa total; aqui são 68%. A roda pesada recebe o
     impulso e a mola o passa para um chassi leve.
   - **Dianteira quase sem amortecimento:** 76% da massa suspensa fica no eixo dianteiro (as duas
     asas, 3,0 de massa, estão no bico), mas o `Damping` dianteiro é metade do traseiro (100 contra
     200). A razão de amortecimento fica em **0,13 na frente** e 0,49 atrás. A dianteira oscila e
     chega ao batente (−0,51) numa entrada de subida a 300.
3. **A pista (Spa) tem as imperfeições que disparam o problema:**
   - **Vértices que não coincidem:** cópias do "mesmo" vértice ficam até 0,05 stud fora de lugar na
     horizontal e até 0,0043 na vertical.
   - **Ângulos entre triângulos vizinhos:** 126 arestas com mais de 1°, 7 com mais de 2°, máximo de
     2,77°.
   - **Superfície em cunhas separadas:** são 8.320 `WedgePart`, então o Roblox enxerga cada emenda
     como uma aresta de verdade.

**Peso de cada lado:** a fonte do impulso é a interação roda rígida × aresta da pista. O que
transforma esse impulso em pulo é a configuração do carro: limites invertidos, massa mal distribuída
e dianteira sem amortecimento. Numa pista perfeitamente lisa o carro é estável; numa pista com
arestas, outro carro com suspensão bem amortecida sentiria muito menos.

## 2. O que foi verificado e como

| fonte | o que é |
|---|---|
| Arquivo `.rbxl` (medição exata) | geometria, attachments, eixos, limites, molas, massas (`UnscaledVolume` × escala), colisão real das malhas (decodifiquei o `PhysicalConfigData`/CSGPHS v8 do `Corpo`, `AsaFrontal`, `aerofolio` e `DRS`) e a malha de triângulos do Spa |
| Modelo numérico (`tools/diagnostico/sim.py`) | dinâmica vertical no plano do carro, com os valores exatos do arquivo, a 240 Hz, com contatos rígidos. **Não é o solver do Roblox**: serve para isolar o mecanismo e comparar hipóteses |
| Studio (a fazer) | `Laboratorio_Pulo.rbxl` monta as 10 situações e registra a telemetria quadro a quadro no motor real |

## 3. Achados no carro

| item | valor | efeito |
|---|---|---|
| Limites da suspensão (4 `CylindricalConstraint`) | `LowerLimit = +0.4986`, `UpperLimit = −0.4986` (invertidos) | se o motor aplicar assim, a suspensão trava (pior caso, ver tabela 5) |
| Eixo de deslizamento | −Y do chassi (para baixo); roda paralela ao eixo de giro (0,000°); attachment no centro da roda (erro < 0,001) | correto: sem roda excêntrica |
| Molas | `Stiffness` 25.000; `FreeLength` 1,5 (tuning da garagem); `Damping` 100 frente / 200 trás | frequência natural de 10,4 Hz na frente e 19,6 Hz atrás; **razão de amortecimento de 0,13 na frente** e 0,49 atrás |
| Mola dianteira | inclinada 18,4° em relação ao eixo de deslizamento | 10% menos rigidez vertical; empurra a roda de lado contra o eixo de deslizamento |
| Pré-carga dianteira | `FreeLength` 1,5 com comprimento geométrico de 1,5765 → a mola já puxa a roda | em repouso a dianteira fica comprimida −0,14 (traseira −0,01), com o carro 0,47° de bico para baixo |
| Massas | chassi 8,16 · assento 0,60 · mangas dianteiras 2×0,69 · `AsaFrontal` 1,50 · `AsaCopia` 1,50 · DRS 0,53 · volante+mãos ≈ 0,15 → **suspensa 13,8**. Rodas 2×6,87 + 2×7,85 = **29,4** | rodas pesadas demais em relação ao chassi |
| Peças "Massless" que têm massa | `AsaFrontal`, `AsaCopia`, `DRS`, `EixoFD`/`EixoFE`, volante+mãos: cada uma é raiz da própria montagem (presa por constraint), e o Roblox ignora `Massless` na raiz | `AsaCopia` é uma segunda asa invisível, com a mesma massa, também no bico |
| Peças que colidem com a pista | rodas (cilindros) · `Corpo` · `AsaFrontal` · `aerofolio`. Nenhuma colisão entre peças do próprio carro (grupo `nocolide`) | sem colisão duplicada; pneus 3D e partes invisíveis não colidem |
| Folga da colisão real até o chão (pose salva) | assoalho do `Corpo`: **0,29–0,36** de z −12 a +2 (um plano de 14 studs) · asa dianteira 0,90 · aerofólio 1,35 | com a pré-carga, a frente do assoalho fica a ~0,2. Não encostou em nenhum teste do modelo, mas tem **elasticidade 0,5** (quica muito se tocar) |
| Downforce | `VectorForce` no referencial do chassi (Y do carro), no centro de massa, até 2000 (≈ 23% do peso) | correta; não é a causa, e ajuda um pouco em alta |
| Direção | eixo vertical (0,1°), então esterçar não levanta o carro. Alvo ±13°, limite de 12° de um lado | em esterço total, o servo de 250.000 fica empurrando o batente (não gera pulo, mas tensiona) |
| DRS | attachments da dobradiça 0,23 stud fora de lugar | a constraint já começa violada |
| Massas pequenas entre grandes | manga (0,69) entre roda (6,87) e chassi | razão de 10:1, no limite do que o solver do Roblox resolve bem |
| Rodas × pista: elasticidade | roda 0,3 (peso 0) × pista 0 (peso 0) | combinação 0/0: confirmar no Studio |

## 4. Achados na pista (Spa)

| item | valor |
|---|---|
| Superfície | 8.320 `WedgePart` (triângulos de duas cunhas) |
| Ângulo entre triângulos vizinhos | mediana 0,18°, p99 1,16°, **máximo 2,77°**; 126 arestas > 1°, 7 > 2° |
| Vértices que deveriam coincidir | até **0,05** stud de diferença na horizontal; degrau vertical mediana 0,0002, p99 **0,0016**, máximo **0,0043** |

## 5. Testes controlados (modelo)

Cada caso rodou 8 vezes, mudando o ponto do frame em que a roda cruza a geometria. "Pula" significa
as 4 rodas no ar por mais de 50 ms ou o chassi subindo mais de 0,3. Resultados completos em
`tools/diagnostico/matrix_out.txt` e `sweep_out.txt`.

| situação | suspensão funcionando (±0,5) | suspensão travada (limites invertidos aplicados) |
|---|---|---|
| 1 piso plano | estável | estável |
| 2 subida suave 3° a 150 / 300 | pula 25% / 38% (a dianteira chega ao batente) | 100% / 88% |
| 3 descida suave 3° | saltita; pula a 300 sem downforce | — |
| 4 crista 2,8° a 300 | **100%** (o chão "foge" mais rápido que o carro cai) | 100% |
| 4 vale 2,8° a 300 | não pula (Vy da roda 17–19) | 25% |
| 5 quina 0,0016 a 50 / 150 / 300 | 0% / 0% / 12% | 0% / 50% / 38% |
| 5 quina 0,0043 a 150 | 0% | 50% |
| 6 poucos triângulos | saltita, sem pular | — |
| 7 muitos triângulos a 150 / 300 | 0% / **50%** | 88% / 100% |
| 9 com × sem downforce | o downforce reduz um pouco em alta; não é causa | — |
| 10 freando × acelerando (quina 0,0016 a 150) | freando 12% · acelerando 0% | 38% · 50% |

**Combinação que faz pular:** velocidade alta (≥ 150, principalmente 300) + aresta da pista (mudança de
inclinação ≥ ~1,5°, emenda com degrau ≥ ~0,001 ou entrada de rampa) + dianteira pouco amortecida. Com
a suspensão travada, basta velocidade média e qualquer emenda. Frear piora: carrega a frente e
aproxima a dianteira do batente.

**Frame do impulso** (registros em `tools/diagnostico/*.csv`): a roda recebe a velocidade vertical
inteira no frame em que cruza a aresta. A suspensão comprime em 1–3 frames (até −0,35 ou −0,51, no
batente), e o chassi ganha de +3 a +6 studs/s no frame seguinte. Pelo mesmo mecanismo, um pulo grande
vem quase sempre de uma roda dianteira.

**Variações hipotéticas, só no modelo** (soma das probabilidades de pulo nos 12 cenários; menor é
melhor):

| variação | soma |
|---|---|
| atual, suspensão funcionando | 2,38 |
| suspensão travada | 7,25 |
| sem colisão do assoalho | 2,38 (o assoalho não é a causa nesses testes) |
| amortecimento ×3 | 2,00 (zera os pulos nas quinas a 300 e na rampa a 150) |
| rodas 4× mais leves | 1,50 |
| restituição da roda 0 | 5,75 no modelo, mas esse resultado é sensível ao jeito como o modelo trata contato em repouso: **confirmar no Studio antes de usar** |

## 6. Recomendações, da menos para a mais invasiva

Nenhuma foi aplicada. Todas mantêm a dirigibilidade que existe hoje.

0. **Confirmar no Studio, sem mudar nada:** abrir `Laboratorio_Pulo.rbxl`, sentar no carro e olhar
   o diagnóstico de partida no Output (`LowerLimit`/`UpperLimit` como o motor está usando, e se
   `CurrentPosition` muda com o carro andando). É isso que decide entre os itens 1 e 2.
1. **Desinverter os limites** dos 4 `CylindricalConstraint` (`LowerLimit = −0.4986`,
   `UpperLimit = +0.4986`). Se o Roblox já tratava como ±0,5, nada muda. Se travava, a suspensão
   passa a funcionar como foi desenhada, e este é o maior ganho.
2. **Igualar o amortecimento relativo da dianteira:** subir o `Damping` dianteiro de ~100 para ~350,
   o que leva a razão de 0,13 para ~0,45, igual à traseira. Rigidez, altura e aderência continuam
   iguais; o bico deixa de oscilar e de bater no batente.
3. **Pista:** soldar os vértices do Spa (cópias do mesmo vértice com coordenadas idênticas) e
   suavizar as dobras acima de ~1°. Isso remove a fonte do impulso sem tocar no carro.
4. **Limpezas pequenas:**
   - alinhar a dobradiça do DRS (0,23 stud de erro);
   - limitar o alvo de direção a 12° ou abrir o batente para 13°;
   - rever se a `AsaCopia` (segunda asa invisível, 1,5 de massa no bico) precisa existir.
5. **Redistribuir a massa** (mais invasiva): diminuir a densidade das rodas e somar a mesma massa ao
   chassi, para manter a massa total e o centro de massa. Muda a inércia das rodas (arrancada e
   controle de tração), então precisa de ajuste fino.
6. **Mais invasiva, não recomendada agora:** dar complacência ao pneu (uma segunda mola) ou trocar
   por suspensão por raycast. Isso muda o modelo de dirigibilidade.

O pulo em **cristas secas acima de ~1,5° a 300** é física, não defeito: o chão desce mais rápido do que
o carro consegue cair (g + downforce). O tempo no ar é ≈ 2·v·Δθ / (196 + 46), ou seja, 0,12 s para
2,8° a 300. Isso só melhora suavizando a pista.

## 7. Como confirmar no Studio (`Laboratorio_Pulo.rbxl`)

* Ao dar Play, `ServerScriptService.LaboratorioPistas` monta à frente do carro uma reta de ~2 km, com
  placas nos trechos:
  - 0: entrada;
  - 1: plano;
  - 2: subida suave;
  - 3: descida suave;
  - 4: vale e crista de 2,8°;
  - 5: quinas de 0,0016 / 0,0043 / 0,01;
  - 6: poucos triângulos;
  - 7: muitos triângulos.

  As superfícies usam as mesmas propriedades físicas das peças de pista do jogo.
* `StarterPlayerScripts.TelemetriaPulo`, ao sentar no carro:
  - imprime o **diagnóstico de partida**: massas reais, centro de massa, limites e posição das
    suspensões;
  - mostra um painel ao vivo;
  - detecta **PULO** (as 4 rodas sem chão) e imprime no Output, em CSV, 0,5 s antes e 0,5 s depois,
    marcando o frame do impulso, o trecho, a velocidade e se o assoalho ou a asa encostaram.
* Teclas: **F** liga e desliga o downforce (teste 9); **G** imprime os últimos 3 s.
* Roteiro: passar por todos os trechos a ~50, ~150 e ~300. Repetir acelerando, freando e esterçando
  no trecho 5, e com o downforce desligado.

Para os testes 8 a 10 (velocidade, downforce e pedal), use as mesmas pistas. A telemetria registra a
velocidade, a força de downforce e o ângulo de direção em cada linha.
