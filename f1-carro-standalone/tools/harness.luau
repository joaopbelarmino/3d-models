--!nocheck
-- Equivalence harness: runs a car client script in a mocked Roblox environment
-- and records every property write, frame by frame.
-- usage: lune run harness.luau <client.lua> <ModuleCar.lua> <ModuleSom.lua> <variant: orig|new> <out.txt>

local fs = require("@lune/fs")
local luau = require("@lune/luau")
local process = require("@lune/process")

local args = process.args
local CLIENT, MODCAR, MODSOM, VARIANT, OUT = args[1], args[2], args[3], args[4], args[5]

local LOG = {}
local FRAME = 0
local function log(s)
	table.insert(LOG, FRAME .. "|" .. s)
end

---------------------------------------------------------------- value types
local function fmt(v)
	local t = type(v)
	if t == "number" then
		return string.format("%.9g", v)
	elseif t == "table" and v.__fmt then
		return v.__fmt(v)
	elseif t == "table" and v.__path then
		return "<" .. v.__path .. ">"
	end
	return tostring(v)
end

local V3 = {}
V3.__index = function(self, k)
	if k == "X" then return rawget(self, "x") end
	if k == "Y" then return rawget(self, "y") end
	if k == "Z" then return rawget(self, "z") end
	if k == "Magnitude" then
		return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)
	end
	if k == "Unit" then
		local m = math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)
		if m == 0 then return self end
		return V3.new(self.x / m, self.y / m, self.z / m)
	end
	return rawget(V3, k)
end
function V3.new(x, y, z)
	return setmetatable({ x = x or 0, y = y or 0, z = z or 0, __fmt = function(s)
		return string.format("V3(%.9g,%.9g,%.9g)", s.x, s.y, s.z)
	end }, V3)
end
V3.__add = function(a, b) return V3.new(a.x + b.x, a.y + b.y, a.z + b.z) end
V3.__sub = function(a, b) return V3.new(a.x - b.x, a.y - b.y, a.z - b.z) end
V3.__mul = function(a, b)
	if type(a) == "number" then a, b = b, a end
	return V3.new(a.x * b, a.y * b, a.z * b)
end
V3.__unm = function(a) return V3.new(-a.x, -a.y, -a.z) end
V3.__eq = function(a, b) return a.x == b.x and a.y == b.y and a.z == b.z end
local Vector3 = { new = V3.new, zero = V3.new(0, 0, 0) }

local function enumProxy(path)
	return setmetatable({}, {
		__index = function(_, k)
			return enumProxy(path .. "." .. k)
		end,
		__tostring = function() return path end,
		__eq = function(a, b) return tostring(a) == tostring(b) end,
	})
end
-- enum items must compare equal by identity: cache them
local enumCache = {}
local function enumItem(path)
	if not enumCache[path] then
		enumCache[path] = setmetatable({ __enum = path }, { __tostring = function() return path end })
	end
	return enumCache[path]
end
local Enum = setmetatable({}, { __index = function(_, cat)
	return setmetatable({}, { __index = function(_, item) return enumItem("Enum." .. cat .. "." .. item) end })
end })

local BrickColor = { new = function(...)
	local a = { ... }
	local parts = {}
	for i, v in ipairs(a) do parts[i] = string.format("%.6g", v) end
	return setmetatable({ __fmt = function() return "BC(" .. table.concat(parts, ",") .. ")" end }, {})
end }
local Color3 = { new = function(r, g, b)
	return setmetatable({ __fmt = function() return string.format("C3(%.6g,%.6g,%.6g)", r, g, b) end }, {})
end }

---------------------------------------------------------------- signals
local function Signal(name)
	local s = { handlers = {}, name = name }
	function s:Connect(fn)
		local entry = { fn = fn, on = true }
		table.insert(self.handlers, entry)
		return { Disconnect = function() entry.on = false end, Connected = true }
	end
	function s:Fire(...)
		for _, h in ipairs(self.handlers) do
			if h.on then h.fn(...) end
		end
	end
	return s
end

---------------------------------------------------------------- instances
local Inst = {}
local function new(class, name, parent, props)
	local o = { __class = class, __name = name, __children = {}, __props = {}, __attrs = {},
		__signals = {}, __parent = nil }
	o.__path = name
	setmetatable(o, Inst)
	if parent then
		rawset(o, "__parent", parent)
		table.insert(parent.__children, o)
		o.__path = parent.__path .. "." .. name
	end
	for k, v in pairs(props or {}) do o.__props[k] = v end
	return o
