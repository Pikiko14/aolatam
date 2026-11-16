-- Aspecto de un personaje a partir de su equipo, con las tablas del propio cliente:
--   item (setting/eng/item.xml)  : 編號 -> 原型外觀 (el numero de "doll")
--   doll (setting/eng/doll.xml)  : 編號 -> numeros de pieza por ranura (頭部, 身體, 腳部, 手部, 主手, 副手, 背部, 座騎 ...)
--   pieza N -> shape/chr/i<N><g|b>/<id>_wait.spr   (id = 20000 + N para g, 30000 + N para b; la capa trasera lleva +5000)
-- Cada pieza es un sprite suelto con el mismo origen: dibujadas en el mismo punto componen el personaje.
local E = {}
E.__index = E

-- Orden de dibujo, de atras hacia delante (座騎 / montura va detras del cuerpo).
local CAPAS = {
  { '座騎', 'montura' }, { '背部另一層', 'trasera' }, { '背部', 'espalda' }, { '身體', 'cuerpo' },
  { '腳部', 'pies' }, { '手部', 'manos' }, { '頭部', 'cabeza' }, { '副手', 'mano_izq' }, { '主手', 'mano_der' },
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

-- Ids de sprite de la pieza N. Prefijo de genero (20000 mujer / 30000 hombre), si falta el otro genero,
-- luego el id pelado; capa trasera = id + 5000. `permitir_montura` acepta carpetas h...
function E:pieza(n, genero, permitir_montura)
  local clave = n .. genero .. (permitir_montura and 'm' or '')
  if self.cache[clave] ~= nil then return self.cache[clave] or nil end
  local pre = genero == 'b' and 30000 or 20000
  local otro = genero == 'b' and 20000 or 30000
  local res = false
  -- Primero la pieza por su nombre en char*.obd ("ITEMn", carpeta del genero y luego la del otro): es como la busca
  -- angel.dat y cubre las prendas nuevas, cuyo Sequence no es 2/3xxxx + n (8117 -> 125117, 4528 -> 100028).
  local por_nombre = self.gfx:piezas_char()[n]
  local otro_gen = genero == 'b' and 'g' or 'b'
  if por_nombre and not permitir_montura then
    local function primera(lista)
      for _, sid in ipairs(lista) do
        local ruta = sid and self.gfx:ruta_de_id(sid)
        if ruta and ruta:sub(1, 10) == 'shape/chr/' then return sid end
      end
    end
    -- capa normal y capa izquierda, cada una del genero y si falta del otro
    local base = primera({ por_nombre[genero], por_nombre[otro_gen] })
    local izq = primera({ por_nombre[genero .. 'l'], por_nombre[otro_gen .. 'l'] })
    if base or izq then res = { base = base, izq = izq } end
  end
  -- Si no: prefijo del genero, luego el otro (mujer sin 2xxxx usa el 3xxxx del hombre: 31156…),
  -- y al final el id pelado. Los 1156-1158 en i914g son retales; el traje completo esta en i118x b.
  for _, id in ipairs(res and {} or { pre + n, otro + n, n }) do
    local ruta = self.gfx:ruta_de_id(id)
    -- solo shape/chr: el mismo numero puede ser NPC/monstruo
    if ruta and ruta:sub(1, 10) == 'shape/chr/' then
      local ok = false
      if permitir_montura and ruta:match('^shape/chr/h') then
        ok = true
      elseif ruta:match('^shape/chr/i') then
        -- Evitar retales de pelo en i9xx con id < 20000; la ropa valida va con 2/3xxxx o fuera de i9xx.
        local pelo = ruta:match('^shape/chr/i9[0-2]%d[bg]/') and id < 20000
        ok = not pelo
      elseif ruta:match('^shape/chr/r') and id == n then
        ok = true
      end
      if ok then
        res = { base = id, otra = self.gfx:ruta_de_id(id + 5000) and (id + 5000) or nil }
        break
      end
    end
  end
  self.cache[clave] = res
  return res or nil
end

-- 26/28/30: en item.xml la 原型外觀 apunta a dolls 129/131/133 (qipao/mono), no al uniforme.
-- angel.dat pinta mal igual; nosotros usamos los dolls de estudiante (15/14/16 → piezas 1157/1156/1158)
-- que SI tienen spr en i914g..i916g (mujer) y 3xxxx (hombre).
local DOLL_ESTUDIANTE = { [26] = 15, [28] = 14, [30] = 16 }
-- Por si el inventario aun trae 26/28/30 en un hombre (personajes viejos).
local SUSTITUTO_HOMBRE = { [26] = 3410, [28] = 3409, [30] = 3411 }

-- Lista de ids de sprite (de atras hacia delante) para el equipo `items` (ids de item) de un personaje 'g' (mujer) o 'b' (hombre).
function E:capas(items, genero)
  self:_cargar()
  local partes, fuente = {}, {}
  for _, raw in ipairs(items) do
    local it = (genero == 'b' and SUSTITUTO_HOMBRE[raw]) or raw
    local doll_id = DOLL_ESTUDIANTE[raw] or (self.items[it] and self.items[it]) or self.items[raw]
    local doll = doll_id and self.dolls[doll_id]
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
    local p = n and self:pieza(n, genero, c[2] == 'montura')
    if p then
      if c[2] == 'trasera' or c[2] == 'cuerpo' or c[2] == 'montura' then
        if p.otra then out[#out + 1] = { id = p.otra, item = fuente[c[2]], atras = true } end
      end
      -- la capa ...l ("左") es la prenda en la MANO IZQUIERDA: la usa la ranura de mano secundaria (副手), y el resto la
      -- normal; con el espejo se voltea todo igual (capturas de Windows del 15/11/2026: el ramo cambia de lado al girar).
      -- El arco de pulpo 8119 es de mano secundaria y por eso solo existe en i1713bl / i1713gl.
      local id = (c[2] == 'mano_izq') and (p.izq or p.base) or (p.base or p.izq)
      if c[2] ~= 'trasera' and id then
        out[#out + 1] = { id = id, item = fuente[c[2]], atras = c[2] == 'montura' or nil }
      end
    end
  end
  return out, partes
end

-- Tinte de una prenda: lo que lleva su icono en itemicon.xml (maskbias, maskcolor, maskrange); si no, el de su objeto en char*.obd.
function E:tinte_de_item(it)
  local ic = it and self.iconos[it] and self.gfx:def_icono_item(self.iconos[it])
  return self.gfx:tinte_icono(ic)
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
    local doll_id = DOLL_ESTUDIANTE[it] or (self.items[it] and self.items[it])
    local doll = doll_id and self.dolls[doll_id]
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
    local ic = c.item and self.iconos[c.item] and g:def_icono_item(self.iconos[c.item])
    local spec = { id = c.id, tinte = g:tinte_pieza(c.id, ic) }
    if c.atras then detras[#detras + 1] = spec else out[#out + 1] = spec end
  end
  for _, c in ipairs(detras) do final[#final + 1] = c end
  for _, c in ipairs(out) do final[#final + 1] = c end
  return final, partes
end

return E
