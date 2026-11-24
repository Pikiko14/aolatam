-- La ventana del Angel MOBA (server/moba_lobby.py): 58300, de wnd03.xml (tools/ventana_moba.py). El servidor llama a
-- MBAbrir, MBClase, MBEstado y MBAviso; los botones contestan con game.netcommand2(175, accion, valor).
local CMD_MB = 175
WND_MB = WND_MB or 0
MB = MB or {}
local Q = MB

-- Los ids de tools/ventana_moba.py
local L_ESTADO, L_TITULO, L_NUMEROS, L_PODER, L_AVISO, L_ELEGIDA = 58301, 58302, 58303, 58304, 58308, 58309
local MW, MH = 478, 410

local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

local function en(id)
  return window.find(WND_MB, id)
end

-- clases: {{nombre, papel}, ...}; estado: la linea de la inscripcion.
function MBAbrir(clases, estado)
  Q.clases = clases
  if window.isexist(WND_MB) then
    window.setforeground(WND_MB)
  else
    WND_MB = window.create(58300, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_MB) then
      return
    end
    window.move(WND_MB, SYSTEM_SCREEN_WIDTH / 2 - MW / 2, SYSTEM_SCREEN_HEIGHT / 2 - MH / 2)
  end
  window.settitle(WND_MB, "Angel MOBA")
  window.settitle(en(L_ESTADO), corto(estado, 80))
  window.settitle(en(L_AVISO), "")
  window.settitle(en(L_TITULO), "Choose the class you will play")
  window.settitle(en(L_NUMEROS), "Click a class to see its skills, then Join.")
  window.settitle(en(L_ELEGIDA), "")
  for k = 0, 3 do
    window.settitle(en(L_PODER + k), "")
  end
end

-- i: 1..9; titulo, numeros y los 4 poderes de la clase elegida.
function MBClase(i, titulo, numeros, poderes)
  if not window.isexist(WND_MB) then
    return
  end
  window.settitle(en(L_TITULO), corto(titulo, 70))
  window.settitle(en(L_NUMEROS), corto(numeros, 80))
  for k = 0, 3 do
    window.settitle(en(L_PODER + k), corto(poderes[k + 1], 82))
  end
  local c = Q.clases and Q.clases[i]
  window.settitle(en(L_ELEGIDA), c and corto("Selected: " .. tostring(c[1]), 34) or "")
end

function MBEstado(texto)
  if window.isexist(WND_MB) then
    window.settitle(en(L_ESTADO), corto(texto, 80))
  end
end

function MBAviso(texto)
  if window.isexist(WND_MB) then
    window.settitle(en(L_AVISO), corto(texto, 34))
  end
end

function MBCerrar()
  if window.isexist(WND_MB) then
    window.destroy(WND_MB)
  end
  WND_MB = 0
end

local function clase(i)
  game.netcommand2(CMD_MB, 2, i - 1)
  return 1
end

function OnMBClase1(dwID, dwCmdID, dwParam, pParam) return clase(1) end
function OnMBClase2(dwID, dwCmdID, dwParam, pParam) return clase(2) end
function OnMBClase3(dwID, dwCmdID, dwParam, pParam) return clase(3) end
function OnMBClase4(dwID, dwCmdID, dwParam, pParam) return clase(4) end
function OnMBClase5(dwID, dwCmdID, dwParam, pParam) return clase(5) end
function OnMBClase6(dwID, dwCmdID, dwParam, pParam) return clase(6) end
function OnMBClase7(dwID, dwCmdID, dwParam, pParam) return clase(7) end
function OnMBClase8(dwID, dwCmdID, dwParam, pParam) return clase(8) end
function OnMBClase9(dwID, dwCmdID, dwParam, pParam) return clase(9) end

function OnMBUnirse(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_MB, 3, 0)
  return 1
end

function OnMBDejar(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_MB, 4, 0)
  return 1
end

-- ------------------------------------------------------------------------------------------------- en la partida
-- 58350 el marcador (dos lineas) y 58360 el final (cartel, 12 lineas y Close): server/moba_marcador.py.
WND_MB_HUD = WND_MB_HUD or 0
WND_MB_FIN = WND_MB_FIN or 0
local H_ARRIBA, H_ABAJO = 58351, 58352
local F_CARTEL, F_LINEA = 58361, 58362
local I_VICTORIA, I_DERROTA = 58432, 58433
local HW, FW, FH = 508, 348, 304

function MBHud(arriba, abajo)
  if not window.isexist(WND_MB_HUD) then
    WND_MB_HUD = window.create(58350, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_MB_HUD) then
      return
    end
    window.move(WND_MB_HUD, SYSTEM_SCREEN_WIDTH / 2 - HW / 2, 36)
  end
  window.settitle(window.find(WND_MB_HUD, H_ARRIBA), corto(arriba, 70))
  window.settitle(window.find(WND_MB_HUD, H_ABAJO), corto(abajo, 70))
end

-- El boton Shop del marcador (58354): la tienda, solo en la partida (ya no hay icono en la barra, 24/11/2026).
function OnMBHudTienda(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_MB, 1, 0)
  return 1
