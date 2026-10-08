--!nocheck
--[[
	Monta o "Carro 2026" (Audi) funcional: chassi V2 anti-pulo + malhas do Audi importadas do Blender.

	uso: lune run montar_audi.luau <entrada.rbxl> <saida.rbxl>

	- Parte de uma cópia de Workspace.Carro (mesma arquitetura e mesmos scripts).
	- Aplica o chassi V2 (rodas leves + lastro, Damping 300, elasticidade 0, limites na ordem certa).
	- Reposiciona eixo traseiro e rodas para as posições das rodas do Audi (entre-eixos 16,52).
	- Rodas físicas com o raio do pneu do Audi (1,79); o atributo FatorRoda faz o cliente converter
	  giro da roda na mesma velocidade/força do carro original.
	- Troca as malhas pelas do Audi, solda tudo e aplica as texturas PBR (SurfaceAppearance).
	- Recalcula o CFrame0 de todas as WeldConstraint (o Roblox respeita esse valor ao carregar).
]]
local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox")
local Instance, CFrame, Vector3, PhysicalProperties = roblox.Instance, roblox.CFrame, roblox.Vector3, roblox.PhysicalProperties

local IN, OUT = process.args[1], process.args[2]
local game = roblox.deserializePlace(fs.readFile(IN))
local ws = game:GetService("Workspace")
local SS = game:GetService("ServerStorage")

local function log(...) print("[audi]", ...) end

---------------------------------------------------------------------------
-- constantes
---------------------------------------------------------------------------
local R0 = 2.9917266 / 2      -- raio da roda física original
local R = 1.79                -- raio da roda física do Audi (pneu 1,8186: afunda 0,03 como no original)
local FATOR = R / R0
local W_F, W_T = 1.52, 1.67   -- largura do cilindro (83% da largura do pneu, como no original)
local DENS_RODA = 0.13        -- massa das rodas ~ igual à do V2 (1,99 / 2,19)
local DAMP = 300
local FREE_F, FREE_T = 1.541, 1.544
local LIM = 0.4986212
local REST_F, REST_T = 0.13, 0.02 -- compressão em repouso medida (frente / trás)
local M_ASA, M_DRS = 1.5, 0.529   -- massas que a asa e a aba do DRS tinham no original

local MAPAS = {
	-- [nome no import] = {cor, metalness, roughness, normal}
	Corpo = {82567428269054, 133173623134510, 122761146277256},
	Barbatanas = {123018566900649, nil, 110228721730627, 113506877836680},
	HALO = {84852168204651, 111336226222926, 118308736833501},
	EixoFrontal = {115213439881899, nil, 85143272084030, 86267297731818},
	EixoTraseiro = {93239140231267, nil, 92969605057268, 105769713028725},
	Asa_Frontal = {118877808663647},
	Asa_Frontal_Mecanica = {131946751464419, 106078757408606, 81755280439043},
	Aerofolio = {133389687224350, 86892520003886, 115712593598047},
	DRS = {79596056509600, 86709872117700, 94891179686741},
	Escapamento = {138866792449874, 108397290629284, 100031366781107},
	Luz = {130643111683627, nil, 81516535705092},
	Pneu_Direito = {139157123908617},
	Pneu_Esquerdo = {136772954422897},
	Pneu_Direito_Tras = {108134017544701},
	Pneu_Esquerdo_Tras = {109077575301904},
	Calota_Direita = {105029436835101, 121156564567082, 128170068256344},
	Calota_Esquerda = {94213291316113, 129776062683776, 70803027381900},
	Calota_Direito_Tras = {133418627419904, 125450152978516, 135505409221802},
	Calota_Esquerda_Tras = {121118296500869, 105323198370725, 74337932538397},
}

---------------------------------------------------------------------------
-- origem
---------------------------------------------------------------------------
local base = ws:FindFirstChild("Carro")
local imp = ws:FindFirstChild("Carro 2026")
assert(base and imp, "precisa de Workspace.Carro e Workspace['Carro 2026']")
imp.Name = "Carro 2026 (malhas importadas)"

local AREF = imp.Corpo.CFrame
local function aL(p) return AREF:ToObjectSpace(p.CFrame) end
local function find(root, name)
	for _, d in root:GetDescendants() do if d.Name == name then return d end end
	error("não achei " .. name)
end

