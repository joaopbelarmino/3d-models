--[[
	LaboratorioPistas (ServerScriptService) - SOMENTE PARA DIAGNÓSTICO

	Monta, na frente do carro, uma pista reta com os testes controlados em sequência.
	Todas as superfícies usam as mesmas CustomPhysicalProperties das peças de pista
	do jogo original (Density 0.0001, Friction 0.5, Elasticity 0, pesos 0).
	Não altera nada no carro.

	Trechos (placas na lateral mostram o nome de cada um):
	  1 PLANO                 piso plano
	  2 SUBIDA SUAVE 3°       rampa de 3° com transições em curva
	  3 DESCIDA SUAVE 3°      rebaixo de 3° com transições em curva
	  4 VALE 2.8°             mudança seca de inclinação para cima (concava)
	    CRISTA 2.8°           mudança seca para baixo (convexa)
	  5 QUINAS                degraus de 0.0016 / 0.0043 / 0.01 stud (subindo e descendo)
	  6 POUCOS TRIÂNGULOS     facetas de 40 studs, ±1°
	  7 MUITOS TRIÂNGULOS     facetas de 4 studs, ±0.3°, vértices com erro de até 0.001
	O valor 2.8° é o maior ângulo entre triângulos vizinhos medido no Spa; 0.0016 e 0.0043
	são o p99 e o máximo dos degraus verticais entre vértices "iguais" do Spa.
]]

local carro = workspace:WaitForChild("Carro")
local chassi = carro:WaitForChild("Chassi")

local PP = PhysicalProperties.new(0.0001, 0.5, 0, 0, 0)
local COR = Color3.fromRGB(17, 17, 17)
local LARG = 40          -- largura da faixa
local ESP = 0.05         -- espessura das cunhas (centradas no plano do triângulo)

local pasta = Instance.new("Folder")
pasta.Name = "Laboratorio"
pasta.Parent = workspace

-- referencial: origem logo à frente do carro, eixo "frente" do carro no plano horizontal
local fwd = chassi.CFrame.ZVector * Vector3.new(1, 0, 1)
fwd = fwd.Unit
local lado = Vector3.yAxis:Cross(fwd).Unit
-- altura do chão = ponto mais baixo das rodas
local yChao = math.huge
for _, nome in ipairs({"EixoFD/RodaFD", "EixoFE/RodaFE", "EixoT/RodaTD", "EixoT/RodaTE"}) do
	local partes = string.split(nome, "/")
	local roda = chassi[partes[1]][partes[2]]
	yChao = math.min(yChao, roda.CFrame.Position.Y - roda.Size.Y / 2)
end
-- se existir o chão do mapa de teste, usa o topo dele (evita um degrau na entrada)
local chaoMapa = workspace:FindFirstChild("PistaTeste")
if chaoMapa then
	yChao = chaoMapa.CFrame.Position.Y + chaoMapa.Size.Y / 2
end
local origem = Vector3.new(chassi.CFrame.Position.X, yChao, chassi.CFrame.Position.Z) + fwd * 30

-- a pista de testes fica ALT studs acima do chão do mapa (os trechos que descem não
-- podem ficar abaixo do chão do mapa), com rampas de entrada e saída bem suaves
local ALT = 4
local BASE = 0
local function mundo(s, l, h)
	return origem + fwd * s + lado * l + Vector3.yAxis * (h + BASE)
end
local function mundoTri(s, l, h)   -- cunhas finas: o topo fica ESP/2 acima do plano
	return mundo(s, l, h - ESP / 2)
end

local trechoAtual = "-"

local function aplicar(p)
	p:SetAttribute("Trecho", trechoAtual)
	p.Anchored = true
	p.Material = Enum.Material.Asphalt
	p.Color = COR
	p.CustomPhysicalProperties = PP
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = pasta
end