end
local methods = {}
function methods:FindFirstChild(n)
	for _, c in ipairs(self.__children) do
		if c.__name == n then return c end
	end
	return nil
end
function methods:WaitForChild(n)
	local c = methods.FindFirstChild(self, n)
	assert(c, "WaitForChild would hang: " .. self.__path .. "." .. n)
	return c
end
function methods:GetChildren()
	local t = {}
	for i, c in ipairs(self.__children) do t[i] = c end
	return t
end
function methods:GetDescendants()
	local t = {}
	local function rec(o)
		for _, c in ipairs(o.__children) do
			table.insert(t, c)
			rec(c)
		end
	end
	rec(self)
	return t
end
local ISA = {
	BasePart = { Part = true, MeshPart = true, VehicleSeat = true },
	Part = { Part = true },
	MeshPart = { MeshPart = true },
}
function methods:IsA(c)
	if self.__class == c then return true end
	return ISA[c] and ISA[c][self.__class] or false
end
function methods:GetAttribute(k) return self.__attrs[k] end
function methods:SetAttribute(k, v) self.__attrs[k] = v end
function methods:GetAttributeChangedSignal(k)
	local key = "attr:" .. k
	self.__signals[key] = self.__signals[key] or Signal(key)
	return self.__signals[key]
end
function methods:GetPropertyChangedSignal(k)
	local key = "prop:" .. k
	self.__signals[key] = self.__signals[key] or Signal(key)
	return self.__signals[key]
end
function methods:Destroy() end
function methods:Play() log(self.__path .. ":Play()") end
function methods:Stop() log(self.__path .. ":Stop()") end
function methods:Clone() return self end
function methods:GetMoveVector() return self.__move end

Inst.__index = function(self, k)
	if methods[k] then return methods[k] end
	if k == "Name" then return self.__name end
	if k == "Parent" then return rawget(self, "__parent") end
	local p = self.__props[k]
	if p ~= nil then return p end
	local c = methods.FindFirstChild(self, k)
	if c then return c end
	-- signals on demand (InputBegan etc)
	if type(k) == "string" and (k:match("^Input") or k:match("Changed$") or k == "RenderStepped" or k == "Heartbeat" or k == "OnClientEvent") then
		self.__signals[k] = self.__signals[k] or Signal(k)
		return self.__signals[k]
	end
	return nil
end
Inst.__newindex = function(self, k, v)
	if k == "Parent" then
		rawset(self, "__parent", v)
		if v then
			table.insert(v.__children, self)
			self.__path = v.__path .. "." .. (self.__name or "?")
		end
		log(self.__path .. ".Parent=" .. fmt(v))
		return
	end
	if k == "Name" then
		self.__name = v
		log(self.__path .. ".Name=" .. tostring(v))
		return
	end
	self.__props[k] = v
	log(self.__path .. "." .. k .. "=" .. fmt(v))
end

---------------------------------------------------------------- world
local game = new("DataModel", "game")
local Players = new("Players", "Players", game)
local RS = new("ReplicatedStorage", "ReplicatedStorage", game)
local RunService = new("RunService", "RunService", game)
local UIS = new("UserInputService", "UserInputService", game, { GamepadEnabled = false, TouchEnabled = false, KeyboardEnabled = true })
local SoundService = new("SoundService", "SoundService", game)
local Lighting = new("Lighting", "Lighting", game)
new("BlurEffect", "Blur", Lighting, { Size = 0, Enabled = true })
local workspace = new("Workspace", "Workspace", game)
local camera = new("Camera", "Camera", workspace, { FieldOfView = 70 })

local player = new("Player", "Player", Players, { Name = "Tester", UserId = 1 })
Players.__props.LocalPlayer = player
local PlayerScripts = new("PlayerScripts", "PlayerScripts", player)
local PlayerModule = new("ModuleScript", "PlayerModule", PlayerScripts)
local ControlModule = new("ModuleScript", "ControlModule", PlayerModule)
local controlApi = { __move = Vector3.new(0, 0, 0) }
function controlApi:GetMoveVector() return self.__move end
ControlModule.__module = controlApi

