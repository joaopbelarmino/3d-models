# F1 standalone (carro de teste de pista)

Este é o carro `ServerStorage.Carros.Carro` do jogo de F1 (`italy.rbxl`), tirado do jogo e rodando
sem nenhum sistema de corrida. A física, a suspensão, a direção, a aceleração, o freio, o câmbio,
a aderência, as colisões, a massa, o centro de massa, os `CustomPhysicalProperties`, os constraints,
os attachments, as câmeras e o HUD de pilotagem continuam os do original.

| arquivo | para que serve |
|---|---|
| `F1_Carro_Standalone_Teste.rbxl` | Mapa de teste pronto. Abra no Studio, aperte **Play** e sente no carro. |
| `Spa_F1_Teste.rbxl` | Spa-Francorchamps com o carro instalado, no grid (posição 1). Abra e aperte **Play**. |
| `Spa_F1_Teste_Chassi.rbxl` | O mesmo mapa com dois carros: o completo (posição 1) e uma cópia sem nenhum modelo 3D, só chassi e Parts coloridas por função (posição 2). |
| `Laboratorio_Pulo.rbxl` | Laboratório de diagnóstico do "pulo": pista de testes controlados + telemetria quadro a quadro. Ver [`diagnostico/DIAGNOSTICO_PULO.md`](diagnostico/DIAGNOSTICO_PULO.md). |
| `Laboratorio_Pulo_V2.rbxl` | Laboratório com o `Carro` original e o `Carro_V2` (chassi anti-pulo) lado a lado. Ver [`diagnostico/CHASSI_V2.md`](diagnostico/CHASSI_V2.md). |
| `Spa_F1_Teste_V2.rbxl` | Spa com o `Carro` (posição 1) e o `Carro_V2` (posição 2). |
| `SPA_EM_GAME_V2.rbxl` | O seu `SPA_EM_GAME.rbxl` com o `Carro_V2` na posição 3 do grid (o resto do mapa idêntico). |
| `game_spa_2026_Audi.rbxl` | Seu `game_spa_2026` com o **Carro 2026 (Audi)** funcionando: chassi V2 + malhas e texturas do Audi, na posição 3 do grid. Ver [`diagnostico/AUDI_2026.md`](diagnostico/AUDI_2026.md). |
| `Carro_V2.rbxm` | Só o modelo `Carro_V2`, para um mapa que já tenha o pacote standalone. |
| `F1_Carro_Standalone.rbxm` | Pacote com tudo que o carro precisa. Arraste para o Studio e distribua as pastas (tabela abaixo). |
| `src/` | Os scripts em texto, para ler e comparar. |
| `tools/` | Ferramentas usadas na extração e na validação (ver "Como foi validado"). |

## Instalação do pacote em outro mapa

O `.rbxm` traz uma pasta `F1_Carro_Standalone` com uma subpasta para cada serviço. Mova o
**conteúdo** de cada subpasta para o serviço que tem o mesmo nome:

| no pacote | vai para | observação |
|---|---|---|
| `Workspace/Carro` | `Workspace` | Também pode ficar em `ServerStorage` e ser clonado para o Workspace. |
| `ReplicatedStorage/EventsCar` (`Join`, `Leave`, `DRS`) | `ReplicatedStorage` | Mantenha o nome `EventsCar`. |
| `ReplicatedStorage/ModuleCar` (`ModuleCar`, `ModuleSom`) | `ReplicatedStorage` | Mantenha o nome `ModuleCar`. |
| `ServerScriptService/CarroStandalone` | `ServerScriptService` | Collision group `nocolide` e personagem massless (ver abaixo). |
| `StarterGui/GUIcar`, `StarterGui/GUIMobileCar` | `StarterGui` | HUD de pilotagem para PC/gamepad e para celular. |
| `StarterPlayer/StarterCharacterScripts/ScriptCarro` | `StarterPlayer.StarterCharacterScripts` | Script de pilotagem do cliente. |
| `LEIA-ME` | não precisa ir para lugar nenhum | Só tem este resumo em comentários. |

