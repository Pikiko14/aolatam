-- Capa de red del cliente: tramas del protocolo de Angels Online (proto/framing.py y proto/handshake.py del servidor, en Lua).
--
--   b0-1 : largo del payload  XOR 0x1357            (LE16)
--   b2-3 : secuencia          XOR largo             (LE16)
--   b4   : flags              XOR (largo & 0xFF)    bit0 = cifrado, bit7 = comprimido
--   b5   : checksum del payload EN CLARO
--   total = 6 + (cifrado ? largo redondeado a 16 : largo)
-- El payload son sub-mensajes: [LE16 largo][LE16 opcode][cuerpo], donde el largo incluye el opcode.
--
-- Solo usa la libreria estandar de Lua/LuaJIT (bit, string, table): corre igual en Windows, Linux, macOS, Android e iOS.

local bit = require('bit')
local band, bor, bxor, bnot, lshift, rshift = bit.band, bit.bor, bit.bxor, bit.bnot, bit.lshift, bit.rshift

local M = {}

M.HDR = 6
M.HDR_XOR = 0x1357
M.FLAG_ENC = 0x01
M.FLAG_CMP = 0x80
M.SEQ_HELLO = 0xFFFF
M.KEY_LEN = 16

-- ---------------------------------------------------------------- enteros pequenos (indices base 1)
local function u16(s, i)
  local a, b = s:byte(i, i + 1)
  return a + b * 256
end

local function u32(s, i)
  local a, b, c, d = s:byte(i, i + 3)
  return a + b * 256 + c * 65536 + d * 16777216
end

local function p16(v)
  v = v % 65536
  return string.char(v % 256, math.floor(v / 256))
end

local function p32(v)
  v = v % 4294967296
  return string.char(v % 256, math.floor(v / 256) % 256, math.floor(v / 65536) % 256, math.floor(v / 16777216) % 256)
end

M.u16, M.u32, M.p16, M.p32 = u16, u32, p16, p32

