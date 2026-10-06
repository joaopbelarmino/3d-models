--[[
	ScriptCar (servidor) - versão STANDALONE para teste de pista.

	Base: ServerStorage.Carros.Carro.Chassi.ScriptCar do jogo original.
	A física, as constantes, as marchas e o envio de dados ao cliente são
	idênticos ao original. Foi removido apenas o que dependia do sistema de
	corrida (voltas, checkpoints, cronômetro, RaceType/Quali/Aligne/Race,
	pit stop por zona, rádio do engenheiro, AreaPit, workspace.Checkpoints,
	workspace.Largada e o módulo Zone).

	Linhas alteradas em relação ao original estão marcadas com [STANDALONE].
]]

local carro = script.Parent
local lataria = carro.Parent.Corpo
local model = lataria.Parent

local replicate = game:GetService("ReplicatedStorage")
local Events    = replicate.EventsCar
local modulecar = require(replicate.ModuleCar.ModuleCar)
local DRS = Events.DRS

-- Referências do chassi
local motorTraseiroD = carro.EixoT.MotorD
local motorTraseiroE = carro.EixoT.MotorE

local MotorDianteiroD = carro.EixoFD.MotorD
local MotorDianteiroE = carro.EixoFE.MotorE

local som      = carro.MotorSound
local DirecaoD = carro.EixoFD.direcao
local DirecaoE = carro.EixoFE.direcao

local RodaTD = carro.EixoT.RodaTD
local RodaTE = carro.EixoT.RodaTE
local RodaFE = carro.EixoFE.RodaFE
local RodaFD = carro.EixoFD.RodaFD

local DownForce = carro.DownForce
local Desvirar = carro.Destombar
local SeatM     = carro.SeatM
local VolanteS  = carro.Volante.Servo
local DrsServo = carro.Parent.Corpo.DRS.HingeConstraint

local maxG     = -2000
local ASL = carro.AssemblyLinearVelocity
local maxspeed = 400
local MaxDistanceVacuo = 500
local DrsForceExtra = .25
local VacuoForceExtra = .75
local player
local Player_car = carro.Player.Value -- [STANDALONE] se ficar vazio (nil), qualquer jogador pode dirigir

local rayfd = carro.RAYFD
local rayfe = carro.RAYFE
local raytd = carro.RAYTD
local rayte = carro.RAYTE


local cameras = {
	carro.Cam1,
	carro.Cam2,
	carro.Cam3,
	carro.Cam4
}

------------------------------------------------------------------------
-- [STANDALONE] Ajuste de spawn.
-- No jogo original o servidor (ServerScriptService.Principal -> SpawnCarro)
-- aplicava, ANTES de colocar o carro no workspace, o tuning e a
-- sensibilidade escolhidos na garagem. Sem mexer em nada na garagem, os
-- valores enviados eram estes (lidos de ReplicatedStorage.Carro e da tabela
-- Sensi da garagem):
--   MolalturaF = 1.5   MolalturaT = 1.5
--   RigidezF = 25000   RigidezT = 25000
--   CamberF = 90       CamberT = 90
--   Sensibilidade (direcao.AngularSpeed) = 1.5
-- Esses valores ficam como atributos em  Carro.Config  e são aplicados aqui
-- exatamente com as mesmas fórmulas do SpawnCarro original.
------------------------------------------------------------------------
local Config = model:FindFirstChild("Config")