O `Lighting.Blur` do mapa original é usado para o efeito de velocidade. Se o mapa novo não tiver um,
o script cria um igual (`BlurEffect`, `Size = 0`).

## ⚠️ Aderência: o chão da sua pista importa

O Roblox combina o atrito do pneu com o do chão por média ponderada pelo `FrictionWeight`. As peças
de pista do jogo original (`workspace.Pista`) usam:

```
CustomPhysicalProperties = Density 0.0001, Friction 0.5, Elasticity 0,
                           FrictionWeight 0, ElasticityWeight 0
```

Como o `FrictionWeight` do chão é 0, só conta o atrito do pneu (0.8 atrás e 0.7 na frente, no seco).
Num chão padrão (Plastic, `FrictionWeight` 1) o atrito efetivo cai para cerca de 0.47 e o carro fica
bem mais solto. **Use esses mesmos valores nas peças da pista nova.** No mapa de teste o chão
(`PistaTeste`) é uma cópia de uma peça `Track` da pista original, com esses valores.

## Spa-Francorchamps (`Spa_F1_Teste.rbxl`)

É o `SpaFrancorchamps_v3.rbxl` com o pacote instalado do jeito descrito acima, mais estes ajustes:

* **Carro na posição 1 do grid** (`Spa/Pista/Grid/GridPos01`), 12 studs atrás da linha da posição,
  com o bico no sentido da corrida. O jogador nasce no `SpawnPitLane`, que já existia no mapa; é
  só ir até o grid e sentar.
* **Física das superfícies igual à do jogo original.** No `v3` nenhuma peça tinha
  `CustomPhysicalProperties`, então valiam os padrões do material. No asfalto padrão a dianteira teria
  mais aderência (≈0.77 em vez de 0.7), e na grama padrão o carro perderia grip (≈0.53 em vez de 0.8).
  Foram aplicados os valores exatos das peças do mapa da Itália:
  * Asfalto da pista e do pit (`Pista/Superficie`, `PitLane/Superficie`, `Entrada`, `Saida`,
    `AreaDosBoxes`, `Paddock`), 9.048 peças: `Density 0.0001, Friction 0.5, Elasticity 0,
    FrictionWeight 0, ElasticityWeight 0`.
  * Grama (`Terreno`), 9.340 peças: `Density 2.403, Friction 2, Elasticity 0.1, FrictionWeight 0,
    ElasticityWeight 0`. No jogo original a grama tinha `FrictionWeight 0`, ou seja, o mesmo grip do
    asfalto. Se quiser a grama escorregadia, remova os `CustomPhysicalProperties` da pasta `Terreno`.
  * Zebras, linhas e marcações continuam sem colisão, como estavam. Guard rails e muros ficaram com
    o material padrão, como os muros do mapa original.
* **`Workspace.StreamingEnabled = false`**, como no jogo original. O `v3` vinha com streaming
  ligado; com ele, peças do carro podem não ter chegado ao cliente quando o servidor envia os dados
  no `Join`.
* **`workspace.ChuvaType = "SUN"`**, como no jogo original.

## Carro completo × só chassi (`Spa_F1_Teste_Chassi.rbxl`)

O arquivo é o `Spa_F1_Teste.rbxl` com um segundo carro, `Workspace.Carro_Chassi`, na posição 2 do
grid. A pista, o `Workspace.Carro` (completo) e todos os serviços são os mesmos do `Spa_F1_Teste.rbxl`.
Os dois carros usam o mesmo script de cliente, então dá para sair de um e entrar no outro.

O `Carro_Chassi` **não tem nenhum modelo 3D (MeshPart)**: só o chassi, as Parts e as constraints.

