-- Los eventos sociales sin comandos (server/sociales_ui.py; ventanas de tools/ventana_sociales.py):
--   * "Duel" en el menu de clic derecho sobre un jugador (59661) abre la ventanita del duelo (58900) para poner el oro;
--   * al retado le sale la misma ventanita con Accept / Decline;
--   * el boton "Events" de la barra (59008) abre el panel (58920) con cuatro pestanas: Duels (apuestas), Hunted
--     Hunter, Weekly Vote y Treasure Hunt.
-- Todo va al servidor con game.netcommand2(178, a, b).
local CMD_SO = 178
WND_DUELO = WND_DUELO or 0
WND_SOCIAL = WND_SOCIAL or 0
SOCIAL = SOCIAL or {modo = "", nombre = ""}

local DU_L1, DU_L2, DU_BOTE, DU_ORO, DU_OK, DU_NO, DU_RAPIDO = 58901, 58902, 58903, 58904, 58905, 58906, 58908
local RAPIDOS_DUELO = {10000, 100000, 1000000, 10000000}
local RAPIDOS_APUESTA = {1000, 10000, 100000}
local D_RAPIDO = 57165
local I_LADO_A, I_LADO_B, I_LADO_NO, I_B136, I_B136_ROJO = 57180, 57181, 57182, 57091, 57185
-- el panel con pestanas (tools/ventana_sociales.py)
local TABS = {57100, 57101, 57102, 57103, 57109}
local ESTADO, REGLA = 57104, 57105
local D_APUESTA, D_FILA, D_A, D_B, D_SIN = 57111, 57113, 57118, 57123, 57128
local H_LINEA, H_BOTON, V_INFO, V_OPCION, V_MIO, T_LINEA = 57130, 57136, 57140, 57141, 57146, 57150
local GRUPOS = {
  {57110, 57111, 57112, 57113, 57114, 57115, 57116, 57117, 57118, 57119, 57120, 57121, 57122, 57123, 57124, 57125,
   57126, 57127, 57128, 57160},
  {57130, 57131, 57132, 57133, 57134, 57135, 57136, 57161},
  {57140, 57141, 57142, 57143, 57144, 57145, 57146, 57162},
  {57150, 57151, 57152, 57153, 57154, 57155, 57163},
  {57164, 57250},
}
local C_DIA, C_FILA, C_EST, C_PIE = 57200, 57210, 57230, 57250
for i = 0, 6 do
  table.insert(GRUPOS[5], C_DIA + i)
end
for i = 0, 13 do
  table.insert(GRUPOS[5], C_FILA + i)
  table.insert(GRUPOS[5], C_EST + i)
end
local SW = 508

local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

local function miles(n)
  local s = tostring(math.floor(tonumber(n) or 0))
  local r = ""
  while string.len(s) > 3 do
    r = "," .. string.sub(s, -3) .. r
    s = string.sub(s, 1, -4)
  end
  return s .. r
end

local function mandar_nombre(nombre, base)
  for t = 0, 3 do
    local v = 0
    for k = 4, 1, -1 do
      v = v * 256 + (string.byte(nombre, t * 4 + k) or 0)
    end
    game.netcommand2(CMD_SO, base + t, v)
  end
end

function OnCommandEventos(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_SO, 1, 0)
  return 1
end

-- ---------------------------------------------------------------------------------------------- el menu del jugador
-- Como "Invite to raid" (raid_menu.lua): se envuelve OnClickChatOption para quedarse con el menu (565) y poner "Duel"
-- debajo de todo.
if not AOF_MENU_DUELO and OnClickChatOption then
  AOF_MENU_DUELO = true
  local original = OnClickChatOption
  OnClickChatOption = function(dwID, dwCmdID, dwParam, pParam)
    local menu = nil
    local crear = window.create
    window.create = function(a, b, c, d)
      local h = crear(a, b, c, d)
      if a == 565 then
        menu = h
      end
      return h
    end
    local ok, r = pcall(original, dwID, dwCmdID, dwParam, pParam)
    window.create = crear
    if menu and window.isexist(menu) then
      local boton = window.find(menu, 59661)
      local alto = window.height(menu)
      window.show(boton, true)
      window.move(boton, window.left(boton), window.top(menu) + alto - 3)
      window.setwindowsize(menu, window.width(menu), alto + 16)
    end
    if ok then
      return r
    end
    return 1
  end
end

function OnClickChatOptionDuelo(dwID, dwCmdID, dwParam, pParam)
  if CHAT_CLICK_NAME and CHAT_CLICK_NAME ~= "" then
    DueloAbrir("retar", CHAT_CLICK_NAME, 0)
  end
  window.destroy(window.parent(dwID))
  return 1
end

