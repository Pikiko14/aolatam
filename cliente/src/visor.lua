-- Visor del mapa: terreno + objetos, leidos de los paks del cliente instalado.
local Pak = require('src.pak')
local Mpc = require('src.mpc')
local Gfx = require('src.gfx')
local Mundo = require('src.mundo')

local V = {}
V.__index = V

function V.nuevo(carpeta_cliente)
  local self = setmetatable({}, V)
  self.paks = Pak.abrir_cliente(carpeta_cliente)
  self.gfx = Gfx.nuevo(self.paks)
  self.equipo = require('src.equipo').nuevo(self.paks, self.gfx)
  self.ui = require('src.ui').nuevo(self.paks, self.gfx)
  self.cam = { x = 0, y = 0 }
  return self
end

function V:cargar_mapa(nombre)
  local d = self.paks:leer('map/' .. nombre .. '.mpc')
  if not d then return false end
  self.mapa = Mpc.leer(d)
  self.bloques = {}
  -- el suelo como angel.dat (src/suelo.lua, en la GPU); AO_SUELO_VIEJO=1 vuelve al fundido aproximado de V:bloque
  self.suelo = nil
  if not os.getenv('AO_SUELO_VIEJO') then
    local ok, s = pcall(require('src.suelo').nuevo, self.paks, self.mapa)
    if ok then self.suelo = s else print('suelo: ' .. tostring(s)) end
  end
  self.ui.mapa_actual = self.mapa
  -- los objetos se dibujan ordenados por y (los de abajo tapan a los de arriba)
  table.sort(self.mapa.objetos, function(a, b) return a.y < b.y end)
  return true
end

function V:centrar(px, py)
  self.cam.x, self.cam.y = px, py
end

-- Terreno en bloques de 16 x 16 casillas (512 x 512 px), pintado pixel a pixel en una ImageData.
-- Las casillas rodeadas del mismo pincel copian su textura tal cual; en las de borde se mezclan los dos pinceles que mas
-- pesan alrededor (interpolando entre los centros de las 4 casillas vecinas) y el corte se rompe con el grano de
-- brush.p03, como el fundido de angel.dat: sin escalones ni cuadros sueltos ("arregla los mapas, se ven feos", 14/11/2026).
local ffi = require('ffi')

