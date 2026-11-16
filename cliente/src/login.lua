-- Pantalla de login y seleccion de personaje (cliente propio AOF / LÖVE).
-- Guarda servidor, usuario y carpeta del juego (nunca la clave) en config.txt del perfil de LÖVE.
local L = {}
L.__index = L

local CAMPOS = {
  { 'servidor', 'Servidor', false },
  { 'usuario', 'Usuario', false },
  { 'clave', 'Clave', true },
  { 'carpeta', 'Carpeta del juego (data1.pak / update*.pak)', false },
}

-- Paleta Angels Online Forever (launcher): azul noche, carmesi, oro.
local C = {
  cielo1 = { 10 / 255, 20 / 255, 62 / 255 },
  cielo2 = { 92 / 255, 10 / 255, 30 / 255 },
  oro = { 255 / 255, 205 / 255, 96 / 255 },
  oro_suave = { 255 / 255, 238 / 255, 170 / 255 },
  texto = { 214 / 255, 214 / 255, 236 / 255 },
  texto_dim = { 160 / 255, 165 / 255, 190 / 255 },
  campo = { 8 / 255, 12 / 255, 36 / 255, 0.72 },
  campo_activo = { 22 / 255, 58 / 255, 168 / 255, 0.55 },
  rosa = { 236 / 255, 72 / 255, 92 / 255 },
}

local function leer_config()
  local cfg = {}
  local ok, txt = pcall(love.filesystem.read, 'config.txt')
  if ok and txt then
    for k, v in txt:gmatch('([%w_]+)=([^\r\n]*)') do cfg[k] = v end
  end
  return cfg
end

local function degradado(ancho, alto)
  local mesh = love.graphics.newMesh({
    { 0, 0, 0, 0, C.cielo1[1], C.cielo1[2], C.cielo1[3], 1 },
    { ancho, 0, 1, 0, C.cielo1[1], C.cielo1[2], C.cielo1[3], 1 },
    { ancho, alto, 1, 1, C.cielo2[1], C.cielo2[2], C.cielo2[3], 1 },
    { 0, alto, 0, 1, C.cielo2[1], C.cielo2[2], C.cielo2[3], 1 },
  }, 'fan')
  love.graphics.setColor(1, 1, 1, 1)
  love.graphics.draw(mesh)
end

local function halo(cx, cy, r, a)
  love.graphics.setColor(C.oro[1], C.oro[2], C.oro[3], a)
  love.graphics.circle('fill', cx, cy, r)
end

function L.nuevo(por_defecto)
  local cfg = leer_config()
  local self = setmetatable({ valores = {}, activo = 1, mensaje = nil, fase = 'form', personajes = nil, nuevo = nil, t0 = love.timer.getTime() }, L)
  self.valores.servidor = cfg.servidor or por_defecto.servidor or '127.0.0.1:16768'
  self.valores.usuario = cfg.usuario or ''
  self.valores.clave = ''
  self.valores.carpeta = cfg.carpeta or por_defecto.carpeta or 'C:/AO/Angels Online'
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

function L:apariencia()
  local n = self.nuevo
  return { n.genero, n.peinado, 0, n.color, 0 }
end

function L:mostrar_personajes(lista)
  self.fase = 'seleccion'
  self.personajes = lista
end

