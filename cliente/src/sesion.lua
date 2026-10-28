-- Sesion con el servidor: login (puerto 16768) -> elegir personaje -> redirect -> mundo (16769).
-- Maquina de estados sin bloqueo para usarla desde love.update. Solo depende de luasocket (viene con LÖVE).
local socket = require('socket')
local net = require('src.net')

local S = {}
S.__index = S

local OP_AUTH, OP_LISTA, OP_ENTRAR, OP_REDIRECT = 0x0002, 0x0000, 0x0006, 0x0004

-- AUTH de login: [usuario en texto + nulo, relleno] + bloque opaco de contrasena (73 B en total).
-- Con el servidor de desarrollo (validar_password = 0) el bloque puede ir en cero.
-- AUTH de login: usuario en texto + nulo (hasta 21 B), 32 B de huella de la clave desde el desplazamiento 21 (cuentas.hash_de_auth del
-- servidor) y relleno hasta 73 B. El cifrado de la clave del cliente original no esta resuelto: este cliente manda su propia huella
-- (sha256 de usuario + clave), asi que solo entra en cuentas creadas con el. Sin clave (nil) va en cero (servidor de desarrollo).
local function auth_login(usuario, clave)
  local cuerpo = (usuario .. '\0'):sub(1, 21)
  cuerpo = cuerpo .. string.rep('\0', 21 - #cuerpo)
  if clave and clave ~= '' then
    cuerpo = cuerpo .. love.data.hash('sha256', 'angels-lua:' .. usuario:lower() .. ':' .. clave)
  end
  cuerpo = cuerpo .. string.rep('\0', 73 - #cuerpo)
  return net.p16(OP_AUTH) .. cuerpo
end

local function auth_mundo()
  return net.p16(OP_AUTH) .. string.rep('\0', 33)
end

function S.nueva(opciones)
  local self = setmetatable({}, S)
  self.host, self.puerto = opciones.host, opciones.puerto
  self.usuario, self.ranura = opciones.usuario, opciones.ranura or 0
  self.clave = opciones.clave
  self.alError = opciones.alError
  self.esperar_seleccion = opciones.esperar_seleccion      -- true: no entra solo, avisa con alLista y espera entrar(ranura)
  self.alLista = opciones.alLista or function() end
  self.alCreado = opciones.alCreado or function() end
  self.alMensaje = opciones.alMensaje or function() end     -- (opcode, cuerpo, rol)
  self.alEstado = opciones.alEstado or function() end
  self.rol, self.estado = 'login', 'inicio'
  self.lista = nil
  return self
end

function S:_conectar(host, puerto, rol)
  if self.sock then self.sock:close() end
  local s = socket.tcp()
  s:settimeout(0)
  s:setoption('tcp-nodelay', true)
  s:connect(host, puerto)                 -- sin bloqueo: devuelve 'timeout' y se completa luego
  self.sock, self.rol = s, rol
  self.lector = net.new_reader()
  self.cripto = net.xor_evolving(string.rep('\0', 16))   -- el cliente real usa clave en cero (ver session.py)
  self.seq = 1
  self.conectado, self.cola = false, {}
  self:_estado('conectando ' .. rol)
end

function S:_estado(t)
  self.estado = t
  self.alEstado(t)
end

function S:iniciar()
  self:_conectar(self.host, self.puerto, 'login')
end

function S:enviar(...)
  local msgs = { ... }
  local payload = net.pack_submessages(msgs)
  self.cola[#self.cola + 1] = net.build_frame(payload, self.seq, self.cripto)
  self.seq = self.seq + 1
end

function S:_volcar()
  if not self.conectado then return end
  while #self.cola > 0 do
    local data = table.remove(self.cola, 1)
    local ok, err = self.sock:send(data)
    if not ok then self:_estado('error enviando: ' .. tostring(err)); return end
  end
end

function S:_al_frame(f)
  if f.seq == net.SEQ_HELLO then
    -- Nuestro servidor manda clave en cero: S->C va en claro y no hay nada que instalar.
    self.hello = net.parse_hello(f.payload)
    if self.rol == 'login' then self:enviar(auth_login(self.usuario, self.clave)) else self:enviar(auth_mundo()) end
    self:_estado('hello recibido (' .. self.hello.variante .. ')')
    return
  end
  for _, m in ipairs((net.submessages(f.payload))) do
    if self.rol == 'login' and m.opcode == OP_LISTA and #m.body >= 2 and net.u16(m.body, 1) ~= 0 then
      -- login rechazado: el servidor responde con el mismo 0x0000 y un codigo de error en los dos primeros bytes (3 = clave incorrecta)
      local codigo = net.u16(m.body, 1)
      local texto = codigo == 3 and 'Clave incorrecta' or ('Login rechazado por el servidor (codigo ' .. codigo .. ')')
      self.rechazado = codigo
      self:_estado(texto)
      if self.alError then self.alError(codigo, texto) end
    elseif self.rol == 'login' and m.opcode == OP_LISTA then
      self.lista = m.body
      self:_estado('lista de personajes recibida')
      if self.esperar_seleccion then
        self.alLista(m.body)
      else
        self:entrar(self.ranura)
      end
    elseif self.rol == 'login' and m.opcode == 0x0001 and #m.body >= 150 then
      -- respuesta a crear personaje: [u16 error][ficha de 147 B desde el byte 2]
      self.alCreado(net.u16(m.body, 1), m.body)
    elseif self.rol == 'login' and m.opcode == OP_REDIRECT then
      local ip = m.body:sub(8, 23):match('^[^%z]*')
      local puerto = net.u16(m.body, 24)
      self:_estado('redirect a ' .. ip .. ':' .. puerto)
      self.destino = { ip, puerto }
    end
    self.alMensaje(m.opcode, m.body, self.rol)
  end
end

-- CREAR PERSONAJE (C2S 0x0003, 57 B): [ranura u8][5 elegidos: genero, peinado, ?, color de pelo, color de piel][nombre ASCII + nulo][ceros]
function S:crear(ranura, elegidos, nombre)
  local cuerpo = string.char(ranura)
  for i = 1, 5 do cuerpo = cuerpo .. string.char(elegidos[i] or 0) end
  cuerpo = cuerpo .. nombre:sub(1, 16) .. '\0'
  cuerpo = cuerpo .. string.rep('\0', 57 - #cuerpo)
  self:enviar(net.p16(0x0003) .. cuerpo)
end

-- Ficha de un personaje dentro de la respuesta de creacion (base 3, igual que la primera de la lista de cuenta).
function S.ficha_creada(body, ranura)
  return {
    ranura = ranura, ocupada = true, nivel = net.u32(body, 3 + 2), nombre = body:sub(3 + 36, 3 + 51):match('^[^%z]*'),
    mapa = net.u32(body, 3 + 12),
  }
end

-- ENTRAR AL MUNDO: ranura + relleno (el servidor solo mira el primer byte)
function S:entrar(ranura)
  self.ranura = ranura
  self:enviar(net.p16(OP_ENTRAR) .. string.char(ranura) .. string.rep('\0', 34))
end

-- Personajes de la lista de cuenta (0x0000): 3 fichas de 147 B desde el byte 3 (sin opcode). Ocupada si el LE32 +31 no es cero.
function S.personajes(lista)
  local out = {}
  for i = 0, 2 do
    local base = 3 + 147 * i
    if base + 147 <= #lista + 1 then
      local ocupada = net.u32(lista, base + 32) ~= 0
      out[#out + 1] = {
        ranura = i, ocupada = ocupada, nivel = net.u32(lista, base + 2),
        nombre = lista:sub(base + 36, base + 51):match('^[^%z]*'), mapa = net.u32(lista, base + 12),
      }
    end
  end
  return out
end

function S:actualizar()
  if not self.sock then return end
  if not self.conectado then
    local r, e = self.sock:connect(self.host, self.puerto)
    if r == 1 or e == 'already connected' then
      self.conectado = true
      self:_estado('conectado (' .. self.rol .. ')')
    elseif e ~= 'timeout' and e ~= 'Operation already in progress' then
      self:_estado('error conectando: ' .. tostring(e))
    end
    return
  end
  self:_volcar()
  local data, err, parcial = self.sock:receive(65536)
  data = data or parcial
  if data and #data > 0 then
    for _, f in ipairs(self.lector:feed(data)) do self:_al_frame(f) end
  end
  if err == 'closed' then self:_estado('cerrado por el servidor'); self.sock = nil; return end
  if self.destino then
    local d = self.destino
    self.destino = nil
    self.host, self.puerto = d[1], d[2]
    self:_conectar(d[1], d[2], 'mundo')
  end
end

return S
