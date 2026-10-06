# F1 standalone (carro de teste de pista)

Este é o carro `ServerStorage.Carros.Carro` do jogo de F1 (`italy.rbxl`), tirado do jogo e rodando
sem nenhum sistema de corrida. A física, a suspensão, a direção, a aceleração, o freio, o câmbio,
a aderência, as colisões, a massa, o centro de massa, os `CustomPhysicalProperties`, os constraints,
os attachments, as câmeras e o HUD de pilotagem continuam os do original.

| arquivo | para que serve |
|---|---|
| `F1_Carro_Standalone_Teste.rbxl` | Mapa de teste pronto. Abra no Studio, aperte **Play** e sente no carro. |
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
* **`ModuleCar`**: `downforce`, `gearRPMAUT`, `TC`, `Traction`, `Direcao`, `vacuo`, `gatilhos` e
  `mobile` estão iguais, byte a byte.
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
