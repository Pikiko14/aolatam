-- El contador de dano en vivo (server/medidor_dano.py): la ventana 59010 de wnd03.xml, pequena y movible.
-- El servidor la abre con MedidorAbrir() y la llena con MedidorDatos(titulo, filas) cada vez que cambia.
local CMD_MEDIDOR = 168
-- Tiene que ser un numero desde el principio: window.isexist(nil) da error y cortaba MedidorAbrir sin crear la
-- ventana (la subasta no lo sufre porque WND_ADTRADE ya lo define adtrade.lua del juego).
WND_MEDIDOR = WND_MEDIDOR or 0

local function hijo(id)
  return window.find(WND_MEDIDOR, id)
end

-- Recorta un texto a `n` letras con ".." al final: nada se sale de su columna o caja.
local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

function MedidorAbrir()
  if window.isexist(WND_MEDIDOR) then
    window.setforeground(WND_MEDIDOR)
    return
  end
  WND_MEDIDOR = window.create(59010, 0, 0, SYSTEM_HANDLER)
  -- Al servidor, para su log: 8 = creada, 9 = no se pudo (sin la ventana 59010 en el wnd03.xml del cliente).
  game.netcommand2(CMD_MEDIDOR, window.isexist(WND_MEDIDOR) and 8 or 9, WND_MEDIDOR or 0)
  if not window.isexist(WND_MEDIDOR) then
    return
  end
  window.move(WND_MEDIDOR, SYSTEM_SCREEN_WIDTH - 250, 170)
  window.regsetting(WND_MEDIDOR, "WND_MEDIDOR")    -- recuerda donde la deja el jugador
  -- El dialogo no trae relleno (en la subasta lo pone la imagen de la pestana) y se veia el mapa detras: fondo
  -- azul oscuro casi opaco, como el que el juego pone con setbgcolor a su ventana de estadisticas de eventos. El
  -- orden es azul, verde, rojo, alfa: el exe (0x687220) lo junta como b | g << 8 | r << 16 | a << 24 (ARGB).
  window.setbgcolor(WND_MEDIDOR, 52, 36, 12, 230)
  window.settitle(WND_MEDIDOR, "Damage")
  window.settitle(hijo(59011), "Hit something to start.")
end

function MedidorCerrar()
  if window.isexist(WND_MEDIDOR) then
    window.destroy(WND_MEDIDOR)
  end
  WND_MEDIDOR = 0
end

-- filas: {{nombre, dano, porcentaje}, ...}, de mas a menos.
function MedidorDatos(titulo, filas)
  if not window.isexist(WND_MEDIDOR) then
    game.netcommand2(CMD_MEDIDOR, 0, 0)            -- la cerraron con la X: que el servidor deje de mandar
    return
  end
  window.settitle(hijo(59011), corto(titulo, 30))
  local lista = hijo(59012)
  window.clearlist(lista)
  -- La primera fila es la cabecera.
  window.insertitemstr(lista, "Name", 0)
  -- setsubitemstr cuenta las columnas desde la segunda: la 0 es la que va tras el nombre (como OnTestMail de mail.lua).
  window.setsubitemstr(lista, 0, 0, "Damage", 0)
  window.setsubitemstr(lista, 0, 1, "%", 0)
  for i, f in ipairs(filas) do
    window.insertitemstr(lista, corto(tostring(i) .. ". " .. f[1], 10), 0)
    window.setsubitemstr(lista, i, 0, f[2], 0)
    window.setsubitemstr(lista, i, 1, tostring(f[3]) .. "%", 0)
  end
end
