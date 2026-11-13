-- La ventana de la Torre de Babel (server/torre_babel.py): la 59020 de wnd03.xml, que dibuja tools/ventana_torre.py
-- (13/11/2026, estilo moderno como las raids). El servidor la abre con TorreAbrir(modos, pisos) y le manda el ranking
-- del modo elegido con TorreRanking(modo, filas).
local CMD_TORRE = 169
WND_TORRE = WND_TORRE or 0        -- un numero desde el principio: window.isexist(nil) da error
TORRE = TORRE or {modo = 0}
local T = TORRE

-- Los ids de tools/ventana_torre.py
local PISOS, SOLO, PARTY, CABECERA, ENTRAR, ESTADO, VACIO, MODO = 59021, 59022, 59023, 59024, 59025, 59026, 59027, 59028
local PUESTO, NOMBRES, NPISOS, TIEMPO, CLIC = 61010, 61020, 61030, 61040, 61050
local I_SOLO, I_SOLO_ON, I_PARTY, I_PARTY_ON = 61062, 61063, 61064, 61065
local I_BOTON = {enter = 61066, join = 61067, leave = 61068}
local AYUDA = {enter = "Enter the Tower of Babel", join = "Join your party's climb", leave = "Leave the tower"}
local W, H = 348, 370             -- la ventana entera, con el marco

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
  window.settitle(hijo(ESTADO), corto(texto, 38))
end

-- El boton grande: "enter", "join" o "leave" (el texto va dibujado en su icono).
local function boton(cual)
  T.boton = cual
  local b = hijo(ENTRAR)
  window.seticon(b, I_BOTON[cual])
  window.settooltiptext(b, AYUDA[cual])
end

local function pintar()
  window.seticon(hijo(SOLO), T.modo == 0 and I_SOLO_ON or I_SOLO)
  window.seticon(hijo(PARTY), T.modo == 1 and I_PARTY_ON or I_PARTY)
  local nombre = (T.modos and T.modos[T.modo + 1]) or (T.modo == 0 and "Solo" or "Party")
  window.settitle(hijo(CABECERA), "Best climbs - " .. nombre)
  if T.modo == 0 then
    window.settitle(hijo(MODO), "Solo: you alone against every boss.")
  else
    window.settitle(hijo(MODO), "Party: the leader starts, the party climbs.")
  end
  estado("")
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
    window.move(WND_TORRE, SYSTEM_SCREEN_WIDTH / 2 - W / 2, SYSTEM_SCREEN_HEIGHT / 2 - H / 2)
  end
  window.settitle(WND_TORRE, "Tower of Babel")
  window.settitle(hijo(PISOS), tostring(pisos) .. " floors, one boss per floor.")
  T.invitacion = nil
  if T.en_curso ~= 0 and modo then
    T.modo = modo
  end
  pintar()
  T.aviso_curso = nil
  if T.en_curso == 1 then
    boton("leave")
    T.aviso_curso = "Floor " .. tostring(piso) .. ". The others keep climbing."
  elseif T.en_curso == 2 then
    boton("join")
    T.aviso_curso = "Your party is on floor " .. tostring(piso) .. "."
  else
    boton("enter")
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
  pintar()
  window.show(hijo(VACIO), not (filas and filas[1]))
  for i = 0, 9 do
    local f = filas and filas[i + 1]
    window.settitle(hijo(PUESTO + i), f and tostring(i + 1) or "")
    window.settitle(hijo(NOMBRES + i), f and corto(f[1], 30) or "")
    window.settitle(hijo(NPISOS + i), f and tostring(f[2]) or "")
    window.settitle(hijo(TIEMPO + i), f and f[3] or "")
    local clic = hijo(CLIC + i)
    window.show(clic, f ~= nil)
    if f then
      window.settooltiptext(clic, tostring(f[1]) .. ": " .. tostring(f[2]) .. " floors in " .. tostring(f[3]))
    end
  end
  if invitacion and modo == 1 then
    estado(corto(invitacion, 12) .. " invites you. Press Join.")
  elseif T.aviso_curso then
    estado(T.aviso_curso)                       -- el aviso de salir o de unirse que puso TorreAbrir
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
  estado(corto(lider, 12) .. " invites you. Press Join.")
  boton("join")
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