local car = base:Clone()
car.Name = "Carro 2026"
car.Parent = ws
local ch = car.Chassi
local C = ch.CFrame
local function L(p) return C:ToObjectSpace(p.CFrame) end
local function partsOf(root)
	local t = {}
	if root:IsA("BasePart") then table.insert(t, root) end
	for _, d in root:GetDescendants() do if d:IsA("BasePart") then table.insert(t, d) end end
	return t
end
local function shift(parts, d) -- translação no referencial do chassi
	for _, p in parts do p.CFrame = C * (CFrame.new(d) * L(p)) end
end
local function shiftAtt(a, d) -- attachment de uma peça alinhada ao chassi
	a.CFrame = CFrame.new(d) * a.CFrame
end
local function scaledVolume(p)
	local s, i = p.Size, p.InitialSize
	return p.UnscaledVolume * (s.X / i.X) * (s.Y / i.Y) * (s.Z / i.Z)
end

---------------------------------------------------------------------------
-- 1. onde o Audi fica em relação ao chassi
---------------------------------------------------------------------------
local aw = {FD = imp.Pneu_Direito, FE = imp.Pneu_Esquerdo, TD = imp.Pneu_Direito_Tras, TE = imp.Pneu_Esquerdo_Tras}
local awL = {}
for k, p in aw do awL[k] = aL(p).Position end
local xF, xT = (awL.FD.X + awL.FE.X) / 2, (awL.TD.X + awL.TE.X) / 2
local yW = (awL.FD.Y + awL.FE.Y + awL.TD.Y + awL.TE.Y) / 4
local wb = xF - xT
local ROT = CFrame.Angles(0, -math.pi / 2, 0)      -- Audi +X (frente) -> chassi +Z ; Audi +Z (direita) -> chassi -X
local PITCH = CFrame.Angles(-math.asin((REST_F - REST_T) / wb), 0, 0) -- em repouso a frente comprime mais
local RB = PITCH * ROT
local pf = RB * Vector3.new(xF, yW, 0)
local Y_RODA = L(ch.EixoFD.RodaFD).Position.Y      -- centro da roda com a suspensão em 0
local Z_F = L(ch.EixoFD.RodaFD).Position.Z
local B = CFrame.new(0, Y_RODA + REST_F - pf.Y, Z_F - pf.Z) * RB
local function audiToChassi(lcf) return B * lcf end
log(string.format("entre-eixos %.3f  raio %.3f  fator %.4f", wb, R, FATOR))

-- alvo de cada roda (suspensão em 0)
local alvo = {}
for k, v in awL do
	local rest = (k == "FD" or k == "FE") and REST_F or REST_T
	alvo[k] = (B * v) - Vector3.new(0, rest, 0)
end

---------------------------------------------------------------------------
-- 2. geometria do chassi
---------------------------------------------------------------------------
-- dianteira: cada canto (manga + roda + RAY + attachment de direção no chassi) vai junto
for _, k in {"FD", "FE"} do
	local eixo = ch["Eixo" .. k]
	local roda = eixo["Roda" .. k]
	local d = alvo[k] - L(roda).Position
	shift(partsOf(eixo), d)
	shift({ch["RAY" .. k]}, d)
	shiftAtt(ch["AttachmentDirecao" .. string.sub(k, 2)], d)
	log(k, "deslocado", tostring(d))
end
-- traseira: o eixo inteiro vai para trás; depois cada roda ajusta a bitola
do
	local eixoT = ch.EixoT
	local mid = (L(eixoT.RodaTD).Position + L(eixoT.RodaTE).Position) / 2
	local alvoMid = (alvo.TD + alvo.TE) / 2
	local d = alvoMid - mid
	shift(partsOf(eixoT), d)
	shift({ch.RAYTD, ch.RAYTE}, d)
	log("eixo traseiro deslocado", tostring(d))
	for _, k in {"TD", "TE"} do
		local roda = eixoT["Roda" .. k]
		local dx = Vector3.new((alvo[k] - L(roda).Position).X, 0, 0)
		shift(partsOf(roda), dx)
		shiftAtt(eixoT["ATT" .. string.sub(k, 2)], dx)
		shiftAtt(eixoT["Mola" .. string.sub(k, 2)], dx)
		log(k, "bitola", tostring(dx))
	end
end