-- ---------------------------------------------------------------------------------------------- la ventanita
local function du(id)
  return window.find(WND_DUELO, id)
end

-- modo "retar" (lo abre el menu) o "recibido" (lo manda el servidor al retado).
function DueloAbrir(modo, nombre, oro)
  SOCIAL.modo = modo
  SOCIAL.nombre = nombre
  if window.isexist(WND_DUELO) then
    window.setforeground(WND_DUELO)
  else
    WND_DUELO = window.create(58900, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_DUELO) then
      game.netcommand2(CMD_SO, 9, 0)
      return
    end
    window.move(WND_DUELO, SYSTEM_SCREEN_WIDTH / 2 - 134, SYSTEM_SCREEN_HEIGHT / 2 - 90)
  end
  for i = 0, 3 do
    window.show(du(DU_RAPIDO + i), modo == "retar")
  end
  if modo == "retar" then
    window.settitle(du(DU_L1), corto("Challenge " .. nombre, 34))
    window.settitle(du(DU_L2), "You both put the same gold. The winner takes it all.")
    window.settitle(du(DU_ORO), "")
    window.settitle(du(DU_BOTE), "")
    window.enable(du(DU_ORO), true)
    window.setfocus(du(DU_ORO))
    window.settitle(du(DU_OK), "Challenge")
    window.settitle(du(DU_NO), "Cancel")
  else
    window.settitle(du(DU_L1), corto(nombre .. " challenges you!", 34))
    window.settitle(du(DU_L2), corto("Winner takes " .. miles(oro * 2) .. " Gold. Answer within 60 seconds.", 60))
    window.settitle(du(DU_ORO), miles(oro))
    window.settitle(du(DU_BOTE), "")
    window.enable(du(DU_ORO), false)
    window.settitle(du(DU_OK), "Accept")
    window.settitle(du(DU_NO), "Decline")
  end
end

function DueloCerrar()
  if window.isexist(WND_DUELO) then
    window.destroy(WND_DUELO)
  end
  WND_DUELO = 0
end

function OnDueloRapido(dwID, dwCmdID, dwParam, pParam)
  for i = 0, 3 do
    if du(DU_RAPIDO + i) == dwID then
      window.settitle(du(DU_ORO), tostring(RAPIDOS_DUELO[i + 1]))
      window.settitle(du(DU_L2), "Winner takes " .. miles(RAPIDOS_DUELO[i + 1] * 2) .. " Gold.")
    end
  end
  return 1
end

function OnDueloOk(dwID, dwCmdID, dwParam, pParam)
  if SOCIAL.modo == "retar" then
    local oro = tonumber((string.gsub(window.gettitle(du(DU_ORO)) or "", ",", ""))) or 0
    mandar_nombre(SOCIAL.nombre, 20)
    game.netcommand2(CMD_SO, 24, oro)
  else
    game.netcommand2(CMD_SO, 25, 0)
  end
  DueloCerrar()
  return 1
end

function OnDueloNo(dwID, dwCmdID, dwParam, pParam)
  if SOCIAL.modo == "recibido" then
    game.netcommand2(CMD_SO, 26, 0)
  end
  DueloCerrar()
  return 1
end

-- ---------------------------------------------------------------------------------------------- el panel
local function so(id)
  return window.find(WND_SOCIAL, id)
end

local function lineas(base, n, lista, largo)
  for i = 0, n - 1 do
    window.settitle(so(base + i), corto((lista or {})[i + 1] or "", largo))
  end
end