end

function MBHudCerrar()
  if window.isexist(WND_MB_HUD) then
    window.destroy(WND_MB_HUD)
  end
  WND_MB_HUD = 0
end

function MBFin(victoria, lineas)
  MBHudCerrar()
  if not window.isexist(WND_MB_FIN) then
    WND_MB_FIN = window.create(58360, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_MB_FIN) then
      return
    end
    window.move(WND_MB_FIN, SYSTEM_SCREEN_WIDTH / 2 - FW / 2, SYSTEM_SCREEN_HEIGHT / 2 - FH / 2)
  end
  window.seticon(window.find(WND_MB_FIN, F_CARTEL), victoria and I_VICTORIA or I_DERROTA)
  for k = 0, 11 do
    window.settitle(window.find(WND_MB_FIN, F_LINEA + k), lineas and lineas[k + 1] or "")
  end
end

function OnMBFinCerrar(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_MB_FIN) then
    window.destroy(WND_MB_FIN)
  end
  WND_MB_FIN = 0
  return 1
end

-- ------------------------------------------------------------------------------------------------- el ranking
-- 58380 (server/moba_lobby.ranking): filas = {{puesto, nombre, rango, puntos, record}, ...} (hasta 10).
WND_MB_RANKING = WND_MB_RANKING or 0
local R_TITULO, R_MARCA, R_RANGOS, R_PREMIOS, R_VACIO = 58381, 58382, 58383, 58384, 58385
local R_COLUMNAS = {58450, 58460, 58470, 58480, 58490}
local RW, RH = 428, 316

function MBRanking(titulo, filas, marca, rangos, premios)
  if not window.isexist(WND_MB_RANKING) then
    WND_MB_RANKING = window.create(58380, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_MB_RANKING) then
      return
    end
    window.move(WND_MB_RANKING, SYSTEM_SCREEN_WIDTH / 2 - RW / 2, SYSTEM_SCREEN_HEIGHT / 2 - RH / 2)
  else
    window.setforeground(WND_MB_RANKING)
  end
  local w = WND_MB_RANKING
  window.settitle(window.find(w, R_TITULO), corto(titulo, 60))
  window.settitle(window.find(w, R_MARCA), corto(marca, 70))
  window.settitle(window.find(w, R_RANGOS), corto(rangos, 70))
  window.settitle(window.find(w, R_PREMIOS), corto(premios, 70))
  window.show(window.find(w, R_VACIO), filas == nil or filas[1] == nil)
  for i = 1, 10 do
    local f = filas and filas[i]
    for c = 1, 5 do
      window.settitle(window.find(w, R_COLUMNAS[c] + i - 1), f and corto(f[c], c == 2 and 18 or 16) or "")
    end
  end
end

function OnMBRanking(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_MB, 5, 0)
  return 1
end

-- ------------------------------------------------------------------------------------------------- puntos de poder
-- 58520 (server/moba_heroe.ventana_puntos): filas = {{nombre, detalle, se_puede, "Learn"|"Upgrade", icono}, ...} (4);
-- icono = el del poder en el juego (tools/ventana_moba.py, 58600..).
WND_MB_PUNTOS = WND_MB_PUNTOS or 0
local P_TITULO, P_ESTADO, P_NOMBRE, P_DETALLE, P_BOTON, P_ICONO = 58521, 58522, 58523, 58527, 58531, 58540
local PW, PH = 388, 250

function MBPuntos(titulo, filas)
  if not window.isexist(WND_MB_PUNTOS) then
    WND_MB_PUNTOS = window.create(58520, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_MB_PUNTOS) then
      return
    end
    window.move(WND_MB_PUNTOS, SYSTEM_SCREEN_WIDTH - PW - 20, SYSTEM_SCREEN_HEIGHT / 2 - PH / 2)
  end
  local w = WND_MB_PUNTOS
  window.settitle(window.find(w, P_TITULO), corto(titulo, 56))
  window.settitle(window.find(w, P_ESTADO), "")
  for k = 0, 3 do
    local f = filas and filas[k + 1]
    window.settitle(window.find(w, P_NOMBRE + k), f and corto(f[1], 40) or "")
    window.settitle(window.find(w, P_DETALLE + k), f and corto(f[2], 40) or "")
    window.show(window.find(w, P_BOTON + k), f ~= nil and f[3] == true)
    window.show(window.find(w, P_ICONO + k), f ~= nil)
    if f and f[5] then
      window.seticon(window.find(w, P_ICONO + k), f[5])
      window.settooltiptext(window.find(w, P_ICONO + k), tostring(f[1]))
    end
  end
end

function MBPuntosAviso(texto)
  if window.isexist(WND_MB_PUNTOS) then
    window.settitle(window.find(WND_MB_PUNTOS, P_ESTADO), corto(texto, 56))
  end
end

function MBPuntosCerrar()
  if window.isexist(WND_MB_PUNTOS) then
    window.destroy(WND_MB_PUNTOS)
  end
  WND_MB_PUNTOS = 0
end

local function punto(k)
  game.netcommand2(CMD_MB, 6, k - 1)
  return 1
