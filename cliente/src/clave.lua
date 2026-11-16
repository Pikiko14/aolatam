-- Contraseña del AUTH como el angel.dat de Windows: Blowfish ECB, clave fija d593b7880791f844.
-- Las tablas P/S ya vienen con esa clave (clave_tablas.lua, generadas desde server/clave_cliente.py).
-- Así el cliente propio entra con las mismas cuentas que la web / Windows.
local bit = require('bit')
local band, bxor, rshift = bit.band, bit.bxor, bit.rshift
local T = require('src.clave_tablas')

local M = {}
local _M = 0xFFFFFFFF

-- F = (((S0[a] + S1[b]) XOR S2[c]) + S3[d]) mod 2^32
local function F(x)
  x = band(x, _M)
  local a = T.S0[rshift(x, 24) + 1]
  local b = T.S1[band(rshift(x, 16), 255) + 1]
  local c = T.S2[band(rshift(x, 8), 255) + 1]
  local d = T.S3[band(x, 255) + 1]
  return band(bxor(band(a + b, _M), c) + d, _M)
end

local function cifrar_bloque(l, r)
  local P = T.P
  for i = 0, 15 do
    l = bxor(l, P[i + 1])
    r = bxor(r, F(l))
    l, r = r, l
  end
  l, r = r, l
  r = bxor(r, P[17])
  l = bxor(l, P[18])
  return band(l, _M), band(r, _M)
end

local function u32le(s, i)
  local a, b, c, d = s:byte(i, i + 3)
  return a + b * 256 + c * 65536 + d * 16777216
end

local function p32le(v)
  v = band(v, _M)
  return string.char(v % 256, math.floor(v / 256) % 256,
                     math.floor(v / 65536) % 256, math.floor(v / 16777216) % 256)
end

function M.cifrar(bufer)
  assert(#bufer == 32)
  local out = {}
  for i = 1, 32, 8 do
    local l, r = u32le(bufer, i), u32le(bufer, i + 4)
    l, r = cifrar_bloque(l, r)
    out[#out + 1] = p32le(l)
    out[#out + 1] = p32le(r)
  end
  return table.concat(out)
end

function M.bloque(clave)
  clave = clave or ''
  if #clave > 31 then clave = clave:sub(1, 31) end
  return M.cifrar(clave .. '\0' .. string.rep('\0', 31 - #clave))
end

return M