local function AplicarTuning()
	if not Config or Config:GetAttribute("AplicarTuning") == false then
		return
	end

	local tuning = {
		MolalturaF = Config:GetAttribute("MolalturaF"),
		MolalturaT = Config:GetAttribute("MolalturaT"),
		CamberF    = Config:GetAttribute("CamberF"),
		CamberT    = Config:GetAttribute("CamberT"),
		RigidezF   = Config:GetAttribute("RigidezF"),
		RigidezT   = Config:GetAttribute("RigidezT"),
	}
	local Sensi = {
		sensiblidade = Config:GetAttribute("Sensibilidade"),
	}

	local chassi = carro

	-- Aplicar Ajustes de sensibilidade
	chassi.EixoFE.direcao.AngularSpeed = Sensi.sensiblidade
	chassi.EixoFD.direcao.AngularSpeed = Sensi.sensiblidade

	-- Aplicar tuning
	local MolaFE = chassi.EixoFE.RodaFE.SpringConstraint
	local MolaFD = chassi.EixoFD.RodaFD.SpringConstraint
	local MolaTE = chassi.EixoT.RodaTE.Mola
	local MolaTD = chassi.EixoT.RodaTD.Mola

	local MotorFE = chassi.EixoFE.MotorE
	local MotorFD = chassi.EixoFD.MotorD
	local MotorTE = chassi.EixoT.MotorE
	local MotorTD = chassi.EixoT.MotorD

	MolaFE.FreeLength = tuning.MolalturaF
	MolaFD.FreeLength = tuning.MolalturaF
	MolaTE.FreeLength = tuning.MolalturaT
	MolaTD.FreeLength = tuning.MolalturaT

	MolaFE.Stiffness = tuning.RigidezF
	MolaFD.Stiffness = tuning.RigidezF
	MolaTE.Stiffness = tuning.RigidezT
	MolaTD.Stiffness = tuning.RigidezT

	MotorFE.InclinationAngle = tuning.CamberF
	MotorFD.InclinationAngle = tuning.CamberF
	MotorTE.InclinationAngle = tuning.CamberT
	local camberD = tuning.CamberT - 90
	camberD = 90 - camberD
	MotorTD.InclinationAngle = camberD
end
AplicarTuning()

-- Pacote de dados enviado ao cliente
local dados = {
	MotorD = motorTraseiroD,
	MotorE = motorTraseiroE,
	DirD   = DirecaoD,
	DirE   = DirecaoE,
	carro  = carro,
	SeatM  = SeatM,
	DownForce = DownForce,
	RodaTD = RodaTD,
	RodaTE = RodaTE,
	RodaFD = RodaFD,
	RodaFE = RodaFE,
	MotorDianteiroD = MotorDianteiroD,
	MotorDianteiroE = MotorDianteiroE,
	VolanteS = VolanteS,
	maxspeed = maxspeed,
	MaxAng   = 13,
	maxG = maxG,
	DrsForceExtra = DrsForceExtra,
	DrsServo = DrsServo,
	MaxDistanceVacuo = MaxDistanceVacuo,
	VacuoForceExtra = VacuoForceExtra,
	cameras = cameras,
	rayfd = rayfd,
	rayfe = rayfe,
	raytd = raytd,
	rayte = rayte,
}

local marchasVelocity = {
	[1] = {min =   0, max = 105},
	[2] = {min =  95, max = 135},
	[3] = {min = 125, max = 180},
	[4] = {min = 165, max = 225},
	[5] = {min = 205, max = 255},
	[6] = {min = 245, max = 290},
	[7] = {min = 275, max = 290},
	[8] = {min = 285, max = 370},
}

local GearForce = {5000, 4500, 4000, 3500, 3500, 3000, 3000, 3000}

local RepairAll -- [STANDALONE] declarada abaixo

function Entrou()
	-- [STANDALONE] removido o ramo RaceType == 'Aligne' (alinhamento de largada)
	local occ = SeatM.Occupant
	if not occ then return end
	local char = occ.Parent
	player = game.Players:GetPlayerFromCharacter(char)
	-- [STANDALONE] original: só o dono do carro (Chassi.Player) podia dirigir.
	-- Agora, se Chassi.Player estiver vazio, qualquer jogador pode dirigir.
	if player and (Player_car == nil or player == Player_car) then
		-- [STANDALONE] original (Principal.SpawnCarro): partes diretas do
		-- personagem com CanQuery = false (não bloqueiam o raycast do vácuo).
		for _, v in ipairs(char:GetChildren()) do
			if v:IsA("BasePart") then
				v.CanQuery = false
			end
		end
		RepairAll() -- [STANDALONE] substitui o reparo que o pit stop fazia
		Events.Join:FireClient(player, dados, som, marchasVelocity, GearForce)
		carro:SetNetworkOwner(player or Player_car)
		task.wait(3)
		-- [STANDALONE] removida a mensagem de rádio (Events.Radio)
		for i,v : Part in char:GetDescendants() do
			if v:IsA('Part') or v:IsA('MeshPart') then
				v.CanTouch = false
			end
		end
	else
		task.wait(1)
		char.Humanoid.Sit = false
		for i,v : Part in char:GetDescendants() do
			if v:IsA('Part') or v:IsA('MeshPart') then
				v.CanTouch = true
			end
		end
	end
