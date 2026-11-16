-- Mapas .mpc (formato descrito en el editor de mapas: cabecera de 96 B = 24 u32, cuadricula de celdas de 6 B, lista de tilesets, objetos de 74 B).
-- v6 (0x10006+): la celda mide 7 B (pincel, 0, atributo, 0, ?, ?, 0); el span hasta la lista de tilesets lo dice.
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
  -- Misma deteccion que tools/transitable.py: el span hasta la lista de tilesets
  -- mide 6 o 7 bytes/celda; el servidor usa eso para se_pisa.
  local span = h[13] > 96 and math.floor((h[13] - 96) / (w * alto)) or 6
  local tam_attr = (span == 7) and 7 or 6
  local off_attr = (tam_attr == 7) and 2 or 1
  return {
    w = w, h = alto, datos = d, celdas = 97, tilesets = ts, objetos = objetos,
    version = h[3], tam_attr = tam_attr, off_attr = off_attr,
  }
end

-- La celda mide lo que diga el span (6 B en los mapas viejos, 7 B intercalados en v6). Leer un v6 a 6 B + "capa aparte"
-- desalinea el suelo (en map041 salia todo hierba con cuadros sueltos; con 7 B salen la plaza de piedra y el cielo).
local function pos(m, x, y) return m.celdas + (y * m.w + x) * (m.tam_attr or 6) end

function M.tileset(m, x, y)
  -- El byte 0 de la celda es el numero de tileset de pincel directamente (tambien en v6; la lista de tilesets solo los resume).
  return m.datos:byte(pos(m, x, y))
end

-- Pincel visible de la casilla; fuera del mapa, el de la casilla mas cercana del borde.
function M.pincel(m, x, y)
  if x < 0 then x = 0 elseif x >= m.w then x = m.w - 1 end
  if y < 0 then y = 0 elseif y >= m.h then y = m.h - 1 end
  return M.tileset(m, x, y)
end

function M.atributo(m, x, y) return m.datos:byte(pos(m, x, y) + (m.off_attr or 1)) end

-- Zona de casa de la casilla (x, fila del .mpc): byte 5 de la celda v6 (2, 4, 6, 8...; 0 = calle). La casilla del ancla de
-- cada casa (HOUSEOUT / HOUSEIN) lleva su zona: estando en ella, se quita la fachada y se ve el interior.
function M.zona(m, x, r)
  if (m.tam_attr or 6) ~= 7 or x < 0 or r < 0 or x >= m.w or r >= m.h then return 0 end
  return m.datos:byte(m.celdas + (r * m.w + x) * 7 + 5)
end

-- Casilla transitable: igual que tools/transitable.py / server/plantillas/transitable.bin
-- (span 6→attr@1, span 7→attr@2; y del .mpc volteada respecto al servidor).
function M.se_pisa(m, x, y)
  if x < 0 or y < 0 or x >= m.w or y >= m.h then return false end
  local tam = m.tam_attr or 6
  local off = m.off_attr or 1
  local fila = (m.h - 1 - y) * m.w + x
  return m.datos:byte(96 + fila * tam + off + 1) % 4 == 0
end

-- Recorta un tramo recto (en pixeles) hasta la ultima casilla libre antes de una pared. Devuelve el punto final y si se pudo avanzar.
function M.tramo_libre(m, x0, y0, x1, y1)
  local tx0, ty0 = math.floor(x0 / 32), math.floor(y0 / 32)
  local tx1, ty1 = math.floor(x1 / 32), math.floor(y1 / 32)
  local n = math.max(math.abs(tx1 - tx0), math.abs(ty1 - ty0))
  local ux, uy = tx0, ty0
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