---------------------------------------------------------------------------
-- 3. chassi V2 com rodas do tamanho do Audi
---------------------------------------------------------------------------
local cantos = {
	FD = {ch.EixoFD, ch.EixoFD.RodaFD, W_F, ch.EixoFD.RodaFD.SpringConstraint, ch.EixoFD.MotorD, FREE_F},
	FE = {ch.EixoFE, ch.EixoFE.RodaFE, W_F, ch.EixoFE.RodaFE.SpringConstraint, ch.EixoFE.MotorE, FREE_F},
	TD = {ch.EixoT, ch.EixoT.RodaTD, W_T, ch.EixoT.RodaTD.Mola, ch.EixoT.MotorD, FREE_T},
	TE = {ch.EixoT, ch.EixoT.RodaTE, W_T, ch.EixoT.RodaTE.Mola, ch.EixoT.MotorE, FREE_T},
}
local massaRoda = {}
for k, c in cantos do
	local eixo, roda, w, mola, cil, free = table.unpack(c)
	local pp = roda.CustomPhysicalProperties
	local mOld = pp.Density * math.pi * (roda.Size.Y / 2) ^ 2 * roda.Size.X
	roda.Size = Vector3.new(w, 2 * R, 2 * R)
	roda.CustomPhysicalProperties = PhysicalProperties.new(DENS_RODA, pp.Friction, 0, pp.FrictionWeight, 1)
	local mNew = DENS_RODA * math.pi * R * R * w
	massaRoda[k] = mNew
	-- lastro suspenso no centro da roda com a massa que saiu dela
	local a = 0.8
	local lastro = Instance.new("Part")
	lastro.Name = "Lastro" .. k
	lastro.Size = Vector3.new(a, a, a)
	lastro.CFrame = roda.CFrame
	lastro.Anchored = false
	lastro.CanCollide = false
	lastro.CanTouch = false
	lastro.CanQuery = false
	lastro.Massless = false
	lastro.Transparency = 1
	lastro.CustomPhysicalProperties = PhysicalProperties.new((mOld - mNew) / (a * a * a), 0.3, 0, 1, 1)
	lastro:SetAttribute("Massa", mOld - mNew)
	lastro.Parent = eixo
	local wc = Instance.new("WeldConstraint")
	wc.Name = "Solda_Lastro" .. k
	wc.Part0 = lastro
	wc.Part1 = eixo
	wc.Parent = lastro
	mola.Damping = DAMP
	mola.FreeLength = free
	cil.LowerLimit = -LIM
	cil.UpperLimit = LIM
	log(string.format("%s roda %.3f -> %.3f, lastro %.3f", k, mOld, mNew, mOld - mNew))
end
ch.EixoFD.Massless = false
ch.EixoFE.Massless = false
-- freio dianteiro: mesmo torque na roda maior = mesma força no chão
ch.EixoFD.MotorD.MotorMaxTorque *= FATOR
ch.EixoFE.MotorE.MotorMaxTorque *= FATOR
car.Config:SetAttribute("MolalturaF", FREE_F)
car.Config:SetAttribute("MolalturaT", FREE_T)
car:SetAttribute("FatorRoda", FATOR)
car:SetAttribute("Versao", "Audi 2026 + chassi V2 anti-pulo")

---------------------------------------------------------------------------
-- 4. carroceria do Audi
---------------------------------------------------------------------------
local function texturizar(p, nomeImport)
	local m = MAPAS[nomeImport]
	if not m then return end
	local sa = Instance.new("SurfaceAppearance")
	if m[1] then sa.ColorMap = "rbxassetid://" .. m[1] end
	if m[2] then sa.MetalnessMap = "rbxassetid://" .. m[2] end
	if m[3] then sa.RoughnessMap = "rbxassetid://" .. m[3] end
	if m[4] then sa.NormalMap = "rbxassetid://" .. m[4] end
	sa.Parent = p
end
local function copiar(src, nome, parent)
	local p = src:Clone()
	p:ClearAllChildren()
	p.Name = nome
	p.CFrame = C * audiToChassi(aL(src))
	p.Anchored = false
	p.Massless = true
	p.CanCollide = false
	p.CanTouch = false
	p.CanQuery = false
	p.CollisionGroup = "nocolide"
	texturizar(p, src.Name)
	p.Parent = parent
	return p
end
local function soldar(p, alvoPart, nome)
	local w = Instance.new("WeldConstraint")
	w.Name = nome or "WeldConstraint"
	w.Part0 = p
	w.Part1 = alvoPart
	w.Parent = p
	return w
end
local function flags(de, para)
	for _, k in {"CanCollide", "CanTouch", "CanQuery", "CollisionGroup", "Massless", "CastShadow"} do para[k] = de[k] end
