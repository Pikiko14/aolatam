-- La ventana de la Torre de Babel (server/torre_babel.py): la 59020 de wnd03.xml. El servidor la abre con
-- TorreAbrir(modos, pisos) y le manda el ranking del modo elegido con TorreRanking(modo, filas).
local CMD_TORRE = 169
WND_TORRE = WND_TORRE or 0        -- un numero desde el principio: window.isexist(nil) da error
TORRE = TORRE or {modo = 0}
local T = TORRE

local function hijo(id)
  return window.find(WND_TORRE, id)
end

-- Recorta un texto a `n` letras con ".." al final: nada se sale de su columna o caja.
local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

local function estado(texto)
  window.settitle(hijo(59026), corto(texto, 40))
end

local function pintar()
  window.seticon(hijo(59022), T.modo == 0 and 59030 or 2734)   -- las del tema del cliente
  window.seticon(hijo(59023), T.modo == 1 and 59030 or 2734)
  if T.modo == 0 then
    estado("Solo: you alone against every boss.")
  else
    estado("Party: your whole party climbs.")
  end
end

-- en_curso: 0 nada; 1 dentro de la torre (el boton sale de ella); 2 fuera, con la subida de su party en marcha (el
-- boton se une). piso: el de la subida. modo: el de la subida (para unirse en el mismo).
function TorreAbrir(modos, pisos, en_curso, piso, modo)
  T.modos = modos
  T.en_curso = en_curso or 0
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
  window.settitle(hijo(59021), tostring(pisos) .. " floors, one boss per floor.")
  window.settitle(hijo(59022), modos[1])
  window.settitle(hijo(59023), modos[2])
  window.settitle(hijo(59027), "Enter")
  T.invitacion = nil
  if T.en_curso ~= 0 and modo then
    T.modo = modo
  end
  pintar()
  T.aviso_curso = nil
  if T.en_curso == 1 then
    window.settitle(hijo(59027), "Leave")
    T.aviso_curso = "Floor " .. tostring(piso) .. ". Leave: the others keep climbing."
  elseif T.en_curso == 2 then
    window.settitle(hijo(59027), "Join")
    T.aviso_curso = "Your party is on floor " .. tostring(piso) .. ". Press Join."
  end
  if T.aviso_curso then
    estado(T.aviso_curso)
  end
end

-- filas: {{nombres, pisos, tiempo}, ...}, de la mejor a la peor.
function TorreRanking(modo, filas)
  if not window.isexist(WND_TORRE) then
    return
  end
  T.modo = modo
  local invitacion = T.invitacion
  local lista = hijo(59024)
  window.clearlist(lista)
  window.insertitemstr(lista, "Best climbs", 0)
  -- setsubitemstr cuenta las columnas desde la segunda: la 0 es la que va tras el nombre (como OnTestMail de mail.lua).
  window.setsubitemstr(lista, 0, 0, "Floors", 0)
  window.setsubitemstr(lista, 0, 1, "Time", 0)
  for i, f in ipairs(filas) do
    window.insertitemstr(lista, corto(tostring(i) .. ". " .. f[1], 13), 0)
    window.setsubitemstr(lista, i, 0, tostring(f[2]), 0)
    window.setsubitemstr(lista, i, 1, f[3], 0)
  end
  pintar()
  if invitacion and modo == 1 then
    estado(corto(invitacion, 12) .. " invites you. Press the check.")
  elseif T.aviso_curso then
    estado(T.aviso_curso)                       -- el aviso de salir o de unirse que puso TorreAbrir
  elseif #filas == 0 then
    estado("No climbs yet. Be the first!")
  end
end

-- La solicitud del lider a los de su party: la misma ventana, en Party, con el aviso; el boton de entrar acepta.
function TorreInvitacion(lider, modos, pisos)
  TorreAbrir(modos, pisos)
  if not window.isexist(WND_TORRE) then
    return
  end
  T.modo = 1
  T.invitacion = lider
  pintar()
  estado(corto(lider, 12) .. " invites you. Press the check.")
  window.settitle(hijo(59027), "Join")
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
  if (T.en_curso or 0) == 1 then
    game.netcommand2(CMD_TORRE, 4, T.modo)      -- salir de la torre (solo este personaje)
  else
    game.netcommand2(CMD_TORRE, 3, T.modo)
  end
  return 1
end
