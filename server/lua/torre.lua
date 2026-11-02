-- La ventana de la Torre de Babel (server/torre_babel.py): la 59020 de wnd03.xml. El servidor la abre con
-- TorreAbrir(modos, pisos) y le manda el ranking del modo elegido con TorreRanking(modo, filas).
local CMD_TORRE = 169
WND_TORRE = WND_TORRE or 0        -- un numero desde el principio: window.isexist(nil) da error
TORRE = TORRE or {modo = 0}
local T = TORRE

local function hijo(id)
  return window.find(WND_TORRE, id)
end

local function estado(texto)
  window.settitle(hijo(59026), texto)
end

local function pintar()
  window.seticon(hijo(59022), T.modo == 0 and 3085 or 3084)
  window.seticon(hijo(59023), T.modo == 1 and 3085 or 3084)
  if T.modo == 0 then
    estado("Solo: you alone against every boss.")
  else
    estado("Party: everyone in your party climbs together.")
  end
end

function TorreAbrir(modos, pisos)
  T.modos = modos
  if window.isexist(WND_TORRE) then
    window.setforeground(WND_TORRE)
  else
    WND_TORRE = window.create(59020, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_TORRE) then
      return
    end
    window.move(WND_TORRE, SYSTEM_SCREEN_WIDTH / 2 - 150, SYSTEM_SCREEN_HEIGHT / 2 - 135)
    window.setbgcolor(WND_TORRE, 52, 36, 12, 230)      -- azul oscuro casi opaco (azul, verde, rojo, alfa)
  end
  window.settitle(WND_TORRE, "Tower of Babel")
  window.settitle(hijo(59021), tostring(pisos) .. " floors, one boss each. Every try starts at floor 1.")
  window.settitle(hijo(59022), modos[1])
  window.settitle(hijo(59023), modos[2])
  window.settitle(hijo(59027), "Enter the tower")
  pintar()
end

-- filas: {{nombres, pisos, tiempo}, ...}, de la mejor a la peor.
function TorreRanking(modo, filas)
  if not window.isexist(WND_TORRE) then
    return
  end
  T.modo = modo
  local lista = hijo(59024)
  window.clearlist(lista)
  window.insertitemstr(lista, "Best climbs", 0)
  window.setsubitemstr(lista, 0, 1, "Floors", 0)
  window.setsubitemstr(lista, 0, 2, "Time", 0)
  for i, f in ipairs(filas) do
    window.insertitemstr(lista, tostring(i) .. ". " .. f[1], 0)
    window.setsubitemstr(lista, i, 1, tostring(f[2]), 0)
    window.setsubitemstr(lista, i, 2, f[3], 0)
  end
  pintar()
  if #filas == 0 then
    estado("Nobody has climbed yet in this mode. Be the first!")
  end
end

function TorreAviso(texto)
  if window.isexist(WND_TORRE) then
    estado(texto)
  end
end

function TorreCerrar()
  if window.isexist(WND_TORRE) then
    window.destroy(WND_TORRE)
  end
  WND_TORRE = 0
end

function OnTorreSolo(dwID, dwCmdID, dwParam, pParam)
  T.modo = 0
  pintar()
  game.netcommand2(CMD_TORRE, 2, 0)
  return 1
end

function OnTorreParty(dwID, dwCmdID, dwParam, pParam)
  T.modo = 1
  pintar()
  game.netcommand2(CMD_TORRE, 2, 1)
  return 1
end

function OnTorreEntrar(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_TORRE, 3, T.modo)
  return 1
end
