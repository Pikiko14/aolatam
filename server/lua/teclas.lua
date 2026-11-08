-- La pestana AOF de la ventana System (tools/parche_aof_ventana.py) y las teclas de la barra a gusto de cada jugador
-- (07/11/2026). Los nativos game.aof* los pone tools/parche_teclas_aof.py en angel.dat; sin ellos esto no hace nada.
-- Las teclas se guardan en el cliente (save\cfg\wob_<ancho>_<alto>.xml) con window.regcustom, como enteros:
-- AOF_KEY_1..AOF_KEY_12 (codigos DIK) y AOF_CHAT_ENTER (1 = el chat se abre con Enter).
if game.aofsetkey == nil then
  return
end

local SLOT0 = 59120
local TECLAS_F = {0x3B, 0x3C, 0x3D, 0x3E, 0x3F, 0x40, 0x41, 0x42, 0x43, 0x44, 0x57, 0x58}

-- Nombre de cada codigo DIK para el boton.
local NOMBRES = {
  [0x01] = "Esc", [0x0C] = "-", [0x0D] = "=", [0x0E] = "Backspace", [0x0F] = "Tab", [0x1A] = "[", [0x1B] = "]",
  [0x1C] = "Enter", [0x1D] = "LCtrl", [0x27] = ";", [0x28] = "'", [0x29] = "`", [0x2A] = "LShift", [0x2B] = "\\",
  [0x33] = ",", [0x34] = ".", [0x35] = "/", [0x36] = "RShift", [0x37] = "Num *", [0x38] = "LAlt", [0x39] = "Space",
  [0x3A] = "CapsLock", [0x45] = "NumLock", [0x46] = "ScrollLock", [0x47] = "Num 7", [0x48] = "Num 8",
  [0x49] = "Num 9", [0x4A] = "Num -", [0x4B] = "Num 4", [0x4C] = "Num 5", [0x4D] = "Num 6", [0x4E] = "Num +",
  [0x4F] = "Num 1", [0x50] = "Num 2", [0x51] = "Num 3", [0x52] = "Num 0", [0x53] = "Num .", [0x57] = "F11",
  [0x58] = "F12", [0x9C] = "Num Enter", [0x9D] = "RCtrl", [0xB5] = "Num /", [0xB8] = "RAlt", [0xC7] = "Home",
  [0xC8] = "Up", [0xC9] = "PgUp", [0xCB] = "Left", [0xCD] = "Right", [0xCF] = "End", [0xD0] = "Down",
  [0xD1] = "PgDn", [0xD2] = "Insert", [0xD3] = "Delete",
}
do
  local fila = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "0"}
  for i = 1, 10 do NOMBRES[0x01 + i] = fila[i] end
  local q = {"Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"}
  for i = 1, 10 do NOMBRES[0x0F + i] = q[i] end
  local a = {"A", "S", "D", "F", "G", "H", "J", "K", "L"}
  for i = 1, 9 do NOMBRES[0x1D + i] = a[i] end
  local z = {"Z", "X", "C", "V", "B", "N", "M"}
  for i = 1, 7 do NOMBRES[0x2B + i] = z[i] end
  for i = 1, 10 do NOMBRES[0x3A + i] = "F" .. i end
end

local function nombre(dik)
  return NOMBRES[dik] or ("Key " .. tostring(dik))
end

-- Las que escriben algo en el chat (numeros, letras, signos, espacio y el teclado numerico): con el chat abierto no
-- usan la casilla.
local function escribe(dik)
  return (dik >= 0x02 and dik <= 0x0D) or (dik >= 0x10 and dik <= 0x1B) or (dik >= 0x1E and dik <= 0x29)
      or (dik >= 0x2B and dik <= 0x35) or dik == 0x37 or dik == 0x39 or (dik >= 0x47 and dik <= 0x53)
end

-- Las que no se dejan poner: modificadores, Enter / Escape (abren y cierran el chat), Tab y Backspace.
local function prohibida(dik)
  return dik == 0x01 or dik == 0x0E or dik == 0x0F or dik == 0x1C or dik == 0x9C or dik == 0x1D or dik == 0x9D
      or dik == 0x2A or dik == 0x36 or dik == 0x38 or dik == 0xB8 or dik == 0x3A
end

local function clave(i)
  return "AOF_KEY_" .. i
end

for i = 1, 12 do
  local k = _G[clave(i)]
  if type(k) ~= "number" or k <= 0 or k > 255 then
    _G[clave(i)] = TECLAS_F[i]
  end
end
if type(AOF_CHAT_ENTER) ~= "number" then
  AOF_CHAT_ENTER = 1
