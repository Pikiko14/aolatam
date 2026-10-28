-- Estado del mundo que cuentan los mensajes del servidor: mi personaje, el mapa y las demas entidades.
local net = require('src.net')
local u16, u32 = net.u16, net.u32

local W = {}
W.__index = W

function W.nuevo()
  return setmetatable({ ents = {}, yo = nil, stage = nil, ver_mapa = 0, chat = {}, flotantes = {}, efectos = {}, objetivo = nil }, W)
end

-- 0x0002/0x0008/0x0001/0x0003 dan la casilla; 0x0005 va en pixeles (32 por casilla). Aqui todo se guarda en pixeles, en la esquina de la casilla (el servidor usa casilla * 32).
local function px(t) return t * 32 end

local function cstr(s)
  return s:match('^[^%z]*')
end

function W:linea(t)
  self.chat[#self.chat + 1] = t
  if #self.chat > 50 then table.remove(self.chat, 1) end
end

-- Direccion de un desplazamiento (vx, vy) en pantalla (y hacia abajo) -> (digito de cuadro 3..7, espejo).
-- Los cuadros guardan 5 direcciones: 3 de frente, 4 de espaldas, 5 espalda 3/4, 6 de perfil, 7 frente 3/4; las otras 3 son espejo.
function W.direccion(vx, vy)
  local a = math.deg(math.atan2(vy, vx))
  if a > -22.5 and a <= 22.5 then return 6, false
  elseif a > 22.5 and a <= 67.5 then return 7, false
  elseif a > 67.5 and a <= 112.5 then return 3, false
  elseif a > 112.5 and a <= 157.5 then return 7, true
  elseif a > 157.5 or a <= -157.5 then return 6, true
  elseif a > -157.5 and a <= -112.5 then return 5, true
  elseif a > -112.5 and a <= -67.5 then return 4, false
  else return 5, false end
end

-- Atributos del bloque 0x0042 (o de su copia dentro del 0x0002, que empieza en +102): o = indice 1-based del primer byte del bloque.
-- Desplazamientos del servidor (inventario.stats): +24 ataque der., +28 ataque izq., +36 defensa, +44 ataque magico, +52 defensa magica,
-- +58 rigor, +62 agilidad, +66 critico, +70 aguante, +74 alma, +76 def. trueno, +80 fuego, +84 hielo, +88 podrido (efectivos).
local function atributos(b, o)
  if #b < o + 91 then return nil end
  return {
    atk_d = u32(b, o + 24), atk_i = u32(b, o + 28), dfs = u32(b, o + 36), matk = u32(b, o + 44), mdef = u32(b, o + 52),
    rigor = u16(b, o + 58), agilidad = u16(b, o + 62), critico = u16(b, o + 66), aguante = u16(b, o + 70), alma = u16(b, o + 74),
    trueno = u16(b, o + 76), fuego = u16(b, o + 80), hielo = u16(b, o + 84), podrido = u16(b, o + 88),
  }
end

-- Procesa un mensaje del servidor de mundo. Devuelve true si cambio algo que el visor deba saber.
function W:mensaje(op, b)
  if op == 0x0002 and #b >= 3960 then
    -- ficha del personaje: entidad@0, x@8, y@12, nombre@16, stage@3953
    self.yo = u32(b, 1)
    self.stage = u32(b, 3954)
    self.ents[self.yo] = { id = self.yo, x = px(u32(b, 9)), y = px(u32(b, 13)), nombre = cstr(b:sub(17, 50)), yo = true }
    self.stats = { hp = u32(b, 103), hp_max = u32(b, 107), mp = u32(b, 111), mp_max = u32(b, 115) }   -- bloque de 0x0042 en +102
    self.atrib = atributos(b, 103) or self.atrib
    -- faccion en +60 (1 Aurora, 2 Beasts, 3 Steel, 4 Shadow, 5 Heaven) y 36 habilidades de 14 B desde +214: id u8, nivel u16, nivel2 u16, exp u32, exp_sig u32
    self.faccion = b:byte(61)
    if #b >= 1874 then self.titulo = u32(b, 1871) end      -- titulo puesto (crown.xml), +0x750 de la ficha con opcode = +1870 del cuerpo
    self.habs = {}
    for i = 0, 35 do
      local o = 215 + i * 14
      if o + 13 <= #b and b:byte(o) ~= 0 then
        self.habs[#self.habs + 1] = { id = b:byte(o), nivel = u16(b, o + 1), exp = u32(b, o + 6), exp_sig = u32(b, o + 10) }
      end
    end
    -- unk_50 de la ficha empieza en +50: nivel u32 @65, exp actual u64 @69, exp siguiente u64 @85 (valores de la barra)
    local nivel_antes = self.nivel
    self.nivel = u32(b, 66)
    if nivel_antes and self.nivel > nivel_antes and self.evento then self.evento('lvup') end
    self.exp, self.exp_sig = u32(b, 70) + u32(b, 74) * 4294967296, u32(b, 86) + u32(b, 90) * 4294967296
    self.apariencia = { b:byte(56), b:byte(57), b:byte(58), b:byte(59), b:byte(60) }
    self.genero = b:byte(56) == 1 and 'b' or 'g'      -- primer byte de la apariencia (+55); 1 = hombre segun las grabaciones
    self.ver_mapa = self.ver_mapa + 1
  elseif op == 0x0042 and #b >= 16 then
    self.stats = { hp = u32(b, 1), hp_max = u32(b, 5), mp = u32(b, 9), mp_max = u32(b, 13) }
    self.atrib = atributos(b, 1) or self.atrib
  elseif op == 0x001D and #b >= 14 and u32(b, 1) == self.yo and (b:byte(6) == 31 or b:byte(6) == 32) then
    local p, n = 6, b:byte(5)
    for _ = 1, n do
      if p + 8 > #b then break end
      local code = b:byte(p)
      if code ~= 31 and code ~= 32 then break end
      local v = u32(b, p + 1) + u32(b, p + 5) * 4294967296
      if code == 32 then self.exp = v else self.exp_sig = v end
      p = p + 9
    end
  elseif op == 0x0013 and #b >= 6 then
    -- atributos de una entidad: entidad@0, n@4 y n veces (kind u8, valor u32). kind 0 = HP (% en monstruos), 2 = MP
    local id, n = u32(b, 1), b:byte(5)
    local e = self.ents[id]
    for i = 0, n - 1 do
      local p = 6 + i * 5
      if p + 4 > #b then break end
      local kind, val = b:byte(p), u32(b, p + 1)
      if kind == 0 then
        if e then e.hp = val end
        if id == self.yo and self.stats then self.stats.hp = val end
      elseif kind == 2 and id == self.yo and self.stats then
        self.stats.mp = val
      end
    end
  elseif op == 0x000A and #b >= 12 then
    -- evento de combate: a@0, b@4, c@8. c = 7 muerte de `a`; c = 0x03060001 `a` fija como objetivo a `b`; otro c = golpe de `a` a `b`
    local a, t, c = u32(b, 1), u32(b, 5), u32(b, 9)
    local ahora = love.timer.getTime()
    local ea, et = self.ents[a], self.ents[t]
    if c == 7 then
      if ea then ea.muerto = ahora end
      if self.objetivo == a then self.objetivo = nil end
    elseif c == 0x03060001 then
      if a == self.yo then self.objetivo = t end
    elseif ea then
      ea.atacando = ahora + 0.5
      if et and (et.x ~= ea.x or et.y ~= ea.y) then ea.dig, ea.espejo = W.direccion(et.x - ea.x, et.y - ea.y) end
    end
  elseif op == 0x000B and #b >= 9 then
    -- numero flotante sobre quien recibe el golpe: entidad@0, tipo@4, valor@5
    local e = self.ents[u32(b, 1)]
    if e then self.flotantes[#self.flotantes + 1] = { id = e.id, valor = u32(b, 6), t = love.timer.getTime(), tipo = b:byte(5) } end
    if e and self.evento then self.evento('golpe', e) end
  elseif op == 0x0007 and #b >= 4 then
    local id = u32(b, 1)
    self.ents[id] = nil
    if self.objetivo == id then self.objetivo = nil end
  elseif op == 0x0011 and #b >= 10 then
    -- efecto de golpe o magia: [efecto u8][fase u8][atacante u32][objetivo u32]; fase 0x00 reproduce el efecto sobre el objetivo
    if b:byte(2) == 0 then
      self.efectos[#self.efectos + 1] = { id = b:byte(1), objetivo = u32(b, 7), t = love.timer.getTime() }
    end
  elseif op == 0x0050 and #b >= 80 then
    -- mascota en el mundo: entidad@0, casilla x@8 y@12, nombre@16 (13 B), sprite u16 @45, dueno@75
    local id = u32(b, 1)
    self.ents[id] = { id = id, x = px(u32(b, 9)), y = px(u32(b, 13)), nombre = cstr(b:sub(17, 29)), sprite = u16(b, 46), mascota = true, dueno = u32(b, 76) }
  elseif op == 0x0065 and #b >= 200 then
    -- ficha de la mascota (200 B): nombre@18, nivel u32@31, exp u64@35, hp@59 mp@63 hpmax@71 mpmax@79, stats dobles (base, efectivo) desde @83
    local function doble(o) return { u32(b, o + 1), u32(b, o + 5) } end
    self.mascota = {
      entidad = u32(b, 1), sprite = u16(b, 17), nombre = cstr(b:sub(19, 31)), nivel = u32(b, 32),
      exp = u32(b, 36) + u32(b, 40) * 4294967296, exp_max = u32(b, 52) + u32(b, 56) * 4294967296,
      hp = u32(b, 60), mp = u32(b, 64), hp_max = u32(b, 72), mp_max = u32(b, 80),
      atk = doble(83), dfs = doble(91), matk = doble(99), mdef = doble(107), rigor = doble(115), agilidad = doble(123),
      saciedad = u16(b, 178), intimidad = b:byte(180), estrellas = u32(b, 197),
    }
  elseif op == 0x0023 and #b >= 5 then
    -- invitacion a un grupo: [char del lider u32][nombre ASCIIZ]
    self.invitacion_grupo = { nombre = cstr(b:sub(5, 21)) }
    self:linea('* ' .. self.invitacion_grupo.nombre .. ' invites you to a team (Y accept, N decline)')
  elseif op == 0x0024 and #b >= 10 then
    -- lista del grupo: cabecera [u32 id][u8 modo][u32 char del lider][u8 n] y n bloques de 78 B
    local lider, n, miembros = u32(b, 6), b:byte(10), {}
    for i = 0, n - 1 do
      local p = 11 + i * 78
      if p + 77 > #b then break end
      miembros[#miembros + 1] = {
        cid = u32(b, p), nombre = cstr(b:sub(p + 8, p + 23)), nivel = b:byte(p + 24), escena = u32(b, p + 25),
        hp = u16(b, p + 33), mp = u16(b, p + 35),
      }
    end
    self.grupo = #miembros > 0 and { lider = lider, miembros = miembros } or nil
  elseif op == 0x0026 and #b >= 78 and self.grupo then
    -- actualizacion de un miembro (mismo bloque de 78 B): vida y mana en porcentaje
    local cid = u32(b, 1)
    for _, m in ipairs(self.grupo.miembros) do
      if m.cid == cid then m.hp, m.mp, m.escena, m.nivel = u16(b, 34), u16(b, 36), u32(b, 26), b:byte(25) end
    end
  elseif op == 0x0025 and #b >= 9 then
    -- evento de grupo: tipo 4 = un miembro se va [u8 tipo][u32 grupo][u32 miembro][nombre 17]
    if b:byte(1) == 4 and self.grupo then
      local cid = u32(b, 6)
      for i, m in ipairs(self.grupo.miembros) do if m.cid == cid then table.remove(self.grupo.miembros, i); break end end
      if #self.grupo.miembros <= 1 then self.grupo = nil end
    end
  elseif op == 0x0126 and #b >= 27 then
    -- chat de equipo / liga / matrimonio: [entidad u32][canal u8][u32 0][nombre 17][texto]
    local canal = ({ [4] = 'Team', [5] = 'League', [14] = 'Marriage' })[b:byte(5)] or tostring(b:byte(5))
    self:linea(string.format('[%s] %s> %s', canal, cstr(b:sub(10, 26)), cstr(b:sub(27))))
  elseif op == 0x0127 and #b >= 40 then
    -- susurro: [u32 0][u16 error][emisor 17][receptor 17][u16 0][texto]
    local err, de, para, txt = u16(b, 5), cstr(b:sub(7, 23)), cstr(b:sub(24, 40)), cstr(b:sub(43))
    if err ~= 0 then self:linea('* ' .. para .. ' is not online')
    elseif self.yo and self.ents[self.yo] and self.ents[self.yo].nombre == de then self:linea('[To ' .. para .. '] ' .. txt)
    else self:linea('[Whisper] ' .. de .. '> ' .. txt) end
  elseif op == 0x0027 and #b >= 8 then
    -- lista de amigos: [char propio u32][n u32] y n filas de 42 B: [char_id u32][nombre 17][grupo 17][u32 0]
    local n, lista = u32(b, 5), {}
    for i = 0, n - 1 do
      local p = 9 + i * 42
      if p + 41 > #b then break end
      lista[#lista + 1] = { cid = u32(b, p), nombre = cstr(b:sub(p + 4, p + 20)), grupo = cstr(b:sub(p + 21, p + 37)), conectado = false }
    end
    self.amigos = lista
  elseif op == 0x0028 and #b >= 67 then
    -- estado de un amigo conectado: cid @26, escena @30, casilla @34/@38, nombre @66
    local cid = u32(b, 27)
    for _, a in ipairs(self.amigos or {}) do
      if a.cid == cid then a.conectado, a.escena = true, u32(b, 31) end
    end
  elseif op == 0x002E and #b >= 8 then
    local cid = u32(b, 5)
    for _, a in ipairs(self.amigos or {}) do if a.cid == cid then a.conectado, a.escena = false, nil end end
  elseif op == 0x0029 and #b >= 23 then
    -- invitacion de amistad: [char destino u32][u16 0][nombre 17]
    self.invitacion = { nombre = cstr(b:sub(7, 23)) }
    self:linea('* ' .. self.invitacion.nombre .. ' wants to be your friend (Y accept, N decline)')
  elseif op == 0x002A and #b >= 44 then
    -- amigo anadido: id @6, nombre @27, estado @44
    self.amigos = self.amigos or {}
    local cid = u32(b, 7)
    local ya = false
    for _, a in ipairs(self.amigos) do if a.cid == cid then ya = true end end
    if not ya then self.amigos[#self.amigos + 1] = { cid = cid, nombre = cstr(b:sub(28, 44)), grupo = '', conectado = u32(b, 45) == 0 } end
    self:linea('* ' .. cstr(b:sub(28, 44)) .. ' is now your friend')
  elseif op == 0x005B and #b >= 9 then
    -- barra de habilidades: 24 ranuras de 9 B: [tipo u8 (1 hechizo, 2 objeto)][id u32][4 B]
    local barra = {}
    for i = 0, 23 do
      local p = 1 + i * 9
      if p + 8 > #b then break end
      local tipo, id = b:byte(p), u32(b, p + 1)
      if tipo ~= 0 and id ~= 0 then barra[i + 1] = { tipo = tipo, id = id } end
    end
    self.barra = barra
  elseif op == 0x0021 and #b >= 4 then
    -- registro de misiones: [u32 n] y n veces [char_id u32][quest_id u16][paso u8][11 B]
    local n, lista = u32(b, 1), {}
    for i = 0, n - 1 do
      local p = 5 + i * 18
      if p + 17 > #b then break end
      lista[#lista + 1] = { id = u16(b, p + 4), paso = b:byte(p + 6) }
    end
    self.misiones = lista
  elseif op == 0x004E and #b >= 4 then
    -- almacen: [u32 tipo * 1000 + n] y n entradas como las del 0x001A; con tipo 2 o 3 se abre la ventana
    local cab = u32(b, 1)
    local n, p = cab % 1000, 5
    self.banco = { items = {}, cantidades = {}, instancias = {} }
    for _ = 1, n do
      if p + 52 > #b then break end
      local casilla = u16(b, p + 38)
      self.banco.items[casilla], self.banco.cantidades[casilla], self.banco.instancias[casilla] = u32(b, p + 9), u32(b, p + 40), b:sub(p + 1, p + 8)
      p = p + 86 + u16(b, p + 51)
    end
    local tipo = math.floor(cab / 1000)
    if tipo == 2 or tipo == 3 then self.banco_abierto = true end
  elseif op == 0x0034 and #b >= 2 then
    self.tienda = { id = u16(b, 1), pagina = 0 }
  elseif op == 0x001B and #b >= 4 and self.items then
    -- actualizacion de casillas: [u32 n] y n entradas. byte 0 = 2: vaciar [2][contenedor u8][dueno u32][casilla u16] (8 B);
    -- si no, entrada completa (item@9, contenedor@33, casilla@38, cantidad@40, largo 86 + u16@51). Contenedor 1 = mochila, 2 = banco.
    local n, p = u32(b, 1), 5
    for _ = 1, n do
      if p > #b then break end
      if b:byte(p) == 2 and p + 7 <= #b then
        local destino = (b:byte(p + 1) == 2 and self.banco) or self
        local casilla = u16(b, p + 6)
        destino.items[casilla], destino.cantidades[casilla], destino.instancias[casilla] = nil, nil, nil
        p = p + 8
      elseif p + 52 <= #b then
        local destino = (b:byte(p + 33) == 2 and self.banco) or self
        local item, casilla = u32(b, p + 9), u16(b, p + 38)
        destino.items[casilla], destino.cantidades[casilla], destino.instancias[casilla] = item, u32(b, p + 40), b:sub(p + 1, p + 8)
        p = p + 86 + u16(b, p + 51)
      else
        break
      end
    end
  elseif op == 0x0012 and #b >= 9 then
    -- linea de dialogo: msg_id@0, retrato@4, n_cadenas@6, n_opciones@7, 0@8, opciones (u32), acciones (u32), cadenas
    local mid, val, ncad, nop = u32(b, 1), u16(b, 5), b:byte(7), b:byte(8)
    if os.getenv('AO_DEBUG') then print('0x0012', mid, val, ncad, nop, #b) end
    if mid == 0 then
      self.dialogo = nil
    else
      local opciones = {}
      for i = 0, nop - 1 do opciones[#opciones + 1] = u32(b, 10 + 4 * i) end
      local cadenas, p = {}, 10 + 8 * nop
      for _ = 1, ncad do
        local t = cstr(b:sub(p))
        cadenas[#cadenas + 1] = t
        p = p + #t + 1
      end
      self.dialogo = { mid = mid, val = val, opciones = opciones, cadenas = cadenas }
    end
  elseif op == 0x0128 and #b >= 23 then
    -- chat por canal: entidad@0, canal@4, nombre@5 (17 B), texto
    self:linea(string.format('[%d] %s> %s', b:byte(5), cstr(b:sub(6, 22)), cstr(b:sub(23))))
  elseif op == 0x000D and #b >= 4 then
    -- aviso del sistema: [u16 id][u8 tipo][texto]; con id de texto literal es el propio texto
    local t = cstr(b:sub(4))
    if t ~= '' then self:linea('* ' .. t) end
  elseif op == 0x001A and #b >= 4 then
    -- inventario completo: [u32 n] y n entradas; cada una: item@9 (u32), casilla@38 (u16), largo = 86 + u16@51
    local n, p = u32(b, 1), 5
    self.items, self.cantidades, self.instancias = {}, {}, {}
    for _ = 1, n do
      if p + 52 > #b then break end
      local item, casilla = u32(b, p + 9), u16(b, p + 38)
      self.items[casilla] = item
      self.cantidades[casilla] = u32(b, p + 40)
      self.instancias[casilla] = b:sub(p + 1, p + 8)
      p = p + 86 + u16(b, p + 51)
    end
  elseif op == 0x0008 and #b >= 62 then
    local id = u32(b, 1)
    self.ents[id] = { id = id, x = px(u32(b, 9)), y = px(u32(b, 13)), nombre = cstr(b:sub(17, 33)), sprite = u32(b, 35), clase = u32(b, 41) }
  elseif op == 0x0001 and #b >= 60 then
    local id = u32(b, 1)
    self.ents[id] = { id = id, x = px(u32(b, 9)), y = px(u32(b, 13)), nombre = cstr(b:sub(17, 32)), jugador = true }
  elseif op == 0x0005 and #b >= 22 then
    local e = self.ents[u32(b, 1)]
    if e then
      e.x, e.y, e.dx, e.dy, e.vel = u32(b, 5), u32(b, 9), u32(b, 13), u32(b, 17), u16(b, 21)
      if e.dx ~= e.x or e.dy ~= e.y then e.dig, e.espejo = W.direccion(e.dx - e.x, e.dy - e.y) end
    end
  elseif op == 0x0003 and #b >= 12 then
    local e = self.ents[u32(b, 1)]
    if e then e.x, e.y, e.dx, e.dy = px(u32(b, 5)), px(u32(b, 9)), nil, nil end
  end
end

-- Oro: la casilla 0 del inventario es el oro (item 1) y su cantidad es el total.
function W:oro()
  return (self.cantidades and self.cantidades[0]) or 0
end

-- Ids de item que lleva puestos mi personaje: equipo regular (casillas 1..19); la Fashion (167..174) pisa a la de Gear.
function W:puesto()
  local out = {}
  for casilla, item in pairs(self.items or {}) do
    if casilla >= 1 and casilla < 20 then out[#out + 1] = { casilla, item } end
  end
  table.sort(out, function(a, b) return a[1] < b[1] end)
  local lista = {}
  for _, v in ipairs(out) do lista[#lista + 1] = v[2] end
  for c = 167, 174 do if self.items and self.items[c] then lista[#lista + 1] = self.items[c] end end
  return lista
end

-- Avanza las entidades que van caminando hacia su destino (vel = pixeles por segundo, medido en 0x0005).
function W:avanzar(dt)
  local ahora = love.timer.getTime()
  for id, e in pairs(self.ents) do
    if e.muerto and ahora - e.muerto > 2 and not e.yo then self.ents[id] = nil end
  end
  for i = #self.efectos, 1, -1 do
    if ahora - self.efectos[i].t > 3 then table.remove(self.efectos, i) end
  end
  for i = #self.flotantes, 1, -1 do
    if ahora - self.flotantes[i].t > 1.2 then table.remove(self.flotantes, i) end
  end
  for _, e in pairs(self.ents) do
    if e.dx then
      local vx, vy = e.dx - e.x, e.dy - e.y
      local d = math.sqrt(vx * vx + vy * vy)
      local paso = (e.vel or 50) * dt * 3
      if d <= paso then e.x, e.y, e.dx, e.dy = e.dx, e.dy, nil, nil
      else e.x, e.y = e.x + vx / d * paso, e.y + vy / d * paso end
    end
  end
end

return W
