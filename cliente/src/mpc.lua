-- Mapas .mpc (formato descrito en el editor de mapas: cabecera de 96 B = 24 u32, cuadricula de celdas de 6 B, lista de tilesets, objetos de 74 B).
local net = require('src.net')
local u16, u32 = net.u16, net.u32

local M = {}

function M.leer(d)
  if d:sub(1, 4) ~= 'MAP\0' then return nil, 'no es un .mpc' end
  local h = {}
  for i = 0, 23 do h[i] = u32(d, i * 4 + 1) end
  local w, alto = h[1], h[2]
  local v6 = h[3] >= 0x10006
  local nts = h[14]
  local ts = {}
  for i = 0, nts - 1 do
    ts[i] = v6 and u16(d, h[13] + 2 * i + 1) or d:byte(h[13] + i + 1)
  end
  local objetos = {}
  for i = 0, h[7] - 1 do
    local p = h[6] + i * 74 + 1
    objetos[#objetos + 1] = { id = u32(d, p), x = u32(d, p + 4), y = u32(d, p + 8), a = u32(d, p + 12), e = u32(d, p + 16), c = u32(d, p + 20) }
  end
  return { w = w, h = alto, datos = d, celdas = 97, tilesets = ts, objetos = objetos, version = h[3] }
end

-- Tileset de pincel de la celda (x, y) con base 0.
-- OJO: en v6 la celda mide 7 bytes (el editor la lee como 6 + una capa aparte al final, y por eso en v6 sale en diagonal).
local function pos(m, x, y) return m.celdas + (y * m.w + x) * (m.version >= 0x10006 and 7 or 6) end

function M.tileset(m, x, y)
  -- El byte 0 de la celda es el numero de tileset de pincel directamente (tambien en v6; la lista de tilesets solo los resume).
  return m.datos:byte(pos(m, x, y))
end
function M.atributo(m, x, y) return m.datos:byte(pos(m, x, y) + 1) end

-- Casilla transitable (misma regla que usa el servidor, server/transitable.py, contrastada con los pasos de jugadores reales):
-- bits 0-1 del byte de atributo (byte 1 en celdas de 6 B, byte 2 en las de 7) a cero = se pisa. Las filas del .mpc cuentan desde ABAJO
-- respecto a la y del servidor, de ahi el h - 1 - y. Fuera del mapa no se pisa.
function M.se_pisa(m, x, y)
  if x < 0 or y < 0 or x >= m.w or y >= m.h then return false end
  local tam = m.version >= 0x10006 and 7 or 6
  local k = tam == 6 and 1 or 2
  return m.datos:byte(m.celdas + ((m.h - 1 - y) * m.w + x) * tam + k) % 4 == 0
end

-- Recorta un tramo recto (en pixeles) hasta la ultima casilla libre antes de una pared. Devuelve el punto final y si se pudo avanzar.
function M.tramo_libre(m, x0, y0, x1, y1)
  local tx0, ty0 = math.floor(x0 / 32), math.floor(y0 / 32)
  local tx1, ty1 = math.floor(x1 / 32), math.floor(y1 / 32)
  local n = math.max(math.abs(tx1 - tx0), math.abs(ty1 - ty0))
  local ux, uy, ax, ay = tx0, ty0, x0, y0
  for k = 1, n do
    local cx = tx0 + math.floor((tx1 - tx0) * k / n + 0.5)
    local cy = ty0 + math.floor((ty1 - ty0) * k / n + 0.5)
    if not M.se_pisa(m, cx, cy) then break end
    ux, uy = cx, cy
  end
  if ux == tx0 and uy == ty0 then return x0, y0, false end
  if ux == tx1 and uy == ty1 then return x1, y1, true end
  return ux * 32 + 16, uy * 32 + 16, true
end

return M
