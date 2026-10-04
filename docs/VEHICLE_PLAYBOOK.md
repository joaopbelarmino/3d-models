# Playbook: carro game-ready do zero (Blender por script)

Notas práticas tiradas do AE86 (14,8k tris, Roblox). Ler antes do próximo veículo.

## Regras
1. **Minuto 0–15: ferramentas antes de geometria.** Extrair as silhuetas do blueprint
   automaticamente, calibrar **cada vista separadamente** (os blueprints vêm com escala
   anisotrópica e offsets diferentes por vista) e validar a calibração com 2 medidas
   conhecidas por vista. Montar o overlay renderizado sobre o blueprint antes do 1º patch.
2. **Câmeras das fotos 3/4 a partir do minuto 15.** Ortográfica certa não garante que o
   carro "leia" certo. Comparar lado a lado com as fotos a cada iteração.
3. **Lista de peças fechada no início**, cada uma com volume próprio: carroceria,
   para-choques (perfil de seção!), saias, unidades de farol e lanterna com moldura e
   profundidade, vidros com borracha, retrovisores, caixas de roda, assoalho, frisos.
4. **Para cada peça, digitalizar a SEÇÃO do blueprint** (perfil lateral ponto a ponto)
   antes de modelar. Nunca chutar offsets "parece reto".
5. **Contorno vermelho do overlay que não bate é bug até prova em contrário.** Não
   descartar como "acessório" sem checar nas fotos.
6. **Mecanismos (pop-up, portas) desenhados no estado aberto E fechado no começo**, com
   restrições: fechado rente, sem invadir para-choque; aberto com a forma da referência.
7. **Distinguir pintura de geometria na primeira passada** e escrever a decisão
   (faixas, two-tone, frisos em relevo, emblemas).
8. **Zenki × kouki** (ou equivalente): confirmar qual geração cada foto mostra antes de usá-la.
9. Orçamento por peça fixado no início; checar a cada build.

## Técnicas que funcionaram
- Patches de Coons sobre curvas 3D de feature lines + campos de altura por vista (lateral
  W(s,z), topo Z(s,w)). Mantêm planos planos e vincos nítidos.
- `patch2d` com correção residual de bordas (o canto também precisa da correção!).
- Sweep em planta com perfil de seção por estação, para para-choques e saias.
- Rebaixo real (degrau duplicado) para faixa de grade/lanternas.
- Normais orientadas por componente conectado + voto ponderado por área com referência por peça.
- Teste de faces invertidas: emissão vermelha **só em raio de câmera** (Light Path) + ray-cast
  para identificar o objeto. Validar o teste com um caso mínimo.
- Script de pop-up no Roblox independente de eixo e escala (frente e escala deduzidas da geometria).
- FBX: triangulação temporária com `keep_custom_normals`, reimportar e conferir.
- Pipeline de um comando (build → export → renders → pranchas JPEG).

## Técnicas que falharam / custaram caro
- Preenchimento CDT com pontos de Steiner em superfície curva: shading ruim. Usar só em
  áreas planas (molduras, painel traseiro).
- Leques de triângulos até o centroide (paredes, tampas): bico e shading estranho.
- Patch de Coons com lado colapsado num ponto: gera ponta aguda. Arredondar o canto.
- `np.interp` sobre perfil com z não monotônico: friso serrilhado. Ordenar antes.
- Emissão do diagnóstico iluminando vizinhos: falsos positivos (perdi tempo nisso).
- Modificador Wireframe explodindo em face de área zero: o "erro" do render era bug de malha.
- Discutir mecanismo/eixo por raciocínio longo em vez de testar com caso mínimo.

## Verificações automáticas obrigatórias (rodar a cada build)
tris por objeto × orçamento · arestas não-manifold · faces de área ~0 e ângulo < 1° ·
laços de borda inesperados (buracos) · faces invertidas (render + ray-cast) · IoU da
silhueta por vista × blueprint (falha abaixo do limite) · interpenetração entre peças
(BVH) · pop-up: folga fechado e lente ⟂ frente aberto · pivôs · reimportação do FBX.

## Distribuição de 15k tris (referência)
Carroceria 6,5–7k · rodas 4×600–700 · para-choques 2,5–3k · faróis+lanternas 0,8–1k ·
vidros 0,5–0,7k · saias/retrovisores/detalhes 0,6–0,8k · reserva 0,5k.

## Checklist de fase
- **Blockout → refino:** overlays nas 4 vistas sem desvio > ~20 mm nas linhas principais;
  3/4 lado a lado com 2 fotos; peças separadas existem (mesmo que simples).
- **Refino → detalhes:** seções de para-choque/saias digitalizadas e conferidas; vincos
  marcados; clay com luz rasante sem ondulação; zero pontas/leques.
- **Detalhes → final:** faróis/lanternas com moldura e profundidade nas posições medidas;
  mecanismos testados aberto e fechado; todas as verificações automáticas verdes;
  orçamento ≤ 15k.

## Atalhos
- Reaproveitar `geom.py`, `sweep.py`, `fill_region`, `overlay.py`, `render.py` e os checks.
- Previews em 600 px e 8 amostras; render final só no fim.
- Agentes em paralelo para leitura de referências e crítica adversarial; um único
  escritor no código.
- Sinais de "casca genérica": para-choque sem mudança de seção, lanterna adesivo
  (sem moldura e profundidade), pop-up em cunha, cantos todos com o mesmo raio, 3/4 que não
  lembra a foto mesmo com as ortográficas certas.
