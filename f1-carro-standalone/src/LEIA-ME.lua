--[[
	F1 CARRO STANDALONE - para testar pistas
	=========================================
	Extraído de ServerStorage.Carros.Carro do jogo original (italy.rbxl).
	Física, suspensão, direção, aceleração, freio, câmbio automático,
	aderência, colisões, massa, CustomPhysicalProperties, constraints,
	attachments, câmeras e HUD de pilotagem são os do carro original.
	Todo o sistema de corrida foi removido.

	ONDE COLOCAR CADA PASTA (arraste o CONTEÚDO de cada pasta para o serviço):
	  Workspace/Carro                                 -> Workspace (ou ServerStorage, e clone para o Workspace)
	  ReplicatedStorage/EventsCar                     -> ReplicatedStorage
	  ReplicatedStorage/ModuleCar                     -> ReplicatedStorage
	  ServerScriptService/CarroStandalone             -> ServerScriptService
	  StarterGui/GUIcar e StarterGui/GUIMobileCar     -> StarterGui
	  StarterPlayer/StarterCharacterScripts/ScriptCarro -> StarterPlayer.StarterCharacterScripts
	Os nomes EventsCar e ModuleCar precisam continuar exatamente esses.

	CONTROLES (iguais ao original)
	  W/S ou setas  acelerar/frear (ré abaixo de 30)   A/D  virar
	  C             trocar câmera (1-4 fixas, 5 = câmera normal)
	  Shift (segurar) câmera traseira                  T    liga/desliga controle de tração
	  Gamepad: R2/L2 acelerar/frear, analógico vira, R1 câmera, L1 TC, DPad baixo câmera traseira
	  Celular: botões na tela (inclusive "sair")
	  Câmbio é automático (8 marchas, igual ao original).

	ADERÊNCIA - IMPORTANTE PARA A SUA PISTA
	  O Roblox mistura o atrito do pneu com o do chão (média ponderada pelo
	  FrictionWeight). As peças de pista do jogo original usam:
	    CustomPhysicalProperties = Density 0.0001, Friction 0.5, Elasticity 0,
	                               FrictionWeight 0, ElasticityWeight 0
	  Com FrictionWeight 0 no chão vale só o atrito do pneu (0.8 traseiro /
	  0.7 dianteiro no seco). Num chão padrão (Plastic, peso 1) o carro tem bem
	  menos grip. Use esses valores nas peças da pista nova.

	CLIMA
	  workspace:SetAttribute("ChuvaType", "SUN" | "LIGHT_RAIN" | "RAIN")
	  muda o composto/atrito dos pneus como no original (padrão SUN).

	AJUSTES (Carro.Config, atributos)
	  Os valores padrão são os que a garagem do jogo original enviava no spawn
	  sem nenhuma alteração. AplicarTuning = false usa os valores crus salvos
	  nas molas/motores do modelo (que o jogo original nunca usava).

	DRS
	  O DRS era ligado por zonas da pista antiga. O suporte continua no carro:
	  ReplicatedStorage.EventsCar.DRS:FireClient(player, true/false).
]]
return nil
