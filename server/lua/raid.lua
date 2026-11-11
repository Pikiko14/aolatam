-- La ventana de la raid Flamefang (server/raid.py): la 59600 de wnd03.xml (tools/parche_raid.py).
-- El servidor la abre con RaidAbrir(titulo, miembros, soy_lider, jefes, hay_corrida, en_raid, aviso) y la refresca con
-- RaidRefrescar(...). miembros: {{nombre, nivel, donde}}; jefes: {{nombre, estado}}.
local CMD_RAID = 171
WND_RAID = WND_RAID or 0          -- un numero desde el principio: window.isexist(nil) da error
RAID = RAID or {}
local R = RAID

local function hijo(id)
  return window.find(WND_RAID, id)
end

local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

local function estado(texto)
  if texto and texto ~= "" then
    window.settitle(hijo(59613), corto(texto, 52))
  end
end

local function pintar(titulo, miembros, soy_lider, jefes, hay_corrida, en_raid)
  RAID_LIDER = soy_lider and true or false      -- raid_menu.lua: "Invite to raid" en el menu del jugador
  window.settitle(WND_RAID, "Flamefang Raid")
  window.settitle(hijo(59601), corto(titulo, 52))
  local lista = hijo(59602)
  window.clearlist(lista)
  window.insertitemstr(lista, "Player", 0)
  -- setsubitemstr cuenta las columnas desde la segunda (como en torre.lua).
  window.setsubitemstr(lista, 0, 0, "Level", 0)
  window.setsubitemstr(lista, 0, 1, "Status", 0)
  for i, m in ipairs(miembros or {}) do
    window.insertitemstr(lista, corto(m[1], 14), 0)
    window.setsubitemstr(lista, i, 0, tostring(m[2]), 0)
    window.setsubitemstr(lista, i, 1, corto(m[3], 18), 0)
  end
  for k = 1, 3 do
    local j = jefes and jefes[k]
    if j then
      window.settitle(hijo(59602 + k), corto(tostring(k) .. ". " .. j[1] .. " - " .. j[2], 52))
    end
  end
  window.settitle(hijo(59608), en_raid and "Leave" or "Create")
  window.enable(hijo(59607), soy_lider and true or false)
  window.enable(hijo(59609), (soy_lider or not en_raid) and true or false)
  window.enable(hijo(59610), en_raid and (soy_lider or hay_corrida) and true or false)
  R.en_raid = en_raid
end

function RaidAbrir(titulo, miembros, soy_lider, jefes, hay_corrida, en_raid, aviso)
  if window.isexist(WND_RAID) then
    window.setforeground(WND_RAID)
  else
    WND_RAID = window.create(59600, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_RAID) then
      return
    end
    window.move(WND_RAID, SYSTEM_SCREEN_WIDTH / 2 - 180, SYSTEM_SCREEN_HEIGHT / 2 - 172)
  end
  pintar(titulo, miembros, soy_lider, jefes, hay_corrida, en_raid)
  if R.invitacion then
    window.show(hijo(59612), true)
  end
  if aviso and aviso ~= "" then
    estado(aviso)
  elseif not en_raid then
    estado("Create a raid, or wait for an invitation. Level 60, up to 20 players.")
  elseif hay_corrida then
    estado("The raid is under way: press Enter to join it.")
  else
    estado("The leader starts the raid with Enter.")
  end
end

function RaidRefrescar(titulo, miembros, soy_lider, jefes, hay_corrida, en_raid)
  RAID_LIDER = soy_lider and true or false
  if window.isexist(WND_RAID) then
    pintar(titulo, miembros, soy_lider, jefes, hay_corrida, en_raid)
  end
end

-- Una invitacion: la ventana con el boton Accept.
function RaidInvitacion(lider, id)
  R.invitacion = id
  game.netcommand2(CMD_RAID, 1, 0)
  if window.isexist(WND_RAID) then
    window.show(hijo(59612), true)
    estado(corto(lider, 14) .. " invites you. Press Accept.")
  end
