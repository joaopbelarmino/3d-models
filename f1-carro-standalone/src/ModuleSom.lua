-- ReplicatedStorage.ModuleCar.ModuleSom
local module = {}

local Controller = {}
Controller.__index = Controller

local function mkSound(parent, name, id, looped, vol)
	local s = Instance.new("Sound")
	s.Name = name
	s.SoundId = "rbxassetid://" .. tostring(id)
	s.Looped = looped
	s.Volume = (vol or 0) * 0.5 -- volume reduzido pela metade
	s.RollOffMode = Enum.RollOffMode.InverseTapered
	s.RollOffMaxDistance = 140
	s.Parent = parent
	return s
end

local function clamp01(x)
	if x < 0 then return 0 elseif x > 1 then return 1 else return x end
end

-- Teto de RPM por marcha (somente ÁUDIO)
local gearUpRPM = {
	[1] = 11000,
	[2] = 12200,
	[3] = 12400,
	[4] = 12550,
	[5] = 12650,
	[6] = 12650,
	[7] = 12550,
	[8] = 12400,
}

function Controller:new(carro, engineSound, opts)
	local o = setmetatable({}, self)
	o.carro       = carro
	o.engine      = engineSound

	o.minSound    = (opts and opts.minSound)  or 1.0
	o.maxSound    = (opts and opts.Maxsound)  or 2.4
	o.maxVolume   = ((opts and opts.MaxVolume) or .5) * 0.5 -- volume máximo reduzido
	o.clickParent = (opts and opts.ClickParent) or carro

	-- estado
	o.currentPitch   = 1.5
	o.currentVolume  = 0.5
	o.pitchTauUp     = 0.20
	o.pitchTauDown   = 0.58
	o.volTauUp       = 0.08
	o.volTauDown     = 0.25

	o.MIN_RPM        = 5000
	o.MAX_RPM        = 11000
	o.LIMITER_RPM    = 10800
	o.SHIFT_CUT      = 0.060

	o.lastGear       = 1
	o.shiftCutTimer  = 0
	o.tAudio         = 0
	o.throttlePrev   = 0
	o.shiftPlayed    = false

	-- Suavização do pneu
	o.tireVol        = 0
	o.tireTauUp      = 0.06
	o.tireTauDown    = 0.12

	-- CAMADAS
	o.sDiff  = mkSound(carro, "DifferentialWhine", 85717403451372, true, 0)
	o.sWind  = mkSound(carro, "Wind",              5813077875,     true, 0)
	o.sTire  = mkSound(carro, "TireSqueal",        73429750798250, true, 0)
	o.sBack  = mkSound(carro, "Backfire",          95058486030177, false,0)
	o.sShift = mkSound(o.clickParent, "ShiftClick",127863440247801,false,0.225) -- 50% do original

	-- distâncias ajustadas
	o.sDiff.RollOffMaxDistance = 90
	o.sShift.RollOffMaxDistance = 30

	-- efeitos sonoros
	local comp = Instance.new("CompressorSoundEffect")
	comp.Ratio = 3; comp.Threshold = -8; comp.Attack = 0.003; comp.Release = 0.08
	comp.Parent = o.engine

	local eq = Instance.new("EqualizerSoundEffect")
	eq.LowGain = -1; eq.MidGain = 0.5; eq.HighGain = 2
	eq.Parent = o.engine

	return o
end