end
AOF_ESPERA = nil

-- Lo que cabe en la etiqueta de la barra (26 px en horizontal, 13 en vertical).
local CORTOS = {
  [0x39] = "Spc", [0xD2] = "Ins", [0xD3] = "Del", [0xC7] = "Hom", [0xCF] = "End", [0xC9] = "PU", [0xD1] = "PD",
  [0xC8] = "Up", [0xD0] = "Dn", [0xCB] = "Lf", [0xCD] = "Rt", [0x46] = "SL", [0x45] = "NL", [0x37] = "N*",
  [0x4A] = "N-", [0x4E] = "N+", [0xB5] = "N/", [0x53] = "N.",
}

local function corto(dik)
  local n = CORTOS[dik]
  if n then
    return n
  end
  n = nombre(dik)
  if string.sub(n, 1, 4) == "Num " then
    return "N" .. string.sub(n, 5)
  end
  if string.sub(n, 1, 4) == "Key " then
    return "?"
  end
  return n
end

-- Las etiquetas encima de los rotulos F1..F12 dibujados en la barra (wnd01.xml 59041.. horizontal, 59061.. vertical).
function AofEtiquetas()
  if WND_QUICK_COMMAND == nil or not window.isexist(WND_QUICK_COMMAND) then
    return
  end
  local vertical = (QUICK_COMMAND_TYPE == 0)
  local base = vertical and 59061 or 59041
  for i = 0, 11 do
    local w = window.find(WND_QUICK_COMMAND, base + i)
    if w == 0 then
      w = window.create(base + i, WND_QUICK_COMMAND, 0, 0)
      local extra = 0
      if i > 3 then extra = extra + 1 end
      if i > 7 then extra = extra + 1 end
      if vertical then
        window.moveoffset(w, 36, 33 + 31 * i + extra + 10)
      else
        window.moveoffset(w, 33 + 31 * i + extra + 2, 35)
      end
    end
    if w ~= 0 then
      local t = corto(_G[clave(i + 1)])
      if vertical and string.len(t) > 2 then
        t = string.sub(t, 1, 2)
      end
      window.settitle(w, t)
    end
  end
end

if AOF_ORIG_CreateQuickCommandButtons == nil then
  AOF_ORIG_CreateQuickCommandButtons = CreateQuickCommandButtons
end

function CreateQuickCommandButtons()
  local r = AOF_ORIG_CreateQuickCommandButtons()
  AofEtiquetas()
  return r
end

function AofAplicar()
  for i = 1, 12 do
    local k = _G[clave(i)]
    game.aofsetkey(i - 1, k, escribe(k) and 1 or 0)
  end
  game.aofmode(AOF_CHAT_ENTER)
  if AOF_CHAT_ENTER == 1 then
    game.aofchat(0)                -- empieza cerrado
  end
  AofEtiquetas()
end

-- Que el cliente guarde las variables al salir (solo escribe las registradas en esta sesion).
function AofRegistrar()
  if WND_QUICK_COMMAND ~= nil and window.isexist(WND_QUICK_COMMAND) then
    for i = 1, 12 do
      window.regcustom(WND_QUICK_COMMAND, clave(i))
    end
    window.regcustom(WND_QUICK_COMMAND, "AOF_CHAT_ENTER")
  end
end

-- La ventana System: la pagina AOF se oculta como las otras al abrir y al cambiar de pestana.
if AOF_ORIG_CreateSystemWnd == nil then
  AOF_ORIG_CreateSystemWnd = CreateSystemWnd
  AOF_ORIG_Setting_ChangePage = Setting_ChangePage
  AOF_ORIG_SetTell = SetTell
end

local function pagina_aof()
  if not window.isexist(WND_SYSTEM) then
    return 0
  end
  return window.find(WND_SYSTEM, 59101)
end

local function pintar_pagina()
  local p = pagina_aof()
  if p == 0 then
    return
  end
  window.setcheck(window.find(WND_SYSTEM, 59103), AOF_CHAT_ENTER == 1)
  local texto
  if AOF_CHAT_ENTER == 1 then
    texto = "Chat is closed until you press Enter. Type your message and press Enter again to send it and close the chat (Esc closes it too). While it is closed, numbers and letters can be used as quick bar keys."
  else
    texto = "Chat is always open, as usual. Numbers and letters on the quick bar only work while you are not typing."
  end
  window.settitle(window.find(WND_SYSTEM, 59106), texto)
end