### O que saiu
`Corpo` (carroceria) com `AsaFrontal`, `AsaCopia`, `aerofolio`, aba do `DRS`, `EixoFrontal`,
`EixoTraseiro` e `Escapamento`; `Volante`; `Maos`; `Pneu` e `Aro` das 4 rodas; `Highlight`.

### O que isso muda (escolhido de propósito)
Parte dessas peças tinha função física. Sem elas, o carro-chassi **dirige igual** (motor, freio,
câmbio, direção, suspensão, downforce, aderência e massa do chassi e das rodas são os mesmos), mas:
* **Colisão**: só as rodas colidem. A carroceria, a asa dianteira e o aerofólio colidiam; o
  carro-chassi atravessa muros e zebras onde o completo bateria com a carroceria.
* **Massa**: a asa dianteira, a `AsaCopia`, a aba do DRS e o conjunto volante + mãos tinham massa
  própria (apesar de marcados `Massless`, cada um era a raiz da própria montagem, presa por
  constraint). O carro-chassi fica um pouco mais leve por isso. Chassi, assento, suportes e rodas,
  que carregam quase toda a massa, não mudaram.
* **Dano**: sem asa, não há quebra de asa, e sem asa quebrada também não há quebra de eixo.
* **Vácuo**: o carro-chassi não pega vácuo (o raio partia do `Corpo`). A placa `Vacuo` ficou,
  pendurada no `Chassi`, então um carro atrás dele ainda pega vácuo.
* **Som**: o clique de troca de marcha sai do chassi em vez do volante.

### Ajustes para funcionar sem as peças
* `Cam1`–`Cam4`, `CamR`, `RAYTD`, `RAYTE` e `RAYVACUO` eram soldados ao `Corpo`, que era soldado ao
  `Chassi`. Agora são soldados direto ao `Chassi`, na mesma posição, e continuam no mesmo bloco rígido.
* `Corpo/Vacuo` foi para `Chassi/Vacuo`, com a mesma solda ao `Chassi`.
* O attachment do servo do volante, que ficou sem uso, saiu.
* `Chassi/ScriptCar` do carro-chassi: linhas marcadas `[CHASSI]` tratam a falta de `Corpo`, asa, DRS,
  volante e pneu 3D.
* Script do cliente e `ModuleCar`, que são compartilhados: ganharam verificações `[CHASSI]` (sem `Maos`,
  sem aba do DRS, sem volante, sem `Corpo` para o vácuo). No carro completo elas não mudam nada:
  rodei de novo o teste de comparação com o script ofuscado original e os 89.704 valores continuam
  idênticos.

### Cores (só `Color` e `Transparency`; material e física intactos)
| categoria (atributo `Categoria`) | cor | peças |
|---|---|---|
| Chassi | cinza claro | `Chassi`, `SeatM` |
| Suporte | laranja | `EixoT` (suporte traseiro), `EixoFD`/`EixoFE` (mangas dianteiras) |
| Suspensao | amarelo | as 4 molas (`SpringConstraint`/`Mola`), desenhadas com `Visible = true` |
| Direcao | azul | as dobradiças `direcao`, desenhadas |
| Roda | vermelho | `RodaFD`, `RodaFE`, `RodaTD`, `RodaTE` (as rodas físicas, cilindros) |
| Camera | magenta (translúcido) | `Cam1`–`Cam4`, `CamR` |
| OutraFisica | verde | `RAY*` (pontos de referência); translúcida: placa `Vacuo` |

As cores também estão em `Carro_Chassi.LegendaCores`, como atributos.

### Organização
Nada que os scripts usam mudou de nome (`EixoFD`, `RodaFD`, `MotorD`, `direcao`, `Mola`,
`SpringConstraint`, `Cam1`… continuam iguais). Para facilitar a leitura, foram renomeadas só as peças
que nenhum script procura pelo nome:
* **Soldas**: `Solda_<Peça0>_<Peça1>`, por exemplo `Solda_Cam1_Chassi` ou `Solda_EixoT_Chassi`.
* **Attachments**: `Att_<constraint>@<onde a constraint está>`, por exemplo `Att_MotorD@EixoT+Mola@RodaTD`
  (usado pelo motor traseiro direito e pela mola traseira direita).

