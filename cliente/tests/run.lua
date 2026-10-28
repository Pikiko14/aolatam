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

print(string.format('PRUEBAS net.lua: %d correctas, %d falladas', pasadas, #falladas))
for _, f in ipairs(falladas) do print('  FALLA ' .. f) end
return #falladas == 0