function CreateSystemWnd()
  local r = AOF_ORIG_CreateSystemWnd()
  local p = pagina_aof()
  if p ~= 0 then
    window.show(p, false)
    pintar_pagina()
  end
  return r
end

function Setting_ChangePage(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local p = window.find(Wnd, 59101)
  if p ~= 0 then
    window.show(p, false)
  end
  local r = AOF_ORIG_Setting_ChangePage(dwID, dwCmdID, dwParam, pParam)
  if window.getappdata(dwID) == 59101 then
    -- El fondo es el de la pagina Sound (icono 12011, wnd05.xml): lleva ICON_ATTRIB_THEME y sigue el color del tema.
    pintar_pagina()
  end
  return r
end

-- Susurrar (clic en un nombre) abre el chat con el nombre puesto.
function SetTell(strName)
  AOF_ORIG_SetTell(strName)
  if AOF_CHAT_ENTER == 1 then
    game.aofchat(1)
  end
end

function AofChatEnter(dwID, dwCmdID, dwParam, pParam)
  AOF_CHAT_ENTER = window.ischeck(dwID) and 1 or 0
  AofAplicar()
  pintar_pagina()
  return 1
end

-- El dialogo de las teclas.
WND_AOF_TECLAS = WND_AOF_TECLAS or 0

local function pintar_teclas()
  if not window.isexist(WND_AOF_TECLAS) then
    return
  end
  for i = 1, 12 do
    local t = "Slot " .. i .. "      " .. nombre(_G[clave(i)])
    if AOF_ESPERA == i then
      t = "Slot " .. i .. "      press a key..."
    end
    window.settitle(window.find(WND_AOF_TECLAS, SLOT0 + i - 1), t)
  end
end

function AofAbrirTeclas(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_AOF_TECLAS) then
    window.setforeground(WND_AOF_TECLAS)
    return 1
  end
  WND_AOF_TECLAS = window.create(59110, 0, 0, SYSTEM_HANDLER)
  if not window.isexist(WND_AOF_TECLAS) then
    return 1
  end
  window.move(WND_AOF_TECLAS, SYSTEM_SCREEN_WIDTH / 2 - 105, SYSTEM_SCREEN_HEIGHT / 2 - 170)
  window.setbgcolor(WND_AOF_TECLAS, 52, 36, 12, 230)
  AOF_ESPERA = nil
  pintar_teclas()
  return 1
end

function AofCerrarTeclas(dwID, dwCmdID, dwParam, pParam)
  AOF_ESPERA = nil
  if window.isexist(WND_AOF_TECLAS) then
    window.destroy(WND_AOF_TECLAS)
  end
  WND_AOF_TECLAS = 0
  return 1
end

function AofElegirSlot(dwID, dwCmdID, dwParam, pParam)
  AOF_ESPERA = dwCmdID - SLOT0 + 1
  AOF_ESPERA_SUELTA = false           -- primero que se suelte lo que estuviera pulsado
  window.settitle(window.find(WND_AOF_TECLAS, 59111), "Press a key (Esc to cancel).")
  pintar_teclas()
  return 1
end

function AofTeclasDefecto(dwID, dwCmdID, dwParam, pParam)
  for i = 1, 12 do
    _G[clave(i)] = TECLAS_F[i]
  end
  AOF_ESPERA = nil
  AofAplicar()
  pintar_teclas()
  return 1
end

function AofTeclasUpdate(dwID, dwCmdID, dwParam, pParam)
  if AOF_ESPERA == nil then
    return 1
  end
  local k = game.aofpressed()
  if not AOF_ESPERA_SUELTA then
    if k == -1 then
      AOF_ESPERA_SUELTA = true
    end
    return 1
  end
  if k == -1 then
    return 1
  end
  local aviso = window.find(WND_AOF_TECLAS, 59111)
  if k == 0x01 then
    AOF_ESPERA = nil
    window.settitle(aviso, "Click a slot, then press a key.")
  elseif prohibida(k) then
    window.settitle(aviso, nombre(k) .. " can't be used. Try another key.")
    AOF_ESPERA_SUELTA = false
    return 1
  else
    local i = AOF_ESPERA
    local viejo = _G[clave(i)]
    for j = 1, 12 do                  -- si ya la tenia otra casilla, se intercambian
      if j ~= i and _G[clave(j)] == k then
        _G[clave(j)] = viejo
      end
    end
    _G[clave(i)] = k
    AOF_ESPERA = nil
    AofAplicar()
    window.settitle(aviso, "Slot " .. i .. " is now " .. nombre(k) .. ".")
  end
  pintar_teclas()
  return 1
end

AofRegistrar()
AofAplicar()