end
local function semQuique(p, densidade, atrito)
	p.CustomPhysicalProperties = PhysicalProperties.new(densidade, atrito, 0, 1, 1)
end
-- mover attachment para outra peça, com deslocamento opcional (no referencial do chassi)
local function moverAtt(a, novoPai, d)
	local w = C:ToObjectSpace(a.Parent.CFrame * a.CFrame)
	if d then w = CFrame.new(d) * w end
	a.Parent = novoPai
	a.CFrame = novoPai.CFrame:ToObjectSpace(C * w)
end

local velho = car.Corpo
local corpo = copiar(imp.Corpo, "Corpo", car)
corpo.CanCollide = false -- o assoalho do Audi fica a 0,12 do chão: colisão vai para caixas com a folga do original
for _, w in car:GetDescendants() do
	if w:IsA("WeldConstraint") then
		if w.Part0 == velho then w.Part0 = corpo end
		if w.Part1 == velho then w.Part1 = corpo end
	end
end
velho.WeldConstraint.Parent = corpo -- solda Corpo-Chassi (já apontada para o Corpo novo)

-- asa dianteira (quebra: CylindricalConstraint "Quebrar" entre AsaFrontal.Attachment1 e Corpo.Asa)
local asaVelha = velho.AsaFrontal
local asa = copiar(imp.Asa_Frontal, "AsaFrontal", corpo)
flags(asaVelha, asa)
asa.RootPriority = 1
semQuique(asa, M_ASA / scaledVolume(asa), 0.3)
local dAsa = L(asa).Position - L(asaVelha).Position
moverAtt(asaVelha.Attachment1, asa, dAsa)
asaVelha.Quebrar.Parent = asa
moverAtt(velho.Asa, corpo, dAsa)
moverAtt(velho.Attachment0, corpo, dAsa)
local copia = velho.AsaCopia
copia.CFrame = C * (CFrame.new(dAsa) * L(copia))
copia.Parent = corpo
local mec = copiar(find(imp, "Asa_Frontal_Mecanica"), "AsaFrontalMecanica", asa)
soldar(mec, asa)

-- aba do DRS (HingeConstraint entre DRS.Attachment e Corpo.Attachment, giro no centro da aba)
local drsVelho = velho.DRS
local drs = copiar(find(imp, "DRS"), "DRS", corpo)
flags(drsVelho, drs)
drs.RootPriority = 1
semQuique(drs, M_DRS / scaledVolume(drs), 0.3)
do
	local rot = C:ToObjectSpace(drsVelho.CFrame * drsVelho.Attachment.CFrame).Rotation
	local pivo = C * (CFrame.new(L(drs).Position) * rot)
	local a0 = drsVelho.Attachment
	a0.Parent = drs
	a0.CFrame = drs.CFrame:ToObjectSpace(pivo)
	local a1 = velho.Attachment
	a1.Parent = corpo
	a1.CFrame = corpo.CFrame:ToObjectSpace(pivo)
	drsVelho.HingeConstraint.Parent = drs
end

-- peças soldadas ao chassi: trocam a malha, mantêm a solda
local function trocar(nomeVelho, src, nomeNovo)
	local v = velho[nomeVelho]
	local n = copiar(src, nomeNovo or nomeVelho, corpo)
	flags(v, n)
	for _, c in v:GetChildren() do
		if c:IsA("WeldConstraint") then
			if c.Part0 == v then c.Part0 = n end
			if c.Part1 == v then c.Part1 = n end
			c.Parent = n
		end
	end
	return n, v
end
local aero, aeroVelho = trocar("aerofolio", imp.Aerofolio)
aero.CanCollide = true
semQuique(aero, 0.7, 0.3)
trocar("EixoFrontal", find(imp, "EixoFrontal"))
trocar("EixoTraseiro", find(imp, "EixoTraseiro"))
trocar("Escapamento", find(imp, "Escapamento"))
for _, n in {"Barbatanas", "HALO", "Luz"} do
	soldar(copiar(find(imp, n), n, corpo), ch)
end
-- placa do vácuo acompanha a traseira nova
local vac = velho.Vacuo
local dAero = L(aero).Position - L(aeroVelho).Position
vac.CFrame = C * (CFrame.new(0, 0, dAero.Z) * L(vac))
vac.Parent = corpo

