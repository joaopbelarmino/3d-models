--[[
	ScriptCarro (cliente) - versão STANDALONE para teste de pista.

	No jogo original este LocalScript era ServerStorage.ScriptCarro (ofuscado),
	clonado pelo servidor para dentro do Character no spawn. Aqui ele fica em
	StarterPlayer.StarterCharacterScripts, que dá o mesmo efeito (roda dentro
	do Character e reinicia a cada respawn).

	O código abaixo é o mesmo do script ofuscado, com as strings decodificadas
	e os nomes de variáveis da versão legível (ServerStorage.ScriptCarroLimpo1),
	conferido linha a linha. A física (downforce, TC, tração, freio, direção,
	vácuo, marchas) é a mesma: tudo continua em ReplicatedStorage.ModuleCar.

	Linhas alteradas em relação ao original estão marcadas com [STANDALONE].
]]

-- ========= Services / Refs =========
local player    = game.Players.LocalPlayer
local replicate = game:GetService("ReplicatedStorage")
local run       = game:GetService("RunService")
local UIS       = game:GetService("UserInputService")
local SS        = game:GetService('SoundService')

-- ========= Remotes / Módulos =========
local events    = replicate:WaitForChild("EventsCar")
local DRSe      = events:WaitForChild("DRS")
-- [STANDALONE] removidos: events.PIT (zona do box) e events.Configs.
-- O nível de TC vinha do evento Configs (tabela Sensi da garagem, padrão 1).
local TCconfig = 1
local BrakeConfig = 1 -- (não era usado pela física no original)

local Modulecar = require(replicate:WaitForChild("ModuleCar"):WaitForChild("ModuleCar"))
local ModuleSom = require(replicate.ModuleCar:WaitForChild("ModuleSom")) -- áudio no módulo

-- ========= Estado de Input / PlayerModule =========
local ismobile, isgamepad = false, false
local Incar               = false

local camPosition = 2 -- isso vai definir qual a camera que o carro deve estar
local cameras
local maxCam
local CamR = false


local ModuleControl = require(
	player:WaitForChild("PlayerScripts")
		:WaitForChild("PlayerModule")
		:WaitForChild("ControlModule")
)

-- ========= GUI / Botões / Refs =========
local playergui = player:WaitForChild("PlayerGui")

local gearGUI, velocimetroGUI, TCGUI, gui, DRSGUI, Camgui -- (declarado aqui para preencher depois)

-- [STANDALONE] WaitForChild: no original o script só era criado depois que a
-- PlayerGui já existia; em StarterCharacterScripts ele pode rodar antes.
local buttons = playergui:WaitForChild("GUIMobileCar"):WaitForChild("Interface")
playergui:WaitForChild("GUIcar"):WaitForChild("Interface")
local BF, BT, BD, BE, BTC, SAIR, CAMB, ButtonR = buttons.Acel, buttons.Freio, buttons.Dir, buttons.Esq, buttons.TC, buttons.sair, buttons.CAM, buttons.ButtonR

local BFT, BTT, BDT, BET = false, false, false, false
local Gatilhos, RT, LT = 0, 0, 0

-- ========= Tuning / Car =========
local MaxSpeed
local MaxTorqueMotor
local maxG
local MaxAng
local minSound    = 1
local Maxsound    = 2.4
local MaxVolume   = 1
local DrsForceExtra
local VacuoForceExtra
local MaxDistanceVacuo

local GearForce
local marchasVelocity

local marchaAtual = 1
local TC          = true
local DRS         = false
local torqueFreio = 2500
local ExtraForce  = 0

local character = player.Character or script.Parent

local FOV   = 70 -- FOV PADRAO
local VelS  = 40 -- SENSAçAO DE VELOCIDADE
local VelB  = 5  -- blur maximo
local camera = workspace.Camera

-- [STANDALONE] o original usava game.Lighting.Blur, que existia no mapa
-- (BlurEffect, Enabled = true, Size = 0). Se o mapa não tiver, é criado igual.
local blur = game.Lighting:FindFirstChild("Blur")
if not blur then
	blur = Instance.new("BlurEffect")
	blur.Name = "Blur"
	blur.Size = 0
	blur.Enabled = true
	blur.Parent = game.Lighting