-- pestana 1..4; titulos: el texto de cada pestana; estado: la linea de la cabecera; reglas: HOW IT WORKS (4 lineas);
-- d: 1 duelos {ayuda, {{texto, nombreA, nombreB}, ...}}   ("" = sin boton)
--    2 cazador {lineas, boton}
--    3 votacion {info, {opcion, ...}, mio}
--    4 tesoro {lineas}
--    5 calendario {dia elegido 0..6, {titulo de cada dia}, {{texto, estado}, ...}, pie}
function SocialDatos(pestana, titulos, estado, reglas, d)
  if not window.isexist(WND_SOCIAL) then
    game.netcommand2(CMD_SO, 0, 0)               -- la cerraron con la X: que el servidor deje de mandar
    return
  end
  SOCIAL.pestana = pestana
  for i = 1, 5 do
    window.seticon(so(TABS[i]), i == pestana and 57174 or 57175)
    window.settitle(so(TABS[i]), titulos[i] or "")
  end
  for g = 1, 5 do
    for _, id in ipairs(GRUPOS[g]) do
      window.show(so(id), g == pestana)
    end
  end
  window.settitle(so(ESTADO), corto(estado, 64))
  lineas(REGLA, 4, reglas, 72)
  if pestana == 1 then
    window.settitle(so(57112), corto(d[1], 24))
    window.show(so(D_SIN), #d[2] == 0)
    window.settitle(so(D_SIN), "No duels right now. Right-click a player and pick Duel.")
    for i = 0, 4 do
      local f = d[2][i + 1]
      window.show(so(D_FILA + i), f ~= nil)
      window.show(so(D_A + i), f ~= nil)
      window.show(so(D_B + i), f ~= nil)
      if f then
        local puede = f[4] == 1
        window.settitle(so(D_FILA + i), corto(f[1], 34))
        window.settitle(so(D_A + i), corto(f[2], 20))
        window.settitle(so(D_B + i), corto(f[3], 20))
        window.seticon(so(D_A + i), puede and I_LADO_A or I_LADO_NO)
        window.seticon(so(D_B + i), puede and I_LADO_B or I_LADO_NO)
        window.enable(so(D_A + i), puede)
        window.enable(so(D_B + i), puede)
      end
    end
  elseif pestana == 2 then
    lineas(H_LINEA, 6, d[1], 72)
    window.show(so(H_BOTON), d[2] ~= "")
    window.settitle(so(H_BOTON), d[2])
    window.seticon(so(H_BOTON), d[2] == "Leave" and I_B136_ROJO or I_B136)
  elseif pestana == 3 then
    window.settitle(so(V_INFO), corto(d[1], 72))
    for i = 0, 4 do
      local t = d[2][i + 1]
      window.show(so(V_OPCION + i), t ~= nil)
      if t then
        window.settitle(so(V_OPCION + i), corto(t, 72))
      end
    end
    window.settitle(so(V_MIO), corto(d[3], 72))
  elseif pestana == 4 then
    lineas(T_LINEA, 6, d[1], 72)
  else
    for i = 0, 6 do
      window.seticon(so(C_DIA + i), i == d[1] and 57178 or 57179)
      window.settitle(so(C_DIA + i), d[2][i + 1] or "")
    end
    for i = 0, 13 do
      local f = d[3][i + 1]
      window.settitle(so(C_FILA + i), corto(f and f[1] or "", 58))
      window.settitle(so(C_EST + i), corto(f and f[2] or "", 18))
    end
    window.settitle(so(C_PIE), corto(d[4], 76))
  end
end

function SocialAbrir(pestana, titulos, estado, reglas, d)
  if window.isexist(WND_SOCIAL) then
    window.setforeground(WND_SOCIAL)
  else
    WND_SOCIAL = window.create(58920, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_SOCIAL) then
      game.netcommand2(CMD_SO, 9, 0)
      return
    end
    window.move(WND_SOCIAL, SYSTEM_SCREEN_WIDTH / 2 - SW / 2, 80)
    window.regsetting(WND_SOCIAL, "WND_EVENTOS")
  end
  window.settitle(WND_SOCIAL, "Events")
  SocialDatos(pestana, titulos, estado, reglas, d)
end

local function cual(dwID, base, n)
  for i = 0, n - 1 do
    if so(base + i) == dwID then
      return i
    end
  end
  return -1
end

function OnSocialPestana(dwID, dwCmdID, dwParam, pParam)
  for i = 1, 5 do
    if so(TABS[i]) == dwID then
      game.netcommand2(CMD_SO, 2, i)
    end
  end
  return 1
end

function OnSocialDia(dwID, dwCmdID, dwParam, pParam)
  local i = cual(dwID, C_DIA, 7)
  if i >= 0 then
    game.netcommand2(CMD_SO, 3, i)
  end
  return 1
end

local function apostar(dwID, base, cmd)
  local i = cual(dwID, base, 5)
  if i >= 0 then
    game.netcommand2(CMD_SO, cmd + i, tonumber(window.gettitle(so(D_APUESTA))) or 0)
  end
  return 1
end

function OnSocialRapido(dwID, dwCmdID, dwParam, pParam)
  local i = cual(dwID, D_RAPIDO, 3)
  if i >= 0 then
    window.settitle(so(D_APUESTA), tostring(RAPIDOS_APUESTA[i + 1]))
  end
  return 1
end

function OnSocialApostarA(dwID, dwCmdID, dwParam, pParam)
  return apostar(dwID, D_A, 30)
end

function OnSocialApostarB(dwID, dwCmdID, dwParam, pParam)
  return apostar(dwID, D_B, 40)
end

function OnSocialCaza(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_SO, 50, 0)
  return 1
end

function OnSocialVotar(dwID, dwCmdID, dwParam, pParam)
  local i = cual(dwID, V_OPCION, 5)
  if i >= 0 then
    game.netcommand2(CMD_SO, 60 + i, 0)
  end
  return 1
end
