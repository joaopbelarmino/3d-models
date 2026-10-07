--!nocheck
-- Runs the car's server ScriptCar in an EMPTY mocked world and checks it works.
-- usage: lune run harness_server.luau <ScriptCar.lua> <ModuleCar.lua>
local fs = require("@lune/fs")
local luau = require("@lune/luau")
local process = require("@lune/process")
local SRC, MODCAR = process.args[1], process.args[2]

local LOG = {}
local function log(s) table.insert(LOG, s) end

local function Signal()
	local s = { h = {} }
	function s:Connect(f) table.insert(self.h, f) return { Disconnect = function() end } end
	function s:Fire(...) for _, f in ipairs(self.h) do f(...) end end
	return s
end
local V3mt = {}
local function V3(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V3mt) end
V3mt.__tostring = function(v) return string.format("V3(%g,%g,%g)", v.X, v.Y, v.Z) end
local Vector3 = { new = V3, zero = V3(0, 0, 0) }
local PP = {}
PP.__tostring = function(p) return string.format("PP(d=%g,f=%g,e=%g,fw=%g,ew=%g)", p.Density, p.Friction, p.Elasticity, p.FrictionWeight, p.ElasticityWeight) end
local PhysicalProperties = { new = function(d, f, e, fw, ew)
	assert(type(f) == "number", "Friction is not a number (attempt with nil)")
	return setmetatable({ Density = d, Friction = f, Elasticity = e, FrictionWeight = fw, ElasticityWeight = ew }, PP)
end }
local enumC = {}
local Enum = setmetatable({}, { __index = function(_, c) return setmetatable({}, { __index = function(_, i)
	local k = "Enum." .. c .. "." .. i; enumC[k] = enumC[k] or setmetatable({}, { __tostring = function() return k end }); return enumC[k] end }) end })

local M = {}
local function new(class, name, parent, props)
	local o = setmetatable({ __c = class, __n = name, __k = {}, __p = props or {}, __a = {}, __s = {} }, M)
	rawset(o, "__path", parent and (parent.__path .. "." .. name) or name)
	if parent then rawset(o, "__par", parent) table.insert(parent.__k, o) end
	return o
end
local meth = {}
function meth:FindFirstChild(n) for _, c in ipairs(self.__k) do if c.__n == n then return c end end end
function meth:WaitForChild(n) return assert(meth.FindFirstChild(self, n), "WaitForChild hang " .. n) end
function meth:GetChildren() return table.clone(self.__k) end
function meth:GetDescendants() local t = {} local function r(o) for _, c in ipairs(o.__k) do table.insert(t, c) r(c) end end r(self) return t end
function meth:IsA(c) return self.__c == c or (c == "BasePart" and (self.__c == "Part" or self.__c == "MeshPart")) end
function meth:GetAttribute(k) return self.__a[k] end
function meth:SetAttribute(k, v) self.__a[k] = v log(self.__path .. "@" .. k .. "=" .. tostring(v)) end
function meth:GetAttributeChangedSignal(k) self.__s["a" .. k] = self.__s["a" .. k] or Signal() return self.__s["a" .. k] end
function meth:GetPropertyChangedSignal(k) self.__s["p" .. k] = self.__s["p" .. k] or Signal() return self.__s["p" .. k] end
function meth:SetNetworkOwner(p) log(self.__path .. ":SetNetworkOwner(" .. (p and p.__n or "nil") .. ")") end
function meth:Clone() local c = new(self.__c, self.__n, nil, table.clone(self.__p)) for _, k in ipairs(self.__k) do local kc = meth.Clone(k) rawset(kc, "__par", c) table.insert(c.__k, kc) end return c end
function meth:Destroy() log(self.__path .. ":Destroy()") end
function meth:GetPlayerFromCharacter(ch) return ch.__player end
M.__index = function(s, k)
	if meth[k] then return meth[k] end
	if k == "Name" then return s.__n end
	if k == "Parent" then return rawget(s, "__par") end
	if s.__p[k] ~= nil then return s.__p[k] end
	local c = meth.FindFirstChild(s, k) if c then return c end
	if k == "Value" or k == "Occupant" then return nil end
	if k == "Heartbeat" or k == "OnServerEvent" then s.__s[k] = s.__s[k] or Signal() return s.__s[k] end
	if k == "FireClient" then return function(self, pl, ...) log(self.__path .. ":FireClient(" .. pl.__n .. "," .. select("#", ...) .. " args)") end end
	error("missing member " .. s.__path .. "." .. tostring(k), 2)
end
M.__newindex = function(s, k, v)
	if k == "Parent" then rawset(s, "__par", v) if v then table.insert(v.__k, s) end log(s.__path .. ".Parent=" .. (v and v.__path or "nil")) return end
	s.__p[k] = v
	log(s.__path .. "." .. k .. "=" .. tostring(v))
	local sig = s.__s["p" .. k] if sig then sig:Fire() end
end

-- EMPTY world: no ChuvaType attribute, no Checkpoints, no Zones, no Pista
local game = new("DataModel", "game")
local Players = new("Players", "Players", game)
local RS = new("ReplicatedStorage", "ReplicatedStorage", game)
local RunService = new("RunService", "RunService", game)
local workspace = new("Workspace", "Workspace", game)
local ev = new("Folder", "EventsCar", RS)
for _, n in ipairs({ "Join", "Leave", "DRS", "PIT", "Radio" }) do new("RemoteEvent", n, ev) end
local mcf = new("Folder", "ModuleCar", RS)
new("ModuleScript", "ModuleCar", mcf).__p.__src = fs.readFile(MODCAR)