function Controller:update(dt, p)
	self.tAudio = self.tAudio + dt

	local gear      = p.marchaAtual or 1
	local soundf    = clamp01(p.soundfator or 0)
	local speed     = p.speed or 0
	local maxspeed  = (p.maxspeed and p.maxspeed > 0) and p.maxspeed or 1
	local vNorm     = clamp01(speed / maxspeed)

	if gear ~= self.lastGear then
		self.shiftCutTimer = self.SHIFT_CUT
		self.shiftPlayed   = false
		self.lastGear      = gear
	end

	local rpmTarget = self.MIN_RPM + soundf * (self.MAX_RPM - self.MIN_RPM)
	local up = gearUpRPM[gear] or 12400
	if rpmTarget > up then rpmTarget = up end

	local throttle = math.clamp(p.TY or 0, -1, 1)
	local load     = (throttle > 0) and throttle or 0
	local coasting = (throttle <= 0 and speed > 20)
	local rpmNorm  = clamp01((rpmTarget - self.MIN_RPM) / (self.MAX_RPM - self.MIN_RPM))

	local targetPitch = (rpmNorm * (self.maxSound - self.minSound)) + self.minSound

	if self.shiftCutTimer > 0 and load > 0.2 then
		self.shiftCutTimer = self.shiftCutTimer - dt
		targetPitch = targetPitch * 0.82
	end

	if rpmTarget >= self.LIMITER_RPM and load > 0.8 then
		local pulse = 0.5 + 0.5 * math.sin(self.tAudio * 2 * math.pi * 8)
		targetPitch = targetPitch * (1 - 0.18 * pulse)
	end

	local pitchTau = (targetPitch > self.currentPitch) and self.pitchTauUp or self.pitchTauDown
	local alphaP   = 1 - math.exp(-dt / pitchTau)
	self.currentPitch = self.currentPitch + (targetPitch - self.currentPitch) * alphaP

	local baseVol = 0.25 + 0.55 * load + 0.20 * rpmNorm
	if coasting then baseVol = math.max(baseVol * 0.7, 0.25) end
	local wobble  = 0.03 * math.sin(self.tAudio * 6.0)
	local targetVolume = math.clamp(baseVol + wobble, 0.2, self.maxVolume * 0.5) -- reduzido 50%

	local volTau  = (targetVolume > self.currentVolume) and self.volTauUp or self.volTauDown
	local alphaV  = 1 - math.exp(-dt / volTau)
	self.currentVolume = self.currentVolume + (targetVolume - self.currentVolume) * alphaV

	self.engine.Playing       = true
	self.engine.PlaybackSpeed = self.currentPitch
	self.engine.Volume        = self.currentVolume

	-- ===== CAMADAS =====
	self.sDiff.Playing       = true
	self.sDiff.PlaybackSpeed = 0.8 + 1.2 * vNorm
	self.sDiff.Volume        = math.clamp(0.025 + 0.11*vNorm + 0.05*load, 0, 0.175)

	self.sWind.Playing       = true
	self.sWind.PlaybackSpeed = 1.0
	self.sWind.Volume        = math.clamp(vNorm*vNorm*0.4, 0, 0.425)

	local steerAbs = math.abs(p.TX or 0)
	local braking  = ((p.TY or 0) < -0.15) and 1 or 0

	local FD, FE, RD, RE = 0,0,0,0
	if p.wheels then
		FD = p.wheels.FD or 0
		FE = p.wheels.FE or 0
		RD = p.wheels.RD or 0
		RE = p.wheels.RE or 0
	end

	local frontAvg = (FD + FE) * 0.5
	local rearAvg  = (RD + RE) * 0.5
	local rearMax  = math.max(RD, RE)

	local diff     = math.abs(rearAvg - frontAvg)
	local baseRef  = math.max(((frontAvg + rearAvg) * 0.5) + 50, 120)
	local longSlip = clamp01(diff / baseRef)

	local lockDelta = 0
	if braking == 1 and rearMax > 1 then
		local targetFront = rearMax * 0.85
		if frontAvg < targetFront then
			lockDelta = targetFront - frontAvg
		end
	end
	local brakeSqueal = braking * clamp01(lockDelta / math.max(rearMax, 1))
	local sideSlip = clamp01(steerAbs * vNorm)
	local slipScore = clamp01(longSlip * 0.8 + sideSlip * 0.4)
	local slip = math.max(slipScore, brakeSqueal)

	local tireTarget = 0
	if speed > 4 and slip > 0.03 then
		tireTarget = math.clamp((slip - 0.03) * 1.5 + 0.35 * brakeSqueal, 0, 0.98)
	end

	local tauTire = (tireTarget > self.tireVol) and self.tireTauUp or self.tireTauDown
	local aTire   = 1 - math.exp(-dt / tauTire)
	self.tireVol  = self.tireVol + (tireTarget - self.tireVol) * aTire

	self.sTire.Playing       = self.tireVol > 0.01
	self.sTire.Volume        = self.tireVol * 0.5 -- 50%
	self.sTire.PlaybackSpeed = 0.9 + 0.6 * vNorm

	if self.shiftCutTimer > 0 and not self.shiftPlayed then
		self.sShift.Volume = 0.20
		self.sShift.PlaybackSpeed = 1.0 + 0.10*math.random()
		self.sShift:Play()

		if load > 0.4 and speed > 25 then
			self.sBack.Volume        = math.clamp((0.35 + 0.5*rpmNorm) * 0.5, 0, 0.5)
			self.sBack.PlaybackSpeed = 0.95 + 0.15*math.random()
			self.sBack:Play()
		end

		self.shiftPlayed = true
	elseif self.shiftCutTimer <= 0 then
		self.shiftPlayed = false
	end

	self.throttlePrev = load
end

function module.Init(carro, engineSound, opts)
	return Controller:new(carro, engineSound, opts)
end

return module
