-- Sonido y musica con los recursos del cliente instalado: music/NN.ogg (music.pak y otros) y sound/*.wav|ogg.
-- Los archivos salen de los pak en memoria y se pasan a LÖVE como FileData: nada se escribe en disco.
local A = {}
A.__index = A

function A.nuevo(paks)
  return setmetatable({ paks = paks, cache = {}, musica_actual = nil, fuente_musica = nil, silencio = false, volumen_musica = 0.5, volumen_efectos = 0.8 }, A)
end

local function fuente(self, ruta, modo)
  local datos = self.paks:leer(ruta)
  if not datos then return nil end
  local ok, src = pcall(function()
    return love.audio.newSource(love.filesystem.newFileData(datos, ruta:match('[^/]+$')), modo)
  end)
  return ok and src or nil
end

-- Musica de fondo (se repite). Si ya suena esa pista no hace nada.
function A:musica(ruta)
  if not ruta or ruta == self.musica_actual then return end
  if self.fuente_musica then self.fuente_musica:stop() end
  self.musica_actual = ruta
  self.fuente_musica = fuente(self, ruta, 'stream')
  if self.fuente_musica then
    self.fuente_musica:setLooping(true)
    self.fuente_musica:setVolume(self.silencio and 0 or self.volumen_musica)
    self.fuente_musica:play()
  end
end

-- Efecto corto: nombre sin carpeta ni extension ('hit', 'magic029'...). Prueba .wav y .ogg. Devuelve true si sono.
function A:efecto(nombre)
  if self.silencio then return false end
  local base = self.cache[nombre]
  if base == nil then
    base = fuente(self, 'sound/' .. nombre .. '.wav', 'static') or fuente(self, 'sound/' .. nombre .. '.ogg', 'static') or false
    self.cache[nombre] = base
  end
  if not base then return false end
  local s = base:clone()
  s:setVolume(self.volumen_efectos)
  s:play()
  return true
end

function A:alternar_silencio()
  self.silencio = not self.silencio
  if self.fuente_musica then self.fuente_musica:setVolume(self.silencio and 0 or self.volumen_musica) end
  return self.silencio
end

function A:sonando()
  return self.fuente_musica ~= nil and self.fuente_musica:isPlaying()
end

return A
