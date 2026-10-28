-- Aspecto de un personaje a partir de su equipo, con las tablas del propio cliente:
--   item (setting/eng/item.xml)  : 編號 -> 原型外觀 (el numero de "doll")
--   doll (setting/eng/doll.xml)  : 編號 -> numeros de pieza por ranura (頭部, 身體, 腳部, 手部, 主手, 副手, 背部, 座騎 ...)
--   pieza N -> shape/chr/i<N><g|b>/<id>_wait.spr   (id = 20000 + N para g, 30000 + N para b; la capa trasera lleva +5000)
-- Cada pieza es un sprite suelto con el mismo origen: dibujadas en el mismo punto componen el personaje.
local E = {}
E.__index = E

-- Orden de dibujo, de atras hacia delante.
local CAPAS = {
  { '背部另一層', 'trasera' }, { '背部', 'espalda' }, { '身體', 'cuerpo' }, { '腳部', 'pies' },
  { '手部', 'manos' }, { '頭部', 'cabeza' }, { '副手', 'mano_izq' }, { '主手', 'mano_der' },
}

local function atributos(linea)
  local t = {}
  for k, v in linea:gmatch('([^%s=<>"]+)="([^"]*)"') do t[k] = v end
  return t
end

function E.nuevo(paks, gfx)
  return setmetatable({ paks = paks, gfx = gfx, items = nil, dolls = nil, carpetas = nil, cache = {} }, E)
end

function E:_cargar()
  if self.items then return end
  self.items, self.dolls, self.iconos = {}, {}, {}
  for _, f in ipairs({ 'item', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7', 'item8', 'item9' }) do
    local xi = self.paks:leer('setting/eng/' .. f .. '.xml') or ''
    for linea in xi:gmatch('<[^/>][^>]*>') do
      local a = atributos(linea)
      local id = tonumber(a['編號'])
      if id and a['原型外觀'] and not self.items[id] then self.items[id] = tonumber(a['原型外觀']) end
      if id and a['原型介面'] and not self.iconos[id] then self.iconos[id] = tonumber(a['原型介面']) end
    end
  end
  local xd = self.paks:leer('setting/eng/doll.xml') or self.paks:leer('setting/big5/doll.xml') or ''
  for linea in xd:gmatch('<[^/>][^>]*>') do
    local a = atributos(linea)
    local id = tonumber(a['編號'])
    if id then self.dolls[id] = a end
  end
end

-- Ids de sprite de la pieza N. El numero de doll es el id del archivo (1160_wait.spr) o, si no existe tal cual, el id con el prefijo de
-- genero (20000 + N mujer, 30000 + N hombre); la capa trasera es el mismo con +5000. Devuelve { base, otra } o nil.
function E:pieza(n, genero)
  local clave = n .. genero
  if self.cache[clave] ~= nil then return self.cache[clave] or nil end
  local pre = genero == 'b' and 30000 or 20000
  local res = false
  for _, id in ipairs({ pre + n, n }) do      -- primero el id con prefijo de genero; sin respaldo al otro genero
    local ruta = self.gfx:ruta_de_id(id)
    -- solo vale una ruta de personaje (shape/chr): el mismo numero puede ser de un NPC o un monstruo
    -- solo carpetas de ropa (i...): las r... son disfraces y robots, las h... monturas
    -- las carpetas i900..i926 son PELO (objetos 1001..1163 de char.obd): un numero de pieza que cae ahi no es una prenda
    if ruta and ruta:sub(1, 11) == 'shape/chr/i' and not ruta:match('^shape/chr/i9[0-2]%d[bg]/') then
      res = { base = id, otra = self.gfx:ruta_de_id(id + 5000) and (id + 5000) or nil }
      break
    end
  end
  self.cache[clave] = res
  return res or nil
end

-- Lista de ids de sprite (de atras hacia delante) para el equipo `items` (ids de item) de un personaje 'g' (mujer) o 'b' (hombre).
function E:capas(items, genero)
  self:_cargar()
  local partes, fuente = {}, {}
  for _, it in ipairs(items) do
    local doll = self.items[it] and self.dolls[self.items[it]]
    if doll then
      for _, c in ipairs(CAPAS) do
        local n = tonumber(doll[c[1]])
        if n then partes[c[2]] = n; fuente[c[2]] = it end        -- la ultima prenda puesta gana la ranura
      end
    end
  end
  local out = {}
  for _, c in ipairs(CAPAS) do
    local n = partes[c[2]]
    local p = n and self:pieza(n, genero)
    if p then
      if c[2] == 'trasera' or c[2] == 'cuerpo' then
        if p.otra then out[#out + 1] = { id = p.otra, item = fuente[c[2]], atras = true } end
      end
      if c[2] ~= 'trasera' and p.base then out[#out + 1] = { id = p.base, item = fuente[c[2]] } end
    end
  end
  return out, partes
end

-- Tinte de una prenda: lo que lleva su icono en itemicon.xml (maskbias, maskcolor, maskrange); si no, el de su objeto en char*.obd.
function E:tinte_de_item(it)
  local ic = it and self.iconos[it] and self.gfx:def_icono_item(self.iconos[it])
  if ic and ic.maskbias then return self.gfx:tinte_de(ic.maskbias, ic.maskcolor or '0', ic.maskrange or '0') end
  return nil
end

-- Personaje completo (setting/char*.obd): cuerpo base 1000 (hombre) / 1100 (mujer), pelo 1001+estilo / 1101+estilo
-- (estilo = segundo byte de la apariencia) y encima las piezas de equipo. Un casco de cobertura total (頭部全罩) oculta el pelo.
function E:personaje(items, ap, genero)
  self:_cargar()
  local capas, partes = self:capas(items, genero)
  local out = {}
  local g = self.gfx
  local base = genero == 'b' and 999 or 1100     -- 999 = cuerpo base masculino (el 1000 no tiene archivo)
  if g:ruta_de_id(base) then
    -- apariencia: [1] genero, [2] estilo de pelo, [3] ?, [4] color de pelo, [5] color de piel (color.obd: piel 1.., pelo 1001..)
    out[#out + 1] = { id = base, tinte = ap and ap[5] and g:tinte_color(1 + ap[5]) or nil }
  end
  local oculta = false
  for _, it in ipairs(items) do
    local doll = self.items[it] and self.dolls[self.items[it]]
    -- un casco de cobertura total solo oculta el pelo si su pieza se puede dibujar (si no, el personaje quedaria calvo)
    if doll and doll['頭部全罩'] == '是' and tonumber(doll['頭部']) and self:pieza(tonumber(doll['頭部']), genero) then oculta = true end
  end
  local estilo = ap and ap[2]
  if estilo and not oculta then
    local pelo = (genero == 'b' and 1001 or 1101) + estilo
    if g:ruta_de_id(pelo) then
      out[#out + 1] = { id = pelo, tinte = ap[4] and g:tinte_color(1001 + ap[4]) or nil }
    end
  end
  -- las capas traseras (capa extra de la prenda: capa, cola de la tunica) van DETRAS del cuerpo; el resto, encima
  local final, detras = {}, {}
  for _, c in ipairs(capas) do
    local spec = { id = c.id, tinte = self:tinte_de_item(c.item) or g:tinte_mascara(c.id) }
    if c.atras then detras[#detras + 1] = spec else out[#out + 1] = spec end
  end
  for _, c in ipairs(detras) do final[#final + 1] = c end
  for _, c in ipairs(out) do final[#final + 1] = c end
  return final, partes
end

return E