end

function OnMBPunto1(dwID, dwCmdID, dwParam, pParam) return punto(1) end
function OnMBPunto2(dwID, dwCmdID, dwParam, pParam) return punto(2) end
function OnMBPunto3(dwID, dwCmdID, dwParam, pParam) return punto(3) end
function OnMBPunto4(dwID, dwCmdID, dwParam, pParam) return punto(4) end

-- ------------------------------------------------------------------------------------------------- la tienda
-- 58560 (server/moba_tienda.ventana): filas = {{nombre, precio, texto, item_id}, ...} (12); propios = {item_id, ...}.
-- Los iconos son los de los objetos del juego (game.getitemicon, como el Item Mall nuevo).
WND_MB_TIENDA = WND_MB_TIENDA or 0
local T_TITULO, T_ESTADO, T_ITEM, T_NOMBRE, T_PRECIO, T_TEXTO, T_PROPIO = 58561, 58562, 58700, 58712, 58724, 58736, 58748
local TW, TH = 400, 432

function MBTienda(titulo, estado, filas, propios)
  if not window.isexist(WND_MB_TIENDA) then
    WND_MB_TIENDA = window.create(58560, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_MB_TIENDA) then
      return
    end
    window.move(WND_MB_TIENDA, 20, SYSTEM_SCREEN_HEIGHT / 2 - TH / 2)
  else
    window.setforeground(WND_MB_TIENDA)
  end
  local w = WND_MB_TIENDA
  window.settitle(window.find(w, T_TITULO), corto(titulo, 56))
  window.settitle(window.find(w, T_ESTADO), corto(estado, 56))
  for i = 0, 11 do
    local f = filas and filas[i + 1]
    window.show(window.find(w, T_ITEM + i), f ~= nil)
    if f then
      window.seticon(window.find(w, T_ITEM + i), game.getitemicon(f[4]))
      window.settooltiptext(window.find(w, T_ITEM + i), tostring(f[1]) .. ": " .. tostring(f[3]) .. " - " .. tostring(f[2]) .. " gold")
    end
    window.settitle(window.find(w, T_NOMBRE + i), f and corto(f[1], 16) or "")
    window.settitle(window.find(w, T_TEXTO + i), f and corto(f[3], 16) or "")
    window.settitle(window.find(w, T_PRECIO + i), f and (tostring(f[2]) .. " gold") or "")
  end
  for k = 0, 5 do
    local id = propios and propios[k + 1]
    window.seticon(window.find(w, T_PROPIO + k), id and game.getitemicon(id) or 0)
  end
end

-- < y > (58563 / 58564): la pagina anterior / siguiente (moba_tienda.pasar).
function OnMBTiendaAnt(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_MB, 8, 0) return 1 end
function OnMBTiendaSig(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_MB, 8, 1) return 1 end
-- Las pestanas (58565..58568): Weapons, Armor, Special, Potions (moba_tienda.elegir_categoria).
function OnMBTiendaCat1(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_MB, 9, 0) return 1 end
function OnMBTiendaCat2(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_MB, 9, 1) return 1 end
function OnMBTiendaCat3(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_MB, 9, 2) return 1 end
function OnMBTiendaCat4(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_MB, 9, 3) return 1 end

function MBTiendaOro(titulo)
  if window.isexist(WND_MB_TIENDA) then
    window.settitle(window.find(WND_MB_TIENDA, T_TITULO), corto(titulo, 56))
  end
end

function MBTiendaAviso(texto)
  if window.isexist(WND_MB_TIENDA) then
    window.settitle(window.find(WND_MB_TIENDA, T_ESTADO), corto(texto, 56))
  end
end

function MBTiendaCerrar()
  if window.isexist(WND_MB_TIENDA) then
    window.destroy(WND_MB_TIENDA)
  end
  WND_MB_TIENDA = 0
end

local function comprar(i)
  game.netcommand2(CMD_MB, 7, i - 1)
  return 1
end

function OnMBComprar1(dwID, dwCmdID, dwParam, pParam) return comprar(1) end
function OnMBComprar2(dwID, dwCmdID, dwParam, pParam) return comprar(2) end
function OnMBComprar3(dwID, dwCmdID, dwParam, pParam) return comprar(3) end
function OnMBComprar4(dwID, dwCmdID, dwParam, pParam) return comprar(4) end
function OnMBComprar5(dwID, dwCmdID, dwParam, pParam) return comprar(5) end
function OnMBComprar6(dwID, dwCmdID, dwParam, pParam) return comprar(6) end
function OnMBComprar7(dwID, dwCmdID, dwParam, pParam) return comprar(7) end
function OnMBComprar8(dwID, dwCmdID, dwParam, pParam) return comprar(8) end
function OnMBComprar9(dwID, dwCmdID, dwParam, pParam) return comprar(9) end
function OnMBComprar10(dwID, dwCmdID, dwParam, pParam) return comprar(10) end
function OnMBComprar11(dwID, dwCmdID, dwParam, pParam) return comprar(11) end
function OnMBComprar12(dwID, dwCmdID, dwParam, pParam) return comprar(12) end