-- caixas de colisão invisíveis (folga do assoalho do original: ~0,30 com a suspensão em 0)
local yChao = yW - R
local function caixa(nome, x0, x1, larg, folga, topo)
	local p = Instance.new("Part")
	p.Name = nome
	local y0 = yChao + folga
	p.Size = Vector3.new(x1 - x0, topo - y0, larg) -- no referencial do Audi (X comprimento)
	p.CFrame = C * audiToChassi(CFrame.new((x0 + x1) / 2, (y0 + topo) / 2, 0))
	p.Anchored = false
	p.Transparency = 1
	p.CanCollide = true
	p.CanTouch = false
	p.CanQuery = false
	p.Massless = true
	p.CollisionGroup = "nocolide"
	semQuique(p, 0.1, 0.2)
	p:SetAttribute("Categoria", "Colisao")
	p.Parent = corpo
	soldar(p, ch)
end
caixa("ColisaoCorpo", -9.5, 3.5, 5.2, 0.30, 0.4)
caixa("ColisaoBico", 3.5, 11.0, 1.6, 1.00, -0.3)
caixa("ColisaoTraseira", -12.5, -9.5, 2.4, 0.45, 0.3)

-- pneus e calotas: concêntricos com a roda física (soldados a ela, giram juntos)
local pneus = {
	FD = {ch.EixoFD.RodaFD, imp.Pneu_Direito, "Calota_Direita"},
	FE = {ch.EixoFE.RodaFE, imp.Pneu_Esquerdo, "Calota_Esquerda"},
	TD = {ch.EixoT.RodaTD, imp.Pneu_Direito_Tras, "Calota_Direito_Tras"},
	TE = {ch.EixoT.RodaTE, imp.Pneu_Esquerdo_Tras, "Calota_Esquerda_Tras"},
}
for k, t in pneus do
	local roda, src, nomeCal = table.unpack(t)
	local velhoP = roda:FindFirstChild("Pneu")
	local pneu = copiar(src, "Pneu", roda)
	if velhoP then flags(velhoP, pneu); velhoP:Destroy() end
	pneu.CanCollide = false
	pneu.Massless = true
	local rot = (C * audiToChassi(aL(src))).Rotation
	pneu.CFrame = CFrame.new(roda.CFrame.Position) * rot
	soldar(pneu, roda)
	local cs = find(src, nomeCal)
	local cal = copiar(cs, "Calota", pneu)
	cal.CFrame = pneu.CFrame * src.CFrame:ToObjectSpace(cs.CFrame)
	soldar(cal, pneu)
end

for _, n in {"AsaFrontal", "DRS", "aerofolio", "EixoFrontal", "EixoTraseiro", "Escapamento"} do
	local v = velho:FindFirstChild(n)
	if v then v:Destroy() end