O nome antigo ficou guardado no atributo `NomeOriginal`.

### Verificação
* Comparei todas as propriedades de todas as instâncias que ficaram no `Carro_Chassi` com as do `Carro`.
  Só diferem cor, transparência, `Visible`/cor das constraints desenhadas, nomes, atributos, `UniqueId`,
  a mesma translação em todas as peças (posição 2 do grid, sem girar) e as 8 soldas que passaram do
  `Corpo` para o `Chassi`. Massa, densidade, tamanho, `CustomPhysicalProperties`, `Stiffness`,
  `Damping`, `FreeLength`, limites, torques e constraints estão iguais.
* Também rodei os scripts num ambiente simulado.
  * **Cliente**, mesmos 2.400 frames: o carro-chassi gera exatamente os mesmos valores de motor, freio,
    direção, downforce, marcha e velocímetro que o completo (27.870 valores).
  * **Servidor**, num mundo vazio sem nenhuma peça 3D: tuning, atrito por clima, `Join`/`Leave` e dono
    de rede são iguais aos do carro completo. Falta só a sequência de quebra e reparo da asa.

## Controles (os mesmos do jogo)

| ação | teclado | gamepad | celular |
|---|---|---|---|
| acelerar / frear (ré abaixo de 30) | W / S | R2 / L2 | botões |
| virar | A / D | analógico | botões |
| trocar câmera (1–4 fixas, 5 = câmera normal) | C | R1 | botão CAM |
| câmera traseira (segurando) | Shift | DPad para baixo | botão |
| controle de tração liga/desliga | T | L1 | botão TC |
| sair | pular | pular | botão sair |

O câmbio é automático, com 8 marchas, igual ao original.

## O que ficou e o que saiu

### Ficou igual ao original
* **Modelo do carro**: todas as peças, malhas, `CustomPhysicalProperties`, `CollisionGroup`,
  `Massless`, `RootPriority`, `CanCollide/CanTouch/CanQuery`, molas, `CylindricalConstraint` das
  rodas, `HingeConstraint` da direção, volante, DRS, `VectorForce` de downforce, `AlignOrientation`
  anti-capotamento, attachments, câmeras `Cam1–4`/`CamR`, som do motor e mãos do piloto. A
  comparação propriedade a propriedade com o original está em "Como foi validado".
* **`ModuleCar`**: `downforce`, `gearRPMAUT`, `TC`, `Traction`, `gatilhos` e `mobile` estão iguais,
  byte a byte. `Direcao` e `vacuo` ganharam só uma verificação `[CHASSI]` para o carro sem volante e
  sem carroceria; no carro completo elas não mudam nada.
* **`ModuleSom`**: igual.
* **Servidor do carro (`Chassi/ScriptCar`)**: mesmas constantes (`maxspeed 400`, `maxG -2000`,
  `MaxAng 13`, DRS, vácuo), mesma tabela de marchas e de força, mesmo pacote `dados` enviado ao
  cliente, mesmo `SetNetworkOwner`, mesma troca de composto e atrito por clima, mesmo
  anti-capotamento e mesma quebra da asa e dos eixos.
* **Cliente (`ScriptCarro`)**: o script do jogo estava **ofuscado**. As strings foram decodificadas e o
  código foi conferido linha a linha com a versão legível que estava no jogo
  (`ServerStorage.ScriptCarroLimpo1`). O laço por frame (downforce, TC, tração, freio, direção,
  vácuo, marchas, câmeras, FOV/blur, áudio) é o mesmo.

### Ajustes de spawn, agora em `Carro.Config`
No jogo, o servidor (`ServerScriptService.Principal` → `SpawnCarro`) aplicava no carro o tuning e a
sensibilidade que a garagem enviava. Sem mexer em nada na garagem, os valores eram:

