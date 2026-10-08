--[[
	TelemetriaPulo (StarterPlayer.StarterPlayerScripts) - SOMENTE DIAGNÓSTICO
	Funciona em qualquer mapa com o carro standalone. Só lê valores; a única coisa que
	mexe é a tecla F, que liga/desliga a VectorForce de downforce para o teste 9.

	Ao sentar no carro:
	  * imprime um diagnóstico de partida: massas reais, centro de massa, limites da
	    suspensão como o motor está usando, posição de cada suspensão parada;
	  * mostra um painel com os valores ao vivo;
	  * grava um quadro por frame (depois da física) com:
	      t, trecho, velocidade, Vy do chassi, giro de arfagem/rolagem, giro das 4 rodas,
	      posição das 4 suspensões, comprimento das 4 molas, downforce, direção,
	      contato de cada roda (folga até o chão), assoalho/asa encostando;
	  * detecta PULO (as 4 rodas sem chão por 2+ frames) e imprime no Output
	    a janela de 0,5 s antes e 0,5 s depois, em CSV, com o frame exato do impulso.
	Teclas: F = downforce liga/desliga   G = imprimir os últimos 3 s em CSV
	Limitação: scripts rodam por frame (~60 Hz); a física roda a 240 Hz por dentro.
]]

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UIS = game:GetService("UserInputService")
local player = Players.LocalPlayer

local BUF_SEG = 3
local buffer = {}        -- linhas recentes
local pendente = nil     -- evento de pulo aguardando a janela "depois"
local eventos = 0
local carro, chassi, partes
local downforceLigado = true
local semChao = 0
local t0 = os.clock()

-- painel
local gui = Instance.new("ScreenGui")
gui.Name = "TelemetriaPulo"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")
local painel = Instance.new("TextLabel")
painel.Size = UDim2.fromOffset(430, 300)
painel.Position = UDim2.fromOffset(10, 120)
painel.BackgroundTransparency = 0.35
painel.BackgroundColor3 = Color3.new(0, 0, 0)
painel.TextColor3 = Color3.new(1, 1, 1)
painel.Font = Enum.Font.Code
painel.TextSize = 14
painel.TextXAlignment = Enum.TextXAlignment.Left
painel.TextYAlignment = Enum.TextYAlignment.Top
painel.Text = "Telemetria: sente no carro"
painel.Parent = gui

local CAMPOS = {"t", "trecho", "vel", "vyChassi", "arfagem", "rolagem",
	"wFD", "wFE", "wTD", "wTE", "posFD", "posFE", "posTD", "posTE",
	"molaFD", "molaFE", "molaTD", "molaTE", "downforce", "dirFD", "dirFE",
	"chaoFD", "chaoFE", "chaoTD", "chaoTE", "assoalho", "asa", "rodasNoChao"}

local function fmt(v)
	if type(v) == "number" then return string.format("%.4g", v) end
	return tostring(v)
end

local function linhaCSV(r)
	local out = {}
	for i, c in ipairs(CAMPOS) do out[i] = fmt(r[c]) end
	return table.concat(out, ",")
end

local function imprimir(titulo, linhas)
	print("===== " .. titulo .. " =====")
	print("TEL," .. table.concat(CAMPOS, ","))
	for _, r in ipairs(linhas) do print("TEL," .. linhaCSV(r)) end
	print("===== fim =====")
end

local function acharCarro()
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	local seat = hum and hum.SeatPart
	if not (seat and seat:IsA("VehicleSeat") and seat.Name == "SeatM") then return nil end
	return seat.Parent.Parent
end

