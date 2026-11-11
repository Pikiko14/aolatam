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

-- EL PANEL (ventana 59700): 4 grupos de 5 como el panel de la party. RaidPanelAbrir() lo crea; RaidPanel(titulo, grupos)
-- lo rellena cada segundo si esta abierto. grupos: 4 listas de {nombre, vida %, mana %, rol (1 tanque, 2 sanador,
-- 3 dano), lider, estado ("dead", "away", "off" o "")}.
WND_RAID_PANEL = WND_RAID_PANEL or 0
local ICONO_ROL = {59851, 59852, 59853}

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
  for i = 0, 19 do
    window.setrange(hijo_panel(59770 + i), 0, 100)
    window.setrange(hijo_panel(59790 + i), 0, 100)
  end
end

function RaidPanel(titulo, grupos)
  if not window.isexist(WND_RAID_PANEL) then
    return
  end
  window.settitle(WND_RAID_PANEL, titulo)
  for g = 0, 3 do
    local grupo = grupos[g + 1] or {}
    window.show(hijo_panel(59830 + g), grupo[1] ~= nil)
    for r = 0, 4 do
      local i = g * 5 + r
      local m = grupo[r + 1]
      local hay = m and true or false
      window.show(hijo_panel(59710 + i), hay)
      window.show(hijo_panel(59810 + i), hay)
      window.show(hijo_panel(59770 + i), hay)
      window.show(hijo_panel(59790 + i), hay)
      window.show(hijo_panel(59750 + i), hay and m[5] and true or false)
      window.show(hijo_panel(59730 + i), hay)
      if m then
        window.settitle(hijo_panel(59710 + i), corto(m[1], 14))
        window.settitle(hijo_panel(59810 + i), m[6] or "")
        window.setpos(hijo_panel(59770 + i), m[2])
        window.setpos(hijo_panel(59790 + i), m[3])
        window.seticon(hijo_panel(59730 + i), ICONO_ROL[m[4]] or 59853)
      end
    end
  end
end

function RaidPanelCerrar()
  if window.isexist(WND_RAID_PANEL) then
    window.destroy(WND_RAID_PANEL)
  end
  WND_RAID_PANEL = 0
end
