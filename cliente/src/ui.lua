-- Ventanas del cliente, leidas de sus propios recursos: setting/eng/wnd0N.xml (ventanas e iconos), shape/wnd01 (imagenes).
--   <window class= range="x,y,w,h" id= icon= ...> con <child>id</child>; <icon id= dir= normal=> da el sprite de fondo.
--   derive="N" hereda de otra ventana. Los comportamientos (OnCommand...) estan en los luas del cliente y NO se interpretan aqui:
--   cada ventana se programa a mano sobre estos datos (la de inventario es la primera).
local U = {}
U.__index = U

local ARCHIVOS = { 'wnd01', 'wnd02', 'wnd03', 'wnd04', 'wnd05' }

local function atributos(txt)
  local t = {}
  for k, v in txt:gmatch('([^%s=<>"/]+)="([^"]*)"') do t[k] = v end
  return t
end

function U.nuevo(paks, gfx)
  return setmetatable({ paks = paks, gfx = gfx, ventanas = nil, iconos = {}, items = nil, imagenes = {} }, U)
end

-- Indice id -> ventana / icono de todos los wnd0N.xml (una sola pasada, la primera vez).
function U:_cargar()
  if self.ventanas then return end
  self.ventanas = {}
  for _, n in ipairs(ARCHIVOS) do
    local t = self.paks:leer('setting/eng/' .. n .. '.xml') or ''
    for attr, cierre in t:gmatch('<window%s+([^>]-)(/?)>') do
      local a = atributos(attr)
      if a.id and not self.ventanas[a.id] then
        a.hijos = {}
        self.ventanas[a.id] = a
        a._pos = nil
      end
    end
    -- hijos: se vuelve a recorrer con posiciones para leer el cuerpo de cada ventana con contenido
    local pos = 1
    while true do
      local i, j, attr, cierre = t:find('<window%s+([^>]-)(/?)>', pos)
      if not i then break end
      pos = j + 1
      if cierre ~= '/' then
        local fin = t:find('</window>', pos, true)
        local cuerpo = fin and t:sub(pos, fin - 1) or ''
        local id = attr:match('id="(%d+)"')
        local w = id and self.ventanas[id]
        if w and #w.hijos == 0 then
          for h in cuerpo:gmatch('<child>(%d+)</child>') do w.hijos[#w.hijos + 1] = h end
          w.estilo = cuerpo:match('<style%s+([^>]-)/?>') or ''
          w.eventos = {}
          for ev, fn in cuerpo:gmatch('<(On%w+)>%s*([%w_]+)%s*</On%w+>') do w.eventos[ev] = fn end
        end
      end
    end
    for attr in t:gmatch('<icon%s+([^>]-)/?>') do
      local a = atributos(attr)
      if a.id and not self.iconos[a.id] then self.iconos[a.id] = a end
    end
  end
end

function U:ventana(id)
  self:_cargar()
  local w = self.ventanas[tostring(id)]
  if not w then return nil end
  if w.derive and w.derive ~= w.id and self.ventanas[w.derive] then
    local base = self.ventanas[w.derive]
    for k, v in pairs(base) do if w[k] == nil and k ~= 'hijos' then w[k] = v end end
  end
  return w
end

local function rango(w)
  local x, y, an, al = (w.range or '0,0,0,0'):match('(-?%d+),(-?%d+),(-?%d+),(-?%d+)')
  return tonumber(x) or 0, tonumber(y) or 0, tonumber(an) or 0, tonumber(al) or 0
end

-- Imagen de un icono de ventana (estado 'normal', 'focus', 'down'...).
function U:imagen_icono(id, estado)
  self:_cargar()
  local ic = self.iconos[tostring(id)]
  if not ic or not ic.dir then return nil end
  local nombre = ic[estado or 'normal'] or ic.normal
  if nombre == 'normal' then nombre = ic.normal end
  if not nombre then return nil end
  local ruta = 'shape/' .. ic.dir:gsub('\\', '/'):gsub('^/+', ''):gsub('/+$', '') .. '/' .. nombre
  local c = self.imagenes[ruta]
  if c == nil then c = self.gfx:sprite(ruta) or false; self.imagenes[ruta] = c end
  return c or nil
end

-- Iconos de item: item.xml da el id de icono (原型介面) y setting/itemicon*.xml lo define:
--   <icon id="5129" dir="\item\" normal="i0129" maskbias=".." maskcolor=".." maskrange="..">  ->  shape/item/i0129.shp, con tinte.
function U:icono_item(item_id)
  if not self.items then
    self.items, self.icon_item = {}, {}
    for _, f in ipairs({ 'item', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7', 'item8', 'item9' }) do
      local t = self.paks:leer('setting/eng/' .. f .. '.xml') or ''
      for linea in t:gmatch('<[^/>][^>]*>') do
        local a = atributos(linea)
        local id = tonumber(a['編號'])
        if id and not self.items[id] then self.items[id] = { icono = tonumber(a['原型介面']), nombre = a['基本名稱'], precio = tonumber(a['價格']) or 0 } end
      end
    end
    for _, f in ipairs({ 'setting/itemicon.xml', 'setting/itemicon1.xml' }) do
      local x = self.paks:leer(f) or ''
      for attr in x:gmatch('<icon%s+([^>]-)/?>') do
        local a = atributos(attr)
        local id = tonumber(a.id)
        if id and a.normal then self.icon_item[id] = a end      -- itemicon1 (mas nuevo) pisa a itemicon
      end
    end
  end
  local it = self.items[item_id]
  if not it or not it.icono then return nil, it end
  local ic = self.icon_item[it.icono]
  if not ic then return nil, it end
  local ruta = 'shape/' .. ic.dir:gsub('\\', '/'):gsub('^/+', ''):gsub('/+$', '') .. '/' .. ic.normal
  local tinte = ic.maskbias and self.gfx:tinte_de(ic.maskbias, ic.maskcolor or '0', ic.maskrange or '0') or nil
  local clave = ruta .. (tinte and tinte.k or '')
  local c = self.imagenes[clave]
  if c == nil then c = self.gfx:sprite(ruta, tinte) or false; self.imagenes[clave] = c end
  return c or nil, it
end

-- Ventana de inventario (3031): fondo, 25 casillas de 5 x 5 (ids 3101..3125) y botones. `mundo` aporta items y cantidades.
-- Devuelve la lista de casillas con su rectangulo para detectar el raton.
function U:dibujar_inventario(x, y, mundo, raton)
  local w = self:ventana(3031)
  if not w then return end
  local _, _, an, al = rango(w)
  local fondo = self:imagen_icono('3031')
  love.graphics.setColor(1, 1, 1)
  if fondo then love.graphics.draw(fondo.img, x, y) else
    love.graphics.setColor(0.15, 0.15, 0.2, 0.95); love.graphics.rectangle('fill', x, y, an, al); love.graphics.setColor(1, 1, 1)
  end
  local casillas, tip = {}, nil
  for i, hid in ipairs(w.hijos) do
    local h = self:ventana(hid)
    if h then
      local hx, hy, hw, hh = rango(h)
      local n = tonumber(hid)
      if n >= 3101 and n <= 3125 then
        local casilla = 20 + (n - 3101)
        local px, py = x + hx, y + hy
        local item = mundo.items and mundo.items[casilla]
        if item then
          local img, info = self:icono_item(item)
          if img then love.graphics.draw(img.img, px, py) else love.graphics.print('?', px + 14, py + 10) end
          local cant = mundo.cantidades and mundo.cantidades[casilla]
          if cant and cant > 1 then love.graphics.print(tostring(cant), px + 2, py + 22) end
          if raton and raton[1] >= px and raton[1] < px + hw and raton[2] >= py and raton[2] < py + hh then
            tip = (info and info.nombre or ('item ' .. item)) .. (cant and cant > 1 and (' x' .. cant) or '')
          end
        end
        casillas[#casillas + 1] = { casilla = casilla, x = px, y = py, w = hw, h = hh }
      elseif h.class == 'WND_CLASS_BUTTON' and h.icon then
        local img = self:imagen_icono(h.icon)
        if img then love.graphics.draw(img.img, x + hx, y + hy) end
      end
    end
  end
  -- dinero (3034 muestra el total; el valor viene en la ficha, aqui solo la etiqueta)
  if tip then
    local tw = love.graphics.getFont():getWidth(tip) + 8
    love.graphics.setColor(0, 0, 0, 0.85); love.graphics.rectangle('fill', raton[1] + 12, raton[2] + 8, tw, 20)
    love.graphics.setColor(1, 1, 1); love.graphics.print(tip, raton[1] + 16, raton[2] + 11)
  end
  return casillas
end

-- Dibujo generico de una ventana: su icono de fondo y, encima, el icono de cada hijo (botones, marcos). Sirve para estudiar ventanas nuevas.
function U:dibujar_generica(id, x, y, omitir_base)
  local w = self:ventana(id)
  if not w then return end
  local img = w.icon and self:imagen_icono(w.icon)
  love.graphics.setColor(1, 1, 1, self._alfa or 1)
  if img then love.graphics.draw(img.img, x, y) end
  for _, hid in ipairs(w.hijos) do
    local h = self:ventana(hid)
    if h and not (omitir_base and h.class == 'WND_CLASS_BASE') then
      local hx, hy = rango(h)
      local ic = h.icon and self:imagen_icono(h.icon)
      love.graphics.setColor(1, 1, 1, self._alfa or 1)
      if ic then love.graphics.draw(ic.img, x + hx, y + hy) end
      if h.title and h.title ~= '' and h.class == 'WND_CLASS_BUTTON' then love.graphics.print(h.title, x + hx + 3, y + hy + 1) end
    end
  end
  return w
end

-- Texto de msg.xml: <字串 編號="id" 文字="..."/>. Se sustituyen %1, %2... por las cadenas de la linea y se quitan los codigos de color (/c$2 ... /c*).
function U:mensaje(mid, cadenas)
  if not self.msgs then
    self.msgs = {}
    local t = self.paks:leer('setting/eng/msg.xml') or ''
    for attr in t:gmatch('<[^>/ ]+%s+([^>]-)/?>') do
      local a = atributos(attr)
      local id = tonumber(a['編號'])
      if id and a['文字'] and not self.msgs[id] then self.msgs[id] = a['文字'] end
    end
  end
  local t = self.msgs[mid] or ('[msg ' .. tostring(mid) .. ']')
  t = t:gsub('&quot;', '"'):gsub('&amp;', '&'):gsub('&lt;', '<'):gsub('&gt;', '>'):gsub('&apos;', "'")
  t = t:gsub('/c%*', ''):gsub('/c[%$#]?%w*', ''):gsub('\\n', '\n')
  t = t:gsub('%%(%d)', function(n) return (cadenas and cadenas[tonumber(n)]) or '' end)
  return t
end

-- Nombre de una habilidad (setting/eng/skill.xml: <技能 編號 名稱>).
function U:habilidad_nombre(id)
  if not self.nombres_hab then
    self.nombres_hab = {}
    local t = self.paks:leer('setting/eng/skill.xml') or ''
    for n, nombre in t:gmatch('編號="(%d+)"%s+名稱="([^"]*)"') do self.nombres_hab[tonumber(n)] = nombre end
  end
  return self.nombres_hab[id] or ('Skill ' .. id)
end

-- Titulo (setting/eng/crown.xml: <crown 編號 封號>).
function U:titulo_nombre(id)
  if not self.titulos then
    self.titulos = {}
    local t = self.paks:leer('setting/eng/crown.xml') or ''
    for n, nombre in t:gmatch('編號="(%d+)"%s+封號="([^"]*)"') do self.titulos[tonumber(n)] = (nombre:gsub('%s+$', '')) end
  end
  return self.titulos[id] or ''
end

-- Retrato del NPC (shape/face/fNNN) o nil.
function U:retrato(val)
  local ruta = string.format('shape/face/f%03d', val or 0)
  local c = self.imagenes[ruta]
  if c == nil then c = self.gfx:sprite(ruta) or false; self.imagenes[ruta] = c end
  return c or nil
end

-- Cuadro de dialogo del NPC. Devuelve las opciones con su rectangulo: { { x, y, w, h, valor } }.
-- valor = lo que se manda en C2S 0x000B: 1 para seguir, 10 + indice para elegir una opcion.
function U:dibujar_dialogo(d, ancho, alto, raton)
  local an, al = 560, 170
  local x, y = (ancho - an) / 2, alto - al - 170
  love.graphics.setColor(0.05, 0.12, 0.35, 0.94); love.graphics.rectangle('fill', x, y, an, al, 6, 6)
  love.graphics.setColor(0.4, 0.7, 1); love.graphics.rectangle('line', x, y, an, al, 6, 6)
  love.graphics.setColor(1, 1, 1)
  local ret = self:retrato(d.val)
  local tx = x + 12
  if ret then
    local k = math.min(1, (al - 20) / ret.h)       -- el retrato se reduce para caber en el cuadro
    love.graphics.draw(ret.img, x + 10, y + 10, 0, k, k)
    tx = x + 10 + ret.w * k + 12
  end
  local texto = self:mensaje(d.mid, d.cadenas)
  love.graphics.printf(texto, tx, y + 12, x + an - tx - 12)
  local opciones = {}
  if #d.opciones > 0 then
    for i, mid in ipairs(d.opciones) do
      local oy = y + al - 12 - (#d.opciones - i + 1) * 20
      local ow = an - 24
      local sobre = raton and raton[1] >= x + 12 and raton[1] < x + 12 + ow and raton[2] >= oy and raton[2] < oy + 18
      love.graphics.setColor(sobre and 1 or 0.75, sobre and 0.9 or 0.85, sobre and 0.4 or 1)
      love.graphics.print('> ' .. self:mensaje(mid, d.cadenas), x + 16, oy)
      opciones[#opciones + 1] = { x = x + 12, y = oy, w = ow, h = 18, valor = 10 + i - 1 }
    end
  else
    love.graphics.setColor(0.7, 0.8, 1); love.graphics.print('(clic para continuar)', x + an - 150, y + al - 20)
    opciones[1] = { x = x, y = y, w = an, h = al, valor = 1 }
  end
  love.graphics.setColor(1, 1, 1)
  return opciones
end

-- Ventana de equipo (2001). La posicion de las casillas no esta en el XML (la pone el ejecutable): salen de medir el fondo w010_3.
-- Casillas del servidor: 1 cabeza, 2 cuerpo, 3 mano derecha, 4 mano izquierda, 5 guantes, 6 zapatos, 7 espalda, 10 montura, 616 burbuja.
local CASILLAS_EQUIPO = {
  { 1, 59, 10 }, { 616, 108, 10 }, { 2, 10, 52 }, { 7, 108, 52 }, { 3, 10, 94 }, { 4, 108, 94 }, { 5, 10, 136 }, { 6, 108, 136 }, { 10, 59, 177 },
}

function U:dibujar_equipo(x, y, mundo, raton)
  self:dibujar_generica(2001, x, y)
  local tip
  for _, c in ipairs(CASILLAS_EQUIPO) do
    local item = mundo.items and mundo.items[c[1]]
    if item then
      local img, info = self:icono_item(item)
      if img then love.graphics.draw(img.img, x + c[2], y + c[3]) end
      if raton and raton[1] >= x + c[2] and raton[1] < x + c[2] + 36 and raton[2] >= y + c[3] and raton[2] < y + c[3] + 36 then
        tip = info and info.nombre or ('item ' .. item)
      end
    end
  end
  if tip then
    local tw = love.graphics.getFont():getWidth(tip) + 8
    love.graphics.setColor(0, 0, 0, 0.85); love.graphics.rectangle('fill', raton[1] + 12, raton[2] + 8, tw, 20)
    love.graphics.setColor(1, 1, 1); love.graphics.print(tip, raton[1] + 16, raton[2] + 11)
  end
end

-- Tiendas: setting/shop.xml, <商店 編號="N"><item1>id</item1>...</商店>. Devuelve la lista de ids de item en orden.
function U:stock_tienda(id)
  if not self.tiendas then
    self.tiendas = {}
    local t = self.paks:leer('setting/shop.xml') or ''
    for sid, cuerpo in t:gmatch('<[^>]-編號="(%d+)"[^>]*>(.-)</[^>]+>%s*</') do
      local lista = {}
      for n, it in cuerpo:gmatch('<item(%d+)>(%d+)</item') do lista[tonumber(n)] = tonumber(it) end
      local ordenada = {}
      for i = 1, 400 do if lista[i] then ordenada[#ordenada + 1] = lista[i] end end
      self.tiendas[tonumber(sid)] = ordenada
    end
  end
  return self.tiendas[id] or {}
end

-- Ventana de tienda de NPC (S2C 0x0034 [shop_id]). Fondo y marcos del propio cliente (ventana 3081); lista de 5 filas por pagina.
-- Clic en una fila = comprar 1 (C2S 0x0027 [n=1][item][cantidad]). Devuelve las filas { x, y, w, h, item } y el boton de cerrar.
function U:dibujar_tienda(x, y, t, mundo, raton)
  local stock = self:stock_tienda(t.id)
  local fondo = self:imagen_icono('3081')
  love.graphics.setColor(1, 1, 1)
  if fondo then love.graphics.draw(fondo.img, x, y) end
  love.graphics.setColor(0, 0, 0, 0.55); love.graphics.rectangle('fill', x + 2, y + 2, 252, 188)
  love.graphics.setColor(1, 1, 1)
  love.graphics.print('Shop ' .. t.id .. '   page ' .. (t.pagina + 1) .. '/' .. math.max(1, math.ceil(#stock / 5)), x + 8, y - 16)
  local filas, tip = {}, nil
  for i = 1, 5 do
    local item = stock[t.pagina * 5 + i]
    if item then
      local fy = y + 2 + (i - 1) * 38
      local img, info = self:icono_item(item)
      local sobre = raton and raton[1] >= x + 2 and raton[1] < x + 254 and raton[2] >= fy and raton[2] < fy + 36
      love.graphics.setColor(sobre and 0.2 or 0.1, sobre and 0.3 or 0.18, sobre and 0.55 or 0.4, 0.85)
      love.graphics.rectangle('fill', x + 2, fy, 252, 36)
      love.graphics.setColor(1, 1, 1)
      if img then love.graphics.draw(img.img, x + 2, fy) end
      love.graphics.print(info and info.nombre or ('item ' .. item), x + 44, fy + 3)
      local precio = info and info.precio or 0
      love.graphics.setColor(1, 0.85, 0.3); love.graphics.print(precio .. ' Gold', x + 44, fy + 18)
      love.graphics.setColor(1, 1, 1)
      filas[#filas + 1] = { x = x + 2, y = fy, w = 252, h = 36, item = item }
    end
  end
  love.graphics.setColor(1, 0.85, 0.3)
  love.graphics.print('Gold: ' .. mundo:oro(), x + 8, y + 196)
  love.graphics.setColor(1, 1, 1)
  love.graphics.print('[ ] pagina   Esc cerrar   clic compra 1   I + clic vende (Mayus: pila)', x + 8, y + 214)
  return filas
end

-- Misiones: setting/eng/quest.xml, <任務 編號 任務名稱 任務類型 任務前言 步驟01 ...>. El %N% de un paso es un contador del servidor (aqui 0).
function U:mision(id)
  if not self.quests then
    self.quests = {}
    local t = self.paks:leer('setting/eng/quest.xml') or ''
    for linea in t:gmatch('<任務%s+([^>]-)/?>') do
      local a = atributos(linea)
      local qid = tonumber(a['編號'])
      if qid and not self.quests[qid] then
        local pasos = {}
        for i = 1, 40 do
          local txt = a[string.format('步驟%02d', i)]
          if txt then pasos[#pasos + 1] = txt end
        end
        self.quests[qid] = { nombre = a['任務名稱'] or ('quest ' .. qid), tipo = a['任務類型'] or '', intro = a['任務前言'] or '', pasos = pasos }
      end
    end
  end
  return self.quests[id]
end

local function limpiar(t)
  t = t:gsub('&quot;', '"'):gsub('&amp;', '&'):gsub('&lt;', '<'):gsub('&gt;', '>'):gsub('&apos;', "'")
  t = t:gsub('/c%*', ''):gsub('/c[%$#]?%w*', ''):gsub('\\n', '\n'):gsub('%%%d+%%', '0')
  return t
end

-- Registro de misiones: lista a la izquierda (clic para elegir) y detalle a la derecha. `sel` es el indice elegido.
-- paso = pasos ya cumplidos (el servidor manda total de pasos si la mision esta completa).
function U:dibujar_misiones(x, y, mundo, sel)
  local an, al = 560, 330
  love.graphics.setColor(0.05, 0.12, 0.35, 0.95); love.graphics.rectangle('fill', x, y, an, al, 6, 6)
  love.graphics.setColor(0.4, 0.7, 1); love.graphics.rectangle('line', x, y, an, al, 6, 6)
  love.graphics.setColor(1, 1, 1); love.graphics.print('Quest log   (Q cierra)', x + 10, y + 8)
  local filas = {}
  local lista = mundo.misiones or {}
  for i, m in ipairs(lista) do
    local q = self:mision(m.id)
    local fy = y + 32 + (i - 1) * 36
    if fy + 34 > y + al then break end
    love.graphics.setColor(i == sel and 0.9 or 0.7, i == sel and 0.9 or 0.8, i == sel and 0.3 or 1)
    love.graphics.printf((i == sel and '> ' or '  ') .. (q and q.nombre or ('quest ' .. m.id)), x + 10, fy, 205)
    filas[#filas + 1] = { x = x + 6, y = fy, w = 205, h = 34, indice = i }
  end
  if #lista == 0 then love.graphics.setColor(0.8, 0.85, 1); love.graphics.print('No quests.', x + 10, y + 40) end
  local m = lista[sel or 1]
  local q = m and self:mision(m.id)
  if q then
    love.graphics.setColor(1, 0.9, 0.5); love.graphics.printf(q.nombre .. '  [' .. q.tipo .. ']', x + 220, y + 32, an - 232)
    love.graphics.setColor(1, 1, 1); love.graphics.printf(limpiar(q.intro), x + 220, y + 70, an - 232)
    local py = y + 140
    for i, paso in ipairs(q.pasos) do
      local hecho = i <= m.paso
      love.graphics.setColor(hecho and 0.5 or 1, hecho and 1 or 1, hecho and 0.5 or (i == m.paso + 1 and 0.4 or 1))
      love.graphics.printf((hecho and '[x] ' or (i == m.paso + 1 and '[>] ' or '[ ] ')) .. limpiar(paso), x + 220, py, an - 232)
      py = py + 34
    end
  end
  love.graphics.setColor(1, 1, 1)
  return filas
end

-- Magias: setting/eng/magic.xml (<法術 編號 介面圖號 名稱 消耗MP 射程 前置時間 後置時間 說明>) e iconos en setting/skillicon.xml
-- (<icon id dir="\skill\" normal="m157">) -> shape/skill/m157.shp.
function U:magia(id)
  if not self.magias then
    self.magias = {}
    local t = self.paks:leer('setting/eng/magic.xml') or ''
    for linea in t:gmatch('<法術%s+([^>]-)/?>') do
      local a = atributos(linea)
      local mid = tonumber(a['編號'])
      if mid and not self.magias[mid] then
        self.magias[mid] = {
          nombre = a['名稱'] or ('magic ' .. mid), icono = tonumber(a['介面圖號']), efecto = tonumber(a['特效編號']), mp = tonumber(a['消耗MP']) or 0,
          rango = tonumber(a['射程']) or 1, previo = tonumber(a['前置時間']) or 0, posterior = tonumber(a['後置時間']) or 1000,
          texto = a['說明'] or '', ataque = a['攻擊型'] == '是',
        }
      end
    end
    self.icon_skill = {}
    local x = self.paks:leer('setting/skillicon.xml') or ''
    for attr in x:gmatch('<icon%s+([^>]-)/?>') do
      local a = atributos(attr)
      if a.id and a.normal then self.icon_skill[tonumber(a.id)] = a end
    end
  end
  return self.magias[id]
end

function U:icono_magia(mg)
  if not mg or not mg.icono then return nil end
  local ic = self.icon_skill[mg.icono]
  if not ic then return nil end
  local ruta = 'shape/' .. ic.dir:gsub('\\', '/'):gsub('^/+', ''):gsub('/+$', '') .. '/' .. ic.normal
  local c = self.imagenes[ruta]
  if c == nil then c = self.gfx:sprite(ruta) or false; self.imagenes[ruta] = c end
  return c or nil
end

-- Barra de habilidades abajo al centro: las 10 primeras ranuras, teclas 1..9 y 0. `enfriando[id]` = segundos que faltan (visual).
-- Devuelve los rectangulos { x, y, w, h, indice } para el clic.
function U:dibujar_barra(ancho, alto, mundo, enfriando, raton)
  self:magia(0)
  local n = 10
  local x0, y0 = (ancho - n * 40) / 2, alto - 52
  local filas, tip = {}, nil
  for i = 1, n do
    local x = x0 + (i - 1) * 40
    love.graphics.setColor(0, 0, 0, 0.55); love.graphics.rectangle('fill', x, y0, 38, 38, 4, 4)
    love.graphics.setColor(0.4, 0.6, 1, 0.8); love.graphics.rectangle('line', x, y0, 38, 38, 4, 4)
    local e = mundo.barra and mundo.barra[i]
    if e and e.tipo == 1 then
      local mg = self:magia(e.id)
      local img = self:icono_magia(mg)
      love.graphics.setColor(1, 1, 1)
      if img then love.graphics.draw(img.img, x + 1, y0 + 1) else love.graphics.print(tostring(e.id), x + 3, y0 + 12) end
      local falta = enfriando and enfriando[e.id]
      if falta and falta > 0 then
        love.graphics.setColor(0, 0, 0, 0.6); love.graphics.rectangle('fill', x, y0, 38, 38, 4, 4)
        love.graphics.setColor(1, 1, 1); love.graphics.print(string.format('%.1f', falta), x + 8, y0 + 11)
      end
      if raton and raton[1] >= x and raton[1] < x + 38 and raton[2] >= y0 and raton[2] < y0 + 38 then
        tip = (mg and mg.nombre or ('magic ' .. e.id)) .. (mg and (' - MP ' .. mg.mp) or '')
      end
    end
    love.graphics.setColor(1, 1, 0.6); love.graphics.print(tostring(i % 10), x + 2, y0 + 1)
    filas[#filas + 1] = { x = x, y = y0, w = 38, h = 38, indice = i }
  end
  if tip then
    local tw = love.graphics.getFont():getWidth(tip) + 8
    love.graphics.setColor(0, 0, 0, 0.85); love.graphics.rectangle('fill', raton[1] + 12, raton[2] - 28, tw, 20)
    love.graphics.setColor(1, 1, 1); love.graphics.print(tip, raton[1] + 16, raton[2] - 25)
  end
  love.graphics.setColor(1, 1, 1)
  return filas
end

-- Escenas: setting/eng/stage.xml (<場景 編號 名稱 地圖檔 雷達圖="smap\041">); el minimapa es shape/smap/<NNN>.shp.
function U:escena(id)
  if not self.escenas then
    self.escenas = {}
    local t = self.paks:leer('setting/eng/stage.xml') or ''
    for linea in t:gmatch('<場景%s+([^>]-)/?>') do
      local a = atributos(linea)
      local sid = tonumber(a['編號'])
      if sid and not self.escenas[sid] then
        self.escenas[sid] = { nombre = a['名稱'] or ('stage ' .. sid), radar = (a['雷達圖'] or ''):gsub('\\', '/'), musica = a['配樂檔1'] and a['配樂檔1']:gsub('\\', '/') or nil }
      end
    end
  end
  return self.escenas[id]
end

-- Minimapa arriba a la derecha: imagen de la escena y puntos (verde = yo, amarillo = NPC, rojo = monstruo, blanco = jugador).
-- `mapa` da el tamano del mundo en casillas. `grande` agranda el cuadro (tecla M).
function U:dibujar_minimapa(ancho, mundo, mapa, grande, ancla_x, ancla_y, ancho_fijo)
  local esc = mundo.stage and self:escena(mundo.stage)
  if not esc or not mapa then return end
  local img = esc.radar ~= '' and self:imagen_radar('shape/' .. esc.radar) or nil
  local an = ancho_fijo or (grande and 360 or 180)
  if grande and ancho_fijo then an = ancho_fijo * 2 end
  local k = img and (an / img.w) or (an / mapa.w)
  local al = img and (img.h * k) or (mapa.h * k)
  local x, y = ancla_x or (ancho - an - 10), ancla_y or 10
  if grande and ancla_x then x = ancho - an - 4 end
  love.graphics.setColor(0, 0, 0, 0.6); love.graphics.rectangle('fill', x - 3, y - 3, an + 6, al + 6, 4, 4)
  love.graphics.setColor(1, 1, 1)
  if img then love.graphics.draw(img.img, x, y, 0, k, k) end
  local sx, sy = an / (mapa.w * 32), al / (mapa.h * 32)
  for _, e in pairs(mundo.ents) do
    if not e.muerto then
      if e.yo then love.graphics.setColor(0.2, 1, 0.3)
      elseif e.clase == 200 then love.graphics.setColor(1, 0.9, 0.2)
      elseif e.jugador then love.graphics.setColor(1, 1, 1)
      else love.graphics.setColor(1, 0.25, 0.2) end
      love.graphics.circle('fill', x + e.x * sx, y + (mapa.h * 32 - e.y) * sy, e.yo and 3 or 1.5)
    end
  end
  love.graphics.setColor(1, 1, 1)
  love.graphics.printf(esc.nombre, x - 3, y + al + 6, an + 6, 'center')
end

function U:imagen_radar(ruta)
  self.radares = self.radares or {}
  local c = self.radares[ruta]
  if c == nil then c = self.gfx:sprite(ruta) or false; self.radares[ruta] = c end
  return c or nil
end

-- Nombre, nivel y barra de experiencia (abajo, sobre la barra de habilidades).
function U:dibujar_hud(ancho, alto, mundo)
  local yo = mundo.yo and mundo.ents[mundo.yo]
  if yo then
    love.graphics.setColor(1, 1, 1)
    love.graphics.print((yo.nombre or '') .. '   Lv ' .. (mundo.nivel or '?'), 220, 8)
  end
  if mundo.exp and mundo.exp_sig and mundo.exp_sig > 0 then
    local an = 400
    local x, y = (ancho - an) / 2, alto - 66
    local pct = math.max(0, math.min(1, mundo.exp / mundo.exp_sig))
    love.graphics.setColor(0, 0, 0, 0.6); love.graphics.rectangle('fill', x, y, an, 9, 3, 3)
    love.graphics.setColor(0.95, 0.75, 0.15); love.graphics.rectangle('fill', x + 1, y + 1, (an - 2) * pct, 7, 3, 3)
    love.graphics.setColor(1, 1, 1)
    love.graphics.print(string.format('EXP %.2f%%', pct * 100), x + an + 8, y - 3)
  end
  love.graphics.setColor(1, 1, 1)
end

-- Lista de amigos (tecla F): nombre, estado y escena; clic elige, Supr borra, I invita (se escribe el nombre en el chat con "/amigo nombre").
-- Devuelve las filas { x, y, w, h, indice } para el clic.
function U:dibujar_amigos(x, y, mundo, sel)
  local an, al = 280, 300
  love.graphics.setColor(0.05, 0.12, 0.35, 0.95); love.graphics.rectangle('fill', x, y, an, al, 6, 6)
  love.graphics.setColor(0.4, 0.7, 1); love.graphics.rectangle('line', x, y, an, al, 6, 6)
  love.graphics.setColor(1, 1, 1); love.graphics.print('Friends   (F cierra, Supr borra, /amigo nombre invita)', x + 8, y + 8)
  local filas = {}
  for i, a in ipairs(mundo.amigos or {}) do
    local fy = y + 32 + (i - 1) * 20
    if fy + 18 > y + al then break end
    local sobre = i == sel
    love.graphics.setColor(sobre and 0.25 or 0.1, sobre and 0.4 or 0.2, sobre and 0.7 or 0.4, 0.8)
    love.graphics.rectangle('fill', x + 6, fy, an - 12, 18, 3, 3)
    love.graphics.setColor(a.conectado and 0.4 or 0.6, a.conectado and 1 or 0.6, a.conectado and 0.5 or 0.6)
    love.graphics.print((a.conectado and '[on] ' or '[off] ') .. a.nombre, x + 12, fy + 1)
    if a.conectado and a.escena then
      local esc = self:escena(a.escena)
      love.graphics.setColor(0.8, 0.85, 1); love.graphics.print(esc and esc.nombre or ('stage ' .. a.escena), x + 150, fy + 1)
    end
    filas[#filas + 1] = { x = x + 6, y = fy, w = an - 12, h = 18, indice = i }
  end
  if #(mundo.amigos or {}) == 0 then love.graphics.setColor(0.8, 0.85, 1); love.graphics.print('No friends yet.', x + 12, y + 40) end
  love.graphics.setColor(1, 1, 1)
  return filas
end

-- Aviso de invitacion de amistad (abajo a la izquierda del centro).
function U:dibujar_invitacion(ancho, alto, inv)
  local an, al = 380, 44
  local x, y = (ancho - an) / 2, 70
  love.graphics.setColor(0.35, 0.2, 0.05, 0.95); love.graphics.rectangle('fill', x, y, an, al, 6, 6)
  love.graphics.setColor(1, 0.85, 0.4); love.graphics.rectangle('line', x, y, an, al, 6, 6)
  love.graphics.setColor(1, 1, 1)
  love.graphics.printf(inv.nombre .. ' wants to be your friend', x, y + 6, an, 'center')
  love.graphics.printf('[Y] accept     [N] decline', x, y + 24, an, 'center')
end

-- Tamano (ancho, alto) de una ventana del cliente, de su "range".
function U:tamano(id)
  local w = self:ventana(id)
  if not w then return 0, 0 end
  local _, _, an, al = rango(w)
  return an, al
end

-- Marcos del HUD con los recursos del cliente (main.lua / quickcmd.lua / chat.lua de los luas): panel de personaje 158 arriba a la
-- izquierda, barra rapida 182 en (210, 0), minimapa 269 arriba a la derecha, menu 116 abajo a la derecha y chat 134 abajo a la izquierda.
-- Devuelve las posiciones para que el resto del HUD (barras, texto) se dibuje encima.
function U:marcos_hud(ancho, alto, minimapa)
  local pos = {}
  love.graphics.setColor(1, 1, 1)
  local function poner(nombre, id, x, y)
    self:dibujar_generica(id, x, y, false)
    local an, al = self:tamano(id)
    pos[nombre] = { x = x, y = y, w = an, h = al }
  end
  self._alfa = nil      -- el panel y el chat del original son translucidos
  self:dibujar_generica(158, 0, 0, true)
  self._alfa = nil
  do local an, al = self:tamano(158); pos.personaje = { x = 0, y = 0, w = an, h = al } end
  poner('rapida', 182, 210, 0)
  local anm = self:tamano(269)
  poner('minimapa', 269, ancho - anm, 0)
  local anc, alc = self:tamano(116)
  poner('menu', 116, ancho - anc - 4, alto - alc - 6)
  local _, alch = self:tamano(134)
  self._alfa = nil
  poner('chat', 134, 0, alto - alch - 6)
  self._alfa = nil
  return pos
end

-- HUD con el aspecto del cliente original: panel de personaje (158), barra rapida F1-F12 (182), minimapa (269), menu (116) y chat (134)
-- tal como los crean main.lua, quickcmd.lua y chat.lua de los luas. Devuelve { barra = filas, menu = filas }.
local MENU = { { 117, 'inventario' }, { 119, 'misiones' }, { 120, 'amigos' }, { 125, 'minimapa' } }

local function barra_h(x, y, an, al, frac, r, g, b)
  love.graphics.setColor(0, 0, 0, 0.55); love.graphics.rectangle('fill', x, y, an, al)
  love.graphics.setColor(r, g, b); love.graphics.rectangle('fill', x, y, an * math.max(0, math.min(1, frac)), al)
end

function U:dibujar_hud_original(ancho, alto, mundo, enfriando, raton, grande, escribiendo, texto)
  local pos = self:marcos_hud(ancho, alto)
  local salida = { barra = {}, menu = {} }
  love.graphics.setColor(1, 1, 1)
  -- panel de personaje: nombre, nivel y barras de HP (rojo), MP (azul), SP (amarillo) y experiencia
  local P = pos.personaje
  local yo = mundo.yo and mundo.ents[mundo.yo]
  love.graphics.setColor(1, 1, 1)
  if yo then love.graphics.print(yo.nombre or '', P.x + 102, P.y + 2) end
  love.graphics.print(tostring(mundo.nivel or ''), P.x + 86, P.y + 17)
  local st = mundo.stats
  if st and st.hp_max > 0 then
    barra_h(P.x + 116, P.y + 18, 100, 10, st.hp / st.hp_max, 0.85, 0.15, 0.15)
    barra_h(P.x + 116, P.y + 31, 100, 10, st.mp / math.max(1, st.mp_max), 0.2, 0.4, 0.95)
    love.graphics.setColor(1, 1, 1)
    love.graphics.print(st.hp .. '/' .. st.hp_max, P.x + 120, P.y + 17, 0, 0.8, 0.8)
    love.graphics.print(st.mp .. '/' .. st.mp_max, P.x + 120, P.y + 30, 0, 0.8, 0.8)
  end
  if mundo.exp and mundo.exp_sig and mundo.exp_sig > 0 then
    barra_h(P.x + 116, P.y + 57, 100, 4, mundo.exp / mundo.exp_sig, 0.95, 0.75, 0.15)
  end
  -- barra rapida: 12 casillas de 31 px desde (+35, +3); F1..F12 = ranuras 1..12 de la barra de habilidades
  local R = pos.rapida
  self:magia(0)
  local tip
  for i = 1, 12 do
    local x, y = R.x + 35 + (i - 1) * 31, R.y + 3
    local e = mundo.barra and mundo.barra[i]
    if e and e.tipo == 1 then
      local mg = self:magia(e.id)
      local img = self:icono_magia(mg)
      love.graphics.setColor(1, 1, 1)
      if img then love.graphics.draw(img.img, x, y, 0, 31 / 36, 31 / 36) end
      local falta = enfriando and enfriando[e.id]
      if falta and falta > 0 then
        love.graphics.setColor(0, 0, 0, 0.6); love.graphics.rectangle('fill', x, y, 31, 31)
        love.graphics.setColor(1, 1, 1); love.graphics.print(string.format('%.1f', falta), x + 4, y + 9, 0, 0.9, 0.9)
      end
      if raton and raton[1] >= x and raton[1] < x + 31 and raton[2] >= y and raton[2] < y + 31 then
        tip = (mg and mg.nombre or ('magic ' .. e.id)) .. (mg and (' - MP ' .. mg.mp) or '')
      end
    end
    salida.barra[#salida.barra + 1] = { x = x, y = y, w = 31, h = 31, indice = i }
  end
  -- minimapa debajo de la barra del marco 269
  local M = pos.minimapa
  self:dibujar_minimapa(ancho, mundo, self.mapa_actual, grande, M.x, M.y + M.h + 2, M.w > 0 and M.w or 160)
  -- chat: 6 lineas en el area de trabajo de la ventana 141 (9,17+4,306x78) y la linea de entrada de la 136 (27,106,254x16)
  local C = pos.chat
  love.graphics.setScissor(C.x + 9, C.y + 21, 306, 78)
  love.graphics.setColor(1, 1, 1)
  local n = #mundo.chat
  for i = math.max(1, n - 5), n do love.graphics.print(mundo.chat[i], C.x + 9, C.y + 21 + (i - math.max(1, n - 5)) * 13) end
  love.graphics.setScissor()
  if escribiendo then
    love.graphics.setColor(0, 0, 0, 0.35); love.graphics.rectangle('fill', C.x + 27, C.y + 106, 254, 16)
    love.graphics.setColor(1, 1, 1); love.graphics.print(texto .. '_', C.x + 31, C.y + 107)
  else
    love.graphics.setColor(1, 1, 1, 0.6); love.graphics.print('Enter: chat', C.x + 31, C.y + 107)
  end
  -- menu inferior: rectangulos de los botones que ya tienen ventana
  local Q = pos.menu
  for _, m in ipairs(MENU) do
    local w = self:ventana(m[1])
    if w then
      local hx, hy, hw, hh = rango(w)
      salida.menu[#salida.menu + 1] = { x = Q.x + hx, y = Q.y + hy, w = hw, h = hh, accion = m[2] }
    end
  end
  if tip then
    local tw = love.graphics.getFont():getWidth(tip) + 8
    love.graphics.setColor(0, 0, 0, 0.85); love.graphics.rectangle('fill', raton[1] + 12, raton[2] + 12, tw, 20)
    love.graphics.setColor(1, 1, 1); love.graphics.print(tip, raton[1] + 16, raton[2] + 15)
  end
  love.graphics.setColor(1, 1, 1)
  return salida
end

-- Panel del grupo bajo el panel de personaje: una fila por miembro con nombre, nivel y barras de vida y mana (en porcentaje).
function U:dibujar_grupo(x, y, mundo)
  local g = mundo.grupo
  if not g then return end
  for i, m in ipairs(g.miembros) do
    local fy = y + (i - 1) * 30
    love.graphics.setColor(0.05, 0.12, 0.35, 0.8); love.graphics.rectangle('fill', x, fy, 150, 27, 3, 3)
    love.graphics.setColor(1, 1, 1)
    love.graphics.print((m.cid == g.lider and '* ' or '') .. m.nombre .. '  Lv' .. (m.nivel or '?'), x + 4, fy + 1, 0, 0.9, 0.9)
    love.graphics.setColor(0, 0, 0, 0.6); love.graphics.rectangle('fill', x + 4, fy + 15, 142, 4)
    love.graphics.setColor(0.85, 0.15, 0.15); love.graphics.rectangle('fill', x + 4, fy + 15, 142 * math.min(1, (m.hp or 0) / 100), 4)
    love.graphics.setColor(0, 0, 0, 0.6); love.graphics.rectangle('fill', x + 4, fy + 20, 142, 3)
    love.graphics.setColor(0.2, 0.4, 0.95); love.graphics.rectangle('fill', x + 4, fy + 20, 142 * math.min(1, (m.mp or 0) / 100), 3)
  end
  love.graphics.setColor(1, 1, 1)
end

-- Aviso de invitacion al grupo (bajo el de amistad si hay los dos).
function U:dibujar_invitacion_grupo(ancho, inv, desplazamiento)
  local an, al = 380, 44
  local x, y = (ancho - an) / 2, 70 + (desplazamiento or 0)
  love.graphics.setColor(0.05, 0.25, 0.15, 0.95); love.graphics.rectangle('fill', x, y, an, al, 6, 6)
  love.graphics.setColor(0.5, 1, 0.6); love.graphics.rectangle('line', x, y, an, al, 6, 6)
  love.graphics.setColor(1, 1, 1)
  love.graphics.printf(inv.nombre .. ' invites you to a team', x, y + 6, an, 'center')
  love.graphics.printf('[Y] accept     [N] decline', x, y + 24, an, 'center')
end

-- Ventana de la mascota (878): marco del cliente y datos del 0x0065 encima. Las casillas medidas sobre el marco: nombre (+8,+4), barras de
-- HP y MP (+46,+27 / +46,+36), dos columnas de 8 filas (base en +52, efectivo en +146, desde y +55, 17 px por fila), saciedad (+23,+246),
-- intimidad (+118,+246) y estrellas (+23,+267).
function U:dibujar_mascota(x, y, m)
  self:dibujar_generica(878, x, y, false)
  love.graphics.setColor(1, 1, 1)
  local function t(txt, dx, dy, k) love.graphics.print(txt, x + dx, y + dy, 0, k or 0.85, k or 0.85) end
  t(m.nombre, 30, 5, 0.9); t(tostring(m.nivel), 44, 17, 0.8)
  local function barra(dx, dy, an, frac, r, g, b)
    love.graphics.setColor(0, 0, 0, 0.5); love.graphics.rectangle('fill', x + dx, y + dy, an, 7)
    love.graphics.setColor(r, g, b); love.graphics.rectangle('fill', x + dx, y + dy, an * math.max(0, math.min(1, frac)), 7)
    love.graphics.setColor(1, 1, 1)
  end
  barra(46, 27, 150, m.hp / math.max(1, m.hp_max), 0.85, 0.15, 0.15)
  barra(46, 36, 150, m.mp / math.max(1, m.mp_max), 0.2, 0.4, 0.95)
  t(m.hp .. '/' .. m.hp_max, 100, 25, 0.7); t(m.mp .. '/' .. m.mp_max, 100, 34, 0.7)
  local filas = { { 'Atk', m.atk }, { 'Def', m.dfs }, { 'M.Atk', m.matk }, { 'M.Def', m.mdef }, { 'Rigor', m.rigor }, { 'Agil', m.agilidad } }
  for i, f in ipairs(filas) do
    local fy = 55 + (i - 1) * 17
    t(f[1], 4, fy + 1, 0.75)
    t(tostring(f[2][1]), 54, fy + 1, 0.75)
    t(tostring(f[2][2]), 148, fy + 1, 0.75)
  end
  t(tostring(m.saciedad), 26, 246, 0.8); t(tostring(m.intimidad), 121, 246, 0.8)
  t(string.format('%.1f stars', m.estrellas / 10), 26, 267, 0.8)
  love.graphics.setColor(1, 1, 1)
end

-- Ventana del banco (2100): fondo, 25 casillas (ids 2101..2125 = casillas 1..25) e iconos de lo guardado. Devuelve las casillas con su rectangulo.
function U:dibujar_banco(x, y, mundo, raton)
  local w = self:ventana(2100)
  if not w then return end
  local fondo = w.icon and self:imagen_icono(w.icon)
  love.graphics.setColor(1, 1, 1)
  if fondo then love.graphics.draw(fondo.img, x, y) else
    love.graphics.setColor(0.15, 0.15, 0.2, 0.95); love.graphics.rectangle('fill', x, y, 200, 262); love.graphics.setColor(1, 1, 1)
  end
  love.graphics.print('Warehouse', x + 8, y - 16)
  local casillas, tip = {}, nil
  local banco = mundo.banco or { items = {}, cantidades = {} }
  for _, hid in ipairs(w.hijos) do
    local n = tonumber(hid)
    if n >= 2101 and n <= 2125 then
      local h = self:ventana(hid)
      local hx, hy, hw, hh = rango(h)
      local casilla = n - 2100
      local px, py = x + hx, y + hy
      local item = banco.items[casilla]
      if item then
        local img, info = self:icono_item(item)
        if img then love.graphics.draw(img.img, px, py) else love.graphics.print('?', px + 14, py + 10) end
        local cant = banco.cantidades[casilla]
        if cant and cant > 1 then love.graphics.print(tostring(cant), px + 2, py + 22) end
        if raton and raton[1] >= px and raton[1] < px + hw and raton[2] >= py and raton[2] < py + hh then
          tip = (info and info.nombre or ('item ' .. item)) .. (cant and cant > 1 and (' x' .. cant) or '')
        end
      end
      casillas[#casillas + 1] = { casilla = casilla, x = px, y = py, w = hw, h = hh }
    end
  end
  love.graphics.setColor(0.8, 0.9, 1)
  love.graphics.print('doble clic: sacar   doble clic en la mochila: guardar   Esc: cerrar', x, y + 266, 0, 0.8, 0.8)
  if tip then
    local tw = love.graphics.getFont():getWidth(tip) + 8
    love.graphics.setColor(0, 0, 0, 0.85); love.graphics.rectangle('fill', raton[1] + 12, raton[2] + 8, tw, 20)
    love.graphics.setColor(1, 1, 1); love.graphics.print(tip, raton[1] + 16, raton[2] + 11)
  end
  love.graphics.setColor(1, 1, 1)
  return casillas
end

return U
