--!nocheck
-- Verificações do "Carro 2026" montado. uso: lune run verificar_audi.luau <arquivo.rbxl>
local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox")
local game = roblox.deserializePlace(fs.readFile(process.args[1]))
local ws = game:GetService("Workspace")
local car = ws["Carro 2026"]
local ch = car.Chassi
local C = ch.CFrame
local falhas = 0
local function ok(cond, msg) if not cond then falhas += 1; print("FALHA: " .. msg) end end

-- 1. caminhos usados pelos scripts
for _, p in {"Chassi.EixoT.MotorD", "Chassi.EixoT.MotorE", "Chassi.EixoFD.MotorD", "Chassi.EixoFE.MotorE", "Chassi.MotorSound",
	"Chassi.EixoFD.direcao", "Chassi.EixoFE.direcao", "Chassi.EixoT.RodaTD.Pneu", "Chassi.EixoT.RodaTE.Pneu", "Chassi.EixoFD.RodaFD.Pneu",
	"Chassi.EixoFE.RodaFE.Pneu", "Chassi.DownForce", "Chassi.Destombar", "Chassi.SeatM", "Chassi.Volante.Servo", "Corpo.DRS.HingeConstraint",
	"Chassi.Player", "Chassi.RAYFD", "Chassi.RAYFE", "Chassi.RAYTD", "Chassi.RAYTE", "Chassi.Cam1", "Chassi.Cam2", "Chassi.Cam3", "Chassi.Cam4",
	"Corpo.AsaFrontal.Quebrar", "Corpo.Vacuo", "Config", "Chassi.ScriptCar", "Chassi.EixoFD.RodaFD.SpringConstraint", "Chassi.EixoT.RodaTD.Mola"} do
	local cur = car
	for n in string.gmatch(p, "[^%.]+") do cur = cur and cur:FindFirstChild(n) end
	ok(cur ~= nil, "falta " .. p)
end

-- 2. soldas consistentes
local maxe = 0
for _, w in car:GetDescendants() do
	if w:IsA("WeldConstraint") then
		local e = ((w.Part0.CFrame:Inverse() * w.Part1.CFrame).Position - w.CFrame0.Position).Magnitude
		maxe = math.max(maxe, e)
	end
end
ok(maxe < 0.01, "solda inconsistente " .. maxe)
print(string.format("soldas: maior erro %.5f", maxe))

-- 3. constraints: attachments onde devem estar
local function W(a) return a.Parent.CFrame * a.CFrame end
for _, c in car:GetDescendants() do
	if c:IsA("Constraint") and c.Attachment0 and c.Attachment1 then
		local a, b = W(c.Attachment0), W(c.Attachment1)
		local d = b.Position - a.Position
		if c:IsA("HingeConstraint") or c.Name == "Quebrar" then
			ok(d.Magnitude < 0.02, string.format("%s: attachments separados %.3f", c:GetFullName(), d.Magnitude))
		elseif c:IsA("CylindricalConstraint") then
			-- desvio fora do eixo de deslizamento (X do Attachment0)
			local ax = a.RightVector
			local fora = (d - ax * d:Dot(ax)).Magnitude
			ok(fora < 0.02, string.format("%s: fora do eixo %.3f", c:GetFullName(), fora))
			print(string.format("%-34s pos ao longo do eixo %.3f  limites %.3f/%.3f", c:GetFullName():gsub("^.-Carro 2026%.", ""), d:Dot(ax), c.LowerLimit, c.UpperLimit))
		elseif c:IsA("SpringConstraint") then
			print(string.format("%-34s comprimento %.3f livre %.3f damping %.0f", c:GetFullName():gsub("^.-Carro 2026%.", ""), d.Magnitude, c.FreeLength, c.Damping))
		end
	end
end

-- 4. toda peça presa (grafo de soldas/constraints a partir do Chassi)
local adj = {}
local function link(a, b) adj[a] = adj[a] or {}; adj[b] = adj[b] or {}; table.insert(adj[a], b); table.insert(adj[b], a) end
for _, c in car:GetDescendants() do
	if c:IsA("WeldConstraint") then link(c.Part0, c.Part1)
	elseif c:IsA("Constraint") and c.Attachment0 and c.Attachment1 then link(c.Attachment0.Parent, c.Attachment1.Parent) end
end
local seen, fila = {[ch] = true}, {ch}
while #fila > 0 do
	local p = table.remove(fila)
	for _, q in adj[p] or {} do if not seen[q] then seen[q] = true; table.insert(fila, q) end end
end
local soltas = {}
for _, p in car:GetDescendants() do
	if p:IsA("BasePart") and not seen[p] and not p:FindFirstAncestor("Maos") then table.insert(soltas, p:GetFullName()) end
end
ok(#soltas == 0, "peças soltas: " .. table.concat(soltas, ", "))

-- 5. colisão, texturas
local col, sas = {}, 0
for _, p in car:GetDescendants() do
	if p:IsA("BasePart") and p.CanCollide then table.insert(col, p.Name .. "(" .. p.CollisionGroup .. ")") end
	if p:IsA("SurfaceAppearance") then sas += 1 end
	if p:IsA("BasePart") then ok(p.Anchored == false, p.Name .. " ancorada") end
end
print("colidem:", table.concat(col, ", "))
print("SurfaceAppearance:", sas)

-- 6. pneu concêntrico com a roda; altura do chão
for _, k in {"FD", "FE", "TD", "TE"} do
	local roda = (k:sub(1, 1) == "F") and ch["Eixo" .. k]["Roda" .. k] or ch.EixoT["Roda" .. k]
	local d = (roda.Pneu.CFrame.Position - roda.CFrame.Position).Magnitude
	ok(d < 0.01, k .. " pneu fora do centro " .. d)
	local l = C:ToObjectSpace(roda.CFrame).Position
	print(string.format("roda %s  centro (%.3f, %.3f, %.3f)  raio %.3f  largura %.3f", k, l.X, l.Y, l.Z, roda.Size.Y / 2, roda.Size.X))
end
print("atributos:", car:GetAttribute("FatorRoda"), car.Config:GetAttribute("MolalturaF"), car.Config:GetAttribute("MolalturaT"))
print(falhas == 0 and "TUDO OK" or ("FALHAS: " .. falhas))