-- triângulo com 2 WedgeParts finas (algoritmo padrão de triângulo com cunhas)
local function tri(a, b, c)
	local ab, ac, bc = b - a, c - a, c - b
	local abd, acd, bcd = ab:Dot(ab), ac:Dot(ac), bc:Dot(bc)
	if abd > acd and abd > bcd then c, a = a, c elseif acd > bcd and acd > abd then a, b = b, a end
	ab, ac, bc = b - a, c - a, c - b
	local right = ac:Cross(ab).Unit
	local up = bc:Cross(right).Unit
	local back = bc.Unit
	local height = math.abs(ab:Dot(up))
	local w1 = Instance.new("WedgePart")
	w1.Size = Vector3.new(ESP, height, math.abs(ab:Dot(back)))
	w1.CFrame = CFrame.fromMatrix((a + b) / 2, right, up, back)
	aplicar(w1)
	local w2 = Instance.new("WedgePart")
	w2.Size = Vector3.new(ESP, height, math.abs(ac:Dot(back)))
	w2.CFrame = CFrame.fromMatrix((a + c) / 2, -right, up, -back)
	aplicar(w2)
end

-- faixa triangulada a partir de uma função de altura h(s), de s0 a s1, passo ds
local function faixa(s0, s1, ds, hfun, jitter)
	local rnd = Random.new(7)
	local function j() return jitter and rnd:NextNumber(-jitter, jitter) or 0 end
	local s = s0
	while s < s1 - 1e-6 do
		local s2 = math.min(s + ds, s1)
		local p00 = mundoTri(s, -LARG / 2, hfun(s) + j())
		local p01 = mundoTri(s, LARG / 2, hfun(s) + j())
		local p10 = mundoTri(s2, -LARG / 2, hfun(s2) + j())
		local p11 = mundoTri(s2, LARG / 2, hfun(s2) + j())
		tri(p00, p10, p11)
		tri(p00, p11, p01)
		s = s2
	end
end

local function bloco(s0, s1, h)   -- bloco reto com topo em altura h
	local p = Instance.new("Part")
	p.Size = Vector3.new(LARG, 4, s1 - s0)
	p.CFrame = CFrame.lookAlong(mundo((s0 + s1) / 2, 0, h - 2), fwd)
	aplicar(p)
end

local function placa(s, texto)
	trechoAtual = texto
	local poste = Instance.new("Part")
	poste.Anchored = true
	poste.CanCollide = false
	poste.Size = Vector3.new(1, 12, 1)
	poste.CFrame = CFrame.new(mundo(s, LARG / 2 + 4, 6))
	poste.Color = Color3.fromRGB(255, 200, 0)
	poste.Parent = pasta
	local bb = Instance.new("BillboardGui")
	bb.Size = UDim2.fromOffset(260, 50)
	bb.StudsOffset = Vector3.new(0, 8, 0)
	bb.AlwaysOnTop = true
	bb.Parent = poste
	local t = Instance.new("TextLabel")
	t.Size = UDim2.fromScale(1, 1)
	t.BackgroundTransparency = 0.3
	t.TextScaled = true
	t.Text = texto
	t.Parent = bb
	poste:SetAttribute("Trecho", texto)
end

local function suave(s0, comp, ang, transicao)
	-- altura de uma rampa com transições em parábola (subida se ang>0)
	local k = math.tan(math.rad(ang))
	return function(s)
		local x = s - s0
		if x <= 0 then return 0 end
		local T = transicao
		local function r(u) -- rampa suave de 0 a comp
			if u <= 0 then return 0 end
			if u < T then return k * u * u / (2 * T) end
			if u < T + comp then return k * T / 2 + k * (u - T) end
			if u < 2 * T + comp then
				local v = u - T - comp
				return k * T / 2 + k * comp + k * v - k * v * v / (2 * T)
			end
			return k * T + k * comp
		end
		local subida = r(x)
		local volta = r(x - (2 * T + comp + 30))
		return subida - volta
	end
end

local s = 0
-- 0 entrada: sobe ALT studs com inclinação máxima de 1.5° e transições longas
local function rampaLeve(s0, subir)
	local k = math.tan(math.rad(1.5))
	local T = 60
	local comp = (ALT - k * T) / k
	local total = 2 * T + comp
	local function r(u)
		if u <= 0 then return 0 end
		if u < T then return k * u * u / (2 * T) end
		if u < T + comp then return k * T / 2 + k * (u - T) end
		if u < total then
			local v = u - T - comp
			return k * T / 2 + k * comp + k * v - k * v * v / (2 * T)
		end
		return ALT
	end
	if subir then
		faixa(s0, s0 + total, 2, function(x) return r(x - s0) end)
	else
		faixa(s0, s0 + total, 2, function(x) return ALT - r(x - s0) end)
	end
	return total
