-- Graficos del cliente instalado: tilesets de pincel (brush/brush.bNN), sprites .shp/.spr y definiciones de objetos (setting/*.obd).
-- Todo se decodifica en memoria a partir de los paks del jugador; nada se guarda en disco.
local bit = require('bit')
local net = require('src.net')
local u16, u32 = net.u16, net.u32

local G = {}
G.__index = G

local function c565(v, bgr)
  local r = math.floor(bit.rshift(v, 11) % 32 * 255 / 31)
  local g = math.floor(bit.rshift(v, 5) % 64 * 255 / 63)
  local b = math.floor(v % 32 * 255 / 31)
  if bgr then r, b = b, r end
  return r / 255, g / 255, b / 255
end

local function i32(s, i)
  local v = u32(s, i)
  return v >= 2147483648 and v - 4294967296 or v
end

function G.nuevo(paks)
  return setmetatable({ paks = paks, ts = {}, spr = {}, defs = nil }, G)
end

-- ---------------------------------------------------------------- tilesets de pincel
-- Devuelve { imagen = Image 512x512, quads = function(x, y) } o nil. La textura se repite cada 16 casillas.
function G:tileset(n)
  local t = self.ts[n]
  if t ~= nil then return t or nil end
  local b = self.paks:leer(string.format('brush/brush.b%02x', n))
  if not b then self.ts[n] = false; return nil end
  local pal = {}
  for i = 0, 255 do
    local r, g, bl = c565(u16(b, 53 + 2 * i))
    pal[i] = { r, g, bl }
  end
  local nt = math.floor((#b - 564) / 1024)
  local lado = math.max(1, math.floor(math.sqrt(nt) + 0.5))
  local px = lado * 32
  local datos = love.image.newImageData(512, 512)
  for ty = 0, lado - 1 do
    for tx = 0, lado - 1 do
      local base = 565 + (ty * lado + tx) * 1024
      if base + 1023 <= #b then
        for yy = 0, 31 do
          for xx = 0, 31 do
            local c = pal[b:byte(base + yy * 32 + xx)]
            local X, Y = tx * 32 + xx, ty * 32 + yy
            -- se repite hasta cubrir 512 x 512
            for ry = Y, 511, px do
              for rx = X, 511, px do datos:setPixel(rx, ry, c[1], c[2], c[3], 1) end
            end
          end
        end
      end
    end
  end
  -- Los pinceles claros tambien son suelo: el b39 (57) es el cielo de nubes que rodea las ciudades flotantes.
  local img = love.graphics.newImage(datos)
  img:setFilter('nearest', 'nearest')
  -- lado nativo del brush (8 o 16…); el atlas 512 lo repite, pero el muestreo usa este periodo.
  -- datos (512x512, rgba8) queda para fundir pinceles pixel a pixel en visor.lua.
  t = { imagen = img, lado = lado, quads = {}, datos = datos }
  self.ts[n] = t
  return t
end

-- Ruido de grano para los bordes entre suelos: brush.p03 (256 casillas de 32x32 = 512x512, valores 5..28) normalizado
-- a 0..1. Es de los propios datos del juego, asi el borde tiene la misma textura que los pinceles.
function G:ruido()
  if self._ruido ~= nil then return self._ruido or nil end
  local b = self.paks:leer('brush/brush.p03')
  if not b or #b < 32 + 262144 then self._ruido = false; return nil end
  local r = {}
  local lo, hi = 255, 0
  for i = 33, 32 + 262144 do local v = b:byte(i); if v < lo then lo = v end; if v > hi then hi = v end end
  local esc = 1 / math.max(1, hi - lo)
  for k = 0, 255 do
    local tx, ty = k % 16, math.floor(k / 16)
    for yy = 0, 31 do
      for xx = 0, 31 do
        r[(ty * 32 + yy) * 512 + tx * 32 + xx] = (b:byte(33 + k * 1024 + yy * 32 + xx) - lo) * esc
      end
    end
  end
  self._ruido = r
  return r
end

-- Quad 32x32: periodo = lado del brush (no siempre 16). brush.b05 etc. son 8×8.
function G:quad_de(t, x, y)
  local L = t.lado or 16
  local tx, ty = x % L, y % L
  if tx < 0 then tx = tx + L end
  if ty < 0 then ty = ty + L end
  local k = tx * L + ty
  local q = t.quads[k]
  if not q then
    q = love.graphics.newQuad(tx * 32, ty * 32, 32, 32, 512, 512)
    t.quads[k] = q
  end
  return q
end

-- ---------------------------------------------------------------- .shp / .spr
local function decodificar_shp(b, pal)
  if b:sub(1, 4) ~= 'TLHS' or #b < 96 then return nil end
  local typ, fl, w, hh = u32(b, 9), u32(b, 13), u32(b, 21), u32(b, 25)
  local ox, oy = i32(b, 29), i32(b, 33)
  if not (w > 0 and w <= 4096 and hh > 0 and hh <= 4096) or #b < 80 + 4 * hh then return nil end
  local L = #b
  local paletted = fl == 768 and typ == 2
  local pal_off = u32(b, 65)
  if paletted and pal_off ~= 0 and pal_off + 512 <= L then
    pal = {}
    for i = 0, 255 do pal[i] = { c565(u16(b, pal_off + 2 * i + 1)) } end
  end
  local bgr = typ == 4
  -- typ 4 con paleta propia (u32 en +64 distinto de 0): 2 bytes por pixel = indice de paleta RGB565 + alfa (marcos de ventana, translucidos)
  local pal_alfa
  if typ == 4 and fl == 768 and pal_off ~= 0 and pal_off + 512 <= L then
    pal_alfa = {}
    for i = 0, 255 do pal_alfa[i] = { c565(u16(b, pal_off + 2 * i + 1)) } end
  end
  local im = love.image.newImageData(w, hh)
  for y = 0, hh - 1 do
    local o = u32(b, 81 + 4 * y)
    while o + 8 <= L do
      local cnt, x, off = u16(b, o + 1), u16(b, o + 3), u32(b, o + 5)
      o = o + 8
      if x == 0xFFFF or (cnt == 0 and off == 0) then break end
      for i = 0, cnt - 1 do
        if x + i >= w then break end
        if paletted then
          local c = pal and off + i < L and pal[b:byte(off + i + 1)]
          if c then im:setPixel(x + i, y, c[1], c[2], c[3], 1) end
        elseif pal_alfa then
          local p = off + 2 * i
          if p + 2 <= L then
            local c = pal_alfa[b:byte(p + 1)]
            im:setPixel(x + i, y, c[1], c[2], c[3], b:byte(p + 2) / 255)
          end
        elseif typ == 4 and fl == 512 then
          -- 32 bits por pixel: B, G, R, A (fondo de casillas, mascaras...)
          local p = off + 4 * i
          if p + 4 <= L then
            local bl, g, r, al = b:byte(p + 1, p + 4)
            im:setPixel(x + i, y, r / 255, g / 255, bl / 255, al / 255)
          end
        else
          local p = off + 2 * i
          if p + 2 <= L then
            local r, g, bl = c565(b:byte(p + 1) + b:byte(p + 2) * 256, bgr)
            im:setPixel(x + i, y, r, g, bl, 1)
          end
        end
      end
    end
  end
  return im, ox, oy
end

local function leer_spr(b)
  if b:sub(1, 4) ~= 'EWSP' then return nil end
  local cnt = u32(b, 9)
  local pal_off = 80 + 12 * cnt
  local primero = u32(b, 81)
  local pal = { crudo = {}, mascara = u32(b, 25) }   -- +24: cuantos colores del principio de la paleta son mascara
  for i = 0, math.max(0, math.floor((primero - pal_off) / 2)) - 1 do
    local v = u16(b, pal_off + 2 * i + 1)
    pal.crudo[i] = v
    pal[i] = { c565(v) }
  end
  local frames, nombres = {}, {}
  for i = 0, cnt - 1 do
    local off, size, noff = u32(b, 85 + 12 * i), u32(b, 89 + 12 * i), u32(b, 93 + 12 * i)
    frames[#frames + 1] = b:sub(off + 1, off + size)
    nombres[#nombres + 1] = b:sub(noff + 1, noff + 16):match('^[^%z]*'):lower():gsub('%.shp$', '')
  end
  return pal, frames, nombres
end

-- Imagen de un archivo de sprite (ruta sin extension, p.ej. "shape/stage/xxx"). Devuelve { img, ox, oy, w, h } o nil.
function G:sprite(ruta, tinte)
  local clave = tinte and (ruta .. '@' .. tinte.k) or ruta
  local c = self.spr[clave]
  if c ~= nil then return c or nil end
  local res = false
  for _, ext in ipairs({ 'shp', 'spr' }) do
    local b = self.paks:leer(ruta .. '.' .. ext)
    if b then
      local im, ox, oy
      if ext == 'shp' then
        im, ox, oy = decodificar_shp(b)
      else
        local pal, frames = leer_spr(b)
        if frames and frames[1] then
          im, ox, oy = decodificar_shp(frames[1], (tinte and pal and pal.crudo) and paleta_tenida(pal, tinte) or pal)
          if im then tinte = nil end            -- ya va en la paleta
        end
      end
      if im then
        if tinte then aplicar_tinte(im, tinte) end
        local img = love.graphics.newImage(im)
        res = { img = img, ox = ox, oy = oy, w = im:getWidth(), h = im:getHeight() }
        break
      end
    end
  end
  self.spr[clave] = res
  return res or nil
end

-- Tinte como angel.dat (SetBias 0x76e3d0 y el retinte de paleta 0x77ca50, 15/11/2026):
--   BaseBias / MaskBias = sesgo, color, rango.  Cada color pasa a HSV 6/5/5 (tono 0..63, saturacion 0..31, brillo 0..31).
--   Ventana de tonos: tono(color) +- (rango & 63), con vuelta; rango >= 128 -> el tono se FIJA a (sesgo & 0xff), si no se
--   le suma. Saturacion += byte 1 del sesgo y brillo += byte 2 (con signo, 0..31). En los .spr de paleta los primeros
--   `mascara` colores usan MaskBias y el resto BaseBias. Un sesgo 0 no toca nada.
local function sb8(v) return v >= 128 and v - 256 or v end
local function hsv565(v)
  local r = bit.band(bit.rshift(v, 11), 31) / 31
  local g = bit.band(bit.rshift(v, 5), 63) / 63
  local b = bit.band(v, 31) / 31
  local mx, mn = math.max(r, g, b), math.min(r, g, b)
  local d = mx - mn
  local h = 0
  if d > 0 then
    if mx == r then h = ((g - b) / d) % 6 elseif mx == g then h = (b - r) / d + 2 else h = (r - g) / d + 4 end
    h = h / 6
  end
  return math.floor(h * 64 + 0.5) % 64, (mx > 0) and math.floor(d / mx * 31 + 0.5) or 0, math.floor(mx * 31 + 0.5)
end
local function rgb_de_hsv(h, s, v)
  h, s, v = (h % 64) / 64 * 6, s / 31, v / 31
  local i = math.floor(h)
  local f = h - i
  local p, q, u = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
  i = i % 6
  if i == 0 then return v, u, p elseif i == 1 then return q, v, p elseif i == 2 then return p, v, u
  elseif i == 3 then return p, q, v elseif i == 4 then return u, p, v else return v, p, q end
end

-- un lado del tinte -> { sesgo, lo, hi, fija, k } o nil (sesgo 0)
local function lado(sesgo, color, rango)
  sesgo, color, rango = tonumber(sesgo) or 0, tonumber(color) or 0, tonumber(rango) or 0
  if sesgo == 0 then return nil end
  local h = hsv565(color)
  local tol = bit.band(rango, 63)
  local lo, hi = h - tol, h + tol
  if lo < 0 then lo, hi = lo + 64, hi + 64 end
  return { sesgo = sesgo, lo = lo, hi = hi, fija = bit.band(rango, 255) >= 128, k = sesgo .. ',' .. color .. ',' .. rango }
end
local function lado_txt(txt)
  if not txt then return nil end
  local a, c, r = txt:match('(0x%x+)%s*,%s*(0x%x+)%s*,%s*(%d+)')
  return a and lado(a, c, r) or nil
end
local function tinte(base, mascara)
  if not base and not mascara then return nil end
  return { base = base, mascara = mascara, k = (base and base.k or '-') .. '|' .. (mascara and mascara.k or '-') }
end

-- color RGB565 retenido por un lado del tinte, o nil si su tono queda fuera de la ventana
local function retenir(v, l)
  local h, s, val = hsv565(v)
  if not ((h >= l.lo and h <= l.hi) or (h + 64 >= l.lo and h + 64 <= l.hi)) then return nil end
  local b0 = bit.band(l.sesgo, 255)
  h = l.fija and (b0 % 64) or ((h + b0) % 64)
  s = math.max(0, math.min(31, s + sb8(bit.band(bit.rshift(l.sesgo, 8), 255))))
  val = math.max(0, math.min(31, val + sb8(bit.band(bit.rshift(l.sesgo, 16), 255))))
  return { rgb_de_hsv(h, s, val) }
end

-- paleta de un .spr retenida: mascara para los primeros pal.mascara colores, base para el resto
local function paleta_tenida(pal, t)
  local out = { crudo = pal.crudo, mascara = pal.mascara }
  local m = pal.mascara or 0
  for i, c in pairs(pal) do
    if type(i) == 'number' then
      local l = (i < m) and t.mascara or t.base
      out[i] = (l and pal.crudo and pal.crudo[i] and retenir(pal.crudo[i], l)) or c
    end
  end
  return out
end

-- imagenes sin paleta: el mismo retinte pixel a pixel con el lado base
function aplicar_tinte(im, t)
  local l = t.base or t.mascara
  if not l then return end
  im:mapPixel(function(x, y, r, g, b, a)
    if a == 0 then return r, g, b, a end
    local v = bit.bor(bit.lshift(math.floor(r * 31 + 0.5), 11), bit.lshift(math.floor(g * 63 + 0.5), 5), math.floor(b * 31 + 0.5))
    local c = retenir(v, l)
    if c then return c[1], c[2], c[3], a end
    return r, g, b, a
  end)
end

-- Bloques de un .obd: texto entre un "[OBJECT]" y el siguiente. Se recorre con find (un gmatch con el delimitador al principio y al final
-- se comia el encabezado del bloque siguiente y perdia uno de cada dos objetos).
local function bloques_obd(texto)
  local pos = texto:find('[OBJECT]', 1, true)
  return function()
    if not pos then return nil end
    local ini = pos + 8
    local sig = texto:find('[OBJECT]', ini, true)
    local bloque = texto:sub(ini, (sig or (#texto + 1)) - 1)
    pos = sig
    return bloque
  end
end

local function sbyte(v) return v >= 128 and v - 256 or v end

-- Tinte de itemicon.xml (variante de color de una prenda): basebias/baserange y maskbias/maskrange, color 0 si no lo trae.
function G:tinte_icono(ic)
  if not ic then return nil end
  return tinte(ic.basebias and lado(ic.basebias, ic.basecolor or 0, ic.baserange or 0) or nil,
               ic.maskbias and lado(ic.maskbias, ic.maskcolor or 0, ic.maskrange or 0) or nil)
end
-- compatibilidad: tinte_de(sesgo, color, rango) = solo mascara
function G:tinte_de(bias, color, rango) return tinte(nil, lado(bias, color, rango)) end

-- Tinte de piel / pelo: setting/color.obd, objeto `seq` (piel 1.., pelo 1001..).
function G:tinte_color(seq)
  if not self.color then
    self.color = {}
    local txt = self.paks:leer('setting/color.obd') or ''
    for bloque in bloques_obd(txt) do
      local sq = tonumber(bloque:match('Sequence%s*=%s*(%d+)'))
      local b = bloque:match('BaseBias%s*=%s*([^\r\n]+)')
      local m = bloque:match('MaskBias%s*=%s*([^\r\n]+)')
      if sq then self.color[sq] = tinte(lado_txt(b), lado_txt(m)) end
    end
  end
  return self.color[seq]
end

-- Tinte de un objeto de cualquier .obd (piezas de char*.obd, NPC y monstruos de npc.obd): su BaseBias y su MaskBias.
function G:tinte_obj(sid)
  self.tintes_obj = self.tintes_obj or {}
  local c = self.tintes_obj[sid]
  if c ~= nil then return c or nil end
  local d = self:definiciones()[sid]
  c = d and tinte(lado_txt(d.basebias), lado_txt(d.maskbias)) or false
  self.tintes_obj[sid] = c
  return c or nil
end
function G:tinte_npc(sid) return self:tinte_obj(sid) end
function G:tinte_mascara(sid) return self:tinte_obj(sid) end

-- Tinte de una prenda: el de su pieza en char*.obd y, encima, lo que traiga la variante de color de su icono.
function G:tinte_pieza(sid, ic)
  local a, b = self:tinte_obj(sid), self:tinte_icono(ic)
  if not b then return a end
  if not a then return b end
  return tinte(b.base or a.base, b.mascara or a.mascara)
end

-- Cuadro `nombre` (o el primero) de un .spr con varios cuadros. Devuelve { img, ox, oy, w, h } o nil.
function G:cuadro_spr(ruta, nombre, tinte)
  local clave = ruta .. '#' .. (nombre or '') .. (tinte and ('@' .. tinte.k) or '')
  local c = self.spr[clave]
  if c ~= nil then return c or nil end
  local res = false
  local b = self.paks:leer(ruta .. '.spr')
  if b then
    local pal, frames, nombres = leer_spr(b)
    if frames and #frames > 0 then
      local k = 1
      if nombre then for i, n in ipairs(nombres) do if n == nombre then k = i; break end end end
      local im, ox, oy = decodificar_shp(frames[k], (tinte and pal.crudo) and paleta_tenida(pal, tinte) or pal)
      if im then res = { img = love.graphics.newImage(im), ox = ox, oy = oy, w = im:getWidth(), h = im:getHeight() } end
    end
  end
  self.spr[clave] = res
  return res or nil
end

-- Indice sprite_id -> ruta de su archivo de reposo (shape/{npc,mon,chr,pet}/<carpeta>/<id>_wait.spr). La carpeta de la
-- definicion no siempre coincide con la real (40053 dice n005 y esta en n052), asi que se busca por el id.
function G:ruta_de_id(sid)
  if not self.por_id then
    local t = {}
    for k in pairs(self.paks.indice) do
      local id = k:match('^shape/[%w]+/[^/]+/(%d+)_wait%.spr$')
      if id and not k:match('^shape/stage') then t[tonumber(id)] = k:sub(1, -5) end
    end
    self.por_id = t
    -- carpeta -> su .spr de espera: la definicion del objeto manda (Directory), no el numero del archivo. Ej.: la 40076 (Assoc. Captain)
    -- apunta a \npc\n039\ (el mago negro), pero el unico 40076_wait.spr esta en n064 (un emblema dorado).
    -- En las carpetas de equipo (shape/chr/iNNNN[g|b]) van dos .spr: el de ir a pie y el montado (+5000); manda el menor.
    local por_dir, num_dir = {}, {}
    for k in pairs(self.paks.indice) do
      local dir, num = k:match('^(shape/[%w]+/[^/]+)/(%d+)_wait%.spr$')
      if dir and not k:match('^shape/stage') and (not num_dir[dir] or tonumber(num) < num_dir[dir]) then
        por_dir[dir], num_dir[dir] = k:sub(1, -5), tonumber(num)
      end
    end
    self.por_dir = por_dir
  end
  local d = self:definiciones()[sid]
  if d and d.dir and d.dir ~= '' then
    local dir = ('shape/' .. d.dir:gsub(string.char(92), '/'):gsub('^/+', ''):gsub('/+$', '')):lower()
    if self.por_dir[dir] then return self.por_dir[dir] end
  end
  return self.por_id[sid]
end

-- Nombres de cuadro (sin extension) de un .spr y su prefijo de animacion ('fw', 'w', 'fr'...). Cacheado.
function G:info_spr(ruta)
  self.info = self.info or {}
  local i = self.info[ruta]
  if i ~= nil then return i or nil end
  local b = self.paks:leer(ruta .. '.spr')
  i = false
  if b then
    local _, frames, nombres = leer_spr(b)
    if nombres and #nombres > 0 then
      local set = {}
      for _, n in ipairs(nombres) do set[n] = true end
      i = { set = set, prefijo = nombres[1]:match('^(%a+)') or '' }
    end
  end
  self.info[ruta] = i
  return i or nil
end

-- Cuadro de la animacion `anim` ('wait', 'run'...) del sprite `id` mirando a la direccion `dig` (3..7) en el paso `paso` (1..6).
-- Nombre: <prefijo>0<paso><dig>, p.ej. fr024. Si falta, prueba otros pasos y al final el primer cuadro.
function G:cuadro_anim(id, anim, dig, paso, tinte)
  local base = self:ruta_de_id(id)
  if not base then return nil end
  local ruta = base:gsub('_wait$', '_' .. anim)
  local info = self:info_spr(ruta)
  if not info then ruta = base; info = self:info_spr(ruta) end
  if not info then return nil end
  for _, p in ipairs({ paso, 2, 1, 3 }) do
    local nombre = info.prefijo .. '0' .. p .. dig
    if info.set[nombre] then return self:cuadro_spr(ruta, nombre, tinte) end
  end
  return self:cuadro_spr(ruta, nil, tinte)
end

-- NPC / criatura / personaje por su sprite_id: cuadro de reposo (el que nombra la definicion, w013*, ..., o el primero).
function G:criatura(sid)
  local ruta = self:ruta_de_id(sid)
  if not ruta then return nil end
  local d = self:definiciones()[sid]
  local primero = d and d.sprite:match('^[Ww]ait%s*,%s*([%w]+)')
  return self:cuadro_spr(ruta, primero and primero:lower())
end

-- ---------------------------------------------------------------- definiciones de objetos
function G:definiciones()
  if self.defs then return self.defs end
  local defs = {}
  -- char*.obd: las piezas de equipo (Sequence 2xxxx..15xxxx, nombre "ITEMnnnn (...)", Directory \chr\i...\); sin ellas las
  -- prendas nuevas (8117, 8130, 4528...) no tenian sprite y el personaje salia desnudo.
  for _, arch in ipairs({ 'setting/mapobj.obd', 'setting/server.obd', 'setting/npc.obd', 'setting/common.obd', 'setting/house.obd', 'setting/m01.obd', 'setting/m02.obd', 'setting/m03.obd', 'setting/npc_alan.obd', 'setting/npc_hch.obd', 'setting/smallgame.obd', 'setting/char.obd', 'setting/char2.obd', 'setting/char3.obd', 'setting/char4.obd' }) do
    local t = self.paks:leer(arch)
    if t then
      for bloque in bloques_obd(t) do
        local d = {}
        for l in bloque:gmatch('[^\r\n]+') do
          local k, v = l:match('^%s*([%w_]+)%s*=%s*(.-)%s*$')
          if k and not l:match('^%s*//') and d[k] == nil then d[k] = v:gsub('//.*$', ''):gsub('%s+$', '') end
        end
        local sid = d.Sequence and tonumber(d.Sequence)
        if sid and not defs[sid] then defs[sid] = { dir = d.Directory or '', sprite = d.Sprite or '', nombre = d.Name or '', proceso = d.Process or '', flags = d.Flags or '', basebias = d.BaseBias, maskbias = d.MaskBias } end
      end
    end
  end
  self.defs = defs
  return defs
end

-- Primer cuadro del objeto `sid`.
-- Piezas de equipo de char*.obd: indice[n][genero] = Sequence de la version a pie (carpeta ...g / ...b, no la "l" ni la
-- montada, que comparte carpeta y lleva +5000 en el Sequence). n es el numero de pieza del doll (nombre "ITEMn").
function G:piezas_char()
  if self._piezas then return self._piezas end
  local idx = {}
  for sid, d in pairs(self:definiciones()) do
    local n = d.nombre and tonumber(d.nombre:match('^ITEM%s*(%d+)'))
    local dir = d.dir and d.dir:lower():gsub(string.char(92), '/'):gsub('/+$', '')
    -- carpeta ...g / ...b (capa normal) o ...gl / ...bl (capa del lado izquierdo, por detras del cuerpo, Sequence +2000):
    -- hay prendas que solo tienen la izquierda (el arco de pulpo 8119 esta solo en i1713bl / i1713gl)
    local gen = dir and (dir:match('^/?chr/i%d+([gb]l)$') or dir:match('^/?chr/i%d+([gb])$') or dir:match('^/?chr/i%w-([gb])$'))
    if n and gen then
      idx[n] = idx[n] or {}
      if not idx[n][gen] or sid < idx[n][gen] then idx[n][gen] = sid end
    end
  end
  self._piezas = idx
  return idx
end

function G:objeto(sid)
  local d = self:definiciones()[sid]
  if not d then return nil end
  if d.sprite:lower():sub(1, 4) ~= 'wait' then return nil end
  local carpeta = d.dir:gsub('\\', '/'):gsub('^/+', ''):gsub('/+$', '')
  local primero = true
  for tok in d.sprite:gmatch('[^,]+') do
    if primero then primero = false
    else
      tok = tok:gsub('^%s+', ''):gsub('%s+$', '')
      if tok:match('^[%w]+%-[%w]+%-[%w]+$') then
        return self:sprite('shape/' .. carpeta .. '/' .. tok:lower())
      end
    end
  end
  return nil
end

-- Secuencia Wait de un objeto del mapa: lista de { spr, dur } en orden. En el obd: "Wait, A-B-C, #8, D-E-F, ..." donde #N fija los
-- N/60 s de los cuadros siguientes (8 por defecto). Devuelve nil si el objeto no tiene sprite; una lista de un solo cuadro es estatico.
function G:objeto_frames(sid)
  self.frames_obj = self.frames_obj or {}
  local c = self.frames_obj[sid]
  if c ~= nil then return c or nil end
  local d = self:definiciones()[sid]
  local lista = false
  if d and d.sprite:lower():sub(1, 4) == 'wait' then
    local carpeta = d.dir:gsub('\\', '/'):gsub('^/+', ''):gsub('/+$', '')
    local dur, primero = 8 / 60, true
    local out = {}
    for tok in d.sprite:gmatch('[^,]+') do
      if primero then primero = false
      else
        tok = tok:gsub('^%s+', ''):gsub('%s+$', '')
        local n = tok:match('^#(%d+)$')
        if n then dur = tonumber(n) / 60
        elseif tok:match('^[%w]+%-[%w]+%-[%w]+$') then
          local spr = self:sprite('shape/' .. carpeta .. '/' .. tok:lower())
          if spr then out[#out + 1] = { spr = spr, dur = math.max(dur, 1 / 60) } end
        end
      end
    end
    if #out > 0 then lista = out end
  end
  self.frames_obj[sid] = lista
  return lista or nil
end

-- Definicion de un icono de item (setting/itemicon.xml, itemicon1.xml pisa): { dir, normal, maskbias, maskcolor, maskrange }.
function G:def_icono_item(id)
  if not self.iconos_item then
    self.iconos_item = {}
    for _, f in ipairs({ 'setting/itemicon.xml', 'setting/itemicon1.xml' }) do
      local x = self.paks:leer(f) or ''
      for attr in x:gmatch('<icon%s+([^>]-)/?>') do
        local a = {}
        for k, v in attr:gmatch('([^%s=<>"/]+)="([^"]*)"') do a[k] = v end
        local n = tonumber(a.id)
        if n and a.normal then self.iconos_item[n] = a end
      end
    end
  end
  return self.iconos_item[id]
end

-- Efectos (objetos Process = SP_CLASS_EFFECT en m01/m02/m03/effect.obd): { frames = { spr... }, dur, aditivo }. Los ids de efecto del
-- 0x0011 y de magic.xml (特效編號) son su Sequence. "Wait, #8, c071, c072" lista los cuadros; si solo hay uno con numero al final
-- (fs0001, hole01) y existen los siguientes archivos consecutivos, se reproducen todos. #N = N/60 s por cuadro (999 = sin ritmo: 5/60).
function G:efecto(id)
  if not self.efectos then
    self.efectos = {}
    for _, f in ipairs({ 'm01', 'm02', 'm03', 'effect', 'common', 'house', 'smallgame' }) do
      local t = self.paks:leer('setting/' .. f .. '.obd') or ''
      for bloque in bloques_obd(t) do
        if bloque:find('SP_CLASS_EFFECT', 1, true) then
          local sq = tonumber(bloque:match('Sequence%s*=%s*(%d+)'))
          if sq and not self.efectos[sq] then
            self.efectos[sq] = {
              dir = (bloque:match('Directory%s*=%s*([^\r\n]+)') or ''):gsub('\\', '/'):gsub('^/+', ''):gsub('/+$', ''),
              sprite = bloque:match('Sprite%s*=%s*([^\r\n]+)') or '',
              aditivo = bloque:find('SP_ATTRIB_WHITELIGHT', 1, true) ~= nil,
            }
          end
        end
      end
    end
    self.efectos_listos = {}
  end
  local listo = self.efectos_listos[id]
  if listo ~= nil then return listo or nil end
  local d = self.efectos[id]
  local res = false
  if d and d.sprite:lower():sub(1, 4) == 'wait' then
    local nombres, dur = {}, 5 / 60
    local primero = true
    for tok in d.sprite:gmatch('[^,]+') do
      tok = tok:gsub('^%s+', ''):gsub('%s+$', '')
      if primero then primero = false
      else
        local n = tok:match('^#(%d+)$')
        if n then if tonumber(n) <= 60 then dur = tonumber(n) / 60 end
        elseif tok:match('^[%w_]+$') then nombres[#nombres + 1] = tok:lower() end
      end
    end
    if #nombres == 1 then
      local pre, num = nombres[1]:match('^(.-)(%d+)$')
      if pre then
        local ancho, k = #num, tonumber(num) + 1
        while k < tonumber(num) + 60 and self.paks:existe('shape/' .. d.dir .. '/' .. pre .. string.format('%0' .. ancho .. 'd', k) .. '.shp') do
          nombres[#nombres + 1] = pre .. string.format('%0' .. ancho .. 'd', k)
          k = k + 1
        end
      end
    end
    local frames = {}
    for _, n in ipairs(nombres) do
      local spr = self:sprite('shape/' .. d.dir .. '/' .. n)
      if spr then frames[#frames + 1] = spr end
    end
    if #frames > 0 then res = { frames = frames, dur = dur, aditivo = d.aditivo } end
  end
  self.efectos_listos[id] = res
  return res or nil
end

return G