function V:bloque(cx, cy)
  local clave = cx * 100000 + cy
  local c = self.bloques[clave]
  if c then return c end
  local m, gfx = self.mapa, self.gfx
  local salida = love.image.newImageData(512, 512)
  local out = ffi.cast('uint8_t*', salida:getPointer())
  local ruido = gfx:ruido()
  local suelo = gfx:tileset(0)
  -- Los pinceles empalman en horizontal como ladrillos: cada periodo S hacia la derecha baja S/2 (medido en b05,
  -- b00, b3b, b02: con desfase la costura iguala a la textura; sin el, cada 256 o 512 px se veia un corte).
  local punteros, periodos = {}, {}
  local function tex(id)
    local p = punteros[id]
    if p == nil then
      local t = gfx:tileset(id) or suelo
      p = t and ffi.cast('uint8_t*', t.datos:getPointer()) or false
      punteros[id] = p
      periodos[id] = t and (t.lado or 16) * 32 or 512
    end
    return p or nil, periodos[id]
  end
  local bx = cx * 512
  local function idx(S, px, py)
    return (((py + math.floor((bx + px) / S) * (S / 2)) % 512) * 512 + px) * 4
  end
  local x0, y0 = cx * 16, cy * 16
  -- pinceles del bloque y de su marco de una casilla (18 x 18)
  local ids = {}
  for j = -1, 16 do
    for i = -1, 16 do ids[(j + 1) * 18 + i + 1] = Mpc.pincel(m, x0 + i, y0 + j) end
  end
  local function id_de(i, j) return ids[(j + 1) * 18 + i + 1] end
  local pid, pw = { 0, 0, 0, 0 }, { 0, 0, 0, 0 }
  for j = 0, 15 do
    for i = 0, 15 do
      local centro = id_de(i, j)
      local igual = true
      for dj = -1, 1 do
        for di = -1, 1 do
          if id_de(i + di, j + dj) ~= centro then igual = false end
        end
      end
      local pc, Sc = tex(centro)
      for yy = 0, 31 do
        local py = j * 32 + yy
        local v = (yy + 0.5) / 32 - 0.5
        local jb, fy = j, v
        if v < 0 then jb, fy = j - 1, v + 1 end
        for xx = 0, 31 do
          local px = i * 32 + xx
          local o = (py * 512 + px) * 4
          if igual then
            if pc then
              local s = idx(Sc, px, py)
              out[o], out[o + 1], out[o + 2], out[o + 3] = pc[s], pc[s + 1], pc[s + 2], 255
            end
          else
            local u = (xx + 0.5) / 32 - 0.5
            local ib, fx = i, u
            if u < 0 then ib, fx = i - 1, u + 1 end
            -- pesos bilineales de las 4 casillas vecinas, sumados por pincel
            local n = 0
            local esquinas = { id_de(ib, jb), id_de(ib + 1, jb), id_de(ib, jb + 1), id_de(ib + 1, jb + 1) }
            local pesos = { (1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy }
            for k = 1, 4 do
              local id, w = esquinas[k], pesos[k]
              local hallado = false
              for q = 1, n do
                if pid[q] == id then pw[q] = pw[q] + w; hallado = true; break end
              end
              if not hallado then n = n + 1; pid[n], pw[n] = id, w end
            end
            -- los dos que mas pesan
            local a, b = 1, nil
            for q = 2, n do if pw[q] > pw[a] then a = q end end
            for q = 1, n do if q ~= a and (not b or pw[q] > pw[b]) then b = q end end
            local pa, Sa = tex(pid[a])
            if not b then
              if pa then
                local s = idx(Sa, px, py)
                out[o], out[o + 1], out[o + 2], out[o + 3] = pa[s], pa[s + 1], pa[s + 2], 255
              end
            else
              local pb, Sb = tex(pid[b])
              local g = ruido and ruido[py * 512 + px] or 0.5
              local t = 0.5 + (pw[a] - pw[b]) * 1.8 + (g - 0.5) * 0.9
              if t < 0 then t = 0 elseif t > 1 then t = 1 end
              t = t * t * (3 - 2 * t)
              if not pa then pa, Sa = pb, Sb elseif not pb then pb, Sb = pa, Sa end
              if pa then
                local sa, sb = idx(Sa, px, py), idx(Sb, px, py)
                out[o] = pa[sa] * t + pb[sb] * (1 - t)
                out[o + 1] = pa[sa + 1] * t + pb[sb + 1] * (1 - t)
                out[o + 2] = pa[sa + 2] * t + pb[sb + 2] * (1 - t)
                out[o + 3] = 255
              end
            end
          end
        end
      end
    end
  end
  c = love.graphics.newImage(salida)
  self.bloques[clave] = c
  return c
end

-- {izq, arriba, der, abajo} que ocupa el objeto en el mapa con cualquiera de sus cuadros; false si no tiene sprite.
function V:_caja(o)
  local frames = self.gfx:objeto_frames(o.id)
  local lista = {}
  if frames then for _, f in ipairs(frames) do lista[#lista + 1] = f.spr end
  else local s = self.gfx:objeto(o.id); if s then lista[1] = s end end
  if #lista == 0 then return false end
  local l, t, r, b = math.huge, math.huge, -math.huge, -math.huge
  for _, s in ipairs(lista) do
    local x1 = (o.e == 2) and (o.x + (s.w - s.ox) - s.w) or (o.x - s.ox)
    l, r = math.min(l, x1), math.max(r, x1 + s.w)
    t, b = math.min(t, o.y - s.oy), math.max(b, o.y - s.oy + s.h)
  end
  return { l, t, r, b }
end

-- Un objeto del mapa con su mezcla (luz, humo...) y su espejo.
function V:_objeto(c)
  local o, s = c.o, c.s
  if c.mezcla ~= 'alpha' then love.graphics.setBlendMode(c.mezcla) end
  if c.opacidad < 1 then love.graphics.setColor(1, 1, 1, c.opacidad) end
  if o.e == 2 then
    love.graphics.draw(s.img, o.x + (s.w - s.ox), o.y - s.oy, 0, -1, 1)
  else
    love.graphics.draw(s.img, o.x - s.ox, o.y - s.oy)
  end
  if c.mezcla ~= 'alpha' then love.graphics.setBlendMode('alpha') end
  if c.opacidad < 1 then love.graphics.setColor(1, 1, 1, 1) end
end

function V:dibujar(ancho, alto, mundo)
  local m = self.mapa
  if not m then return end
  local x0 = self.cam.x - ancho / 2
  local y0 = self.cam.y - alto / 2
  local c0, c1 = math.max(0, math.floor(x0 / 32)), math.min(m.w - 1, math.floor((x0 + ancho) / 32))
  local r0, r1 = math.max(0, math.floor(y0 / 32)), math.min(m.h - 1, math.floor((y0 + alto) / 32))
  love.graphics.push()
  love.graphics.translate(-math.floor(x0), -math.floor(y0))
  love.graphics.setColor(1, 1, 1, 1)
  if self.suelo then
    self.suelo:dibujar(c0, r0, c1, r1)
  else
    for by = math.floor(r0 / 16), math.floor(r1 / 16) do
      for bx = math.floor(c0 / 16), math.floor(c1 / 16) do
        love.graphics.draw(self:bloque(bx, by), bx * 512, by * 512)
      end
    end
  end
  local altos = {}
  -- zona de casa donde esta el jugador (byte 5 de la celda): dentro de una casa se quita su fachada (HOUSEOUT)
  local zona_yo = 0
  local yo = mundo and mundo.yo and mundo.ents[mundo.yo]
  if yo then zona_yo = Mpc.zona(m, math.floor(yo.x / 32), math.floor((m.h * 32 - yo.y) / 32)) end
  if os.getenv('AO_ZONA') then zona_yo = tonumber(os.getenv('AO_ZONA')) end   -- prueba sin servidor
  if not os.getenv('AO_SIN_OBJ') then
    for _, o in ipairs(m.objetos) do
      -- Caja de cada objeto (union de todos sus cuadros, con espejo), calculada una vez: con un margen fijo o con el
      -- cuadro actual, las casas y el humo que cambia de tamano aparecian y desaparecian al moverse ("da flashazos").
      if not o.caja then o.caja = self:_caja(o) end
      local cj = o.caja
      if cj and cj[1] < x0 + ancho and cj[3] > x0 and cj[2] < y0 + alto and cj[4] > y0 then
        local def = self.gfx:definiciones()[o.id]
        local proceso = def and def.proceso or ''
        local flags = def and def.flags or ''
        local nombre = def and def.nombre or ''
        -- Como se mezcla con lo de debajo, segun las marcas del .obd ("arregla los mapas", 14/11/2026): el humo y las
        -- luces vienen sobre negro y dibujados tal cual salian como manchas negras.
        --   WHITELIGHT = luz (suma), DARKLIGHT = sombra (resta), MIXER / SMOKE = humo (pantalla), ALPHA = semitransparente.
        local mezcla, opacidad = 'alpha', 1
        if flags:find('WHITELIGHT', 1, true) then mezcla = 'add'
        elseif flags:find('DARKLIGHT', 1, true) then mezcla = 'subtract'
        elseif flags:find('MIXER', 1, true) or flags:find('SMOKE', 1, true) then mezcla = 'screen'
        elseif flags:find('ATTRIB_ALPHA', 1, true) then opacidad = 0.55 end
        -- LIGHTOBJ/EFFECT/光源 sin marca de luz: sin mezcla salen manchas blancas, se siguen saltando.
        -- Nombres del .obd vienen en Big5 (雲 = B6 7D), no en UTF-8.
        local omitir = flags:find('SKIP_RENDER', 1, true)
          or (mezcla == 'alpha' and (proceso:find('EFFECT', 1, true)
            or proceso:find('LIGHTOBJ', 1, true)
            or nombre:find('光源', 1, true)
            or nombre:find('\xB6\xB3', 1, true)   -- 雲 Big5/cp950
            or nombre:lower():find('cloud', 1, true)))
        if not omitir and zona_yo ~= 0 and proceso:find('HOUSEOUT', 1, true) then
          if o.zona == nil then o.zona = Mpc.zona(m, math.floor(o.x / 32), math.floor(o.y / 32)) end
          omitir = o.zona == zona_yo
        end
        if not omitir then
          local s
          local frames = self.gfx:objeto_frames(o.id)
          if frames and #frames > 1 then
            local total = 0
            for _, f in ipairs(frames) do total = total + f.dur end
            local t = (love.timer.getTime() + (o.x * 0.013 + o.y * 0.007)) % total
            for _, f in ipairs(frames) do
              if t < f.dur then s = f.spr; break end
              t = t - f.dur
            end
            s = s or frames[1].spr
          elseif frames then
            s = frames[1].spr
          else
            s = self.gfx:objeto(o.id)
          end
          if s then
            local cosa ={ o = o, s = s, mezcla = mezcla, opacidad = opacidad, y = o.y }
            -- Como angel.dat (0x530d50): los objetos con SP_ATTRIB_ZBUFFER1/2 escriben su y en el z-buffer y tapan a
            -- quien pasa detras; los que no (bordes, agujeros, losas, matas) solo se comparan con el (modo 2) y nunca
            -- tapan a un personaje. Aqui: los ZBUFFER se ordenan por la y del pie junto con los personajes; el resto, debajo.
            -- ZBUFFER2 (interiores de casa, paredes y muebles de fondo) va debajo: anclado abajo del todo, ordenado por y
            -- tapaba a todos los que estaban dentro ("dentro del banco solo se ven los nombres", 14/11/2026).
            if flags:find('ZBUFFER1', 1, true) then altos[#altos + 1] = cosa else self:_objeto(cosa) end
          end
        end
      end
    end
  end
  if not mundo then
    for _, c in ipairs(altos) do self:_objeto(c) end      -- ya vienen ordenados por y (cargar_mapa)
  end
  if mundo then
    local t = love.timer.getTime()
    -- de atras hacia delante: las entidades mas abajo en pantalla tapan a las de arriba
    local lista = {}
    -- las posiciones del servidor cuentan la y desde ABAJO del mapa (la minimapa del cliente original, el .mpc y transitable.bin lo confirman):
    -- se voltea mientras se dibuja y se restaura al final
    local alto_mapa = m.h * 32
    for _, e in pairs(mundo.ents) do e.y = alto_mapa - e.y; lista[#lista + 1] = e end
    table.sort(lista, function(a, b) return a.y < b.y end)
    -- sombras: elipse oscura translucida bajo los pies de cada entidad viva (el original marca SP_ATTRIB_SHADOW en char.obd / npc.obd)
    for _, e in ipairs(lista) do
      if not e.muerto and not e.objeto_mapa then          -- los objetos de mapa traen su propia sombra en el sprite
        local rx = (e.yo or e.jugador) and 15 or (e.clase == 200 and 16 or 22)
        love.graphics.setColor(0, 0, 0, 0.26)
        love.graphics.ellipse('fill', e.x, e.y + 1, rx, rx * 0.42)
      end
    end
    love.graphics.setColor(1, 1, 1)
    -- personajes y objetos de pie, juntos y por la y del pie
    local orden = {}
    for _, e in ipairs(lista) do orden[#orden + 1] = { y = e.y, e = e } end
    for _, c in ipairs(altos) do orden[#orden + 1] = c end
    table.sort(orden, function(a, b) return a.y < b.y end)
    for _, it in ipairs(orden) do
     if it.o then self:_objeto(it) else
      local e = it.e
      local ids
      if e.yo and (mundo.items or mundo.puesto_visual) then
        ids = self.equipo:personaje(mundo:puesto(), mundo.apariencia, mundo.genero or 'g')
      elseif e.jugador then
        ids = self.equipo:personaje(Mundo.equipo_de(e), e.apariencia, e.genero or 'g')
      elseif e.sprite then ids = { { id = e.sprite, tinte = not e.objeto_mapa and self.gfx:tinte_npc(e.sprite) or nil } } end
      local dibujado = false
      if ids then
        local anim = e.dx and 'run' or 'wait'
        -- ciclo de pasos y tiempo por paso (el '#N' del obd son N/60 s): reposo 1,2,3,2 a 8; correr 1..6 a 7; atacar 1..4 a 6
        local ciclo, tick = { 1, 2, 3, 2 }, 8 / 60
        local paso
        if e.muerto then
          anim = 'dead'
          paso = math.min(6, 1 + math.floor((t - e.muerto) / (6 / 60)))     -- se queda en el ultimo cuadro
        elseif e.atacando and t < e.atacando then
          anim, ciclo, tick = 'att', { 1, 2, 3, 4 }, 6 / 60
          paso = ciclo[math.floor((e.atacando - t < 0.5 and 0.5 - (e.atacando - t) or 0) / tick) % #ciclo + 1]
        elseif anim == 'run' then ciclo, tick = { 1, 2, 3, 4, 5, 6 }, 7 / 60 end
        paso = paso or ciclo[math.floor((t + e.id * 0.37) / tick) % #ciclo + 1]
        love.graphics.setColor(1, 1, 1)
        for _, c in ipairs(ids) do
          local s = self.gfx:cuadro_anim(c.id, anim, e.dig or 3, paso, c.tinte)
          if s then
            dibujado = true
            e.alto_sprite = math.max(e.alto_sprite or 0, s.oy)
            if e.espejo then love.graphics.draw(s.img, e.x + s.ox, e.y - s.oy, 0, -1, 1)
            else love.graphics.draw(s.img, e.x - s.ox, e.y - s.oy) end
          end
        end
      end
      if not dibujado then
        local s = e.sprite and self.gfx:objeto(e.sprite)
        if s then
          love.graphics.setColor(1, 1, 1); love.graphics.draw(s.img, e.x - s.ox, e.y - s.oy)
        elseif e.objeto_mapa then
          -- objeto de mapa sin dibujo (marcas invisibles: portales, puntos de evento): el original no pinta nada
        else
          love.graphics.setColor(e.yo and 1 or 0.9, e.yo and 0.9 or 0.3, 0.2)
          love.graphics.circle('fill', e.x, e.y, 6)
        end
      end
     end
    end
    -- nombres y objetivo encima de todo (un arbol delante no tapa la placa)
    for _, e in ipairs(lista) do
      love.graphics.setColor(1, 1, 1)
      if e.nombre and e.nombre ~= '' then
        -- placa de nombre como la del cliente original: caja oscura con borde claro y texto claro, centrada sobre la cabeza
        local fuente = love.graphics.getFont()
        local tw = fuente:getWidth(e.nombre) + 14
        local px, py = math.floor(e.x - tw / 2), math.floor(e.y - (e.alto_sprite or 100) - 24)
        love.graphics.setColor(0.2, 0.22, 0.25, 0.85); love.graphics.rectangle('fill', px, py, tw, 20)
        love.graphics.setColor(0.7, 0.72, 0.75, 0.9); love.graphics.rectangle('line', px + 0.5, py + 0.5, tw - 1, 19)
        love.graphics.setColor(0.92, 0.95, 1); love.graphics.print(e.nombre, px + 7, py + 3)
      end
      -- objetivo: aro bajo los pies y barra de vida (en monstruos el HP llega en porcentaje)
      if mundo.objetivo == e.id and not e.muerto then
        love.graphics.setColor(1, 0.9, 0.2); love.graphics.ellipse('line', e.x, e.y, 26, 12)
        local pct = math.max(0, math.min(100, e.hp or 100))
        love.graphics.setColor(0, 0, 0, 0.7); love.graphics.rectangle('fill', e.x - 26, e.y - 62, 52, 7)
        love.graphics.setColor(0.85, 0.15, 0.15); love.graphics.rectangle('fill', e.x - 25, e.y - 61, 50 * pct / 100, 5)
        love.graphics.setColor(1, 1, 1)
      end
    end
    -- efectos de golpes y magias sobre su objetivo; se reproducen una vez y se quitan
    for i = #mundo.efectos, 1, -1 do
      local ef = mundo.efectos[i]
      local def = self.gfx:efecto(ef.id)
      local e = mundo.ents[ef.objetivo]
      if not def or not e then
        table.remove(mundo.efectos, i)
      else
        local k = math.floor((t - ef.t) / (def.dur * (tonumber(os.getenv('AO_FX_LENTO')) or 1))) + 1      -- AO_FX_LENTO: prueba, alarga los efectos
        if k > #def.frames then
          table.remove(mundo.efectos, i)
        else
          local sp = def.frames[k]
          if def.aditivo then love.graphics.setBlendMode('add') end
          love.graphics.setColor(1, 1, 1)
          love.graphics.draw(sp.img, e.x - sp.ox, e.y - sp.oy)
          love.graphics.setBlendMode('alpha')
        end
      end
    end
    -- numeros de dano: suben y se desvanecen
    for _, f in ipairs(mundo.flotantes) do
      local e = mundo.ents[f.id]
      if e then
        local edad = t - f.t
        love.graphics.setColor(1, 0.25, 0.2, 1 - edad / 1.2)
        love.graphics.print(tostring(f.valor), e.x - 8, e.y - 70 - edad * 40, 0, 1.4, 1.4)
      end
    end
    for _, e in pairs(mundo.ents) do e.y = alto_mapa - e.y end
    love.graphics.setColor(1, 1, 1)
  end
  love.graphics.pop()
end

return V