-- ---------------------------------------------------------------- checksum (sub_81DBF0): siempre sobre el payload en claro
function M.checksum(payload, length)
  length = length or #payload
  local v = 0xD31F
  local n = math.min(band(length, bnot(1)), #payload)
  for i = 0, n - 1, 2 do
    v = bxor(v, u16(payload, i + 1))
  end
  v = band(v, 0xFFFF)
  local s = band(v, 0xF)
  if s ~= 0 then
    v = band(bor(lshift(v, s), rshift(v, 16 - s)), 0xFFFF)
  end
  return bxor(band(v, 0xFF), band(rshift(v, 8), 0xFF))
end

-- ---------------------------------------------------------------- cabecera
function M.decode_header(raw, off)
  off = off or 1
  local l = bxor(u16(raw, off), M.HDR_XOR)
  local seq = bxor(u16(raw, off + 2), l)
  local flags = band(bxor(raw:byte(off + 4), band(l, 0xFF)), 0xFF)
  local enc = band(flags, M.FLAG_ENC) ~= 0
  local padded = enc and lshift(rshift(l + 0xF, 4), 4) or l
  return {
    length = l, seq = seq, flags = flags, checksum = raw:byte(off + 5),
    padded = padded, wire = M.HDR + padded,
    encrypted = enc, compressed = band(flags, M.FLAG_CMP) ~= 0,
  }
end

function M.encode_header(length, seq, flags, csum)
  return p16(bxor(length, M.HDR_XOR)) .. p16(bxor(seq, length))
      .. string.char(band(bxor(flags, band(length, 0xFF)), 0xFF)) .. string.char(band(csum, 0xFF))
end

-- ---------------------------------------------------------------- cifrados (handshake.py)
-- S -> C: XOR estatico con la clave de 16 bytes (con clave en cero es la identidad).
function M.xor_static(key)
  local self = {}
  function self:apply(d)
    local out = {}
    for i = 1, #d do
      out[i] = string.char(bxor(d:byte(i), key:byte((i - 1) % M.KEY_LEN + 1)))
    end
    return table.concat(out)
  end
  self.encrypt, self.decrypt = self.apply, self.apply
  return self
end

-- C -> S: XOR con clave evolutiva: tras cada paquete, cada DWORD de la clave += largo (con el relleno a 16 ya incluido).
function M.xor_evolving(key)
  local w = {}
  for i = 0, 3 do w[i] = u32(key, i * 4 + 1) end
  local self = {}
  function self:apply(d)
    local kb = {}
    for i = 0, M.KEY_LEN - 1 do
      kb[i] = math.floor(w[math.floor(i / 4)] / 256 ^ (i % 4)) % 256
    end
    local out = {}
    for i = 1, #d do
      out[i] = string.char(bxor(d:byte(i), kb[(i - 1) % M.KEY_LEN]))
    end
    for i = 0, 3 do w[i] = (w[i] + #d) % 4294967296 end
    return table.concat(out)
  end
  self.encrypt, self.decrypt = self.apply, self.apply
  return self
end

-- ---------------------------------------------------------------- tramas
-- Arma un frame completo. Sin `crypto` va en claro (flags = 0). El checksum se calcula ANTES de cifrar.
function M.build_frame(payload, seq, crypto)
  local n = #payload
  local ck = M.checksum(payload, n)
  if not crypto then
    return M.encode_header(n, seq, 0x00, ck) .. payload
  end
  local padded = lshift(rshift(n + 0xF, 4), 4)
  local body = crypto:encrypt(payload .. string.rep('\0', padded - n))
  return M.encode_header(n, seq, M.FLAG_ENC, ck) .. body
end

-- [LE16 largo][opcode+cuerpo] por cada mensaje ya serializado (opcode incluido).
function M.pack_submessages(msgs)
  local out = {}
  for i, m in ipairs(msgs) do out[i] = p16(#m) .. m end
  return table.concat(out)
end

-- [(opcode, cuerpo)] y bytes consumidos.
function M.submessages(payload)
  local out, i = {}, 1
  while i + 3 <= #payload do
    local sl = u16(payload, i)
    if sl < 2 or i + 1 + sl > #payload then break end
    out[#out + 1] = { opcode = u16(payload, i + 2), body = payload:sub(i + 4, i + 1 + sl) }
    i = i + 2 + sl
  end
  return out, i - 1
end

-- Lector de flujo: se le dan los bytes que llegan del socket y devuelve los frames completos.
-- `recv_crypto` (opcional) descifra el cuerpo de los frames con bit0; por defecto la clave en cero (identidad).
function M.new_reader()
  local self = { buf = '', recv_crypto = nil }
  function self:feed(data)
    self.buf = self.buf .. data
    local frames = {}
    while #self.buf >= M.HDR do
      local h = M.decode_header(self.buf, 1)
      if h.length == 0 or h.length > 0x10000 then
        self.buf = self.buf:sub(2)                -- cabecera imposible: se descarta un byte y se resincroniza
      elseif #self.buf < h.wire then
        break
      else
        local cuerpo = self.buf:sub(M.HDR + 1, h.wire)
        self.buf = self.buf:sub(h.wire + 1)
        if h.encrypted and self.recv_crypto then cuerpo = self.recv_crypto:decrypt(cuerpo) end
        h.payload = cuerpo:sub(1, h.length)
        h.checksum_ok = (M.checksum(h.payload, h.length) == h.checksum)
        frames[#frames + 1] = h
      end
    end
    return frames
  end
  return self
end

-- ---------------------------------------------------------------- Hello (frame con seq 0xFFFF, sin cifrar)
-- Lee las dos variantes: la minima (clave) y la del cifrador embebido (clave + codigo x86 + contexto).
-- El cliente nuevo NO ejecuta el codigo x86: solo toma la clave. Con clave en cero el S->C va en claro.
function M.parse_hello(payload)
  local sub_len = u16(payload, 1)
  local a2 = payload:sub(3, 2 + sub_len)
  local key_len = u32(a2, 1)
  local out = { sub_len = sub_len, key_len = key_len, key = a2:sub(5, 4 + key_len), variante = 'minima' }
  local off = 4 + key_len
  if #a2 > off + 4 then
    local code_len = u32(a2, off + 1)
    out.code_len = code_len
    off = off + 4 + code_len
    out.variante = 'cifrador embebido'
  end
  return out
end

return M
