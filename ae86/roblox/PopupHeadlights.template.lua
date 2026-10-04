--[[
	AE86 Trueno - pop-up headlights
	Script (server). Put it inside the car Model, next to Body, Popup_L and Popup_R.

	Toggle with the boolean attribute "Headlights" on the Model:
		model:SetAttribute("Headlights", true)   -- open
		model:SetAttribute("Headlights", false)  -- close

	Each pop-up is driven by a Motor6D whose frame sits on the hinge line at
	the rear edge of its lid.  The script does not assume any import axis
	convention or import scale: it takes "forward" from the body towards the
	pop-ups, "up" from the body, and the stud/metre ratio from the body
	length, then places the hinge using offsets measured in Blender.
	Rotating the hinge frame about its X axis by +OPEN_ANGLE lifts the front
	of each unit so the lens faces forward.
]]

local TweenService = game:GetService("TweenService")

local model = script.Parent
local body = model:WaitForChild("Body")
local popups = { model:WaitForChild("Popup_L"), model:WaitForChild("Popup_R") }

local OPEN_ANGLE = math.rad({{ANGLE}})
local BODY_LENGTH_M = {{BODY_LEN}}  -- length of the Body mesh in metres
local HINGE_UP_M = {{HINGE_UP}}      -- hinge height above the pop-up bounding-box centre
local HINGE_BACK_M = {{HINGE_BACK}}  -- hinge distance behind the pop-up bounding-box centre
local TWEEN = TweenInfo.new(0.55, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut)

local size = body.Size
local studsPerMetre = math.max(size.X, size.Y, size.Z) / BODY_LENGTH_M
local up = body.CFrame.UpVector
local front = (popups[1].Position + popups[2].Position) / 2 - body.Position
front = (front - up * front:Dot(up)).Unit

local units = {}
for _, popup in ipairs(popups) do
	local hingePos = popup.Position
		+ up * (HINGE_UP_M * studsPerMetre)
		- front * (HINGE_BACK_M * studsPerMetre)
	local hinge = CFrame.lookAt(hingePos, hingePos + front, up)

	local motor = Instance.new("Motor6D")
	motor.Name = popup.Name .. "_Hinge"
	motor.Part0 = body
	motor.Part1 = popup
	motor.C0 = body.CFrame:ToObjectSpace(hinge)
	motor.C1 = popup.CFrame:ToObjectSpace(hinge)
	motor.Parent = popup
	popup.Anchored = false

	table.insert(units, { motor = motor, closed = motor.C0 })
end

local function setOpen(open)
	for _, unit in ipairs(units) do
		local goal = unit.closed
		if open then
			goal = unit.closed * CFrame.Angles(OPEN_ANGLE, 0, 0)
		end
		TweenService:Create(unit.motor, TWEEN, { C0 = goal }):Play()
	end
end

if model:GetAttribute("Headlights") == nil then
	model:SetAttribute("Headlights", false)
end
model:GetAttributeChangedSignal("Headlights"):Connect(function()
	setOpen(model:GetAttribute("Headlights") == true)
end)
setOpen(model:GetAttribute("Headlights") == true)