end

function Saiu()
	if player then
		Events.Leave:FireClient(player)
		carro:SetNetworkOwner(nil)
	end
	player = nil
end
SeatM:GetPropertyChangedSignal("Occupant"):Connect(function()
	if SeatM.Occupant ~= nil then
		Entrou()
	else
		Saiu()
	end
end)

local Compostos = {
	SUN = 'rbxassetid://115917279609923',
	LIGHT_RAIN = 'rbxassetid://99686252469857',
	RAIN = 'rbxassetid://91743904091252'
}

local Friction = {
	SUN = 0.8,
	LIGHT_RAIN = 0.7,
	RAIN = .6
}

function MudarComposto()
	local Clima = workspace:GetAttribute('ChuvaType')
	-- [STANDALONE] no jogo original o workspace sempre tinha ChuvaType
	-- ('SUN' por padrão). Num mapa vazio o atributo não existe e o original
	-- daria erro aqui; por isso o padrão 'SUN' é usado quando ele falta.
	if Friction[Clima] == nil then
		Clima = 'SUN'
	end
	local orig = RodaTD.CustomPhysicalProperties
	local newProps = PhysicalProperties.new(
		orig.Density,
		Friction[Clima],         -- novo valor de Friction
		orig.Elasticity,
		orig.FrictionWeight,
		orig.ElasticityWeight
	)


	local newPropsFront = PhysicalProperties.new(
		orig.Density,
		Friction[Clima] - .1,         -- novo valor de Friction
		orig.Elasticity,
		orig.FrictionWeight,
		orig.ElasticityWeight
	)
	local compostoAtual = Compostos[Clima]
	RodaTD.Pneu.TextureID = compostoAtual
	RodaFD.Pneu.TextureID = compostoAtual
	RodaTE.Pneu.TextureID = compostoAtual
	RodaFE.Pneu.TextureID = compostoAtual

	RodaTD.CustomPhysicalProperties = newProps
	RodaTE.CustomPhysicalProperties = newProps
	RodaFD.CustomPhysicalProperties = newPropsFront
	RodaFE.CustomPhysicalProperties = newPropsFront
end

workspace:GetAttributeChangedSignal('ChuvaType'):Connect(function()
	MudarComposto()
end)
MudarComposto()


local run = game:GetService("RunService")

local Autopit = false

-- [STANDALONE] Substitui o PitStop() original. O original zerava a velocidade,
-- teleportava o carro para model.AreaPit.Value.Parent.PITLOC e reparava.
-- Sem pit, o carro é reparado no próprio lugar com a mesma sequência de
-- rede/velocidade (sem teleporte e sem os tempos de espera do box).
function PitStop()
	if carro:GetAttribute('Inpit') then
		return
	end
	carro:SetAttribute('Inpit', true)

	local sucess = pcall(function()
		local AsaBroken, EixoFdBroken, EixoFeBroken = carro:GetAttribute('AsaBroken'), carro:GetAttribute('EixoFdBroken'), carro:GetAttribute('EixoFeBroken')
		if AsaBroken or EixoFdBroken or EixoFeBroken then
			carro:SetNetworkOwner(nil)
			carro.AssemblyAngularVelocity = Vector3.zero
			carro.AssemblyLinearVelocity = Vector3.zero
			task.wait(.5)
			carro.AssemblyAngularVelocity = Vector3.zero
			carro.AssemblyLinearVelocity = Vector3.zero
			RepairAll()
		end
	end)
	if not sucess then
		warn('Ocorreu um Erro no reparo')
	end

	if carro.SeatM.Occupant ~= nil and player then
		carro:SetNetworkOwner(player)
	end

	carro:SetAttribute('Inpit', false)
	Autopit = false
