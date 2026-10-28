-- Lector de .pak de Angels Online (formato "OD"): SOLO LECTURA sobre el cliente instalado del jugador.
--   * los ultimos 18 bytes (EOCD) van XOR (0xB1 + 3*i); de ahi salen el tamano y el desplazamiento del directorio
--   * el directorio va comprimido con zlib, con su primer byte XOR 0x7A
--   * cada entrada: 46 bytes + nombre; los datos estan en el desplazamiento `lo` (sin cabecera local), deflate crudo si meth == 8
-- Los assets son de IGG: se leen del cliente que ya tiene el jugador, nunca se copian ni se redistribuyen.
local bit = require('bit')
local net = require('src.net')
local u16, u32 = net.u16, net.u32

local P = {}

local function ordenar(nombre)
  local n = nombre:lower()
  if n == 'data1.pak' then return -1 end
  local num = n:match('^update(%d*)%.pak$')
  if num then return tonumber(num) or 1 end
  return 500
end

-- Entradas de un pak: lista de { nombre, meth, cs, us, lo }
local function leer_directorio(f)
  local n = f:seek('end')
  f:seek('set', n - 18)
  local e = f:read(18)
  local x = {}
  for i = 0, 17 do x[i + 1] = string.char(bit.bxor(e:byte(i + 1), (0xB1 + 3 * i) % 256)) end
  e = table.concat(x)
  local cdsz, cdoff = u32(e, 1), u32(e, 13)
  f:seek('set', cdoff + 4)
  local blob = f:read(cdsz)
  blob = string.char(bit.bxor(blob:byte(1), 0x7A)) .. blob:sub(2)
  local cd = love.data.decompress('string', 'zlib', blob)
  local out, p = {}, 1
  while p + 45 <= #cd do
    local nl, xl, cl = u16(cd, p + 28), u16(cd, p + 30), u16(cd, p + 32)
    out[#out + 1] = {
      nombre = cd:sub(p + 46, p + 45 + nl):gsub('\\', '/'),
      meth = u16(cd, p + 10), cs = u32(cd, p + 20), us = u32(cd, p + 24), lo = u32(cd, p + 42),
    }
    p = p + 46 + nl + xl + cl
  end
  return out
end

-- Indice de TODOS los paks de la carpeta del cliente (el de numero mas alto gana, como en el juego).
function P.abrir_cliente(carpeta, omitir)
  local self = { carpeta = carpeta, indice = {}, archivos = {}, total = 0 }
  local lista = {}
  local sep = carpeta:find('\\') and '\\' or '/'
  -- Sin io.popen (no existe en Android/iOS): se prueban los nombres que usa el juego (data1..9, music, update, update2..99).
  local candidatos = { 'music.pak', 'update.pak' }
  for i = 1, 9 do candidatos[#candidatos + 1] = 'data' .. i .. '.pak' end
  for i = 2, 99 do candidatos[#candidatos + 1] = 'update' .. i .. '.pak' end
  for _, n in ipairs(candidatos) do
    local f = io.open(carpeta .. sep .. n, 'rb')
    if f then f:close(); if not (omitir and omitir[n:lower()]) then lista[#lista + 1] = n end end
  end
  table.sort(lista, function(a, b) return ordenar(a) < ordenar(b) end)
  for _, n in ipairs(lista) do
    local f = io.open(carpeta .. sep .. n, 'rb')
    if f then
      self.archivos[n] = f
      for _, e in ipairs(leer_directorio(f)) do
        if e.nombre:sub(-1) ~= '/' then
          e.pak = n
          self.indice[e.nombre:lower()] = e
          self.total = self.total + 1
        end
      end
    end
  end
  setmetatable(self, { __index = P })
  return self
end

function P:existe(ruta) return self.indice[ruta:lower():gsub('\\', '/')] ~= nil end

-- Bytes del archivo (descomprimidos) o nil.
function P:leer(ruta)
  local e = self.indice[(ruta:lower():gsub('\\', '/'))]
  if not e then return nil end
  local f = self.archivos[e.pak]
  f:seek('set', e.lo)
  local raw = f:read(e.cs)
  if e.meth == 8 then return love.data.decompress('string', 'deflate', raw) end
  return raw
end

-- Rutas que empiezan por un prefijo (en minusculas).
function P:con_prefijo(prefijo)
  local out, pre = {}, prefijo:lower()
  for k in pairs(self.indice) do if k:sub(1, #pre) == pre then out[#out + 1] = k end end
  table.sort(out)
  return out
end

return P