function L:dibujar(ancho, alto, raton)
  degradado(ancho, alto)
  local t = love.timer.getTime() - (self.t0 or 0)
  halo(ancho * 0.18, alto * 0.22, 90 + math.sin(t * 0.7) * 8, 0.07)
  halo(ancho * 0.82, alto * 0.7, 120 + math.cos(t * 0.5) * 10, 0.05)

  local x = math.floor(ancho / 2 - 260)
  local y0 = math.floor(alto * 0.14)

  love.graphics.setColor(C.oro[1], C.oro[2], C.oro[3], 1)
  love.graphics.print('ANGELS ONLINE FOREVER', x, y0, 0, 1.65, 1.65)
  love.graphics.setColor(C.oro_suave[1], C.oro_suave[2], C.oro_suave[3], 0.95)
  love.graphics.print('Cliente propio · multiplataforma', x, y0 + 36, 0, 1.05, 1.05)
  love.graphics.setColor(C.texto_dim[1], C.texto_dim[2], C.texto_dim[3], 1)
  love.graphics.print('Sin angel.dat · lee los .pak de tu instalacion', x, y0 + 58)

  local filas = {}
  if self.fase == 'form' then
    for i, c in ipairs(CAMPOS) do
      local y = y0 + 100 + (i - 1) * 68
      love.graphics.setColor(C.texto[1], C.texto[2], C.texto[3], 1)
      love.graphics.print(c[2], x, y)
      local activo = (i == self.activo)
      local col = activo and C.campo_activo or C.campo
      love.graphics.setColor(col[1], col[2], col[3], col[4] or 1)
      love.graphics.rectangle('fill', x, y + 20, 520, 32, 2, 2)
      if activo then
        love.graphics.setColor(C.oro[1], C.oro[2], C.oro[3], 0.85)
        love.graphics.rectangle('line', x, y + 20, 520, 32, 2, 2)
      end
      love.graphics.setColor(1, 1, 1, 1)
      local v = self.valores[c[1]]
      local mostrar = (c[3] and string.rep('•', #v) or v) .. (activo and (math.floor(t * 2) % 2 == 0 and '|' or ' ') or '')
      love.graphics.print(mostrar, x + 10, y + 26)
    end
    love.graphics.setColor(C.texto_dim[1], C.texto_dim[2], C.texto_dim[3], 1)
    love.graphics.print('Tab cambia campo · Enter entra', x, y0 + 390)
    love.graphics.print('Misma clave que en la web / Windows (Blowfish). La cuenta se crea en la web si aun no existe.', x, y0 + 412, 0, 0.95, 0.95)
  elseif self.fase == 'crear' then
    local n = self.nuevo
    love.graphics.setColor(C.oro[1], C.oro[2], C.oro[3], 1)
    love.graphics.print('Nuevo personaje · ranura ' .. (n.ranura + 1), x, y0 + 100)
    love.graphics.setColor(C.texto[1], C.texto[2], C.texto[3], 1)
    love.graphics.print('Nombre: ' .. n.nombre .. '|', x, y0 + 140)
    love.graphics.print('Genero: ' .. (n.genero == 1 and 'Hombre' or 'Mujer') .. '   (Tab)', x, y0 + 172)
    love.graphics.print('Peinado: ' .. n.peinado .. '   (← →)', x, y0 + 204)
    love.graphics.print('Color de pelo: ' .. n.color .. '   (↑ ↓)', x, y0 + 236)
    love.graphics.setColor(C.texto_dim[1], C.texto_dim[2], C.texto_dim[3], 1)
    love.graphics.print('Enter crea · Esc vuelve', x, y0 + 280)
    if self.vista_previa then self.vista_previa(x + 380, y0 + 380, self:apariencia(), n.genero == 1 and 'b' or 'g') end
  else
    love.graphics.setColor(C.oro[1], C.oro[2], C.oro[3], 1)
    love.graphics.print('Elige personaje', x, y0 + 100)
    for i, pj in ipairs(self.personajes or {}) do
      local y = y0 + 140 + (i - 1) * 74
      local sobre = raton and raton[1] >= x and raton[1] < x + 520 and raton[2] >= y and raton[2] < y + 62
      love.graphics.setColor(C.campo[1], C.campo[2], C.campo[3], sobre and 0.9 or 0.65)
      love.graphics.rectangle('fill', x, y, 520, 62, 2, 2)
      if sobre then
        love.graphics.setColor(C.oro[1], C.oro[2], C.oro[3], 0.9)
        love.graphics.rectangle('line', x, y, 520, 62, 2, 2)
      end
      love.graphics.setColor(1, 1, 1, 1)
      if pj.ocupada then
        love.graphics.print(pj.nombre, x + 16, y + 10, 0, 1.25, 1.25)
        love.graphics.setColor(C.texto_dim[1], C.texto_dim[2], C.texto_dim[3], 1)
        love.graphics.print('Nivel ' .. pj.nivel .. ' · mapa ' .. pj.mapa, x + 16, y + 36)
        filas[#filas + 1] = { x = x, y = y, w = 520, h = 62, ranura = pj.ranura }
      else
        love.graphics.setColor(C.texto[1], C.texto[2], C.texto[3], 1)
        love.graphics.print('Ranura vacia — clic para crear', x + 16, y + 22)
        filas[#filas + 1] = { x = x, y = y, w = 520, h = 62, ranura = pj.ranura, vacia = true }
      end
    end
  end
  if self.mensaje then
    love.graphics.setColor(C.rosa[1], C.rosa[2], C.rosa[3], 1)
    love.graphics.print(self.mensaje, x, alto - 48)
  end
  love.graphics.setColor(1, 1, 1, 1)
  return filas
end

return L
