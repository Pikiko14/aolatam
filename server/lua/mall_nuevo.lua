-- El Item Mall nuevo (14/11/2026): la ventana 61000 (tools/parche_mall_nuevo.py) con el diseno del usuario. Lo que se
-- ve lo decide el servidor (server/mall_nuevo.py) y llega en MallPintar(d); cada clic va con game.netcommand2(173, a, b).
WND_MALL = WND_MALL or 0
MALL = MALL or {}
local M = MALL
local CMD = 173
local VENTANA = 61000
local CERRAR_X, AG, ORO = 61001, 61002, 61003
local TAB, SUB = 61010, 61020
local PAG_TXT = 61031
local C_NOMBRE, C_ICONO, C_PRECIO, C_COMPRAR = 61040, 61050, 61060, 61070
local CAB, MOCH = 61080, 61100
local ESPACIO, MENSAJE, REGALO_NOMBRE = 61140, 61150, 61151
local INTRO, PAG_ANT, PAG_SIG = 61156, 61030, 61032
local I_TAB, I_SUB = 61510, 61540
local N_TABS, N_SUBS, N_CARTAS, N_CAB, N_MOCH = 10, 10, 6, 10, 35

local function hijo(id)
  return window.find(WND_MALL, id)
end

local function abierta()
  return WND_MALL ~= 0 and window.isexist(WND_MALL)
end

local function cmd(a, b)
  game.netcommand2(CMD, a, b or 0)
  return 1
end

function MallAbrir()
  if abierta() then
    window.setforeground(WND_MALL)
    return
  end
  WND_MALL = window.create(VENTANA, 0, 0, SYSTEM_HANDLER)
  if not window.isexist(WND_MALL) then
    return
  end
  window.move(WND_MALL, SYSTEM_SCREEN_WIDTH / 2 - 380, SYSTEM_SCREEN_HEIGHT / 2 - 304)
end

local function casilla(id, f)
  if f then
    window.seticon(hijo(id), game.getitemicon(f[1]))
    window.settitle(hijo(id), f[2] > 1 and tostring(f[2]) or "")
  else
    window.seticon(hijo(id), 0)
    window.settitle(hijo(id), "")
  end
end

-- d: ag, oro, tab (-1 = Historial), subs (indices de categoria), sub, pag ("1/3"), cartas {{item, nombre, precio,
-- elegida}}, cab {{item, cantidad}}, moch {{item, cantidad}}, espacio, msg, regalo, intro (texto o "")
function MallPintar(d)
  if not abierta() then
    return
  end
  M.d = d
  window.settitle(hijo(AG), d.ag)
  window.settitle(hijo(ORO), d.oro)
  for i = 0, N_TABS - 1 do
    window.seticon(hijo(TAB + i), I_TAB + 2 * i + (i == d.tab and 1 or 0))
  end
  for k = 0, N_SUBS - 1 do
    local s = d.subs[k + 1]
    local w = hijo(SUB + k)
    window.show(w, s ~= nil)
    if s then
      window.seticon(w, I_SUB + 2 * s + (k == d.sub and 1 or 0))
    end
  end
  -- Intro: el texto en lugar de las tarjetas.
  local intro = d.intro ~= ""
  window.show(hijo(INTRO), intro)
  window.settitle(hijo(INTRO), d.intro)
  window.show(hijo(PAG_ANT), not intro)
  window.show(hijo(PAG_SIG), not intro)
  window.settitle(hijo(PAG_TXT), intro and "" or d.pag)
  for c = 0, N_CARTAS - 1 do
    local f = d.cartas[c + 1]
    window.show(hijo(C_ICONO + c), f ~= nil)
    window.show(hijo(C_COMPRAR + c), f ~= nil)
    if f then
      window.seticon(hijo(C_ICONO + c), game.getitemicon(f[1]))
      window.settitle(hijo(C_NOMBRE + c), f[4] == 1 and ("* " .. f[2] .. " *") or f[2])
      window.settitle(hijo(C_PRECIO + c), f[3])
    else
      window.settitle(hijo(C_NOMBRE + c), "")
      window.settitle(hijo(C_PRECIO + c), "")
    end
  end
  for k = 0, N_CAB - 1 do
    casilla(CAB + k, d.cab[k + 1])
  end
  for k = 0, N_MOCH - 1 do
    casilla(MOCH + k, d.moch[k + 1])
  end
  window.settitle(hijo(ESPACIO), d.espacio)
  window.settitle(hijo(MENSAJE), d.msg)
  window.show(hijo(REGALO_NOMBRE), d.regalo)
  if d.regalo then
    window.setfocus(hijo(REGALO_NOMBRE))
  end
end

function OnMallTab(dwID, dwCmdID, dwParam, pParam)
  return cmd(2, window.getappdata(dwID))
end

function OnMallSub(dwID, dwCmdID, dwParam, pParam)
  return cmd(3, window.getappdata(dwID))
end

function OnMallPag(dwID, dwCmdID, dwParam, pParam)
  return cmd(4, window.getappdata(dwID))
end

function OnMallCarta(dwID, dwCmdID, dwParam, pParam)
  return cmd(5, window.getappdata(dwID))
end

function OnMallComprar(dwID, dwCmdID, dwParam, pParam)
  return cmd(6, window.getappdata(dwID))
end

function OnMallCab(dwID, dwCmdID, dwParam, pParam)
  return cmd(7, window.getappdata(dwID) - 100)
end

-- El nombre va en cuatro trozos de cuatro letras (netcommand2 solo lleva numeros), como el de la raid.
function OnMallRegalar(dwID, dwCmdID, dwParam, pParam)
  local caja = hijo(REGALO_NOMBRE)
  local nombre = ""
  if M.d and M.d.regalo then
    nombre = window.gettitle(caja) or ""
  end
  if nombre == "" then
    return cmd(9)
  end
  for t = 0, 3 do
    local v = 0
    for k = 4, 1, -1 do
      v = v * 256 + (string.byte(nombre, t * 4 + k) or 0)
    end
    game.netcommand2(CMD, 20 + t, v)
  end
  window.settitle(caja, "")
  return cmd(8)
end

function OnMallHistorial(dwID, dwCmdID, dwParam, pParam)
  return cmd(10)
end

function OnMallOrdenar(dwID, dwCmdID, dwParam, pParam)
  return cmd(11)
end

function OnMallFavorito(dwID, dwCmdID, dwParam, pParam)
  return cmd(12)
end

function OnMallCerrar(dwID, dwCmdID, dwParam, pParam)
  if abierta() then
    window.destroy(WND_MALL)
  end
  WND_MALL = 0
  return 1
end

-- La ficha del objeto al pasar el raton: tarjetas (appdata 0..5), Mi Compra (100..109) y Mis Objetos (200..234).
function OnMallTip(dwID, dwCmdID, dwParam, pParam)
  local d = M.d
  if not d then
    return 1
  end
  local a = window.getappdata(dwID)
  local f
  if a >= 200 then
    f = d.moch[a - 199]
  elseif a >= 100 then
    f = d.cab[a - 99]
  else
    f = d.cartas[a + 1]
  end
  if f then
    game.setitemtooltip(dwID, f[1])
  end
  return 1
end