end

-- O script ofuscado usava estes fatores (resultado de 734.4 - 733 e 3.4 - 2
-- no código original); mantidos exatamente iguais.
local FATOR_RD = 734.4 - 733
local FATOR_RE = 3.4 - 2
local FATOR_FD = 860.4 - 859
local FATOR_FE = 1.4

-- ========= Helpers / Funções =========
local function GearRPM(VelocidadeAtual)
	return Modulecar.gearRPMAUT(VelocidadeAtual, marchasVelocity, GearForce, ExtraForce)
end


local isfirt = true
-- [STANDALONE] carro atualmente ligado a este script e conexões do loop.
-- No original o script era recriado a cada carro novo; aqui, se o jogador
-- sentar em OUTRO carro, as conexões antigas são desligadas e o RunCar roda
-- de novo para o carro novo (o loop por frame é o mesmo).
local carroAtual
local conexoesCarro = {}
local personagemOculto = false -- [CHASSI] usado só quando o carro não tem Maos
function RunCar(dados, som: Sound, marchasV, Gforce)
	isfirt = false
	for _, c in ipairs(conexoesCarro) do
		c:Disconnect()
	end
	table.clear(conexoesCarro)
	carroAtual = dados.carro
	-- Ajusta colisão do personagem
	if character:FindFirstChild('CollisionPart') then
		character.CollisionPart.CanCollide = false
	elseif character:FindFirstChild('HumanoidRootPart') then
		character.HumanoidRootPart.CanCollide = false
	end

	Incar = true

	-- Referências do chassi e controles
	local motorTraseiroD : CylindricalConstraint = dados.MotorD
	local motorTraseiroE : CylindricalConstraint = dados.MotorE
	local direcaoD       : HingeConstraint       = dados.DirD
	local direcaoE       : HingeConstraint       = dados.DirE
	local carro          : Part                  = dados.carro
	local DownForce      : VectorForce           = dados.DownForce
	local RodaTD         : Part                  = dados.RodaTD
	local RodaTE         : Part                  = dados.RodaTE
	local RodaFD         : Part                  = dados.RodaFD
	local RodaFE         : Part                  = dados.RodaFE
	local MotorDianteiroD: CylindricalConstraint = dados.MotorDianteiroD
	local MotorDianteiroE: CylindricalConstraint = dados.MotorDianteiroE
	local VolanteS       : HingeConstraint       = dados.VolanteS
	local DrsServo       : HingeConstraint       = dados.DrsServo

	-- [STANDALONE] removida a montagem dos raios RAYFD/RAYFE/RAYTD/RAYTE usada
	-- só pelo limite de pista (Modulecar.InLimits contra workspace.Pista).

	-- [STANDALONE] nível de TC configurável em Carro.Config (padrão 1, igual à garagem)
	local cfg = carro.Parent:FindFirstChild("Config")
	if cfg and type(cfg:GetAttribute("TC")) == "number" then
		TCconfig = cfg:GetAttribute("TC")
	end

	-- Configura variáveis do carro
	MaxSpeed          = dados.maxspeed
	maxG              = dados.maxG
	MaxAng            = dados.MaxAng
	DrsForceExtra     = dados.DrsForceExtra
	MaxDistanceVacuo  = dados.MaxDistanceVacuo
	VacuoForceExtra   = dados.VacuoForceExtra
	cameras           = dados.cameras

	maxCam = #cameras + 1

	marchasVelocity = marchasV
	GearForce       = Gforce

	-- ÁUDIO (módulo)
	local audio = ModuleSom.Init(carro, som, {
		minSound   = minSound,
		Maxsound   = Maxsound,
		MaxVolume  = MaxVolume,
		ClickParent = VolanteS and VolanteS.Parent, -- click de marcha vindo do volante ([CHASSI] sem volante: vai para o chassi)
	})

	local control

	if UIS.GamepadEnabled then
		control = 'gamepad'
	elseif UIS.TouchEnabled then
		control = 'mobile'
	elseif UIS.KeyboardEnabled then
		control = 'teclado'
	end

	table.insert(conexoesCarro, UIS.LastInputTypeChanged:Connect(function(input)
		if input == Enum.UserInputType.Touch then
			control = 'mobile'
		elseif input == Enum.UserInputType.Keyboard then
			control = 'teclado'
		elseif input == Enum.UserInputType.Gamepad1 then
			control = 'gamepad'
		end
	end))

	-- Loop por frame (cliente)
	table.insert(conexoesCarro, run.RenderStepped:Connect(function(dt)
		if not Incar then return end

		-- atualiza fisica/forças
		maxG = dados.maxG
		ExtraForce = 1
		if DRS then
			maxG = maxG / 2
			ExtraForce = ExtraForce + DrsForceExtra
		end
		ExtraForce = Modulecar.vacuo(carro, ExtraForce, MaxDistanceVacuo, VacuoForceExtra, MaxSpeed)

		-- Camera handling: posição fixa ou câmera custom
		if CamR then
			camera.CameraType = Enum.CameraType.Scriptable
			camera.CFrame = carro.CamR.CFrame
		elseif camPosition ~= 5 then
			camera.CameraType = Enum.CameraType.Scriptable
			camera.CFrame = cameras[camPosition].CFrame
			local maos = carro.Parent:FindFirstChild("Maos") -- [CHASSI] o carro só-chassi não tem mãos
			if not maos then
				-- mesmo efeito do bloco abaixo (esconder o personagem na câmera 1), sem as mãos
				if camPosition == 1 and not personagemOculto then
					personagemOculto = true
					for i,v :Part in ipairs(character:GetDescendants()) do
						if v:IsA('MeshPart') then
							v.Transparency = 1
						end
					end
				elseif camPosition ~= 1 and personagemOculto then
					personagemOculto = false
					for i,v :Part in ipairs(character:GetDescendants()) do
						if v:IsA('MeshPart') then
							v.Transparency = 0
						end
					end
				end
			elseif camPosition == 1 and carro.Parent.Maos.M1.LeftLowerArm.Transparency == 0 then
				for i,v : Part in ipairs(carro.Parent.Maos:GetDescendants()) do
					if v:IsA('MeshPart') then
						v.Transparency = 1
					end
				end

				for i,v :Part in ipairs(character:GetDescendants()) do
					if v:IsA('MeshPart') then
						v.Transparency = 1
					end
				end
			elseif camPosition ~= 1 and carro.Parent.Maos.M1.Transparency == 1 then
				for i,v : Part in ipairs(carro.Parent.Maos:GetDescendants()) do
					if v:IsA('MeshPart') then
						v.Transparency = 0
					end
				end
				for i,v :Part in ipairs(character:GetDescendants()) do
					if v:IsA('MeshPart') then
						v.Transparency = 0
					end
				end
			end
		else
			camera.CameraType = Enum.CameraType.Custom
		end


		-- Plataforma/input atual
		if control == 'gamepad' then
			gui = playergui.GUIcar.Interface
			isgamepad = true
			ismobile  = false
		elseif control == 'mobile' then
			gui = playergui.GUIMobileCar.Interface
			ismobile  = true
			isgamepad = false
			if playergui:FindFirstChild("TouchGui") then
				playergui.TouchGui.Enabled = false
			end
		elseif control == 'teclado' then
			gui = playergui.GUIcar.Interface
			isgamepad = false
			ismobile  = false
		end

		-- Pegar refs da GUI
		gearGUI        = gui.Velocimetro.Gear
		velocimetroGUI = gui.Velocimetro.Vel
		TCGUI          = gui.TC.display
		DRSGUI         = gui.DRS.display
		Camgui         = gui.CAM.display

		-- ---------------------------
		-- Velocidades / Marcha
		-- ---------------------------
		local VelRD = RodaTD.AssemblyAngularVelocity.Magnitude * FATOR_RD
		local VelRE = RodaTE.AssemblyAngularVelocity.Magnitude * FATOR_RE
		local VelFD = RodaFD.AssemblyAngularVelocity.Magnitude * FATOR_FD -- para áudio
		local VelFE = RodaFE.AssemblyAngularVelocity.Magnitude * FATOR_FE -- para áudio
		local VelocidadeAtual = (VelRD + VelRE) / 2

		local DadosGear = GearRPM(VelocidadeAtual, marchaAtual)
		marchaAtual     = DadosGear[1]
		MaxTorqueMotor  = DadosGear[2]
		local soundfator = 1 - DadosGear[3] -- 0..1 (quão perto do topo da marcha)

		-- ---------------------------
		-- Input
		-- ---------------------------
		local AslVelocity = carro.AssemblyLinearVelocity
		local move : Vector3 = ModuleControl:GetMoveVector()

		local TX, TY = 0, 0
		if ismobile then
			TY, TX = Modulecar.mobile(BFT, BTT, BET, BDT)
			playergui.GUIMobileCar.Enabled = true
			playergui.GUIcar.Enabled       = false
		elseif isgamepad then
			playergui.GUIMobileCar.Enabled = false
			playergui.GUIcar.Enabled       = true
			TX = move.X
			TY = Gatilhos
		else
			TX = move.X
			TY = -move.Z
			playergui.GUIcar.Enabled       = true
			playergui.GUIMobileCar.Enabled = false
		end

		local maxspeed = MaxSpeed
		-- [STANDALONE] removido o limitador de box e de limite de pista:
		-- no original, dentro da zona do pit OU com menos de 2 rodas sobre
		-- workspace.Pista, acima de 80 de velocidade o TY era forçado a -1 (freio).
		-- Fora do pit e dentro da pista (situação normal de corrida) esse bloco
		-- não fazia nada - que é o comportamento mantido aqui.

		-- ---------------------------
		-- GUI Atualização
		-- ---------------------------
		gearGUI.Text        = marchaAtual
		velocimetroGUI.Text = math.floor(AslVelocity.Magnitude)
		Camgui.Text         = camPosition

		-- TC
		if TC then
			TCGUI.Text = "ON"
			TCGUI.TextColor = BrickColor.new(0.101961, 1, 0)
		else
			TCGUI.Text = "OFF"
			TCGUI.TextColor = BrickColor.new(1, 0, 0.0156863)
		end

		-- DRS
		if DRS then
			DRSGUI.Text = "ON"
			DRSGUI.TextColor = BrickColor.new(0.101961, 1, 0)
			if DrsServo then DrsServo.TargetAngle = 35 end -- [CHASSI] carro só-chassi não tem a aba do DRS
		else
			DRSGUI.Text = "OFF"
			DRSGUI.TextColor = BrickColor.new(1, 0, 0.0156863)
			if DrsServo then DrsServo.TargetAngle = 0 end
		end

		-- ---------------------------
		-- FOV / Blur (sensação de velocidade)
		-- ---------------------------
		if camPosition == 1 then
			local FatorFOV = VelocidadeAtual / maxspeed
			local FOVAP    = (FatorFOV * 10) + FOV
			local BLURAP   = FatorFOV * VelB
			camera.FieldOfView = FOVAP
			blur.Size = BLURAP
		else
			local FatorFOV = VelocidadeAtual / maxspeed
			local FOVAP    = (FatorFOV * VelS) + FOV
			local BLURAP   = FatorFOV * VelB
			camera.FieldOfView = FOVAP
			blur.Size = BLURAP
		end

		-- ---------------------------
		-- Tração / Downforce / Física
		-- ---------------------------
		local DforceAP, velNorm = Modulecar.downforce(AslVelocity, maxspeed, maxG, ExtraForce)
		DownForce.Force = Vector3.new(0, DforceAP, 0)

		local forceD, forceE = Modulecar.TC(TC, velNorm, RodaFE, RodaFD, RodaTD, RodaTE, gui, TY, TCconfig)
		Modulecar.Traction(MaxTorqueMotor, maxspeed, TY, motorTraseiroD, motorTraseiroE, MotorDianteiroD, MotorDianteiroE, AslVelocity, forceD, forceE, torqueFreio)
		Modulecar.Direcao(direcaoD, direcaoE, VolanteS, MaxAng, TX)

		-- ÁUDIO (delegado ao módulo)
		audio:update(dt, {
			marchaAtual = marchaAtual,
			soundfator  = soundfator,
			TY          = TY,
			TX          = TX,
			speed       = AslVelocity.Magnitude,
			maxspeed    = MaxSpeed,
			wheels      = { FD = VelFD, FE = VelFE, RD = VelRD, RE = VelRE },
		})

		-- [STANDALONE] removido o destaque visual da AreaPit (box do pit).
	end))