end

local Destombando = false
function Destombar()
	Destombando = true
	task.wait(5)
	Desvirar.Enabled = true
	task.wait(3)
	Desvirar.Enabled = false
	Destombando = false
end


local asaFrontal = model.Corpo.AsaFrontal

run.Heartbeat:Connect(function(D)
	local x, z = carro.Orientation.X, carro.Orientation.Z
	if math.abs(x) > 70 or math.abs(z) > 70 then
		if not Destombando then
			Destombar()
		end
	end
	-- [STANDALONE] removido o cronômetro de volta (atributo 'Timer')

	local AsaBroken, EixoFdBroken, EixoFeBroken = carro:GetAttribute('AsaBroken'), carro:GetAttribute('EixoFdBroken'), carro:GetAttribute('EixoFeBroken')

	if model.Corpo:FindFirstChild('AsaFrontal') then
		if math.abs(model.Corpo.AsaFrontal.Quebrar.CurrentAngle) > 15 and not AsaBroken then
			carro:SetAttribute('AsaBroken', true)
			local BrokenAsa = model.Corpo.AsaFrontal:Clone()
			BrokenAsa.Quebrar.Enabled = false
			BrokenAsa.Parent = model.Corpo
			model.Corpo.AsaFrontal.Transparency = 1
			model.Corpo.AsaFrontal.CanCollide = false
			-- [STANDALONE] removida a mensagem de rádio (Events.Radio)
			task.wait(5)
			BrokenAsa:Destroy()
		end
	end

	if math.abs(DirecaoD.CurrentAngle) > 35 and not EixoFdBroken and carro:GetAttribute('AsaBroken') then
		DirecaoD.ActuatorType = Enum.ActuatorType.None
		carro:SetAttribute('EixoFdBroken', true)
		if not Autopit then
			Autopit = true
			task.wait(3)
			carro:SetNetworkOwner(nil)
			-- [STANDALONE] removida a mensagem de rádio (Events.Radio)
			PitStop()
		end

	end

	if math.abs(DirecaoE.CurrentAngle) > 35 and not EixoFeBroken and carro:GetAttribute('AsaBroken') then
		DirecaoE.ActuatorType = Enum.ActuatorType.None
		carro:SetAttribute('EixoFeBroken', true)
		if not Autopit then
			Autopit = true
			task.wait(3)
			carro:SetNetworkOwner(nil)
			-- [STANDALONE] removida a mensagem de rádio (Events.Radio)
			PitStop()
		end
	end

end)

-- [STANDALONE] removidos: contagem de checkpoints (workspace.Checkpoints),
-- voltas, melhor volta, delta, e o tratamento de RaceType (Quali/Aligne/Race).

function RepairAll()
	local AsaBroken, EixoFdBroken, EixoFeBroken = carro:GetAttribute('AsaBroken'), carro:GetAttribute('EixoFdBroken'), carro:GetAttribute('EixoFeBroken')
	if AsaBroken then
		carro:SetAttribute('AsaBroken', false)
		model.Corpo.AsaFrontal.Transparency = 0
		model.Corpo.AsaFrontal.CanCollide = true
	end

	if EixoFeBroken then
		carro:SetAttribute('EixoFeBroken', false)
		carro.EixoFE.direcao.ActuatorType = Enum.ActuatorType.Servo
	end
	if EixoFdBroken then
		carro:SetAttribute('EixoFdBroken', false)
		carro.EixoFD.direcao.ActuatorType = Enum.ActuatorType.Servo
	end
end