local PlayerGui = new("PlayerGui", "PlayerGui", player)
player.__props.PlayerGui = PlayerGui
local function mkGui(name, mobile)
	local g = new("ScreenGui", name, PlayerGui, { Enabled = false })
	local i = new("Frame", "Interface", g)
	for _, n in ipairs({ "Velocimetro", "TC", "DRS", "CAM" }) do new("ImageLabel", n, i) end
	new("TextLabel", "Gear", i.Velocimetro)
	new("TextLabel", "Vel", i.Velocimetro)
	new("TextLabel", "display", i.TC)
	new("TextLabel", "TC", i.TC)
	new("TextLabel", "display", i.DRS)
	new("TextLabel", "display", i.CAM)
	if VARIANT == "orig" then
		for _, n in ipairs({ "Pos", "Lap", "Time", "List", "Radio" }) do new("Frame", n, i) end
	end
	if mobile then
		for _, n in ipairs({ "Acel", "Freio", "Dir", "Esq", "sair", "ButtonR" }) do new("ImageButton", n, i) end
	end
	return g
end
mkGui("GUIcar", false)
mkGui("GUIMobileCar", true)

local character = new("Model", "Character", workspace)
player.__props.Character = character
local hrp = new("Part", "HumanoidRootPart", character, { CanCollide = true })
new("MeshPart", "LeftHand", character, { Transparency = 0 })
new("Humanoid", "Humanoid", character, { Sit = true })

-- remotes and modules
local EventsCar = new("Folder", "EventsCar", RS)
local evNames = { "Join", "Leave", "DRS" }
if VARIANT == "orig" then
	evNames = { "Join", "Leave", "DRS", "PIT", "Configs", "UpdateGui", "Radio" }
end
for _, n in ipairs(evNames) do new("RemoteEvent", n, EventsCar) end
local ModuleCarF = new("Folder", "ModuleCar", RS)
local mcar = new("ModuleScript", "ModuleCar", ModuleCarF)
mcar.__src = fs.readFile(MODCAR)
local msom = new("ModuleScript", "ModuleSom", ModuleCarF)
msom.__src = fs.readFile(MODSOM)

-- car
local model = new("Model", "Carro", workspace)
local chassi = new("Part", "Chassi", model, { AssemblyLinearVelocity = Vector3.new(0, 0, 0) })
local corpo = new("MeshPart", "Corpo", model, { Position = Vector3.new(0, 1, 0) })
new("Part", "Vacuo", corpo)
local drs = new("MeshPart", "DRS", corpo)
local drsServo = new("HingeConstraint", "HingeConstraint", drs, { TargetAngle = 0 })
local maos = new("Model", "Maos", model)
local m1 = new("MeshPart", "M1", maos, { Transparency = 0 })
new("MeshPart", "LeftLowerArm", m1, { Transparency = 0 })
new("MeshPart", "LeftUpperArm", m1, { Transparency = 0 })
local m2 = new("MeshPart", "M2", maos, { Transparency = 0 })
new("MeshPart", "RightLowerArm", m2, { Transparency = 0 })
if VARIANT == "orig" then
	new("ObjectValue", "AreaPit", model, { Value = nil })
end
local cams = {}
for i = 1, 4 do cams[i] = new("Part", "Cam" .. i, chassi, { CFrame = "CF_cam" .. i }) end
new("Part", "CamR", chassi, { CFrame = "CF_camR" })
new("Part", "RAYVACUO", chassi, { Position = Vector3.new(0, 1, -10) })
local function wheel(n)
	return new("Part", n, chassi, { AssemblyAngularVelocity = Vector3.new(0, 0, 0), Position = Vector3.new(0, 0, 0) })
end
local RodaTD, RodaTE, RodaFD, RodaFE = wheel("RodaTD"), wheel("RodaTE"), wheel("RodaFD"), wheel("RodaFE")
for _, n in ipairs({ "RAYFD", "RAYFE", "RAYTD", "RAYTE" }) do
	new("Part", n, chassi, { Position = Vector3.new(0, 2, 0) })
end
local function cyl(n) return new("CylindricalConstraint", n, chassi, { MotorMaxTorque = 0, AngularVelocity = 0 }) end
local MotorD, MotorE, MotorDD, MotorDE = cyl("MotorTD"), cyl("MotorTE"), cyl("MotorFD"), cyl("MotorFE")
local DirD = new("HingeConstraint", "direcaoD", chassi, { TargetAngle = 0, CurrentAngle = 0 })
local DirE = new("HingeConstraint", "direcaoE", chassi, { TargetAngle = 0, CurrentAngle = 0 })
local volante = new("MeshPart", "Volante", chassi)
local VolS = new("HingeConstraint", "Servo", volante, { TargetAngle = 0 })
local DownForce = new("VectorForce", "DownForce", chassi, { Force = Vector3.new(0, 0, 0) })
local som = new("Sound", "MotorSound", chassi, { PlaybackSpeed = 0, Volume = 0.5, Playing = true })

