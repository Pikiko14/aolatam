-- Pruebas de la capa de red contra los vectores que genera el servidor Python (vectores.lua).
-- Se corren con:  love cliente --pruebas     (lovec.exe en Windows para ver la salida en consola)
local net = require('src.net')
local V = require('tests.vectores')

local pasadas, falladas = 0, {}

local function hex(s) return (s:gsub('.', function(c) return string.format('%02x', c:byte()) end)) end
local function unhex(h) return (h:gsub('%x%x', function(x) return string.char(tonumber(x, 16)) end)) end

local function igual(nombre, obtenido, esperado)
  if obtenido == esperado then
    pasadas = pasadas + 1
  else
    falladas[#falladas + 1] = string.format('%s: obtuvo %s, esperaba %s', nombre, tostring(obtenido), tostring(esperado))
  end
end

-- checksum
for i, c in ipairs(V.checksum) do
  local p = unhex(c.payload)
  igual('checksum #' .. i .. ' (' .. #p .. ' B)', net.checksum(p, #p), c.csum)
end

-- frames en claro: se arman iguales y se leen igual
for i, c in ipairs(V.claro) do
  local p = unhex(c.payload)
  igual('claro #' .. i .. ' armado', hex(net.build_frame(p, c.seq)), c.frame)
  local h = net.decode_header(unhex(c.frame))
  igual('claro #' .. i .. ' largo', h.length, c.length)
  igual('claro #' .. i .. ' secuencia', h.seq, c.seq)
  igual('claro #' .. i .. ' flags', h.flags, c.flags)
  igual('claro #' .. i .. ' total', h.wire, c.wire)
end

-- frames cifrados con clave evolutiva (secuencia: el estado pasa de un frame al siguiente)
local function secuencia(nombre, lista, clave)
  local cripto = net.xor_evolving(clave)
  for i, c in ipairs(lista) do
    igual(nombre .. ' #' .. i .. ' armado', hex(net.build_frame(unhex(c.payload), c.seq, cripto)), c.frame)
  end
  -- el lado que recibe (servidor) descifra la misma secuencia con otro objeto y recupera los payloads
  local rx = net.xor_evolving(clave)
  local lector = net.new_reader()
  lector.recv_crypto = rx
  local texto = {}
  for _, c in ipairs(lista) do texto[#texto + 1] = unhex(c.frame) end
  local frames = lector:feed(table.concat(texto))
  igual(nombre .. ' cantidad de frames leidos', #frames, #lista)
  for i, f in ipairs(frames) do
    if lista[i] then
      igual(nombre .. ' #' .. i .. ' payload leido', hex(f.payload), lista[i].payload)
      igual(nombre .. ' #' .. i .. ' checksum del payload', f.checksum_ok, true)
    end
  end
end
secuencia('cifrado', V.cifrado, unhex(V.clave))
secuencia('clave cero', V.cero, string.rep('\0', 16))

-- el lector parte bien el flujo aunque llegue a trozos de 1 byte
do
  local lector = net.new_reader()
  local texto = {}
  for _, c in ipairs(V.claro) do texto[#texto + 1] = unhex(c.frame) end
  local todo = table.concat(texto)
  local n = 0
  for i = 1, #todo do n = n + #lector:feed(todo:sub(i, i)) end
  igual('flujo byte a byte', n, #V.claro)
end

-- sub-mensajes
do
  local msgs = net.submessages(unhex(V.sub.payload))
  igual('sub-mensajes: cantidad', #msgs, V.sub.n)
  for i, m in ipairs(msgs) do igual('sub-mensaje #' .. i .. ' opcode', m.opcode, V.sub.opcodes[i]) end
  -- y se vuelven a empaquetar igual
  local crudos = {}
  for i, m in ipairs(msgs) do crudos[i] = net.p16(m.opcode) .. m.body end
  igual('sub-mensajes re-empaquetados', hex(net.pack_submessages(crudos)), V.sub.payload)
end

-- Hello (el de nuestro servidor y el minimo)
for _, h in ipairs(V.hello) do
  local r = net.parse_hello(unhex(h.payload))
  igual('hello ' .. h.nombre .. ' clave', hex(r.key), h.key)
  igual('hello ' .. h.nombre .. ' variante', r.variante, h.variante)
end

-- Blowfish del AUTH (igual que server/clave_cliente.py con clave "secreta")
do
  local clave = require('src.clave')
  local esperado = 'ba060f983787c77ba23443825daf4edda23443825daf4edda23443825daf4edd'
  igual('clave Blowfish secreta', hex(clave.bloque('secreta')), esperado)
end

-- Objeto de mapa con nombre (0x000F real de una sesion: veta "Copper(L)") y el mismo id otra vez (busca-o-crea)
do
  local W = require('src.mundo')
  local w = W.nuevo()
  local b = unhex('f0d9d20300000000d40a000050090000436f70706572284c29000000000000006d0601eb0000000000000002')
  w:mensaje(0x000F, b)
  local e = w.ents[64150000]
  igual('0x000F crea el objeto', e ~= nil, true)
  igual('0x000F posicion', e and (e.x .. ',' .. e.y), '2772,2384')
  igual('0x000F sprite', e and e.sprite, 60161)
  igual('0x000F nombre', e and e.nombre, 'Copper(L)')
  w:mensaje(0x000E, b:sub(1, 43))
  igual('0x000E no rehace el objeto', w.ents[64150000] == e, true)
  -- flags de mapa y stage de una sesion real (stage 41 = 0x29), y el bit 0x20 que apaga el minimapa
  w:mensaje(0x0014, unhex('05020000ff0000'))
  igual('0x0014 con minimapa', w.sin_minimapa, false)
  w:mensaje(0x0014, unhex('25020000ff0000'))
  igual('0x0014 sin minimapa', w.sin_minimapa, true)
  w:mensaje(0x0196, unhex('020003010100000029005c00000003'))
  igual('0x0196 stage', w.stage, 41)
end

-- Canal Lua (0x01A0): el saludo del servidor (subasta_ventana.SALUDO) llega como codigo y debe salir el c2s 0x002F
do
  local W = require('src.mundo')
  local nat = require('src.nativo')
  local w = W.nuevo()
  w:mensaje(0x01A0, 'game.netcommand2(160, 1, 0)\0')
  igual('0x01A0 encola el codigo', w.lua_pendiente and w.lua_pendiente[1], 'game.netcommand2(160, 1, 0)')
  local enviado
  local g_prev = rawget(_G, 'game')
  rawset(_G, 'game', nat.game)
  nat.game.enviar = function(m) enviado = m end
  nat.ejecutar(w.lua_pendiente[1])
  igual('netcommand2 -> c2s 0x002F', enviado and hex(enviado), '2f00a00100000000000000')
  nat.game.netcommand(117, 0)
  igual('netcommand -> c2s 0x002E', enviado and hex(enviado), '2e007500000000000000')
  nat.game.enviar = nil
  rawset(_G, 'game', g_prev)
end

print(string.format('PRUEBAS net.lua: %d correctas, %d falladas', pasadas, #falladas))
for _, f in ipairs(falladas) do print('  FALLA ' .. f) end
return #falladas == 0
