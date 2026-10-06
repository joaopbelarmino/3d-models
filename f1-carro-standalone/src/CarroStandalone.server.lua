--[[
	CarroStandalone (ServerScriptService)

	Junta os dois scripts de servidor do jogo original que mexem na física do
	carro/personagem e NÃO fazem parte do sistema de corrida:

	1) ServerScriptService.NoColide  (cópia fiel)
	   Registra o CollisionGroup "nocolide" (que não colide consigo mesmo) e
	   coloca os personagens nele. Rodas, Corpo, asas, assento e volante do
	   carro já estão salvos com CollisionGroup = "nocolide"; sem este registro
	   eles cairiam no grupo Default e passariam a colidir com o piloto e com
	   outros carros, mudando o comportamento.

	2) ServerScriptService.Script#2  (cópia fiel, sem o print de debug)
	   Deixa todas as partes do personagem Massless = true. Como o personagem
	   é soldado ao VehicleSeat, isso mantém a massa e o centro de massa do
	   conjunto iguais aos do jogo original.
]]

-- ===================== 1) NoColide =====================
local PhysicsService    = game:GetService("PhysicsService")
local Players           = game:GetService("Players")
local CollectionService = game:GetService("CollectionService")

local GROUP = "nocolide"

-- Garante que o grupo existe
if not PhysicsService:IsCollisionGroupRegistered(GROUP) then
	PhysicsService:RegisterCollisionGroup(GROUP)
end

-- Define colisão: nocolide não colide consigo mesmo, mas colide com Default
PhysicsService:CollisionGroupSetCollidable(GROUP, GROUP, false)
PhysicsService:CollisionGroupSetCollidable(GROUP, "Default", true)

-- Função para aplicar o grupo a todas as partes de um modelo
local function applyGroupToModel(model)
	if not model:IsA("Model") then return end

	local function setPart(part)
		if part:IsA("BasePart") then
			part.CollisionGroup = GROUP
		end
	end

	-- Aplica a todas as partes existentes
	for _, part in ipairs(model:GetDescendants()) do
		setPart(part)
	end

	-- Conecta apenas 1 vez para novos filhos
	model.DescendantAdded:Connect(setPart)
end

-- Players: aplica aos personagens
local function onCharacter(character)
	applyGroupToModel(character)
end

-- ===================== 2) Massless =====================
local function setMassless(character)
	for _, obj in ipairs(character:GetDescendants()) do
		if obj:IsA("BasePart") then
			obj.Massless = true
		end
	end
end

local function onCharacterAdded(character)
	setMassless(character)

	-- garante que acessórios ou partes que spawnem depois também fiquem massless
	character.DescendantAdded:Connect(function(obj)
		if obj:IsA("BasePart") then
			obj.Massless = true
		end
	end)
end

-- ===================== Conexões =====================
local function onPlayer(plr)
	if plr.Character then
		onCharacter(plr.Character)
		onCharacterAdded(plr.Character)
	end
	plr.CharacterAdded:Connect(onCharacter)
	plr.CharacterAdded:Connect(onCharacterAdded)
end

Players.PlayerAdded:Connect(onPlayer)
-- caso o script rode com players já no jogo
for _, plr in ipairs(Players:GetPlayers()) do
	onPlayer(plr)
end

-- Carros: usa CollectionService tag "nocolide" (como no original)
for _, inst in ipairs(CollectionService:GetTagged("nocolide")) do
	applyGroupToModel(inst)
end

CollectionService:GetInstanceAddedSignal("nocolide"):Connect(applyGroupToModel)
