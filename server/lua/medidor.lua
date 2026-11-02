-- El contador de dano en vivo (server/medidor_dano.py): la ventana 59010 de wnd03.xml, pequena y movible.
-- El servidor la abre con MedidorAbrir() y la llena con MedidorDatos(titulo, filas) cada vez que cambia.
local CMD_MEDIDOR = 168

local function hijo(id)
  return window.find(WND_MEDIDOR, id)
end

function MedidorAbrir()
  if window.isexist(WND_MEDIDOR) then
    window.setforeground(WND_MEDIDOR)
    return
  end
  WND_MEDIDOR = window.create(59010, 0, 0, SYSTEM_HANDLER)
  window.move(WND_MEDIDOR, SYSTEM_SCREEN_WIDTH - 250, 170)
  window.regsetting(WND_MEDIDOR, "WND_MEDIDOR")    -- recuerda donde la deja el jugador
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
  window.settitle(hijo(59011), titulo)
  local lista = hijo(59012)
  window.clearlist(lista)
  for i, f in ipairs(filas) do
    window.insertitemstr(lista, tostring(i) .. ". " .. f[1], 0)
    window.setsubitemstr(lista, i - 1, 1, f[2], 0)
    window.setsubitemstr(lista, i - 1, 2, tostring(f[3]) .. "%", 0)
  end
end
