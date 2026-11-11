-- Lo de las raids que tiene que estar desde que se entra al juego (server/raid.py lo manda con el saludo):
--   * el boton de la barra "AOF Raid" (59004) abre el listado de raids (ventana 59670, tools/parche_raid.py);
--   * "Invite to raid" en el menu de clic derecho sobre un jugador (565, chat.lua OnClickChatOption), si eres el lider
--     de una raid (RAID_LIDER lo pone raid.lua al pintar la ventana de la raid).
local CMD_RAID = 171
RAID_LIDER = RAID_LIDER or false
WND_RAID_LISTA = WND_RAID_LISTA or 0
RAID_LISTA = RAID_LISTA or {}

function OnCommandRaid(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_RAID, 30, 0)
  return 1
end

-- ---------------------------------------------------------------------------------------------- el menu del jugador
-- OnClickChatOption crea el menu con window.create(565, ...) y no lo guarda en ningun sitio: se envuelve
-- window.create mientras dura la llamada para quedarse con el menu y ponerle "Invite to raid" debajo de todo.
if not AOF_MENU_RAID and OnClickChatOption then
  AOF_MENU_RAID = true
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
      local boton = window.find(menu, 59660)
      if RAID_LIDER then
        local alto = window.height(menu)
        window.show(boton, true)
        window.move(boton, window.left(boton), window.top(menu) + alto - 3)
        window.setwindowsize(menu, window.width(menu), alto + 16)
      else
        window.show(boton, false)
      end
    end
    if ok then
      return r
    end
    return 1
  end
end

-- El nombre va en cuatro trozos de cuatro letras (netcommand2 solo lleva numeros) y luego la orden de invitar.
function RaidInvitarNombre(nombre)
  for t = 0, 3 do
    local v = 0
    for k = 4, 1, -1 do
      v = v * 256 + (string.byte(nombre, t * 4 + k) or 0)
    end
    game.netcommand2(CMD_RAID, 20 + t, v)
  end
  game.netcommand2(CMD_RAID, 7, 0)
end

function OnClickChatOptionRaid(dwID, dwCmdID, dwParam, pParam)
  if CHAT_CLICK_NAME and CHAT_CLICK_NAME ~= "" then
    RaidInvitarNombre(CHAT_CLICK_NAME)
  end
  window.destroy(window.parent(dwID))
  return 1
end

-- ---------------------------------------------------------------------------------------------- AOF Raids
-- RaidListaAbrir(filas): filas {{nombre, nivel, jugadores, jefes, estado}}, una por raid.
local function hijo_lista(id)
  return window.find(WND_RAID_LISTA, id)
end

function RaidListaAbrir(filas)
  RAID_LISTA.filas = filas
  RAID_LISTA.sel = nil
  if window.isexist(WND_RAID_LISTA) then
    window.setforeground(WND_RAID_LISTA)
  else
    WND_RAID_LISTA = window.create(59670, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_RAID_LISTA) then
      return
    end
    window.move(WND_RAID_LISTA, SYSTEM_SCREEN_WIDTH / 2 - 165, SYSTEM_SCREEN_HEIGHT / 2 - 100)
  end
  local lista = hijo_lista(59671)
  window.clearlist(lista)
  window.insertitemstr(lista, "Raid", 0)
  window.setsubitemstr(lista, 0, 0, "Level", 0)
  window.setsubitemstr(lista, 0, 1, "Players", 0)
  window.setsubitemstr(lista, 0, 2, "This week", 0)
  for i, f in ipairs(filas or {}) do
    window.insertitemstr(lista, f[1], 0)
    window.setsubitemstr(lista, i, 0, tostring(f[2]), 0)
    window.setsubitemstr(lista, i, 1, tostring(f[3]), 0)
    window.setsubitemstr(lista, i, 2, f[5], 0)
  end
  window.settitle(hijo_lista(59672), "Open")
  window.settitle(hijo_lista(59673), "Pick a raid and press Open.")
end

function OnRaidListaFila(dwID, dwCmdID, dwParam, pParam)
  local f = RAID_LISTA.filas and RAID_LISTA.filas[dwParam]       -- la fila 0 es la cabecera
  if f then
    RAID_LISTA.sel = dwParam
    window.settitle(hijo_lista(59673), f[1] .. ": " .. tostring(f[4]) .. " bosses, level " .. tostring(f[2]) .. ".")
  end
  return 1
end

function OnRaidListaAbrir(dwID, dwCmdID, dwParam, pParam)
  local sel = RAID_LISTA.sel or (RAID_LISTA.filas and RAID_LISTA.filas[1] and 1)
  if sel then
    game.netcommand2(CMD_RAID, 31, sel - 1)
  end
  return 1
end
