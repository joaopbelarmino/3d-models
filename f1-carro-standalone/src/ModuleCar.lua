local module = {}

--modulo de controle do controle GAMEPAD

function module.gatilhos(I,GatilhosV,RT,LT) 
	local DEADZONE = 0.10
	local Gatilhos = GatilhosV
	if I.KeyCode == Enum.KeyCode.ButtonR2 then
		RT = math.clamp(I.Position.Z, 0, 1)
	elseif I.KeyCode == Enum.KeyCode.ButtonL2 then
		LT = math.clamp(I.Position.Z, 0, 1)
	else
		return GatilhosV, RT,LT
	end

	-- aplica deadzone para eliminar ruído
	local r = (RT > DEADZONE) and RT or 0
	local l = (LT > DEADZONE) and LT or 0

	-- se ambos pressionados, neutraliza; senão, usa a diferença
	if r > 0 and l > 0 then
		Gatilhos = 0
	else
		Gatilhos = r - l   -- R2 acelera (+), L2 freia (−)
	end
	return Gatilhos, RT , LT
end

-- Modulo do controle do mobile

function module.mobile(BFT,BTT,BET,BDT)
	local TX,TY = 0,0
	if BFT and not BTT then
		TY = 1
	elseif not BFT and BTT then
		TY = -1
	end

	if BDT and not BET then
		TX = 1
	elseif not BDT and BET then
		TX = -1
	end

	return TY, TX
end

function module.downforce(ASL,MS,MG,FE) -- Asemblyvelocity, maxspeed, maxG, forca extra == menos downforce
	FE = FE - 1
	local velNorm   = math.clamp(ASL.Magnitude / MS, 0, 1)
	local downforce = velNorm * MG
	return downforce,velNorm
end

function module.gearRPMAUT(VelocidadeAtual, marchasVelocity, GearForce, extraForce)
	local Atual
	for i = 1, #marchasVelocity do
		local m = marchasVelocity[i]
		if VelocidadeAtual >= m.min and VelocidadeAtual <= m.max then
			Atual = i
		end
	end

	-- fallback simples (caso passe do topo)
	Atual = Atual or #marchasVelocity

	local m = marchasVelocity[Atual]
	local fator = (m.max - VelocidadeAtual) / (m.max - m.min)
	fator = math.clamp(fator, 0, 1)

	local ForceAplicar = math.clamp(fator * GearForce[Atual], GearForce[Atual] * .5, GearForce[Atual])
	--print(extraForce)
	return {Atual, ForceAplicar, fator}
end

function module.TC(TC,velNorm,RodaFE,RodaFD,RodaTD,RodaTE,gui,TY, TCconfig)
	local VelRD = RodaTD.AssemblyAngularVelocity.Magnitude * 1.4
	local VelRE = RodaTE.AssemblyAngularVelocity.Magnitude * 1.4
	local baseForce = math.abs((1 - velNorm) * TY)
	local forceDM, forceEM = baseForce, baseForce
	local VelFE = RodaFE.AssemblyAngularVelocity.Magnitude * 1.4
	local VelFD = RodaFD.AssemblyAngularVelocity.Magnitude * 1.4
	local MedF  = (VelFD + VelFE + 10) / 2
	local Fator = (VelRD + VelRE) / 2
	-- print('O fator é '..tostring(Fator)..' O TC CONFIG é '..tostring(TCconfig))
	local TAP = baseForce * TCconfig
	TAP = baseForce - TAP


	if TC and (VelRD > MedF or VelRE > MedF) then
		forceDM, forceEM = TAP, TAP
		gui.TC.TC.TextColor = BrickColor.new(255, 128, 0)
	else
		gui.TC.TC.TextColor = BrickColor.new(255, 255, 255)
	end
	return forceDM, forceEM
end

function module.Traction(MaxTorqueMotor, maxspeed,TY,motorTraseiroD,motorTraseiroE,MotorDianteiroD,MotorDianteiroE,AslVelocity,forceD,forceE,torqueFreio)
	local targetAV      = TY * maxspeed
	local targetTorqueD = forceD * MaxTorqueMotor
	local targetTorqueE = forceE * MaxTorqueMotor

	motorTraseiroD.MotorMaxTorque = targetTorqueD
	motorTraseiroE.MotorMaxTorque = targetTorqueE
	motorTraseiroD.AngularVelocity = targetAV
	motorTraseiroE.AngularVelocity = targetAV

	MotorDianteiroD.AngularActuatorType = Enum.ActuatorType.None
	MotorDianteiroE.AngularActuatorType = Enum.ActuatorType.None

	if TY <= -.1 then
		if AslVelocity.Magnitude > 30 then
			motorTraseiroD.MotorMaxTorque = torqueFreio
			motorTraseiroE.MotorMaxTorque = torqueFreio
			motorTraseiroD.AngularVelocity = 0
			motorTraseiroE.AngularVelocity = 0
			MotorDianteiroD.AngularActuatorType = Enum.ActuatorType.Motor
			MotorDianteiroE.AngularActuatorType = Enum.ActuatorType.Motor
		else
			motorTraseiroD.MotorMaxTorque = targetTorqueD
			motorTraseiroE.MotorMaxTorque = targetTorqueE
			motorTraseiroD.AngularVelocity = -30
			motorTraseiroE.AngularVelocity = -30
			MotorDianteiroD.AngularActuatorType = Enum.ActuatorType.None
			MotorDianteiroE.AngularActuatorType = Enum.ActuatorType.None
		end
	end
end

function module.Direcao(direcaoD,direcaoE,VolanteS,MaxAng,TX)
	direcaoD.TargetAngle = TX * MaxAng
	direcaoE.TargetAngle = TX * MaxAng
	local MediaDir = (direcaoD.CurrentAngle + direcaoE.CurrentAngle) / 2
	VolanteS.TargetAngle = MediaDir * 12
end

function module.vacuo(carro, ExtraForce, MaxDistanceVacuo, VacuoForceExtra, MaxSpeed)
	local corpo = carro.Parent.Corpo
	local distancia = 200
	local diretion = (carro.RAYVACUO.Position - corpo.Position).Unit * distancia
	local origin = Vector3.new(corpo.Position.X, corpo.Position.Y, corpo.Position.Z)

	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = {carro.Parent.Corpo}

	local vacuo = workspace:Raycast(origin, diretion, params)

	if vacuo then
		local HitPart = vacuo.Instance

		local Part : Part
		local iscar = false

		-- Verifica se é carro
		if HitPart.Name == 'Vacuo' then
			Part = HitPart.Parent
			iscar = true
		end


		if iscar and Part then
			local FrentVelocity = Part.AssemblyLinearVelocity.Magnitude
			local distance = (corpo.Position - Part.Position).Magnitude - 30

			local VelocityFator = math.clamp(FrentVelocity/MaxSpeed,0,1)
			local DistanceFator = math.abs(math.clamp(distance / MaxDistanceVacuo, 0,1) -1)
			local fator = (DistanceFator * VelocityFator) * VacuoForceExtra
			ExtraForce = fator + ExtraForce
			return ExtraForce
		end
	end
	return ExtraForce
end

-- [STANDALONE] removidas module.InLimits (limite de pista contra workspace.Pista)
-- e module.ListOrg (lista de classificação da corrida). Só eram usadas pelo
-- sistema de corrida; as funções de física acima estão idênticas ao original.

return module