end
placa(s, "0 ENTRADA (rampa leve, 1.5°)")
s += rampaLeve(s, true)
BASE = ALT
-- 1 plano
placa(s, "1 PLANO"); bloco(s, s + 150, 0); s += 150
-- 2 subida suave
placa(s, "2 SUBIDA SUAVE 3°")
local f2 = suave(s, 40, 3, 15); faixa(s, s + 200, 2, f2); s += 200
bloco(s, s + 40, 0); s += 40
-- 3 descida suave
placa(s, "3 DESCIDA SUAVE 3°")
local f3 = suave(s, 40, -3, 15); faixa(s, s + 200, 2, function(x) return f3(x) end); s += 200
bloco(s, s + 40, 0); s += 40
-- 4 vale e crista secos (2.8°)
placa(s, "4 VALE 2.8° / CRISTA 2.8°")
do
	local s0 = s
	local k = math.tan(math.rad(2.8))
	faixa(s0, s0 + 40, 40, function(x) return k * (x - s0) end)                 -- vale 2.8° em s0 (sobe)
	bloco(s0 + 40, s0 + 80, k * 40)                                              -- crista 2.8° em s0+40 (plano no alto)
	faixa(s0 + 80, s0 + 120, 40, function(x) return k * 40 - k * (x - s0 - 80) end) -- crista 2.8° em s0+80 (desce)
	s += 120                                                                     -- vale 2.8° em s0+120 (volta ao plano)
end
bloco(s, s + 40, 0); s += 40
-- 5 quinas
placa(s, "5 QUINAS 0.0016 / 0.0043 / 0.01")
for _, h in ipairs({0.0016, 0.0043, 0.01}) do
	bloco(s, s + 40, h); s += 40      -- sobe h
	bloco(s, s + 40, 0); s += 40      -- desce h
end
-- 6 poucos triângulos
placa(s, "6 POUCOS TRIÂNGULOS (40 studs, ±1°)")
do
	local rnd = Random.new(3)
	local pts, h, sl = {}, 0, 0
	for i = 0, 6 do
		pts[i] = h
		sl = math.clamp(sl + math.rad(rnd:NextNumber(-1, 1)), -0.03, 0.03)
		h += math.tan(sl) * 40
	end
	local fim = pts[6]
	for i = 0, 6 do pts[i] -= fim * i / 6 end   -- termina na altura 0 sem degrau
	local s0 = s
	faixa(s0, s0 + 240, 40, function(x)
		local i = math.clamp(math.floor((x - s0) / 40 + 1e-6), 0, 5)
		local u = (x - s0 - i * 40) / 40
		return pts[i] + (pts[i + 1] - pts[i]) * u
	end)
	s += 240
end
bloco(s, s + 40, 0); s += 40
-- 7 muitos triângulos
placa(s, "7 MUITOS TRIÂNGULOS (4 studs, ±0.3°, erro 0.001)")
do
	local rnd = Random.new(5)
	local s0 = s
	local alturas, h, sl = {}, 0, 0
	for i = 0, 60 do
		alturas[i] = h
		sl = math.clamp(sl + math.rad(rnd:NextNumber(-0.3, 0.3)), -0.02, 0.02) * 0.9
		h += math.tan(sl) * 4
	end
	local fim = alturas[60]
	faixa(s0, s0 + 240, 4, function(x)
		local i = math.clamp(math.floor((x - s0) / 4 + 1e-6), 0, 59)
		local u = (x - s0 - i * 4) / 4
		local y = alturas[i] + (alturas[i + 1] - alturas[i]) * u
		return y - fim * (x - s0) / 240  -- termina na altura 0
	end, 0.001)
	s += 240
end
placa(s, "FIM (volte e repita em outra velocidade)")
bloco(s, s + 100, 0); s += 100
BASE = 0
s += rampaLeve(s, false)

print(string.format("[Laboratorio] pista de testes montada: %d peças, %.0f studs à frente do carro", #pasta:GetChildren(), s))
