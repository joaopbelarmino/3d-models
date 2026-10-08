local fs = require("@lune/fs")
local roblox = require("@lune/roblox")
local luau = require("@lune/luau")
local process = require("@lune/process")
local game = roblox.deserializePlace(fs.readFile(process.args[1]))
local workspace = game:GetService("Workspace")
local src = string.gsub(fs.readFile(process.args[2]), ":WaitForChild%(", ":FindFirstChild(")
local env = setmetatable({
	game = game, workspace = workspace, Instance = roblox.Instance, Vector3 = roblox.Vector3, CFrame = roblox.CFrame,
	Color3 = roblox.Color3, PhysicalProperties = roblox.PhysicalProperties, Enum = roblox.Enum, UDim2 = roblox.UDim2,
	Random = { new = function(seed)
		local st = seed
		return { NextNumber = function(_, a, b)
			st = (st * 1103515245 + 12345) % 2147483648
			return a + (b - a) * (st / 2147483648)
		end }
	end },
}, {__index = _G})
luau.load(src, {environment = env})()
fs.writeFile(process.args[3], roblox.serializePlace(game))
