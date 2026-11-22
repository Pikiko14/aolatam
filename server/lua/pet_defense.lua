-- Las ventanas de Pet Defense (server/pet_defense_ui.py): 59280 menu, 59350 elegir mascota, 59380 ficha de torre,
-- 59330 barra de la partida y 59340 fin, de wnd03.xml (tools/ventana_pet_defense.py). El servidor llama a PDAbrir,
-- PDElegir, PDTorre, PDHud, PDFin y sus avisos; los botones contestan con game.netcommand2(174, accion, valor).
local CMD_PD = 174
WND_PD_MENU = WND_PD_MENU or 0      -- numeros desde el principio: window.isexist(nil) da error
WND_PD_ELEGIR = WND_PD_ELEGIR or 0
WND_PD_TORRE = WND_PD_TORRE or 0
WND_PD_HUD = WND_PD_HUD or 0
WND_PD_FIN = WND_PD_FIN or 0
PD = PD or {}
local P = PD

-- Los ids de tools/ventana_pet_defense.py
local M_SUB, M_INFO, M_ESTADO, M_ARTE, M_NOMBRE, M_COSTE = 59281, 59282, 59283, 59286, 59298, 59310
local E_TITULO, E_ESTADO, E_OPCION, E_COSTE = 59351, 59352, 59354, 59366
local T_RETRATO, T_NOMBRE, T_NIVEL, T_STATS, T_SIGUIENTE, T_MEJORAR, T_VENDER, T_ESTADO = 59381, 59382, 59383, 59384, 59385, 59386, 59387, 59388
local H_CRISTAL, H_OLEADA, H_ESSENCE, H_AVISO, H_SIGUIENTE = 59331, 59332, 59333, 59334, 59335
local F_TITULO, F_LINEA = 59341, 59342
local I_RETRATO, I_VICTORIA, I_DERROTA = 59740, 59704, 59705
local N_MAX = 12
-- Las ventanas enteras, con el marco
local MW, MH, EW, EH, TW, TH, HW, HH, FW, FH = 440, 364, 440, 286, 288, 174, 408, 76, 308, 220

local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

local function en(wnd, id)
  return window.find(wnd, id)
end

local function crear(actual, id, x, y)
  if window.isexist(actual) then
    window.setforeground(actual)
    return actual
  end
  local w = window.create(id, 0, 0, SYSTEM_HANDLER)
  if window.isexist(w) then
    window.move(w, x, y)
  end
  return w
end

local function cerrar(w)
  if window.isexist(w) then
    window.destroy(w)
  end
  return 0
end

-- ------------------------------------------------------------------------------------------------- el menu
-- torres: {{nombre, papel, "ATK 250  RNG 5", coste}, ...} (hasta 12); sub e info: los textos de arriba y de abajo.
function PDAbrir(torres, sub, info)
  P.torres = torres
  WND_PD_MENU = crear(WND_PD_MENU, 59280, SYSTEM_SCREEN_WIDTH / 2 - MW / 2, SYSTEM_SCREEN_HEIGHT / 2 - MH / 2)
  if not window.isexist(WND_PD_MENU) then
    return
  end
  window.settitle(WND_PD_MENU, "Pet Defense")
  window.settitle(en(WND_PD_MENU, M_SUB), corto(sub, 44))
  window.settitle(en(WND_PD_MENU, M_INFO), corto(info, 76))
  window.settitle(en(WND_PD_MENU, M_ESTADO), "")
  for i = 1, N_MAX do
    local t = torres[i]
    window.show(en(WND_PD_MENU, M_ARTE + i - 1), t ~= nil)
    window.settitle(en(WND_PD_MENU, M_NOMBRE + i - 1), t and corto(t[1], 12) or "")
    window.settitle(en(WND_PD_MENU, M_COSTE + i - 1), t and tostring(t[4]) or "")
    if t then
      window.settooltiptext(en(WND_PD_MENU, M_ARTE + i - 1), tostring(t[1]) .. ": " .. tostring(t[2]) .. " (" .. tostring(t[3]) .. ")")
    end
  end
end

function PDAviso(texto)
  if window.isexist(WND_PD_MENU) then
    window.settitle(en(WND_PD_MENU, M_ESTADO), corto(texto, 44))
  end
end

function PDCerrar()
  WND_PD_MENU = cerrar(WND_PD_MENU)
end

local function carta(i)
  local t = P.torres and P.torres[i]
  if t then
    PDAviso(tostring(t[1]) .. ": " .. tostring(t[2]) .. ", " .. tostring(t[3]))
  end
  return 1
end