end

local function cmd(a, b)
  game.netcommand2(CMD_RAID, a, b or 0)
  return 1
end

function OnRaidCrear(dwID, dwCmdID, dwParam, pParam)
  if R.en_raid then
    return cmd(3)
  end
  return cmd(2)
end

function OnRaidParty(dwID, dwCmdID, dwParam, pParam)
  return cmd(4)
end

function OnRaidEntrar(dwID, dwCmdID, dwParam, pParam)
  return cmd(5)
end

function OnRaidSalirMapa(dwID, dwCmdID, dwParam, pParam)
  return cmd(8)
end

function OnRaidAceptar(dwID, dwCmdID, dwParam, pParam)
  local id = R.invitacion
  R.invitacion = nil
  window.show(hijo(59612), false)
  if id then
    return cmd(6, id)
  end
  return 1
end

-- El nombre escrito va en cuatro trozos de cuatro letras (netcommand2 solo lleva numeros) y luego la orden.
function OnRaidInvitar(dwID, dwCmdID, dwParam, pParam)
  local nombre = window.gettitle(hijo(59606)) or ""
  if nombre == "" then
    estado("Write the name of the player to invite.")
    return 1
  end
  RaidInvitarNombre(nombre)                     -- raid_menu.lua
  return 1
end

-- EL PANEL (ventana 59700, tools/parche_raid.py): 24 filas seguidas; cada grupo pone una fila "Group N" y luego sus
-- miembros, y la ventana se encoge a las filas usadas. RaidPanelAbrir() lo crea; RaidPanel(titulo, grupos) lo rellena
-- cada segundo si esta abierto. grupos: listas de {nombre, vida %, mana %, rol (1 tanque, 2 sanador, 3 dano), lider,
-- estado ("dead", "away", "off" o ""), char_id}. Clic derecho en un miembro: el menu 60210 (Make leader, Remove).
WND_RAID_PANEL = WND_RAID_PANEL or 0
WND_RAID_PANEL_MENU = WND_RAID_PANEL_MENU or 0
RAID_PANEL = RAID_PANEL or {}
local ICONO_ROL = {59851, 59852, 59853}
local N_FILAS, FILA, ANCHO = 24, 20, 172
local MARCO_X, MARCO_Y, MARCO_ABAJO = 4, 20, 4        -- lo que anade el marco de WND_CLASS_DLG_1

local function hijo_panel(id)
  return window.find(WND_RAID_PANEL, id)
end

function RaidPanelAbrir()
  if window.isexist(WND_RAID_PANEL) then
    window.setforeground(WND_RAID_PANEL)
    return
  end
  WND_RAID_PANEL = window.create(59700, 0, 0, SYSTEM_HANDLER)
  if not window.isexist(WND_RAID_PANEL) then
    return
  end
  window.move(WND_RAID_PANEL, 4, 120)
  for i = 0, N_FILAS - 1 do
    window.setrange(hijo_panel(60030 + i), 0, 100)
    window.setrange(hijo_panel(60060 + i), 0, 100)
  end
end

local function fila(i, m, grupo)
  local es_miembro = m ~= nil
  window.show(hijo_panel(60180 + i), true)                     -- la franja del fondo
  window.show(hijo_panel(60120 + i), grupo ~= nil)
  window.show(hijo_panel(60150 + i), es_miembro)
  window.show(hijo_panel(59940 + i), es_miembro)
  window.show(hijo_panel(60090 + i), es_miembro)
  window.show(hijo_panel(60030 + i), es_miembro)
  window.show(hijo_panel(60060 + i), es_miembro)
  window.show(hijo_panel(60240 + i), es_miembro)              -- la pista oscura de las barras
  window.show(hijo_panel(59970 + i), es_miembro)
  window.show(hijo_panel(60000 + i), es_miembro and m[5] and true or false)
  if grupo then
    window.settitle(hijo_panel(60120 + i), grupo)
  end
  if m then
    window.settitle(hijo_panel(59940 + i), corto(m[1], 14))
    window.settitle(hijo_panel(60090 + i), m[6] or "")
    window.setpos(hijo_panel(60030 + i), m[2])
    window.setpos(hijo_panel(60060 + i), m[3])
    window.seticon(hijo_panel(59970 + i), ICONO_ROL[m[4]] or 59853)
  end