end

-- [STANDALONE] removidos: UpdateGui (posição, voltas, tempos, delta e lista
-- de classificação via events.UpdateGui) e o rádio do engenheiro (events.Radio).

-- ========= Evento: Entrar no carro =========
events:WaitForChild("Join").OnClientEvent:Connect(function(dados, som: Sound, marchasV, Gforce)
	Incar = true

	for i,v : Part in character:GetDescendants() do
		if v:IsA('Part') or v:IsA('MeshPart') then
			v.CanTouch = false
		end
	end

	if isfirt or dados.carro ~= carroAtual then -- [STANDALONE] ver comentário em RunCar
		RunCar(dados, som, marchasV, Gforce)
	end
end)

-- ========= Evento: Sair do carro =========
events:WaitForChild("Leave").OnClientEvent:Connect(function()

	for i,v : Part in character:GetDescendants() do
		if v:IsA('Part') or v:IsA('MeshPart') then
			v.CanTouch = true
		end
	end

	if character:FindFirstChild('CollisionPart') then
		character.CollisionPart.CanCollide = true
	elseif character:FindFirstChild('HumanoidRootPart') then
		character.HumanoidRootPart.CanCollide = true
	end

	playergui.GUIcar.Enabled       = false
	playergui.GUIMobileCar.Enabled = false
	camera.FieldOfView = 70
	blur.Size = 0

	if playergui:FindFirstChild("TouchGui") then
		playergui.TouchGui.Enabled = true
	end

	Incar = false
end)

