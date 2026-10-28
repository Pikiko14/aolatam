-- Capa nativa window.* del cliente original, sobre los wnd0N.xml. Los scripts originales (extracted_luas) se ejecutan SIN modificar
-- encima de esta tabla. Cada ventana viva tiene un handle entero; las funciones que no existen se registran en faltantes.
local M = { diferidos = {}, faltantes = {}, vivas = {}, raices = {}, siguiente = 1000, ui = nil, trazas = {} }

local function nueva(id, padre)
  M.siguiente = M.siguiente + 1
  local def = M.ui and M.ui:ventana(id)
  local x, y, an, al = 0, 0, 0, 0
  if def and def.range then
    local a, b, c, d = def.range:match('(-?%d+),(-?%d+),(-?%d+),(-?%d+)')
    x, y, an, al = tonumber(a) or 0, tonumber(b) or 0, tonumber(c) or 0, tonumber(d) or 0
  end
  local w = {
    h = M.siguiente, id = tonumber(id), def = def, padre = padre, hijos = {}, x = x, y = y, w = an, hh = al,
    titulo0 = def and def.title or '', visible = (def == nil) or (((def.estilo or '') .. (def.style or '')):find('wsVisible', 1, true) ~= nil), titulo = (def and (def.class == 'WND_CLASS_STATIC' or def.class == 'WND_CLASS_EDIT') and def.title) or '', titulo_n = 0, check = false, activo = true, datos = {}, icono = def and def.icon,
  }
  M.vivas[w.h] = w
  if padre then padre.hijos[#padre.hijos + 1] = w else M.raices[#M.raices + 1] = w end
  -- una ventana instancia a sus <child> igual que en el cliente
  if def then
    for _, hid in ipairs(def.hijos or {}) do
      if tonumber(hid) ~= tonumber(id) then nueva(hid, w) end
    end
  end
  return w
end

local function obt(h) return M.vivas[h] end

local function buscar(w, id)
  for _, c in ipairs(w.hijos) do
    if c.id == id then return c end
    local r = buscar(c, id)
    if r then return r end
  end
end

local function destruir(w)
  for i = #w.hijos, 1, -1 do destruir(w.hijos[i]) end
  M.vivas[w.h] = nil
  local lista = w.padre and w.padre.hijos or M.raices
  for i, c in ipairs(lista) do if c == w then table.remove(lista, i) break end end
end

local function abs(w)
  local x, y = w.x, w.y
  local p = w.padre
  while p do x, y = x + p.x, y + p.y; p = p.padre end
  return x, y
end

local W = {}
function W.create(id, a, b, c)
  local padre
  if c ~= nil then padre = obt(c) elseif a and a ~= 0 and obt(a) then padre = obt(a) end
  local w = nueva(id, padre)
  if c ~= nil then w.x, w.y = a or w.x, b or w.y end
  return w.h
end
function W.find(h, id) local w = obt(h); local r = w and buscar(w, id); return r and r.h or 0 end
function W.isexist(h) return M.vivas[h] ~= nil end
function W.destroy(h) local w = obt(h); if w then destruir(w) end end
function W.parent(h) local w = obt(h); return w and w.padre and w.padre.h or 0 end
W.getparent = W.parent
function W.show(h, v) local w = obt(h); if w then w.visible = v ~= false and v ~= 0 end end
function W.isvisible(h) local w = obt(h); return w and w.visible or false end
function W.enable(h, v) local w = obt(h); if w then w.activo = v ~= false and v ~= 0 end end
function W.move(h, x, y) local w = obt(h); if w then w.x, w.y = x, y end end
function W.moveoffset(h, dx, dy) local w = obt(h); if w then w.x, w.y = w.x + dx, w.y + dy end end
function W.setpos(h, x, y) W.move(h, x, y) end
function W.getpos(h) local w = obt(h); if w then return w.x, w.y end return 0, 0 end
function W.left(h) local w = obt(h); return w and w.x or 0 end
function W.top(h) local w = obt(h); return w and w.y or 0 end
function W.width(h) local w = obt(h); return w and w.w or 0 end
function W.height(h) local w = obt(h); return w and w.hh or 0 end
function W.setwindowsize(h, an, al) local w = obt(h); if w then w.w, w.hh = an, al end end
function W.settitle(h, t) local w = obt(h); if w then w.titulo = tostring(t) end end
function W.gettitle(h) local w = obt(h); return w and w.titulo or '' end
function W.settitleint(h, n) local w = obt(h); if w then w.titulo = tostring(n); w.titulo_n = n end end
function W.gettitleint(h) local w = obt(h); return w and tonumber(w.titulo) or 0 end
function W.seticon(h, ic) local w = obt(h); if w then w.icono = ic end end
function W.setcheck(h, v) local w = obt(h); if w then w.check = v == true or v == 1 end end
function W.ischeck(h) local w = obt(h); return w and w.check or false end
function W.setappdata(h, v) local w = obt(h); if w then w.appdata = v end end
function W.getappdata(h) local w = obt(h); return w and w.appdata or 0 end
function W.trace(t) M.trazas[#M.trazas + 1] = tostring(t) end
function W.getclock() return math.floor(love.timer.getTime() * 1000) end
function W.regsetting() end
function W.regcustom() end

-- cualquier otra funcion: se anota (con cuantas veces) y devuelve nada
setmetatable(W, { __index = function(_, nombre)
  return function()
    M.faltantes[nombre] = (M.faltantes[nombre] or 0) + 1
  end
end })

M.api = W
M.abs = abs

-- Dibujo: icono de fondo de cada ventana visible y su titulo.
function M.dibujar(w)
  if not w.visible then return end
  local x, y = abs(w)
  local clase = w.def and w.def.class
  if w.icono and M.ui and clase ~= 'WND_CLASS_PROGRESS' then
    local im = M.ui:imagen_icono(w.icono)
    if w.check and w.def and w.def.check then im = M.ui:imagen_icono(w.def.check) or im end
    if im then
      -- paneles grandes (marcos del personaje y del chat): translucidos como en el original
      local a = 1
      love.graphics.setColor(1, 1, 1, a); love.graphics.draw(im.img, x, y)
    end
  end
  if w.itemid and M.ui then
    local img = M.ui:icono_item(w.itemid)
    if img then love.graphics.setColor(1, 1, 1); love.graphics.draw(img.img, x, y) end
    if w.cant and w.cant > 1 then love.graphics.setColor(1, 1, 1); love.graphics.print(tostring(w.cant), x + 2, y + 22, 0, 0.8, 0.8) end
  end
  if clase == 'WND_CLASS_PROGRESS' and w.def.picon and M.ui then
    -- barra: la imagen picon recortada a la fraccion actual
    local im = M.ui:imagen_icono(w.def.picon)
    if im and w.max and w.max > 0 then
      love.graphics.setScissor(x, y, math.floor(w.w * math.max(0, math.min(1, (w.valor or 0) / w.max))), w.hh)
      love.graphics.setColor(1, 1, 1); love.graphics.draw(im.img, x, y)
      love.graphics.setScissor()
    end
    if w.texto and w.texto ~= '' then love.graphics.setColor(1, 1, 1); love.graphics.print(w.texto, x + 4, y - 1, 0, 0.8, 0.8) end
  elseif clase == 'WND_CLASS_CHATSTATIC' and w.lineas then
    M.diferidos[#M.diferidos + 1] = function()
    local n = #w.lineas
    local pa = (w.def.workrange or '9,4,0,0'):match('(-?%d+),(-?%d+)')
    local lineas = tonumber(w.def.lines) or 6
    for i = math.max(1, n - lineas + 1), n do
      love.graphics.setColor(1, 1, 1)
      love.graphics.print(w.lineas[i], x + 9, y + 4 + (i - math.max(1, n - lineas + 1)) * 13, 0, 0.85, 0.85)
    end
    end
  elseif w.titulo ~= '' then
    if w.def and w.def.fcolor == '105' then love.graphics.setColor(0.08, 0.14, 0.2) else love.graphics.setColor(1, 1, 1) end
    love.graphics.print(w.titulo, x + 2, y + 1, 0, 0.85, 0.85)
  end
  for _, c in ipairs(w.hijos) do M.dibujar(c) end
end

-- Casillas de la ventana de equipo (2001): la posicion la pone el ejecutable, salen de medir el fondo. { casilla del servidor, x, y }
local EQUIPO = { { 1, 59, 10 }, { 616, 108, 10 }, { 2, 10, 52 }, { 7, 108, 52 }, { 3, 10, 94 }, { 4, 108, 94 }, { 5, 10, 136 }, { 6, 108, 136 }, { 10, 59, 177 } }
function M.dibujar_equipo(mundo)
  for h, tipos in pairs(require('src.nativo').game.itemwnds or {}) do
    local w = obt(h)
    if w and w.id == 2001 and w.visible then
      local x, y = abs(w)
      for _, c in ipairs(EQUIPO) do
        local item = mundo.items and mundo.items[c[1]]
        local img = item and M.ui:icono_item(item)
        if img then love.graphics.setColor(1, 1, 1); love.graphics.draw(img.img, x + c[2], y + c[3]) end
      end
    end
  end
end

-- Registro de misiones (434): game.initquestlist lo rellena el motor; aqui se dibuja sobre el marco original. Izquierda la lista, derecha el detalle.
local function limpia(t) return (tostring(t or ''):gsub('<[^>]*>', ''):gsub('%^%w%w?%w?%w?%w?%w?%w?', '')) end
function M.dibujar_misiones(mundo)
  for _, w in pairs(M.vivas) do
    if w.id == 434 and w.visible then
      local x, y = abs(w)
      local lista = mundo.misiones or {}
      M.sel_mision = math.min(M.sel_mision or 1, math.max(1, #lista))
      M.filas_mision = {}
      for i, m in ipairs(lista) do
        local q = M.ui:mision(m.id)
        local fy = y + 28 + (i - 1) * 15
        if fy > y + w.hh - 36 then break end
        love.graphics.setColor(i == M.sel_mision and 1 or 0.85, i == M.sel_mision and 0.95 or 0.9, i == M.sel_mision and 0.4 or 1)
        love.graphics.setScissor(x + 6, fy, math.floor(w.w / 2) - 14, 15)
        love.graphics.print((q and q.nombre or ('quest ' .. m.id)), x + 8, fy, 0, 0.85, 0.85)
        love.graphics.setScissor()
        M.filas_mision[#M.filas_mision + 1] = { x = x + 6, y = fy, w = math.floor(w.w / 2) - 10, h = 15, indice = i }
      end
      local m = lista[M.sel_mision]
      local q = m and M.ui:mision(m.id)
      if q then
        local dx = x + math.floor(w.w / 2) + 2
        love.graphics.setColor(1, 0.9, 0.5); love.graphics.printf(q.nombre, dx, y + 26, math.floor((w.w / 2 - 10) / 0.85), 'left', 0, 0.85, 0.85)
        local py = y + 60
        for i, paso in ipairs(q.pasos) do
          local hecho = i <= m.paso
          love.graphics.setColor(hecho and 0.5 or 1, 1, hecho and 0.5 or 1)
          local txt = (hecho and '[x] ' or '[ ] ') .. limpia(paso)
          love.graphics.printf(txt, dx, py, math.floor(w.w / 2) - 10, 'left', 0, 0.8, 0.8)
          py = py + 26
        end
      end
    end
  end
end

-- Lista de amigos: game.friendwnd(handle) le dice al motor en que ventana (2301) pintar la lista; las filas van sobre el marco original.
function M.dibujar_amigos(mundo)
  local w = obt(require('src.nativo').game.amigos_wnd or 0)
  if not w or not w.visible then return end
  local x, y = abs(w)
  M.filas_amigos = {}
  local sel = M.sel_amigo
  for i, a in ipairs(mundo.amigos or {}) do
    local fy = y + 54 + (i - 1) * 15
    if fy > y + w.hh - 60 then break end
    if i == sel then love.graphics.setColor(0.2, 0.55, 0.75, 0.5); love.graphics.rectangle('fill', x + 8, fy, w.w - 30, 14) end
    love.graphics.setColor(a.conectado and 0.5 or 0.65, a.conectado and 1 or 0.7, a.conectado and 0.6 or 0.7)
    love.graphics.print(a.nombre, x + 12, fy, 0, 0.85, 0.85)
    if a.conectado and a.escena and M.ui then
      local esc = M.ui:escena(a.escena)
      love.graphics.setColor(0.85, 0.92, 1); love.graphics.print(esc and esc.nombre or ('stage ' .. a.escena), x + 150, fy, 0, 0.85, 0.85)
    end
    M.filas_amigos[#M.filas_amigos + 1] = { x = x + 8, y = fy, w = w.w - 30, h = 14, indice = i }
  end
end

-- Casilla de mochila bajo el raton (ventana de inventario abierta): devuelve el numero de casilla del servidor (20..44).
function M.casilla_bajo(mx, my)
  local iw = obt(require('src.nativo').game.itemwnd or 0)
  if not iw then return nil end
  for k = 0, 24 do
    local c = obt(M.api.find(iw.h, 3101 + k))
    if c and c.visible then
      local x, y = abs(c)
      if mx >= x and mx < x + c.w and my >= y and my < y + c.hh then return 20 + k end
    end
  end
end

-- Datos que en el cliente original pone el motor nativo (los scripts solo montan la interfaz): barras, nombre y chat.
function M.alimentar(mundo)
  M.mundo = mundo
  local raiz = M.api.find
  local info = _G.WND_CHAR_INFO
  local function w(h, id) return obt(W.find(h, id)) end
  local st = mundo.stats
  local function barra(id, v, m, txt) local b = w(info, id); if b then b.valor, b.max, b.texto = v, m, txt end end
  if st then
    barra(160, st.hp, st.hp_max, st.hp .. '/' .. st.hp_max)
    barra(161, st.mp, st.mp_max, st.mp .. '/' .. st.mp_max)
  end
  if mundo.exp and mundo.exp_sig then barra(159, mundo.exp, mundo.exp_sig, string.format('%.2f %%', 100 * mundo.exp / math.max(1, mundo.exp_sig))) end
  local nom = w(info, 166)
  local yo = mundo.yo and mundo.ents[mundo.yo]
  if nom and yo then nom.titulo = yo.nombre or '' end
  M.nivel_txt = mundo.nivel and ('L ' .. tostring(mundo.nivel)) or nil
  -- ventana de inventario (la crea CreateItemWnd y pide su relleno con game.inititemwnd): casillas 3101..3125 = mochila 20..44
  local iw = obt(require('src.nativo').game.itemwnd or 0)
  if iw then
    for k = 0, 24 do
      local c = w(iw.h, 3101 + k)
      if c then
        c.itemid = mundo.items and mundo.items[20 + k]
        if c.itemid then c.visible = true end
        c.cant = mundo.cantidades and mundo.cantidades[20 + k]
      end
    end
  end
  -- ventana de informacion del personaje (265): los valores los pone el motor
  local a = mundo.atrib
  if a then
    local ids = { [358] = a.atk_d, [359] = a.atk_i, [360] = a.critico, [361] = a.dfs, [362] = a.matk, [363] = a.mdef, [364] = a.rigor,
      [365] = a.agilidad, [366] = a.aguante, [367] = a.alma, [368] = a.trueno, [369] = a.fuego, [370] = a.hielo, [371] = a.podrido }
    for id, v in pairs(ids) do local c = w(info, id); if c then c.titulo = tostring(v) end end
  end
  -- faccion y panel de experiencia de habilidades (264): las seis de mayor nivel; filas 318/319 (nombre/nivel) y barras 330..335
  local tit = w(info, 376); if tit and mundo.titulo and M.ui then tit.titulo = M.ui:titulo_nombre(mundo.titulo) end
  local FAC = { 'Aurora', 'Beasts', 'Steel', 'Shadow', 'Heaven' }
  local fac = w(info, 850); if fac and mundo.faccion then fac.titulo = FAC[mundo.faccion] or '' end
  if mundo.habs and M.ui then
    local lista = {}
    for _, h in ipairs(mundo.habs) do if h.nivel > 1 then lista[#lista + 1] = h end end
    table.sort(lista, function(x, y) return x.nivel > y.nivel end)
    for i = 1, 6 do
      local h = lista[i]
      local nom, niv, bar = w(info, 318 + (i - 1) * 2), w(info, 319 + (i - 1) * 2), w(info, 330 + i - 1)
      if nom then nom.titulo = h and M.ui:habilidad_nombre(h.id) or '' end
      if niv then niv.titulo = h and tostring(h.nivel) or '' end
      if bar then bar.valor, bar.max, bar.texto = h and h.exp or 0, h and math.max(1, h.exp_sig) or 0, '' end
    end
  end
  local chat = obt(_G.WND_CHAT_CONTENT_0 or 0)
  if chat then chat.lineas = mundo.chat end
end

-- Clic: la ventana visible mas profunda bajo el raton con OnCommand; los botones bsCheck conmutan su marca y llaman al script original.
local function bajo(w, mx, my)
  if not w.visible or not w.activo then return nil end
  for i = #w.hijos, 1, -1 do
    local r = bajo(w.hijos[i], mx, my)
    if r then return r end
  end
  local x, y = abs(w)
  if w.def and w.def.eventos and w.def.eventos.OnCommand and mx >= x and mx < x + w.w and my >= y and my < y + w.hh then return w end
end

function M.clic(mx, my)
  for _, f in ipairs(M.filas_amigos or {}) do
    if mx >= f.x and mx < f.x + f.w and my >= f.y and my < f.y + f.h then M.sel_amigo = f.indice; return true end
  end
  for _, f in ipairs(M.filas_mision or {}) do
    if mx >= f.x and mx < f.x + f.w and my >= f.y and my < f.y + f.h then M.sel_mision = f.indice; return true end
  end
  for i = #M.raices, 1, -1 do
    local w = bajo(M.raices[i], mx, my)
    if w then
      if (w.def.estilo or ''):find('bsCheck', 1, true) then w.check = not w.check end
      local fn = _G[w.def.eventos.OnCommand]
      if fn then
        local ok, e = pcall(fn, w.h, w.id, 0, 0)
        if not ok then M.trazas[#M.trazas + 1] = 'error ' .. w.def.eventos.OnCommand .. ': ' .. tostring(e) end
      else
        M.faltantes['handler:' .. w.def.eventos.OnCommand] = (M.faltantes['handler:' .. w.def.eventos.OnCommand] or 0) + 1
      end
      return w
    end
  end
end

function M.dibujar_todo()
  M.diferidos = {}
  for _, r in ipairs(M.raices) do M.dibujar(r) end
  for _, f in ipairs(M.diferidos) do f() end
  if M.mundo then M.dibujar_equipo(M.mundo); M.dibujar_misiones(M.mundo); M.dibujar_amigos(M.mundo) end
  -- retrato: el motor lo dibuja dentro del aro del panel de personaje (158)
  local pan = obt(_G.WND_CHAR_INFO or 0)
  if pan and pan.visible and M.retrato_fn then
    local x, y = abs(pan)
    M.retrato_fn(x + 46, y + 45, 28)
    if M.nivel_txt then love.graphics.setColor(1, 1, 1); love.graphics.print(M.nivel_txt, x + 84, y + 17, 0, 0.85, 0.85) end
  end
  -- minimapa: el original lo dibuja el motor dentro de la ventana que le pasa game.openmap
  local mm = obt(require('src.nativo').game.minimapa or 0)
  if mm and mm.visible and M.mundo and M.ui and M.ui.mapa_actual then
    local x, y = abs(mm)
    M.ui:dibujar_minimapa(0, M.mundo, M.ui.mapa_actual, false, x + 4, y + 17, mm.w - 8)
  end
end

return M
