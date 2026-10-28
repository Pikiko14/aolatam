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
  local img = love.graphics.newImage(datos)
  img:setFilter('nearest', 'nearest')
  t = { imagen = img, quads = {} }
  self.ts[n] = t
  return t
end

-- Quad 32x32 de la textura para la casilla (x, y): la textura se repite cada 16 casillas.
function G:quad_de(t, x, y)
  local k = (x % 16) * 16 + (y % 16)
  local q = t.quads[k]
  if not q then
    q = love.graphics.newQuad((x % 16) * 32, (y % 16) * 32, 32, 32, 512, 512)
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
  local pal = {}
  for i = 0, math.max(0, math.floor((primero - pal_off) / 2)) - 1 do pal[i] = { c565(u16(b, pal_off + 2 * i + 1)) } end
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
        if frames and frames[1] then im, ox, oy = decodificar_shp(frames[1], pal) end
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

-- Tinte: BaseBias / MaskBias = <sesgo BGR de 3 bytes con signo>, <color base RGB565>, <tolerancia>. A cada pixel parecido al color base
-- se le suma el sesgo, en proporcion a lo parecido que es (1 - distancia / tolerancia). Interpretacion deducida de color.obd y char*.obd
-- (el color base coincide con el gris/piel del sprite); falta compararla con el cliente original.
function aplicar_tinte(im, t)
  im:mapPixel(function(x, y, r, g, b, a)
    if a == 0 then return r, g, b, a end
    local d = math.max(math.abs(r - t.br), math.abs(g - t.bg), math.abs(b - t.bb))
    local w = 1 - d / t.tol
    if w <= 0 then return r, g, b, a end
    return math.min(1, math.max(0, r + t.dr * w)), math.min(1, math.max(0, g + t.dg * w)), math.min(1, math.max(0, b + t.db * w)), a
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

-- "0xf60425, 0x9492, 160" -> tinte { dr, dg, db (0..1), br, bg, bb (0..1), tol (0..1), k }
local function leer_tinte(txt)
  local a, c, tol = txt:match('(0x%x+)%s*,%s*(0x%x+)%s*,%s*(%d+)')
  if not a then return nil end
  local sesgo, base = tonumber(a), tonumber(c)
  local br, bg, bb = c565(base)
  return { dr = sbyte(bit.band(sesgo, 255)) / 255, dg = sbyte(bit.band(bit.rshift(sesgo, 8), 255)) / 255,
           db = sbyte(bit.band(bit.rshift(sesgo, 16), 255)) / 255, br = br, bg = bg, bb = bb, tol = tonumber(tol) / 255, k = txt }
end

-- Tinte a partir de los tres valores sueltos (maskbias, maskcolor, maskrange) de itemicon.xml.
function G:tinte_de(bias, color, rango)
  return leer_tinte(bias .. ', ' .. color .. ', ' .. rango)
end

-- Tinte de piel / pelo: setting/color.obd, objeto `seq` (piel 1.., pelo 1001..).
function G:tinte_color(seq)
  if not self.color then
    self.color = {}
    local t = self.paks:leer('setting/color.obd') or ''
    for bloque in bloques_obd(t) do
      local sq = tonumber(bloque:match('Sequence%s*=%s*(%d+)'))
      local b = bloque:match('BaseBias%s*=%s*([^\r\n]+)')
      if sq and b then self.color[sq] = leer_tinte(b) end
    end
  end
  return self.color[seq]
end

-- Tinte propio de un objeto de personaje (MaskBias en char*.obd), o nil.
function G:tinte_mascara(id)
  self.mascaras = self.mascaras or {}
  if self.mascaras[id] ~= nil then return self.mascaras[id] or nil end
  if not self.char_obd then
    self.char_obd = {}
    for _, n in ipairs({ 'char', 'char2', 'char3', 'char4' }) do
      self.char_obd[#self.char_obd + 1] = self.paks:leer('setting/' .. n .. '.obd') or ''
    end
  end
  local res = false
  local aguja = '\nSequence = ' .. id .. '\r\n'
  for _, t in ipairs(self.char_obd) do
    local i = t:find(aguja, 1, true)
    if i then
      local fin = t:find('[OBJECT]', i, true) or (i + 600)
      local b = t:sub(i, fin):match('MaskBias%s*=%s*([^\r\n]+)')
      if b then res = leer_tinte(b) or false end
      break
    end
  end
  self.mascaras[id] = res
  return res or nil
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
      local im, ox, oy = decodificar_shp(frames[k], pal)
      if im and tinte then aplicar_tinte(im, tinte) end
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
    local por_dir = {}
    for k in pairs(self.paks.indice) do
      local dir = k:match('^(shape/[%w]+/[^/]+)/%d+_wait%.spr$')
      if dir and not k:match('^shape/stage') then por_dir[dir] = k:sub(1, -5) end
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
  for _, arch in ipairs({ 'setting/mapobj.obd', 'setting/server.obd', 'setting/npc.obd', 'setting/common.obd', 'setting/house.obd', 'setting/m01.obd', 'setting/m02.obd', 'setting/m03.obd', 'setting/npc_alan.obd', 'setting/npc_hch.obd', 'setting/smallgame.obd' }) do
    local t = self.paks:leer(arch)
    if t then
      for bloque in bloques_obd(t) do
        local d = {}
        for l in bloque:gmatch('[^\r\n]+') do
          local k, v = l:match('^%s*([%w_]+)%s*=%s*(.-)%s*$')
          if k and not l:match('^%s*//') and d[k] == nil then d[k] = v:gsub('//.*$', ''):gsub('%s+$', '') end
        end
        local sid = d.Sequence and tonumber(d.Sequence)
        if sid and not defs[sid] then defs[sid] = { dir = d.Directory or '', sprite = d.Sprite or '', nombre = d.Name or '', proceso = d.Process or '' } end
      end
    end
  end
  self.defs = defs
  return defs
end

-- Primer cuadro del objeto `sid`.
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