end

local function vacia(i)
  for _, base in ipairs({60180, 60120, 60150, 59940, 60090, 60030, 60060, 60240, 59970, 60000}) do
    window.show(hijo_panel(base + i), false)
  end
end

function RaidPanel(titulo, grupos)
  if not window.isexist(WND_RAID_PANEL) then
    return
  end
  window.settitle(WND_RAID_PANEL, titulo)
  RAID_PANEL.filas = {}
  local i = 0
  for g, grupo in ipairs(grupos or {}) do
    if grupo[1] and i < N_FILAS then
      fila(i, nil, "Group " .. tostring(g))
      i = i + 1
      for _, m in ipairs(grupo) do
        if i < N_FILAS then
          RAID_PANEL.filas[i] = m
          fila(i, m, nil)
          i = i + 1
        end
      end
    end
  end
  for k = i, N_FILAS - 1 do
    vacia(k)
  end
  local alto = 2 + math.max(i, 1) * FILA + 4
  window.setwindowsize(WND_RAID_PANEL, ANCHO + 2 * MARCO_X, alto + MARCO_Y + MARCO_ABAJO)
end

-- Clic derecho en un miembro (OnCommandEx del boton transparente de su fila, appdata = la fila).
function OnRaidPanelMenu(dwID, dwCmdID, dwParam, pParam)
  local m = RAID_PANEL.filas and RAID_PANEL.filas[window.getappdata(dwID)]
  if not m then
    return 1
  end
  RAID_PANEL.menu_cid = m[7]
  if not window.isexist(WND_RAID_PANEL_MENU) then
    WND_RAID_PANEL_MENU = window.create(60210, 0, 0, SYSTEM_HANDLER)
  end
  if not window.isexist(WND_RAID_PANEL_MENU) then
    return 1
  end
  local x, y = window.getsysmousexy()
  x, y = x - 10, y + 5
  if x > SYSTEM_SCREEN_WIDTH - window.width(WND_RAID_PANEL_MENU) then
    x = SYSTEM_SCREEN_WIDTH - window.width(WND_RAID_PANEL_MENU)
  end
  if y > SYSTEM_SCREEN_HEIGHT - window.height(WND_RAID_PANEL_MENU) then
    y = SYSTEM_SCREEN_HEIGHT - window.height(WND_RAID_PANEL_MENU)
  end
  window.move(WND_RAID_PANEL_MENU, x, y)
  window.setforeground(WND_RAID_PANEL_MENU)
  window.settitle(window.find(WND_RAID_PANEL_MENU, 60211), corto(m[1], 16))
  local puede = (RAID_LIDER and not m[5]) and true or false   -- solo el lider, y no sobre si mismo
  window.enable(window.find(WND_RAID_PANEL_MENU, 60212), puede)
  window.enable(window.find(WND_RAID_PANEL_MENU, 60213), puede)
  return 1
end

local function menu_orden(a)
  if RAID_PANEL.menu_cid then
    game.netcommand2(CMD_RAID, a, RAID_PANEL.menu_cid)
  end
  if window.isexist(WND_RAID_PANEL_MENU) then
    window.destroy(WND_RAID_PANEL_MENU)
  end
  WND_RAID_PANEL_MENU = 0
  return 1
end

function OnRaidPanelLider(dwID, dwCmdID, dwParam, pParam)
  return menu_orden(10)
end

function OnRaidPanelSacar(dwID, dwCmdID, dwParam, pParam)
  return menu_orden(9)
end

function RaidPanelCerrar()
  if window.isexist(WND_RAID_PANEL) then
    window.destroy(WND_RAID_PANEL)
  end
  WND_RAID_PANEL = 0
end