end
assert(#velho:GetChildren() == 0, "sobrou filho no Corpo antigo: " .. (velho:GetChildren()[1] and velho:GetChildren()[1].Name or ""))
velho:Destroy()

---------------------------------------------------------------------------
-- 5. scripts
---------------------------------------------------------------------------
local function patch(src, de, para, n)
	local count = 0
	local out = src
	local i = 1
	while true do
		local a, b = string.find(out, de, i, true)
		if not a then break end
		out = string.sub(out, 1, a - 1) .. para .. string.sub(out, b + 1)
		i = a + #para
		count += 1
	end
	assert(count == (n or 1), string.format("patch '%s': %d ocorrências", de, count))
	return out
end
-- cliente (compartilhado): FatorRoda = 1 nos carros que não têm o atributo
do
	local sc = game:GetService("StarterPlayer").StarterCharacterScripts.ScriptCarro
	local s = sc.Source
	s = patch(s, "\tlocal carro          : Part                  = dados.carro\n",
		"\tlocal carro          : Part                  = dados.carro\n" ..
		"\tlocal fatorRoda = (carro.Parent and carro.Parent:GetAttribute(\"FatorRoda\")) or 1 -- [AUDI] roda maior: mesma velocidade, marchas, torque e freio do original\n")
	for _, f in {"FATOR_RD", "FATOR_RE", "FATOR_FD", "FATOR_FE"} do
		s = patch(s, "AssemblyAngularVelocity.Magnitude * " .. f, "AssemblyAngularVelocity.Magnitude * " .. f .. " * fatorRoda")
	end
	s = patch(s, "MaxTorqueMotor  = DadosGear[2]\n", "MaxTorqueMotor  = DadosGear[2] * fatorRoda -- [AUDI]\n")
	s = patch(s, "AslVelocity, forceD, forceE, torqueFreio)", "AslVelocity, forceD, forceE, torqueFreio * fatorRoda)")
	sc.Source = s
	fs.writeFile(OUT .. ".ScriptCarro.client.lua", s)
end
-- servidor deste carro: a asa quebrada esconde também as peças presas nela
do
	local sc = ch.ScriptCar
	local s = sc.Source
	s = patch(s, "\t\t\tmodel.Corpo.AsaFrontal.Transparency = 1\n",
		"\t\t\tmodel.Corpo.AsaFrontal.Transparency = 1\n" ..
		"\t\t\tfor _, p in model.Corpo.AsaFrontal:GetDescendants() do if p:IsA('BasePart') then p.Transparency = 1 end end -- [AUDI]\n")
	s = patch(s, "\t\tmodel.Corpo.AsaFrontal.Transparency = 0\n",
		"\t\tmodel.Corpo.AsaFrontal.Transparency = 0\n" ..
		"\t\tfor _, p in model.Corpo.AsaFrontal:GetDescendants() do if p:IsA('BasePart') then p.Transparency = 0 end end -- [AUDI]\n")
	sc.Source = s
	fs.writeFile(OUT .. ".ScriptCar.server.lua", s)
end

---------------------------------------------------------------------------
-- 6. posição no grid (GridPos03, mesma posição relativa do Carro no GridPos01) e soldas
---------------------------------------------------------------------------
local grid = ws.Folder.Pista.Grid
local dGrid = grid.GridPos03.CFrame.Position - grid.GridPos01.CFrame.Position
for _, p in partsOf(car) do p.CFrame = p.CFrame + dGrid end

local function refazerSoldas(modelo)
	local n = 0
	for _, w in modelo:GetDescendants() do
		if w:IsA("WeldConstraint") and w.Part0 and w.Part1 then
			w.CFrame0 = w.Part0.CFrame:Inverse() * w.Part1.CFrame
			n += 1
		end
	end
	return n
end
log("soldas recalculadas (Carro 2026):", refazerSoldas(car))

-- Carro_Chassi: câmeras e RAYs tinham ido para o lugar errado (solda com deslocamento antigo)
do
	local cc = ws:FindFirstChild("Carro_Chassi")
	if cc then
		for _, n in {"Cam1", "Cam2", "Cam3", "Cam4", "CamR", "RAYFD", "RAYFE", "RAYTD", "RAYTE", "RAYVACUO"} do
			local p, ref = cc.Chassi:FindFirstChild(n), base.Chassi:FindFirstChild(n)
			if p and ref then p.CFrame = cc.Chassi.CFrame * base.Chassi.CFrame:ToObjectSpace(ref.CFrame) end
		end
		log("soldas recalculadas (Carro_Chassi):", refazerSoldas(cc))
	end
end

-- malhas originais guardadas sem alteração
imp.Parent = SS

---------------------------------------------------------------------------
-- 7. resumo de massa (como o Roblox calcula)
---------------------------------------------------------------------------
local function massa(p)
	if p.Massless then return 0 end
	local d = p.CustomPhysicalProperties and p.CustomPhysicalProperties.Density or 0.7
	if p:IsA("MeshPart") then return d * scaledVolume(p) end
	local okS, shape = pcall(function() return p.Shape end)
	if okS and shape == roblox.Enum.PartType.Cylinder then return d * math.pi * (p.Size.Y / 2) ^ 2 * p.Size.X end
	return d * p.Size.X * p.Size.Y * p.Size.Z
end
local tot, mz = 0, 0
for _, p in partsOf(car) do
	local m = massa(p)
	if p.Massless and (p == asa or p == drs or p.Name == "AsaCopia" or p.Name == "Volante" or p.Name == "EixoFD" or p.Name == "EixoFE") then
		m = (p.CustomPhysicalProperties and p.CustomPhysicalProperties.Density or 0.7) * (p:IsA("MeshPart") and scaledVolume(p) or p.Size.X * p.Size.Y * p.Size.Z)
	end
	if m > 0 then tot += m; mz += m * C:ToObjectSpace(p.CFrame - dGrid).Z end
end
log(string.format("massa total ~%.2f  centro de massa z ~%.2f  rodas %.3f/%.3f", tot, mz / tot, massaRoda.FD, massaRoda.TD))

fs.writeFile(OUT, roblox.serializePlace(game))
log("gravado", OUT)