local function montar(m)
	local c = m.Chassi
	local p = {
		chassi = c,
		roda = {FD = c.EixoFD.RodaFD, FE = c.EixoFE.RodaFE, TD = c.EixoT.RodaTD, TE = c.EixoT.RodaTE},
		cil = {FD = c.EixoFD.MotorD, FE = c.EixoFE.MotorE, TD = c.EixoT.MotorD, TE = c.EixoT.MotorE},
		mola = {FD = c.EixoFD.RodaFD.SpringConstraint, FE = c.EixoFE.RodaFE.SpringConstraint,
			TD = c.EixoT.RodaTD.Mola, TE = c.EixoT.RodaTE.Mola},
		dir = {FD = c.EixoFD.direcao, FE = c.EixoFE.direcao},
		df = c.DownForce,
		corpo = m:FindFirstChild("Corpo"),
	}
	p.asa = p.corpo and p.corpo:FindFirstChild("AsaFrontal")
	p.ray = RaycastParams.new()
	p.ray.FilterType = Enum.RaycastFilterType.Exclude
	p.ray.FilterDescendantsInstances = {m, player.Character}
	p.ovl = OverlapParams.new()
	p.ovl.FilterType = Enum.RaycastFilterType.Exclude
	p.ovl.FilterDescendantsInstances = {m, player.Character}
	return p
end

local function diagnosticoPartida(m, p)
	print("===== DIAGNÓSTICO DE PARTIDA: " .. m:GetFullName() .. " =====")
	local c = p.chassi
	print(string.format("Massa do conjunto do chassi (AssemblyMass): %.3f", c.AssemblyMass))
	for k, r in pairs(p.roda) do
		print(string.format("Roda %s: massa %.3f  AssemblyMass %.3f  elasticidade %s", k, r:GetMass(), r.AssemblyMass,
			tostring(r.CurrentPhysicalProperties.Elasticity)))
	end
	local cm = c.CFrame:PointToObjectSpace(c.AssemblyCenterOfMass)
	print(string.format("Centro de massa do conjunto do chassi (no referencial do chassi): x=%.3f y=%.3f z=%.3f", cm.X, cm.Y, cm.Z))
	for _, nome in ipairs({"Corpo/AsaFrontal", "Corpo/AsaCopia", "Corpo/DRS", "Chassi/Volante"}) do
		local inst = m
		for seg in string.gmatch(nome, "[^/]+") do inst = inst and inst:FindFirstChild(seg) end
		if inst then
			print(string.format("%s: massa %.3f  raiz da montagem = %s", nome, inst:GetMass(), inst.AssemblyRootPart and inst.AssemblyRootPart.Name or "?"))
		end
	end
	for k, cyl in pairs(p.cil) do
		print(string.format("Suspensão %s: LimitsEnabled=%s LowerLimit=%.4f UpperLimit=%.4f  CurrentPosition=%.4f  | mola CurrentLength=%.4f FreeLength=%.4f Stiffness=%.0f Damping=%.1f",
			k, tostring(cyl.LimitsEnabled), cyl.LowerLimit, cyl.UpperLimit, cyl.CurrentPosition,
			p.mola[k].CurrentLength, p.mola[k].FreeLength, p.mola[k].Stiffness, p.mola[k].Damping))
	end
	print("(Se LowerLimit > UpperLimit aqui, os limites estão invertidos. Se CurrentPosition não muda com o carro carregado/dirigindo, a suspensão está travada.)")
	print("===== fim do diagnóstico =====")
end

local function chao(p, roda)
	local r = roda.Size.Y / 2
	local hit = workspace:Raycast(roda.Position, -p.chassi.CFrame.UpVector * (r + 0.6), p.ray)
	if not hit then return 99, nil end
	return hit.Distance - r, hit.Instance
end

local function encostando(p, parte)
	if not parte or not parte.CanCollide then return 0 end
	local lista = workspace:GetPartsInPart(parte, p.ovl)
	for _, x in ipairs(lista) do
		if x.CanCollide then return 1 end
	end
	return 0
end

UIS.InputBegan:Connect(function(io, gp)
	if gp then return end
	if io.KeyCode == Enum.KeyCode.F and partes then
		downforceLigado = not downforceLigado
		partes.df.Enabled = downforceLigado
		print("[Telemetria] downforce " .. (downforceLigado and "LIGADO" or "DESLIGADO"))
	elseif io.KeyCode == Enum.KeyCode.G then
		imprimir("últimos " .. BUF_SEG .. " s", buffer)
	end
end)

