-- Pantalla de login y seleccion de personaje. Guarda servidor, usuario y carpeta del juego (nunca la clave) en config.txt del perfil de LÖVE.
local L = {}
L.__index = L

local CAMPOS = {
  { 'servidor', 'Servidor (host:puerto)', false },
  { 'usuario', 'Usuario', false },
  { 'clave', 'Clave', true },
  { 'carpeta', 'Carpeta del juego (con los .pak)', false },
}

local function leer_config()
  local cfg = {}
  local ok, txt = pcall(love.filesystem.read, 'config.txt')
  if ok and txt then
    for k, v in txt:gmatch('([%w_]+)=([^\r\n]*)') do cfg[k] = v end
  end
  return cfg
end

function L.nuevo(por_defecto)
  local cfg = leer_config()
  local self = setmetatable({ valores = {}, activo = 1, mensaje = nil, fase = 'form', personajes = nil, nuevo = nil }, L)
  self.valores.servidor = cfg.servidor or por_defecto.servidor or '127.0.0.1:16768'
  self.valores.usuario = cfg.usuario or ''
  self.valores.clave = ''
  self.valores.carpeta = cfg.carpeta or por_defecto.carpeta or ''
  return self
end

function L:guardar()
  local v = self.valores
  pcall(love.filesystem.write, 'config.txt', string.format('servidor=%s\nusuario=%s\ncarpeta=%s\n', v.servidor, v.usuario, v.carpeta))
end

function L:texto(t)
  if self.fase == 'crear' then
    local n = self.nuevo
    if #n.nombre < 12 and t:match('^[%w_]+$') then n.nombre = n.nombre .. t end
    return
  end
  if self.fase == 'form' then
    local c = CAMPOS[self.activo][1]
    self.valores[c] = self.valores[c] .. t
  end
end

-- Devuelve 'enviar' cuando el formulario esta completo y se pulso Enter.
function L:tecla(k)
  if self.fase == 'crear' then
    local n = self.nuevo
    if k == 'backspace' then n.nombre = n.nombre:sub(1, -2)
    elseif k == 'left' then n.peinado = (n.peinado - 1) % 13
    elseif k == 'right' then n.peinado = (n.peinado + 1) % 13
    elseif k == 'up' then n.color = (n.color + 1) % 20
    elseif k == 'down' then n.color = (n.color - 1) % 20
    elseif k == 'tab' then n.genero = 1 - n.genero
    elseif k == 'return' or k == 'kpenter' then
      if #n.nombre < 3 then self.mensaje = 'El nombre necesita al menos 3 letras'; return end
      return 'crear'
    elseif k == 'escape' then self.fase = 'seleccion'; self.mensaje = nil
    end
    return
  end
  if self.fase ~= 'form' then return end
  local c = CAMPOS[self.activo][1]
  if k == 'backspace' then
    self.valores[c] = self.valores[c]:sub(1, -2)
  elseif k == 'tab' or k == 'down' then
    self.activo = self.activo % #CAMPOS + 1
  elseif k == 'up' then
    self.activo = (self.activo - 2) % #CAMPOS + 1
  elseif k == 'return' or k == 'kpenter' then
    if self.valores.usuario == '' then self.mensaje = 'Escribe un usuario'; self.activo = 2; return end
    if self.valores.carpeta == '' then self.mensaje = 'Indica la carpeta del juego'; self.activo = 4; return end
    return 'enviar'
  end
end

function L:datos_conexion()
  local host, puerto = self.valores.servidor:match('^([^:]+):?(%d*)$')
  return host or '127.0.0.1', tonumber(puerto) or 16768
end

function L:empezar_creacion(ranura)
  self.fase = 'crear'
  self.nuevo = { ranura = ranura, nombre = '', genero = 1, peinado = 2, color = 0 }
  self.mensaje = nil
end

-- apariencia que se manda y con la que se dibuja la vista previa: genero (1 hombre), peinado, ?, color de pelo, color de piel
function L:apariencia()
  local n = self.nuevo
  return { n.genero, n.peinado, 0, n.color, 0 }
