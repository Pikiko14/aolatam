-- El suelo como lo pinta angel.dat (CMap, 0x498980 / 0x4998a0 / 0x499690), en la GPU (14/11/2026, "arregla los mapas
-- guiandote del angel.dat, debe verse igual, eso si mas optimo").
--
-- Lo que hace el original, medido con capstone:
--   * pincel de la casilla = u16 al principio de la celda (-1 fuera del mapa); prioridad = su posicion en la lista de
--     tilesets del .mpc (0 si no esta).
--   * la baldosa logica son DOS columnas (x y su pareja x+1 si x es par, x-1 si es impar); de las dos vale el pincel de
--     menor prioridad. Las 8 vecinas estan a dx = -2,0,2,2,2,0,-2,-2 y dy = -1,-1,-1,0,1,1,1,0 (y del motor, hacia arriba).
--   * encima de la base van, de menor a mayor prioridad, los pinceles vecinos de MAS prioridad que la base; cada uno con
--     una mascara de brush.p00: cuadro = TABLA[bits de las vecinas que lo tienen] * 2 + (x & 1). Opacidad v / 31.
--   * trozo de textura: tx = x % W, ty = y % H, y si la cabecera lleva desfase (campo 4 = 1) ty += (x / W) * (H / 2).
-- Aqui cada bloque de 16 x 16 casillas es una sola malla (base + capas) que se pinta de una vez con un shader: los
-- pinceles del mapa van en un ArrayImage y las mascaras en una imagen.
local ffi = require('ffi')
local net = require('src.net')
local u16 = net.u16

local S = {}
S.__index = S

-- 0x498c80: para cada combinacion de las 8 vecinas, la pareja de mascaras (el primer patron que encaja gana).
local TABLA = {
  [0] = 42, 14, 1, 1, 13, 47, 1, 1, 10, 28, 2, 2, 10, 28, 2, 2, 5, 21, 35, 35, 29, 38, 35, 35, 10, 28, 2, 2, 10, 28, 2, 2,
  17, 44, 26, 26, 43, 15, 26, 26, 18, 12, 34, 34, 18, 12, 34, 34, 17, 44, 26, 26, 43, 15, 26, 26, 18, 12, 34, 34, 18, 12,
  34, 34, 6, 30, 36, 36, 22, 37, 36, 36, 20, 23, 4, 4, 20, 23, 4, 4, 39, 45, 7, 7, 46, 33, 7, 7, 20, 23, 4, 4, 20, 23, 4,
  4, 17, 44, 26, 26, 43, 15, 26, 26, 18, 12, 34, 34, 18, 12, 34, 34, 17, 44, 26, 26, 43, 15, 26, 26, 18, 12, 34, 34, 18,
  12, 34, 34, 8, 8, 0, 0, 27, 27, 0, 0, 24, 24, 25, 25, 24, 24, 25, 25, 19, 19, 3, 3, 31, 31, 3, 3, 24, 24, 25, 25, 24,
  24, 25, 25, 16, 16, 32, 32, 11, 11, 32, 32, 41, 41, 40, 40, 41, 41, 40, 40, 16, 16, 32, 32, 11, 11, 32, 32, 41, 41, 40,
  40, 41, 41, 40, 40, 8, 8, 0, 0, 27, 27, 0, 0, 24, 24, 25, 25, 24, 24, 25, 25, 19, 19, 3, 3, 31, 31, 3, 3, 24, 24, 25,
  25, 24, 24, 25, 25, 16, 16, 32, 32, 11, 11, 32, 32, 41, 41, 40, 40, 41, 41, 40, 40, 16, 16, 32, 32, 11, 11, 32, 32, 41,
  41, 40, 40, 41, 41, 40, 40,
}
local DX = { [0] = -2, 0, 2, 2, 2, 0, -2, -2 }
local DY = { [0] = -1, -1, -1, 0, 1, 1, 1, 0 }      -- se aplica tal cual a las filas del .mpc (probado: invertida deja rayas)
local LLENA = 96                                     -- cuadro extra de la imagen de mascaras: opaco (para las bases)

local SHADER = [[
uniform ArrayImage pinceles;
uniform Image mascaras;
varying vec3 vPincel;
varying vec2 vMascara;
#ifdef VERTEX
attribute vec3 PincelUV;
attribute vec2 MascaraUV;
vec4 position(mat4 t, vec4 p) { vPincel = PincelUV; vMascara = MascaraUV; return t * p; }
#endif
#ifdef PIXEL
vec4 effect(vec4 c, Image tex, vec2 tc, vec2 sc) {
  vec4 col = Texel(pinceles, vPincel);
  return vec4(col.rgb, Texel(mascaras, vMascara).r) * c;
}
#endif
]]

local FORMATO = {
  { 'VertexPosition', 'float', 2 }, { 'PincelUV', 'float', 3 }, { 'MascaraUV', 'float', 2 },
}

-- Cabecera y cuadros de brush.bNN: 52 B + paleta RGB565 (256) + W*H cuadros de 32x32 indices.
local function leer_pincel(b)
  if not b or #b < 564 then return nil end
  local W, H, desfase = net.u32(b, 9), net.u32(b, 13), net.u32(b, 17)
  if W < 1 or H < 1 or W > 16 or H > 16 or #b < 564 + W * H * 1024 then return nil end
  return { W = W, H = H, desfase = desfase == 1, datos = b }
end

function S.nuevo(paks, mapa)
  local self = setmetatable({ paks = paks, mapa = mapa, mallas = {} }, S)
  -- prioridad = posicion en la lista de tilesets del .mpc
  self.prioridad = {}
  for i = 0, #mapa.tilesets do
    local id = mapa.tilesets[i]
    if id and self.prioridad[id] == nil then self.prioridad[id] = i end
  end
  self:_pinceles()
  self:_mascaras()
  self.shader = love.graphics.newShader(SHADER)
  self.shader:send('pinceles', self.capas)
  self.shader:send('mascaras', self.img_mascaras)
  return self
end

-- Los pinceles que usa el mapa, cada uno en una capa de 512 x 512 del ArrayImage (cuadro (tx, ty) en (tx*32, ty*32)).
function S:_pinceles()
  local m = self.mapa
  local usados, lista = {}, {}
  for y = 0, m.h - 1 do
    for x = 0, m.w - 1 do
      local id = self:pincel(x, y)
      if id >= 0 and not usados[id] then usados[id] = true; lista[#lista + 1] = id end
    end
  end
  table.sort(lista)
  self.info, self.capa_de = {}, {}
  local datos = {}
  for _, id in ipairs(lista) do
    local p = leer_pincel(self.paks:leer(string.format('brush/brush.b%02x', id)))
    if p then
      local img = love.image.newImageData(512, 512)
      local out = ffi.cast('uint8_t*', img:getPointer())
      local pal = {}
      for i = 0, 255 do
        local v = u16(p.datos, 53 + 2 * i)
        pal[i] = { math.floor(math.floor(v / 2048) % 32 * 255 / 31), math.floor(math.floor(v / 32) % 64 * 255 / 63),
                   math.floor(v % 32 * 255 / 31) }
      end
      local b = p.datos
      for t = 0, p.W * p.H - 1 do
        local tx, ty = t % p.W, math.floor(t / p.W)
        local base = 565 + t * 1024
        for yy = 0, 31 do
          local o = ((ty * 32 + yy) * 512 + tx * 32) * 4
          for xx = 0, 31 do
            local c = pal[b:byte(base + yy * 32 + xx)]
            out[o], out[o + 1], out[o + 2], out[o + 3] = c[1], c[2], c[3], 255
            o = o + 4
          end
        end
      end
      p.datos = nil
      datos[#datos + 1] = img
      self.info[id] = p
      self.capa_de[id] = #datos      -- capa 1-based en Lua, 0-based en el shader (se resta al poner el uv)
    end
  end
  if #datos == 0 then datos[1] = love.image.newImageData(512, 512) end
  self.capas = love.graphics.newArrayImage(datos)
  self.capas:setFilter('nearest', 'nearest')
  self.capas:setWrap('clamp', 'clamp')
end

-- brush.p00: 96 cuadros de 32 x 32 (valores 0..31, 31 = la capa entera) en 16 x 6, mas uno opaco (el 96) para las bases.
function S:_mascaras()
  local b = self.paks:leer('brush/brush.p00')
  local img = love.image.newImageData(512, 7 * 32)
  local out = ffi.cast('uint8_t*', img:getPointer())
  for k = 0, LLENA do
    local tx, ty = k % 16, math.floor(k / 16)
    for yy = 0, 31 do
      local o = ((ty * 32 + yy) * 512 + tx * 32) * 4
      for xx = 0, 31 do
        local v = 255
        if k < LLENA and b and #b >= 32 + (k + 1) * 1024 then
          v = math.floor(b:byte(33 + k * 1024 + yy * 32 + xx) * 255 / 31 + 0.5)
        end
        out[o], out[o + 1], out[o + 2], out[o + 3] = v, v, v, 255
        o = o + 4
      end
    end
  end
  self.img_mascaras = love.graphics.newImage(img)
  self.img_mascaras:setFilter('nearest', 'nearest')
end

-- Pincel de la casilla (x, fila del .mpc); -1 fuera del mapa.
function S:pincel(x, r)
  local m = self.mapa
  if x < 0 or r < 0 or x >= m.w or r >= m.h then return -1 end
  local p = m.celdas + (r * m.w + x) * (m.tam_attr or 6)
  if (m.tam_attr or 6) == 7 then return u16(m.datos, p) end
  return m.datos:byte(p)
end

function S:prio(id) return (id and id >= 0) and (self.prioridad[id] or 0) or 0 end

-- El de menor prioridad de la pareja de columnas (como 0x4998a0).
function S:_de_pareja(x, r, s)
  local a = self:pincel(x, r)
  if a < 0 then return -1 end
  local b = self:pincel(x + s, r)
  if b >= 0 and self:prio(a) > self:prio(b) then a = b end
  return a
end

-- Las capas de la casilla: base y lista { {id, bits} } de menor a mayor prioridad.
function S:capas_de(x, r)
  local s = (x % 2 == 1) and -1 or 1
  local base = self:_de_pareja(x, r, s)
  local pb = self:prio(base)
  local lista = {}
  for k = 0, 7 do
    local nb = self:_de_pareja(x + DX[k], r + DY[k], s)
    if nb >= 0 and nb ~= base and self:prio(nb) > pb then
      local hallado
      for _, c in ipairs(lista) do if c.id == nb then hallado = c; break end end
      if hallado then hallado.bits = hallado.bits + 2 ^ k
      else
        local nuevo = { id = nb, bits = 2 ^ k }
        local j = #lista + 1
        for q = 1, #lista do if self:prio(nb) < self:prio(lista[q].id) then j = q; break end end
        table.insert(lista, j, nuevo)
      end
    end
  end
  return base, lista
end

-- uv del cuadro de textura del pincel para la casilla (x, fila r); y del motor = alto - 1 - r.
function S:_uv(id, x, r)
  local p = self.info[id]
  if not p then return nil end
  local tx = x % p.W
  local ye = self.mapa.h - 1 - r
  local ty = ye
  if p.desfase then ty = ty + math.floor(x / p.W) * math.floor(p.H / 2) end
  ty = ty % p.H
  -- los cuadros estan de arriba abajo en la textura y la y del motor crece hacia arriba
  ty = p.H - 1 - ty
  return tx * 32 / 512, ty * 32 / 512, self.capa_de[id] - 1
end

-- Malla de un bloque de 16 x 16 casillas (o nil si no hay nada que pintar).
function S:malla(cx, cy)
  local clave = cx * 100000 + cy
  local c = self.mallas[clave]
  if c ~= nil then return c or nil end
  local m = self.mapa
  local v = {}
  local function cuadro(px, py, u, w, capa, mu, mv)
    local d, dm = 32 / 512, 32 / 512
    local dmv = 32 / (7 * 32)
    v[#v + 1] = { px, py, u, w, capa, mu, mv }
    v[#v + 1] = { px + 32, py, u + d, w, capa, mu + dm, mv }
    v[#v + 1] = { px + 32, py + 32, u + d, w + d, capa, mu + dm, mv + dmv }
    v[#v + 1] = { px, py, u, w, capa, mu, mv }
    v[#v + 1] = { px + 32, py + 32, u + d, w + d, capa, mu + dm, mv + dmv }
    v[#v + 1] = { px, py + 32, u, w + d, capa, mu, mv + dmv }
  end
  local function mascara(k) return (k % 16) * 32 / 512, math.floor(k / 16) * 32 / (7 * 32) end
  local lu, lv = mascara(LLENA)
  for j = 0, 15 do
    for i = 0, 15 do
      local x, r = cx * 16 + i, cy * 16 + j
      if x < m.w and r < m.h then
        local base, lista = self:capas_de(x, r)
        local px, py = x * 32, r * 32
        local u, w, capa = self:_uv(base, x, r)
        if u then cuadro(px, py, u, w, capa, lu, lv) end
        for _, c in ipairs(lista) do
          local u2, w2, capa2 = self:_uv(c.id, x, r)
          if u2 then
            local mu, mv = mascara(TABLA[c.bits] * 2 + x % 2)
            cuadro(px, py, u2, w2, capa2, mu, mv)
          end
        end
      end
    end
  end
  if #v == 0 then self.mallas[clave] = false; return nil end
  c = love.graphics.newMesh(FORMATO, v, 'triangles', 'static')
  self.mallas[clave] = c
  return c
end

function S:dibujar(c0, r0, c1, r1)
  love.graphics.setShader(self.shader)
  love.graphics.setColor(1, 1, 1, 1)
  for by = math.floor(r0 / 16), math.floor(r1 / 16) do
    for bx = math.floor(c0 / 16), math.floor(c1 / 16) do
      local malla = self:malla(bx, by)
      if malla then love.graphics.draw(malla) end
    end
  end
  love.graphics.setShader()
end

return S