function OnPDCarta1(dwID, dwCmdID, dwParam, pParam) return carta(1) end
function OnPDCarta2(dwID, dwCmdID, dwParam, pParam) return carta(2) end
function OnPDCarta3(dwID, dwCmdID, dwParam, pParam) return carta(3) end
function OnPDCarta4(dwID, dwCmdID, dwParam, pParam) return carta(4) end
function OnPDCarta5(dwID, dwCmdID, dwParam, pParam) return carta(5) end
function OnPDCarta6(dwID, dwCmdID, dwParam, pParam) return carta(6) end
function OnPDCarta7(dwID, dwCmdID, dwParam, pParam) return carta(7) end
function OnPDCarta8(dwID, dwCmdID, dwParam, pParam) return carta(8) end
function OnPDCarta9(dwID, dwCmdID, dwParam, pParam) return carta(9) end
function OnPDCarta10(dwID, dwCmdID, dwParam, pParam) return carta(10) end
function OnPDCarta11(dwID, dwCmdID, dwParam, pParam) return carta(11) end
function OnPDCarta12(dwID, dwCmdID, dwParam, pParam) return carta(12) end

function OnPDEmpezar(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_PD, 3, 0)
  return 1
end

-- ------------------------------------------------------------------------------------------------- elegir mascota
-- titulo: "Stone 4 - choose a pet  (Essence 150)"; opciones: {{nombre, papel, coste, alcanza}, ...}
function PDElegir(titulo, opciones)
  WND_PD_TORRE = cerrar(WND_PD_TORRE)
  WND_PD_ELEGIR = crear(WND_PD_ELEGIR, 59350, SYSTEM_SCREEN_WIDTH / 2 - EW / 2, SYSTEM_SCREEN_HEIGHT / 2 - EH / 2)
  if not window.isexist(WND_PD_ELEGIR) then
    return
  end
  window.settitle(WND_PD_ELEGIR, "Choose a pet")
  window.settitle(en(WND_PD_ELEGIR, E_TITULO), corto(titulo, 70))
  window.settitle(en(WND_PD_ELEGIR, E_ESTADO), "")
  for i = 1, N_MAX do
    local o = opciones[i]
    window.show(en(WND_PD_ELEGIR, E_OPCION + i - 1), o ~= nil)
    if o then
      window.settitle(en(WND_PD_ELEGIR, E_COSTE + i - 1), (o[4] and "" or "x ") .. tostring(o[3]))
      window.settooltiptext(en(WND_PD_ELEGIR, E_OPCION + i - 1), tostring(o[1]) .. ": " .. tostring(o[2]))
    else
      window.settitle(en(WND_PD_ELEGIR, E_COSTE + i - 1), "")
    end
  end
end

function PDElegirAviso(texto)
  if window.isexist(WND_PD_ELEGIR) then
    window.settitle(en(WND_PD_ELEGIR, E_ESTADO), corto(texto, 70))
  end
end

function PDElegirCerrar()
  WND_PD_ELEGIR = cerrar(WND_PD_ELEGIR)
end

local function opcion(i)
  game.netcommand2(CMD_PD, 7, i - 1)
  return 1
end

function OnPDOpcion1(dwID, dwCmdID, dwParam, pParam) return opcion(1) end
function OnPDOpcion2(dwID, dwCmdID, dwParam, pParam) return opcion(2) end
function OnPDOpcion3(dwID, dwCmdID, dwParam, pParam) return opcion(3) end
function OnPDOpcion4(dwID, dwCmdID, dwParam, pParam) return opcion(4) end
function OnPDOpcion5(dwID, dwCmdID, dwParam, pParam) return opcion(5) end
function OnPDOpcion6(dwID, dwCmdID, dwParam, pParam) return opcion(6) end
function OnPDOpcion7(dwID, dwCmdID, dwParam, pParam) return opcion(7) end
function OnPDOpcion8(dwID, dwCmdID, dwParam, pParam) return opcion(8) end
function OnPDOpcion9(dwID, dwCmdID, dwParam, pParam) return opcion(9) end
function OnPDOpcion10(dwID, dwCmdID, dwParam, pParam) return opcion(10) end
function OnPDOpcion11(dwID, dwCmdID, dwParam, pParam) return opcion(11) end
function OnPDOpcion12(dwID, dwCmdID, dwParam, pParam) return opcion(12) end