end

function L:mostrar_personajes(lista)
  self.fase = 'seleccion'
  self.personajes = lista
end

function L:dibujar(ancho, alto, raton)
  love.graphics.clear(0.06, 0.09, 0.16)
  local x = ancho / 2 - 250
  love.graphics.setColor(1, 1, 1)
  love.graphics.print('Angels Online - cliente multiplataforma (prototipo)', x, 70, 0, 1.4, 1.4)
  local filas = {}
  if self.fase == 'form' then
    for i, c in ipairs(CAMPOS) do
      local y = 140 + (i - 1) * 62
      love.graphics.setColor(0.7, 0.8, 1); love.graphics.print(c[2], x, y)
      love.graphics.setColor(i == self.activo and 0.15 or 0.1, i == self.activo and 0.25 or 0.15, i == self.activo and 0.5 or 0.3)
      love.graphics.rectangle('fill', x, y + 18, 500, 28, 4, 4)
      love.graphics.setColor(1, 1, 1)
      local v = self.valores[c[1]]
      love.graphics.print((c[3] and string.rep('*', #v) or v) .. (i == self.activo and '_' or ''), x + 8, y + 24)
    end
    love.graphics.setColor(0.8, 0.9, 1)
    love.graphics.print('Tab: cambiar campo    Enter: conectar', x, 400)
    love.graphics.print('La clave solo sirve para cuentas creadas con este cliente (la del cliente original no se puede reproducir).', x, 424, 0, 1, 1)
  elseif self.fase == 'crear' then
    local n = self.nuevo
    love.graphics.setColor(0.7, 0.8, 1); love.graphics.print('Nuevo personaje (ranura ' .. (n.ranura + 1) .. ')', x, 130)
    love.graphics.setColor(1, 1, 1)
    love.graphics.print('Nombre: ' .. n.nombre .. '_', x, 170)
    love.graphics.print('Genero: ' .. (n.genero == 1 and 'Hombre' or 'Mujer') .. '      (Tab cambia)', x, 200)
    love.graphics.print('Peinado: ' .. n.peinado .. '      (izquierda / derecha)', x, 230)
    love.graphics.print('Color de pelo: ' .. n.color .. '      (arriba / abajo)', x, 260)
    love.graphics.setColor(0.8, 0.9, 1); love.graphics.print('Enter: crear     Esc: volver', x, 300)
    if self.vista_previa then self.vista_previa(x + 380, 420, self:apariencia(), n.genero == 1 and 'b' or 'g') end
  else
    love.graphics.setColor(0.7, 0.8, 1); love.graphics.print('Elige personaje', x, 140)
    for i, pj in ipairs(self.personajes or {}) do
      local y = 180 + (i - 1) * 70
      local sobre = raton and raton[1] >= x and raton[1] < x + 500 and raton[2] >= y and raton[2] < y + 58
      love.graphics.setColor(sobre and 0.2 or 0.1, sobre and 0.35 or 0.18, sobre and 0.65 or 0.4)
      love.graphics.rectangle('fill', x, y, 500, 58, 6, 6)
      love.graphics.setColor(1, 1, 1)
      if pj.ocupada then
        love.graphics.print(pj.nombre, x + 14, y + 8, 0, 1.3, 1.3)
        love.graphics.print('Nivel ' .. pj.nivel .. '   mapa ' .. pj.mapa, x + 14, y + 34)
        filas[#filas + 1] = { x = x, y = y, w = 500, h = 58, ranura = pj.ranura }
      else
        love.graphics.setColor(0.8, 0.9, 1); love.graphics.print('(ranura vacia) clic para crear un personaje', x + 14, y + 20)
        filas[#filas + 1] = { x = x, y = y, w = 500, h = 58, ranura = pj.ranura, vacia = true }
      end
    end
  end
  if self.mensaje then
    love.graphics.setColor(1, 0.6, 0.4); love.graphics.print(self.mensaje, x, 470)
  end
  love.graphics.setColor(1, 1, 1)
  return filas
end

return L