-- ========= Input bindings (teclado / gamepad) =========
UIS.InputBegan:Connect(function(I)
	if I.KeyCode == Enum.KeyCode.LeftShift or I.KeyCode == Enum.KeyCode.DPadDown then
		CamR = true
	end
end)


UIS.InputEnded:Connect(function(I)
	if not Incar then return end

	if I.KeyCode == Enum.KeyCode.T or I.KeyCode == Enum.KeyCode.ButtonL1 then
		TC = not TC
	elseif I.KeyCode == Enum.KeyCode.C or I.KeyCode == Enum.KeyCode.ButtonR1 then
		if camPosition >= maxCam then
			camPosition = 1
		else
			camPosition = camPosition + 1
		end
	elseif I.KeyCode == Enum.KeyCode.LeftShift or I.KeyCode == Enum.KeyCode.DPadDown then
		CamR = false
	end
end)

UIS.InputChanged:Connect(function(I)
	if not Incar then return end
	if isgamepad then
		Gatilhos, RT, LT = Modulecar.gatilhos(I, Gatilhos, RT, LT)
	end
end)

-- ========= Input Mobile (touch buttons) =========
BF.InputBegan:Connect(function() BFT = true  end)
BF.InputEnded:Connect(function() BFT = false end)

BT.InputBegan:Connect(function() BTT = true  end)
BT.InputEnded:Connect(function() BTT = false end)

BD.InputBegan:Connect(function() BDT = true  end)
BD.InputEnded:Connect(function() BDT = false end)

BE.InputBegan:Connect(function() BET = true  end)
BE.InputEnded:Connect(function() BET = false end)

ButtonR.InputBegan:Connect(function() CamR = true end)
ButtonR.InputEnded:Connect(function() CamR = false end)


BTC.InputBegan:Connect(function()
	TC = not TC
end)

SAIR.InputEnded:Connect(function()
	player.Character.Humanoid.Sit = false
end)

CAMB.InputEnded:Connect(function()
	if camPosition >= maxCam then
		camPosition = 1
	else
		camPosition = camPosition + 1
	end
end)

-- ========= DRS =========
-- [STANDALONE] mantido: o servidor do jogo original ligava o DRS ao entrar
-- nas zonas DRS1/DRS2/DRS3 da pista. Sem zonas, o DRS fica desligado (como
-- fora das zonas no original). Para testar com DRS, basta o servidor fazer
-- ReplicatedStorage.EventsCar.DRS:FireClient(player, true/false).
DRSe.OnClientEvent:Connect(function(Value)
	DRS = Value
end)