-- ------------------------------------------------------------------------------------------------- ficha de torre
-- tipo: 1..12 (su orden); fase: 1..3; textos ya hechos; puede_mejorar: false al nivel maximo; ayudas de los botones.
function PDTorre(tipo, fase, nombre, nivel, stats, siguiente, puede_mejorar, ayuda_mejorar, ayuda_vender)
  WND_PD_ELEGIR = cerrar(WND_PD_ELEGIR)
  WND_PD_TORRE = crear(WND_PD_TORRE, 59380, SYSTEM_SCREEN_WIDTH / 2 - TW / 2, SYSTEM_SCREEN_HEIGHT / 2 - TH / 2)
  if not window.isexist(WND_PD_TORRE) then
    return
  end
  window.settitle(WND_PD_TORRE, "Tower")
  window.seticon(en(WND_PD_TORRE, T_RETRATO), I_RETRATO + 3 * (tipo - 1) + (fase - 1))
  window.settitle(en(WND_PD_TORRE, T_NOMBRE), corto(nombre, 26))
  window.settitle(en(WND_PD_TORRE, T_NIVEL), nivel)
  window.settitle(en(WND_PD_TORRE, T_STATS), corto(stats, 30))
  window.settitle(en(WND_PD_TORRE, T_SIGUIENTE), corto(siguiente, 30))
  window.settitle(en(WND_PD_TORRE, T_ESTADO), "")
  local b = en(WND_PD_TORRE, T_MEJORAR)
  window.show(b, puede_mejorar and true or false)
  window.settooltiptext(b, ayuda_mejorar or "")
  window.settooltiptext(en(WND_PD_TORRE, T_VENDER), ayuda_vender or "")
end

function PDTorreAviso(texto)
  if window.isexist(WND_PD_TORRE) then
    window.settitle(en(WND_PD_TORRE, T_ESTADO), corto(texto, 44))
  end
end

function PDTorreCerrar()
  WND_PD_TORRE = cerrar(WND_PD_TORRE)
end

function OnPDMejorar(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_PD, 8, 0)
  return 1
end

function OnPDVender(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_PD, 9, 0)
  return 1
end

-- ------------------------------------------------------------------------------------------------- la barra
-- cristal "18/20", oleada "3/10", essence, aviso; pausa: true si se puede adelantar la oleada.
function PDHud(cristal, oleada, essence, aviso, pausa)
  if not window.isexist(WND_PD_HUD) then
    WND_PD_HUD = crear(WND_PD_HUD, 59330, SYSTEM_SCREEN_WIDTH / 2 - HW / 2, 36)
    if not window.isexist(WND_PD_HUD) then
      return
    end
    window.settitle(WND_PD_HUD, "Pet Defense")
  end
  window.settitle(en(WND_PD_HUD, H_CRISTAL), "Crystal " .. tostring(cristal))
  window.settitle(en(WND_PD_HUD, H_OLEADA), "Wave " .. tostring(oleada))
  window.settitle(en(WND_PD_HUD, H_ESSENCE), "Essence " .. tostring(essence))
  window.settitle(en(WND_PD_HUD, H_AVISO), corto(aviso, 36))
  window.show(en(WND_PD_HUD, H_SIGUIENTE), pausa and true or false)
end

function PDHudCerrar()
  WND_PD_HUD = cerrar(WND_PD_HUD)
  WND_PD_ELEGIR = cerrar(WND_PD_ELEGIR)
  WND_PD_TORRE = cerrar(WND_PD_TORRE)
end

function OnPDSiguiente(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_PD, 4, 0)
  return 1
end

function OnPDSalir(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_PD, 5, 0)
  return 1
end

-- ------------------------------------------------------------------------------------------------- el final
-- victoria: true / false; lineas: cuatro textos (oleadas, cristal, tiempo, puntos).
function PDFin(victoria, lineas)
  PDHudCerrar()
  WND_PD_FIN = crear(WND_PD_FIN, 59340, SYSTEM_SCREEN_WIDTH / 2 - FW / 2, SYSTEM_SCREEN_HEIGHT / 2 - FH / 2)
  if not window.isexist(WND_PD_FIN) then
    return
  end
  window.settitle(WND_PD_FIN, "Pet Defense")
  window.seticon(en(WND_PD_FIN, F_TITULO), victoria and I_VICTORIA or I_DERROTA)
  for k = 0, 3 do
    window.settitle(en(WND_PD_FIN, F_LINEA + k), lineas and lineas[k + 1] or "")
  end
end

function OnPDOtra(dwID, dwCmdID, dwParam, pParam)
  WND_PD_FIN = cerrar(WND_PD_FIN)
  game.netcommand2(CMD_PD, 6, 0)
  return 1
end

function OnPDSalirFin(dwID, dwCmdID, dwParam, pParam)
  WND_PD_FIN = cerrar(WND_PD_FIN)
  game.netcommand2(CMD_PD, 5, 0)
  return 1
end
