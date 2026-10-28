-- Escalado de toda la imagen (mundo e interfaz), como hace Windows con el cliente original en pantallas con ampliacion: se dibuja en un
-- lienzo de tamano "virtual" (alto ~700) y se estira a la ventana. love.graphics.getDimensions y la posicion del raton devuelven medidas
-- virtuales, asi que el resto del cliente no se entera.
local E = { k = 1, alto_virtual = tonumber(os.getenv('AO_ALTO_VIRTUAL') or '') or 700, lienzo = nil }

local real_dims = love.graphics.getDimensions
local real_pos = love.mouse.getPosition

local function calcular()
  local w, h = real_dims()
  local k = math.max(1, math.min(3, h / E.alto_virtual))
  E.k = math.floor(k * 20 + 0.5) / 20           -- pasos de 0.05: evita tamanos fraccionarios raros
  return w, h
end

function E.aplicar()
  love.graphics.getDimensions = function()
    local w, h = real_dims()
    return math.floor(w / E.k), math.floor(h / E.k)
  end
  love.graphics.getWidth = function() return (love.graphics.getDimensions()) end
  love.graphics.getHeight = function() return select(2, love.graphics.getDimensions()) end
  love.mouse.getPosition = function() local x, y = real_pos(); return x / E.k, y / E.k end

  -- los chunks del terreno restauran el lienzo con setCanvas(previo): sin stencil=true el retrato (stencil) fallaria
  local set_real = love.graphics.setCanvas
  love.graphics.setCanvas = function(c, ...)
    if c ~= nil and c == E.lienzo and select('#', ...) == 0 then return set_real({ c, stencil = true }) end
    return set_real(c, ...)
  end

  local dibujar = love.draw
  love.draw = function()
    local w, h = calcular()
    local vw, vh = math.floor(w / E.k), math.floor(h / E.k)
    if not E.lienzo or E.lienzo:getWidth() ~= vw or E.lienzo:getHeight() ~= vh then
      E.lienzo = love.graphics.newCanvas(vw, vh)
      E.lienzo:setFilter('linear', 'linear')
    end
    love.graphics.setCanvas({ E.lienzo, stencil = true })
    love.graphics.clear(0, 0, 0, 1)
    dibujar()
    love.graphics.setCanvas()
    love.graphics.setColor(1, 1, 1)
    love.graphics.draw(E.lienzo, 0, 0, 0, w / vw, h / vh)
  end

  for _, nombre in ipairs({ 'mousepressed', 'mousereleased', 'mousemoved', 'wheelmoved' }) do
    local f = love[nombre]
    if f and nombre ~= 'wheelmoved' then
      love[nombre] = function(x, y, ...)
        if nombre == 'mousemoved' then local dx, dy = ...; return f(x / E.k, y / E.k, (dx or 0) / E.k, (dy or 0) / E.k) end
        return f(x / E.k, y / E.k, ...)
      end
    end
  end
  calcular()
end

return E
