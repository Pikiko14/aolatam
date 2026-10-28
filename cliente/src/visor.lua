-- Visor del mapa: terreno + objetos, leidos de los paks del cliente instalado.
local Pak = require('src.pak')
local Mpc = require('src.mpc')
local Gfx = require('src.gfx')

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
  self.ui.mapa_actual = self.mapa
  -- los objetos se dibujan ordenados por y (los de abajo tapan a los de arriba)
  table.sort(self.mapa.objetos, function(a, b) return a.y < b.y end)
  return true
end

function V:centrar(px, py)
  self.cam.x, self.cam.y = px, py
end

-- Terreno en bloques de 16 x 16 casillas (512 x 512 px) que se pintan una vez en un canvas. En la frontera entre dos suelos el que tiene
-- el numero de tileset mayor "invade" 16 px del vecino con un degradado: sin ese degradado los cambios de suelo salen como cuadros.
-- (Interpretacion propia: el original usa mascaras brush.pNN que no estan descifradas.)
local PLUMA = 16
local DIRS = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }

function V:bloque(cx, cy)
  local clave = cx * 100000 + cy
  local c = self.bloques[clave]
  if c then return c end
  local m = self.mapa
  c = love.graphics.newCanvas(512, 512)
  local previo = love.graphics.getCanvas()
  love.graphics.push('all')
  love.graphics.origin()
  love.graphics.setCanvas(c)
  love.graphics.clear(0, 0, 0, 0)
  love.graphics.setColor(1, 1, 1)
  local x0, y0 = cx * 16, cy * 16
  for j = 0, 15 do
    for i = 0, 15 do
      local x, y = x0 + i, y0 + j
      if x < m.w and y < m.h then
        local t = self.gfx:tileset(Mpc.tileset(m, x, y))
        if t then love.graphics.draw(t.imagen, self.gfx:quad_de(t, x, y), i * 32, j * 32) end
      end
    end
  end
  if not self.malla then self.malla = love.graphics.newMesh(4, 'fan', 'stream') end
  for j = 0, 15 do
    for i = 0, 15 do
      local x, y = x0 + i, y0 + j
      if x < m.w and y < m.h then
        local a = Mpc.tileset(m, x, y)
        for _, d in ipairs(DIRS) do
          local nx, ny = x + d[1], y + d[2]
          if nx >= 0 and ny >= 0 and nx < m.w and ny < m.h then
            local b = Mpc.tileset(m, nx, ny)
            local t = b > a and self.gfx:tileset(b) or nil
            if t then
              -- franja de PLUMA px dentro de la casilla (x, y), pegada al lado de la casilla vecina; alfa 1 junto al borde y 0 hacia dentro
              local px, py = i * 32, j * 32
              local rx, ry, rw, rh = px, py, 32, 32
              local a0, a1, a2, a3
              if d[1] == 1 then rx, rw = px + 32 - PLUMA, PLUMA; a0, a1, a2, a3 = 0, 1, 1, 0
              elseif d[1] == -1 then rw = PLUMA; a0, a1, a2, a3 = 1, 0, 0, 1
              elseif d[2] == 1 then ry, rh = py + 32 - PLUMA, PLUMA; a0, a1, a2, a3 = 0, 0, 1, 1
              else rh = PLUMA; a0, a1, a2, a3 = 1, 1, 0, 0 end
              local qx, qy = (x % 16) * 32, (y % 16) * 32
              local u0, v0 = (qx + (rx - px)) / 512, (qy + (ry - py)) / 512
              local u1, v1 = u0 + rw / 512, v0 + rh / 512
              self.malla:setVertices({
                { rx, ry, u0, v0, 1, 1, 1, a0 }, { rx + rw, ry, u1, v0, 1, 1, 1, a1 },
                { rx + rw, ry + rh, u1, v1, 1, 1, 1, a2 }, { rx, ry + rh, u0, v1, 1, 1, 1, a3 },
              })
              self.malla:setTexture(t.imagen)
              love.graphics.draw(self.malla)
            end
          end
        end
      end
    end
  end
  love.graphics.pop()
  love.graphics.setCanvas(previo)
  self.bloques[clave] = c
  return c
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
  love.graphics.setColor(1, 1, 1)
  for by = math.floor(r0 / 16), math.floor(r1 / 16) do
    for bx = math.floor(c0 / 16), math.floor(c1 / 16) do
      love.graphics.draw(self:bloque(bx, by), bx * 512, by * 512)
    end
  end
  for _, o in ipairs(m.objetos) do
    if o.x > x0 - 256 and o.x < x0 + ancho + 256 and o.y > y0 - 64 and o.y < y0 + alto + 256 then
      local s
      local frames = self.gfx:objeto_frames(o.id)
      if frames and #frames > 1 then
        -- animado: el ciclo completo dura la suma de las duraciones; cada objeto con su fase para que no vayan al unisono
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
        if o.e == 2 then
          love.graphics.draw(s.img, o.x + (s.w - s.ox), o.y - s.oy, 0, -1, 1)
        else
          love.graphics.draw(s.img, o.x - s.ox, o.y - s.oy)
        end
      end
    end
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
      if not e.muerto then
        local rx = (e.yo or e.jugador) and 15 or (e.clase == 200 and 16 or 22)
        love.graphics.setColor(0, 0, 0, 0.26)
        love.graphics.ellipse('fill', e.x, e.y + 1, rx, rx * 0.42)
      end
    end
    love.graphics.setColor(1, 1, 1)
    for _, e in ipairs(lista) do
      local ids
      if e.yo and mundo.items then ids = self.equipo:personaje(mundo:puesto(), mundo.apariencia, mundo.genero or 'g')
      elseif e.sprite then ids = { { id = e.sprite } } end
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
        else
          love.graphics.setColor(e.yo and 1 or 0.9, e.yo and 0.9 or 0.3, 0.2)
          love.graphics.circle('fill', e.x, e.y, 6)
        end
      end
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