| atributo | valor | onde é aplicado |
|---|---|---|
| `MolalturaF` / `MolalturaT` | 1.5 / 1.5 | `FreeLength` das molas dianteiras e traseiras |
| `RigidezF` / `RigidezT` | 25000 / 25000 | `Stiffness` das molas |
| `CamberF` / `CamberT` | 90 / 90 | `InclinationAngle` dos motores das rodas (traseiro direito = 180 − CamberT, como no original) |
| `Sensibilidade` | 1.5 | `AngularSpeed` da direção |
| `TC` | 1 | intensidade do controle de tração (o evento `Configs` do original) |

Atenção: os valores salvos nas molas do `ServerStorage.Carros.Carro` são um pouco diferentes
(`FreeLength` 1.596/1.496, `Stiffness` 24862), porque o modelo foi escalado em 0.997. Como o jogo
sempre sobrescrevia esses valores no spawn, quem dirigia nunca usava os valores crus. O script
standalone aplica os valores da garagem, como o jogo fazia. Com `AplicarTuning = false`, ficam os
valores crus do modelo.

### Removido (só existia para a corrida)
* `ServerScriptService`: `CorridasPublicas V1/V2/V3` (intermission, quali, alinhamento, largada,
  luzes, voltas, classificação, pódio, clima aleatório), `Principal` (garagem, spawn nos boxes, zonas
  de pit e DRS, servidores privados, DataStore `salas`) e `Script` (que punha `workspace.carros` no
  grupo `Default` na hora em que o servidor iniciava).
* No servidor do carro: checkpoints (`workspace.Checkpoints`), voltas, melhor volta, delta,
  cronômetro (`Timer`), `RaceType` (Quali/Aligne/Race), teleporte para o grid (`workspace.Largada`),
  pit stop por zona (`AreaPit`, `PITLOC`, módulo `Zone`), mensagens de rádio, `TimerUP` e os
  atributos de corrida do `Chassi`.
* No cliente: limitador de velocidade do box (`PIT`), limite de pista (`InLimits` contra
  `workspace.Pista`), destaque da `AreaPit`, HUD de corrida (posição, voltas, tempos, delta, lista de
  classificação via `UpdateGui`) e rádio (`Radio`).
* No `ModuleCar`: `InLimits` e `ListOrg`, que não eram usadas por mais nada.
* No HUD: os frames `Pos`, `Lap`, `Time`, `List`, `Radio` e `Flags`.
* RemoteEvents `SpawnCar`, `PIT`, `Configs`, `UpdateGui`, `Radio` e toda a pasta `Events` (`Code`,
  `KeyServer`, `NewCar`, `RaceUpdate`).
* Garagem, skins pagas, traçado dinâmico (`TraceScript`/`Trace`), chuva visual (`Rain`/`Chuva`) e
  mapa da Itália.

### Mudanças pequenas, todas marcadas com `[STANDALONE]` nos scripts
1. **Qualquer jogador pode dirigir.** No original só o dono (`Chassi.Player`) podia. Se você
   preencher `Chassi.Player`, a restrição volta a valer.
2. **Clima padrão `SUN`** quando o atributo `workspace.ChuvaType` não existe. O original daria erro
   num mapa vazio. Para testar chuva: `workspace:SetAttribute("ChuvaType", "LIGHT_RAIN")` ou `"RAIN"`.
3. **Reparo sem pit.** A quebra da asa e dos eixos continua igual. Quando o original mandaria o carro
   para o pit (eixo quebrado), o carro agora é reparado no próprio lugar, com o mesmo
   zera-velocidade e a mesma troca de dono de rede, só que sem teleporte. O carro também é reparado
   quando alguém senta nele.
4. **`CanQuery = false` nas partes do personagem** ao sentar. É o que o `SpawnCarro` original fazia,
   para que o personagem não bloqueie o raycast do vácuo.