-- world raycast: original track-limit rays hit the track (car on track); vacuum ray hits nothing
local pista = new("Folder", "Pista", workspace)
new("Part", "Track", pista)
function workspace:Raycast(origin, dir, params)
	if params.FilterType == Enum.RaycastFilterType.Include then
		return { Instance = pista.Track }
	end
	return nil
end

---------------------------------------------------------------- env
local function makeEnv(script)
	local env = {}
	env.game = game
	env.workspace = workspace
	env.script = script
	env.Vector3 = Vector3
	env.Enum = Enum
	env.BrickColor = BrickColor
	env.Color3 = Color3
	env.RaycastParams = { new = function() return {} end }
	env.Instance = { new = function(class)
		return new(class, class, nil)
	end }
	env.task = { wait = function() end, spawn = function(f, ...) f(...) end }
	env.warn = function(...) log("warn " .. table.concat({ ... }, " ")) end
	env.print = function(...) log("print " .. table.concat({ ... }, " ")) end
	env.typeof = function(v) return type(v) end
	for _, k in ipairs({ "math", "string", "table", "bit32", "ipairs", "pairs", "type", "tostring", "tonumber",
		"setmetatable", "getmetatable", "pcall", "error", "select", "unpack", "next", "rawget", "rawset", "assert", "utf8", "os" }) do
		env[k] = _G[k] or (k == "math" and math) or (k == "string" and string) or (k == "table" and table)
			or (k == "bit32" and bit32) or (k == "ipairs" and ipairs) or (k == "pairs" and pairs) or (k == "type" and type)
			or (k == "tostring" and tostring) or (k == "tonumber" and tonumber) or (k == "setmetatable" and setmetatable)
			or (k == "getmetatable" and getmetatable) or (k == "pcall" and pcall) or (k == "error" and error)
			or (k == "select" and select) or (k == "unpack" and (table.unpack or unpack)) or (k == "next" and next)
			or (k == "rawget" and rawget) or (k == "rawset" and rawset) or (k == "assert" and assert)
			or (k == "utf8" and utf8) or (k == "os" and os)
	end
	env.require = function(inst)
		if inst.__module then return inst.__module end
		if not inst.__loaded then
			local fn = luau.load(inst.__src, { debugName = inst.__path, environment = makeEnv(inst) })
			inst.__loaded = { fn() }
		end
		return inst.__loaded[1]
	end
	return env
end

game.__props.GetService = function(_, n)
	local s = methods.FindFirstChild(game, n)
	assert(s, "service " .. n)
	return s
end
game.__props.Players = Players
game.__props.Lighting = Lighting

---------------------------------------------------------------- run client
local clientScript = new("LocalScript", "ScriptCarro", character)
local fn = luau.load(fs.readFile(CLIENT), { debugName = VARIANT, environment = makeEnv(clientScript) })
fn()

-- original: leave the pit zone (server fired PIT false when leaving AreaPitStop)
-- and the server sends the garage Sensi 5 s after spawn (TC = 1)
if VARIANT == "orig" then
	EventsCar.PIT.OnClientEvent:Fire(false)
	EventsCar.Configs.OnClientEvent:Fire({ TC = 1, brake = 1, sensiblidade = 1.5 })
end

local dados = {
	MotorD = MotorD, MotorE = MotorE, DirD = DirD, DirE = DirE, carro = chassi, SeatM = nil,
	DownForce = DownForce, RodaTD = RodaTD, RodaTE = RodaTE, RodaFD = RodaFD, RodaFE = RodaFE,
	MotorDianteiroD = MotorDD, MotorDianteiroE = MotorDE, VolanteS = VolS, maxspeed = 400, MaxAng = 13,
	maxG = -2000, DrsForceExtra = .25, DrsServo = drsServo, MaxDistanceVacuo = 500, VacuoForceExtra = .75,
	cameras = cams,
}
local marchasVelocity = {
	[1] = { min = 0, max = 105 }, [2] = { min = 95, max = 135 }, [3] = { min = 125, max = 180 },
	[4] = { min = 165, max = 225 }, [5] = { min = 205, max = 255 }, [6] = { min = 245, max = 290 },
	[7] = { min = 275, max = 290 }, [8] = { min = 285, max = 370 },
}
local GearForce = { 5000, 4500, 4000, 3500, 3500, 3000, 3000, 3000 }

math.randomseed(12345)
FRAME = 0
EventsCar.Join.OnClientEvent:Fire(dados, som, marchasVelocity, GearForce)