local diagnosticados = {}
RunService.PostSimulation:Connect(function()
	local m = acharCarro()
	if m ~= carro then
		carro = m
		partes = m and montar(m)
		buffer = {}
		if m and not diagnosticados[m] then
			diagnosticados[m] = true
			diagnosticoPartida(m, partes)
			task.delay(2, function() if partes then diagnosticoPartida(m, partes) end end)
		end
	end
	if not partes then return end
	local p = partes
	local c = p.chassi
	local t = os.clock() - t0
	local lv = c.AssemblyLinearVelocity
	local av = c.CFrame:VectorToObjectSpace(c.AssemblyAngularVelocity)
	local r = {t = t, vel = lv.Magnitude, vyChassi = lv.Y, arfagem = av.X, rolagem = av.Z,
		downforce = p.df.Enabled and p.df.Force.Y or 0, dirFD = p.dir.FD.CurrentAngle, dirFE = p.dir.FE.CurrentAngle}
	local noChao = 0
	local trecho = "-"
	for k, roda in pairs(p.roda) do
		r["w" .. k] = roda.AssemblyAngularVelocity.Magnitude
		r["pos" .. k] = p.cil[k].CurrentPosition
		r["mola" .. k] = p.mola[k].CurrentLength
		local folga, inst = chao(p, roda)
		r["chao" .. k] = folga
		if folga < 0.05 then noChao += 1 end
		if inst and inst:GetAttribute("Trecho") then trecho = inst:GetAttribute("Trecho") end
	end
	r.trecho = trecho
	r.rodasNoChao = noChao
	r.assoalho = encostando(p, p.corpo)
	r.asa = encostando(p, p.asa)
	table.insert(buffer, r)
	while #buffer > 0 and buffer[1].t < t - BUF_SEG do table.remove(buffer, 1) end

	-- detector de pulo: 4 rodas sem chão por 2 frames seguidos
	if noChao == 0 then semChao += 1 else semChao = 0 end
	if semChao == 2 and not pendente then
		eventos += 1
		local antes = {}
		for _, x in ipairs(buffer) do if x.t >= t - 0.5 then table.insert(antes, x) end end
		-- frame do impulso: maior aumento de Vy antes da decolagem
		local imp, maior = nil, -math.huge
		for i = 2, #antes do
			local d = antes[i].vyChassi - antes[i - 1].vyChassi
			if d > maior then maior, imp = d, antes[i] end
		end
		pendente = {fim = t + 0.5, linhas = antes, imp = imp, maior = maior, trecho = trecho, vel = r.vel}
	end
	if pendente then
		if t > pendente.fim then
			local e = pendente
			pendente = nil
			print(string.format("##### PULO #%d  trecho=%s  vel=%.0f  impulso no frame t=%.3f (ΔVy=%.1f, assoalho=%s, asa=%s, rodas no chão antes=%s)",
				eventos, e.trecho, e.vel, e.imp and e.imp.t or -1, e.maior, e.imp and e.imp.assoalho or "?",
				e.imp and e.imp.asa or "?", e.imp and e.imp.rodasNoChao or "?"))
			imprimir("PULO #" .. eventos, e.linhas)
		elseif #pendente.linhas < 200 then
			table.insert(pendente.linhas, r)
		end
	end

	painel.Text = string.format(
		"TELEMETRIA  (F downforce, G imprimir)\ntrecho: %s\nvel %.0f   Vy chassi %+.1f   arfagem %+.2f  rolagem %+.2f\n" ..
		"suspensão  FD %+.3f  FE %+.3f  TD %+.3f  TE %+.3f\n" ..
		"molas      FD %.3f  FE %.3f  TD %.3f  TE %.3f\n" ..
		"giro rodas FD %.0f  FE %.0f  TD %.0f  TE %.0f\n" ..
		"folga chão FD %.2f  FE %.2f  TD %.2f  TE %.2f\n" ..
		"downforce %.0f (%s)   direção %.1f / %.1f\nassoalho %d  asa %d   rodas no chão %d\nPULOS detectados: %d",
		trecho, r.vel, r.vyChassi, r.arfagem, r.rolagem,
		r.posFD, r.posFE, r.posTD, r.posTE, r.molaFD, r.molaFE, r.molaTD, r.molaTE,
		r.wFD, r.wFE, r.wTD, r.wTE, r.chaoFD, r.chaoFE, r.chaoTD, r.chaoTE,
		r.downforce, downforceLigado and "ligado" or "DESLIGADO", r.dirFD, r.dirFE,
		r.assoalho, r.asa, noChao, eventos)
end)