5. **Cliente em `StarterCharacterScripts`**, com `WaitForChild` nas GUIs. Antes o servidor clonava o
   script no Character. Se o jogador trocar de carro, o laço passa para o carro novo; no original
   isso nunca acontecia, porque cada carro vinha com um script novo.
6. **Skin padrão**: Sauter ST25, a primeira skin grátis da garagem. É só textura e não afeta a
   física.

### DRS
O DRS era ligado pelas zonas `DRS1/2/3` da pista da Itália. O mecanismo continua no carro (asa
móvel, menos downforce e força extra), mas sem zonas ele fica desligado, como acontecia fora das zonas
no jogo. Para ligar numa pista nova, chame
`ReplicatedStorage.EventsCar.DRS:FireClient(player, true)` (e `false` para desligar).

### Scripts de servidor que continuam necessários (`CarroStandalone`)
* **Collision group `nocolide`**: cópia fiel do `NoColide` original. Rodas, corpo, asas, assento e
  volante estão salvos nesse grupo, que não colide consigo mesmo, e o personagem também entra nele.
  Sem o registro do grupo, essas peças cairiam no `Default` e passariam a colidir com o piloto e com
  outros carros.
* **Personagem massless**: cópia fiel do `Script#2` original. O personagem fica soldado ao
  `VehicleSeat`, então isso mantém a massa e o centro de massa iguais aos do jogo.

## Como foi validado
* **Referências**: todo caminho usado pelos scripts (`EventsCar.*`, `ModuleCar.*`, peças do carro,
  frames do HUD, `Lighting.Blur`) existe no pacote. Os scripts não usam mais `workspace.Pista`,
  `workspace.Checkpoints`, `workspace.Largada`, `Zone` nem `AreaPit`.
* **Compilação**: os 6 scripts compilam no compilador Luau (`tools/compile_check.luau`, rodando no Lune).
* **Servidor num mapa vazio** (`tools/harness_server.luau`): sem `ChuvaType`, `Checkpoints`, `Zones`
  ou `Pista`, o `ScriptCar` carrega, aplica o tuning, usa o composto SUN (atrito 0.8/0.7, os mesmos
  valores salvos nas rodas do original), envia `Join` e passa o dono de rede ao piloto. Também testei
  a quebra da asa e do eixo, com reparo e devolução do dono de rede, a troca para chuva (0.6/0.5) e a
  saída do carro (`Leave`). No mesmo mapa vazio, o script original não carrega.
* **Física do modelo**: comparei todas as propriedades de todas as instâncias do carro com o
  `ServerStorage.Carros.Carro` original. As únicas diferenças são as listadas acima (texturas da skin,
  atributos de corrida do `Chassi`, `AreaPit`/`TimerUP` removidos, `Config` adicionado). Posições e
  orientações estão idênticas bit a bit, e o carro está nas mesmas coordenadas em que foi salvo.
* **Comportamento do cliente**: `tools/harness.luau` roda o script **ofuscado original** e o
  standalone num ambiente Roblox simulado. Os dois recebem a mesma sequência de 2400 frames:
  aceleração, freio, ré, curvas, patinagem que aciona o TC, T/C/Shift, DRS ligado e desligado,
  gamepad (R2/L2), botões de celular, sair e entrar de novo. O harness registra cada valor escrito em
  motores, direção, volante, downforce, flap do DRS, câmera, FOV, blur, sons e HUD de pilotagem. As
  duas sequências saem **idênticas**: 89.704 valores, passando pelas 8 marchas e pelas 5 câmeras. O
  original roda fora do box e dentro da pista, que é a situação normal de corrida.

O harness não substitui um teste no Studio: ele confere a lógica dos scripts, mas não roda o motor de
física do Roblox. O próximo passo é abrir o `F1_Carro_Standalone_Teste.rbxl` e dar uma volta.