local function key(kc, began)
	local io = { KeyCode = Enum.KeyCode[kc], UserInputType = Enum.UserInputType.Keyboard }
	if began then UIS.InputBegan:Fire(io, false) else UIS.InputEnded:Fire(io, false) end
end

-- scenario
local dt = 1 / 60
local speed = 0
for f = 1, 2400 do
	FRAME = f
	local t = f * dt
	-- driver input
	local throttle, steer
	if f < 900 then throttle = 1 elseif f < 1100 then throttle = -1 elseif f < 1500 then throttle = 0.6 elseif f < 1700 then throttle = 0 else throttle = 1 end
	steer = math.sin(t * 1.3) * ((f % 300 < 150) and 1 or 0.4)
	controlApi.__move = Vector3.new(steer, 0, -throttle)
	-- fake vehicle state
	if throttle > 0 then speed = math.min(360, speed + throttle * 0.6) elseif throttle < 0 then speed = math.max(0, speed - 2.2) else speed = math.max(0, speed - 0.2) end
	local slip = (f % 97 < 10) and 1.25 or 1.0
	chassi.__props.AssemblyLinearVelocity = Vector3.new(speed * 0.7, 0, -speed * 0.7)
	RodaTD.__props.AssemblyAngularVelocity = Vector3.new(speed / 1.4 * slip, 0, 0)
	RodaTE.__props.AssemblyAngularVelocity = Vector3.new(speed / 1.4 * slip * 1.01, 0, 0)
	RodaFD.__props.AssemblyAngularVelocity = Vector3.new(speed / 1.4, 0, 0)
	RodaFE.__props.AssemblyAngularVelocity = Vector3.new(speed / 1.4 * 0.99, 0, 0)
	DirD.__props.CurrentAngle = steer * 12
	DirE.__props.CurrentAngle = steer * 11.5
	-- events
	if f == 200 then key("T", true) key("T", false) end -- TC off
	if f == 260 then key("T", true) key("T", false) end -- TC on
	for i, ff in ipairs({ 300, 360, 420, 480, 540 }) do
		if f == ff then key("C", true) key("C", false) end -- cycle cameras 3,4,5,1,2
	end
	if f == 600 then key("LeftShift", true) end
	if f == 640 then key("LeftShift", false) end
	if f == 700 then EventsCar.DRS.OnClientEvent:Fire(true) end
	if f == 820 then EventsCar.DRS.OnClientEvent:Fire(false) end
	if f == 1800 then -- switch to gamepad
		UIS.LastInputTypeChanged:Fire(Enum.UserInputType.Gamepad1)
	end
	if f >= 1800 and f < 2000 then
		UIS.InputChanged:Fire({ KeyCode = Enum.KeyCode.ButtonR2, Position = Vector3.new(0, 0, (f % 50) / 50) }, false)
		if f % 40 == 0 then UIS.InputChanged:Fire({ KeyCode = Enum.KeyCode.ButtonL2, Position = Vector3.new(0, 0, 0.5) }, false) end
		if f % 40 == 5 then UIS.InputChanged:Fire({ KeyCode = Enum.KeyCode.ButtonL2, Position = Vector3.new(0, 0, 0) }, false) end
	end
	if f == 2000 then UIS.LastInputTypeChanged:Fire(Enum.UserInputType.Touch) end
	if f >= 2000 then
		local gm = PlayerGui.GUIMobileCar.Interface
		if f == 2010 then gm.Acel.InputBegan:Fire({}) end
		if f == 2100 then gm.Acel.InputEnded:Fire({}) gm.Freio.InputBegan:Fire({}) end
		if f == 2150 then gm.Dir.InputBegan:Fire({}) end
		if f == 2200 then gm.Dir.InputEnded:Fire({}) gm.Esq.InputBegan:Fire({}) gm.Freio.InputEnded:Fire({}) end
		if f == 2250 then gm.TC.InputBegan:Fire({}) end
		if f == 2300 then gm.CAM.InputEnded:Fire({}) gm.ButtonR.InputBegan:Fire({}) end
		if f == 2320 then gm.ButtonR.InputEnded:Fire({}) end
	end
	if f == 2350 then EventsCar.Leave.OnClientEvent:Fire() end
	if f == 2380 then EventsCar.Join.OnClientEvent:Fire(dados, som, marchasVelocity, GearForce) end
	RunService.RenderStepped:Fire(dt)
end

fs.writeFile(OUT, table.concat(LOG, "\n") .. "\n")
print(VARIANT .. ": " .. #LOG .. " property writes recorded")