-- car (structure as in the package)
local model = new("Model", "Carro", workspace)
local cfg = new("Configuration", "Config", model)
for k, v in pairs({ AplicarTuning = true, MolalturaF = 1.5, MolalturaT = 1.5, RigidezF = 25000, RigidezT = 25000, CamberF = 90, CamberT = 90, Sensibilidade = 1.5, TC = 1 }) do cfg.__a[k] = v end
local ch = new("Part", "Chassi", model, { AssemblyLinearVelocity = Vector3.zero, AssemblyAngularVelocity = Vector3.zero, Orientation = V3(0, 0, 0) })
for _, k in ipairs({ "AsaBroken", "EixoFdBroken", "EixoFeBroken", "Inpit" }) do ch.__a[k] = false end
local SEMCORPO = process.args[3] == "semcorpo"
local asa
if not SEMCORPO then
	local corpo = new("MeshPart", "Corpo", model, { Transparency = 0, CanCollide = true })
	asa = new("MeshPart", "AsaFrontal", corpo, { Transparency = (process.args[3] == "sempneu") and 0.7 or 0, CanCollide = true })
	new("CylindricalConstraint", "Quebrar", asa, { CurrentAngle = 0, Enabled = true })
	new("HingeConstraint", "HingeConstraint", new("MeshPart", "DRS", corpo))
end
new("ObjectValue", "Player", ch, { Value = nil })
local cpp = function(f) return PhysicalProperties.new(0.7, f, 0.3, 0.5, 0) end
local function axle(name, wheels, motors, steer)
	local e = new("Part", name, ch)
	for _, m in ipairs(motors) do new("CylindricalConstraint", m, e, { InclinationAngle = 90 }) end
	for _, w in ipairs(wheels) do
		local r = new("Part", w[1], e, { CustomPhysicalProperties = cpp(w[3]) })
		if process.args[3] ~= "sempneu" and not SEMCORPO then new("MeshPart", "Pneu", r, { TextureID = "" }) end
		new("SpringConstraint", w[2], r, { FreeLength = 1.59, Stiffness = 24862 })
	end
	if steer then new("HingeConstraint", "direcao", e, { CurrentAngle = 0, AngularSpeed = 1.5, ActuatorType = Enum.ActuatorType.Servo }) end
end
axle("EixoT", { { "RodaTD", "Mola", 0.8 }, { "RodaTE", "Mola", 0.8 } }, { "MotorD", "MotorE" }, false)
axle("EixoFD", { { "RodaFD", "SpringConstraint", 0.7 } }, { "MotorD" }, true)
axle("EixoFE", { { "RodaFE", "SpringConstraint", 0.7 } }, { "MotorE" }, true)
new("Sound", "MotorSound", ch)
new("VectorForce", "DownForce", ch)
new("AlignOrientation", "Destombar", ch, { Enabled = false })
local seat = new("VehicleSeat", "SeatM", ch, { Occupant = nil })
if not SEMCORPO then new("HingeConstraint", "Servo", new("MeshPart", "Volante", ch)) end
for _, n in ipairs({ "RAYFD", "RAYFE", "RAYTD", "RAYTE", "Cam1", "Cam2", "Cam3", "Cam4" }) do new("Part", n, ch) end

local function env(script)
	local e = setmetatable({ game = game, workspace = workspace, script = script, Vector3 = Vector3, Enum = Enum,
		PhysicalProperties = PhysicalProperties, task = { wait = function() end },
		warn = function(...) log("WARN " .. table.concat({ ... }, " ")) end }, { __index = _G })
	e.require = function(i) return luau.load(i.__p.__src, { environment = env(i) })() end
	return e
end
game.__p.GetService = function(_, n) return assert(meth.FindFirstChild(game, n), n) end
game.__p.Players = Players

local script = new("Script", "ScriptCar", ch)
local ok, err = pcall(luau.load(fs.readFile(SRC), { debugName = "ScriptCar", environment = env(script) }))
print("load:", ok and "OK" or ("ERROR " .. tostring(err)))
if not ok then process.exit(1) end

-- driver sits
local plr = new("Player", "Tester", Players)
local charm = new("Model", "Character", workspace)
charm.__p.__player = plr
new("Part", "HumanoidRootPart", charm, { CanQuery = true, CanTouch = true })
new("Humanoid", "Humanoid", charm, { Sit = true })
seat.Occupant = charm.Humanoid
RunService.Heartbeat:Fire(1 / 60)
-- crash: wing breaks, then front-right axle
if asa then asa.Quebrar.__p.CurrentAngle = 20 end
RunService.Heartbeat:Fire(1 / 60)
ch.EixoFD.direcao.__p.CurrentAngle = 40
RunService.Heartbeat:Fire(1 / 60)
-- weather change
workspace.__a.ChuvaType = "RAIN"
workspace:GetAttributeChangedSignal("ChuvaType"):Fire()
seat.Occupant = nil

for _, l in ipairs(LOG) do print(l) end
