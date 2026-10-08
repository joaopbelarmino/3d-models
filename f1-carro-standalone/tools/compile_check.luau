local fs = require("@lune/fs")
local luau = require("@lune/luau")
local process = require("@lune/process")
local bad = 0
for _, p in process.args do
	local ok, err = pcall(luau.compile, fs.readFile(p))
	print((ok and "OK   " or "FAIL ") .. p .. (ok and "" or ("  " .. tostring(err))))
	if not ok then bad += 1 end
end
process.exit(bad)
