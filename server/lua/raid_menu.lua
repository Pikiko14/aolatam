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
-- RaidListaAbrir(filas): filas {{nombre, nivel, jugadores, jefes, estado, {{jefe, "ready"|"looted"}}}}, una por raid.
-- La lista de la izquierda solo lleva los nombres; los detalles de la elegida van a la derecha (59676..59684).
local function hijo_lista(id)
  return window.find(WND_RAID_LISTA, id)
end

local function detalle(i)
  local f = RAID_LISTA.filas and RAID_LISTA.filas[i]
  if not f then
    return
  end
  RAID_LISTA.sel = i
  window.seticon(hijo_lista(60320), 60330 + (f[9] or 0))         -- el banner de esa raid (tools/parche_raid.py)
  window.settitle(hijo_lista(59676), f[1])
  window.settitle(hijo_lista(59677), "Level " .. tostring(f[2]) .. "+   Players: " .. tostring(f[3]))
  window.settitle(hijo_lista(59678), "This week: " .. tostring(f[5]))
  window.settitle(hijo_lista(59679), "Bosses")
  for k = 1, 3 do
    local j = f[6] and f[6][k]
    if j then
      local marca = (j[2] == "looted") and "  (looted)" or ""
      window.settitle(hijo_lista(59679 + k), tostring(k) .. ". " .. j[1] .. marca)
    else
      window.settitle(hijo_lista(59679 + k), "")
    end
  end
  window.settitle(hijo_lista(59683), f[7] or "")
  window.settitle(hijo_lista(59684), f[8] or "")
  window.settitle(hijo_lista(59673), "Press Open to form or join a raid group.")
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
    window.move(WND_RAID_LISTA, SYSTEM_SCREEN_WIDTH / 2 - 200, SYSTEM_SCREEN_HEIGHT / 2 - 150)
  end
  local lista = hijo_lista(59671)
  window.clearlist(lista)
  for i, f in ipairs(filas or {}) do
    window.insertitemstr(lista, f[1], 0)
  end
  window.settitle(hijo_lista(59672), "Open")
  detalle(1)
end

function OnRaidListaFila(dwID, dwCmdID, dwParam, pParam)
  detalle((dwParam or 0) + 1)                                     -- las filas cuentan desde 0
  return 1
end

function OnRaidListaAbrir(dwID, dwCmdID, dwParam, pParam)
  local sel = RAID_LISTA.sel or (RAID_LISTA.filas and RAID_LISTA.filas[1] and 1)
  if sel then
    game.netcommand2(CMD_RAID, 31, sel - 1)
  end
  return 1
end

-- ---------------------------------------------------------------------------------------------- la guia
-- RaidGuia(titulo, paginas): la ventana 59880 (tools/parche_raid.py). paginas {{pestana, titulo, retrato, {lineas}}};
-- retrato 0 sin retrato, 1..12 el jefe (iconos 59861..59863 y 60301..60309). Lo manda server/raid.py guia (netcommand2 171, 32, raid).
WND_RAID_GUIA = WND_RAID_GUIA or 0
RAID_GUIA = RAID_GUIA or {}

local function hijo_guia(id)
  return window.find(WND_RAID_GUIA, id)
end

function RaidGuiaPagina(i)
  local p = RAID_GUIA.paginas and RAID_GUIA.paginas[i]
  if not p or not window.isexist(WND_RAID_GUIA) then
    return
  end
  local pestanas = {59881, 59882, 59883, 59884, 59885, 60323}     -- tools/parche_raid.py PESTANAS_GUIA
  for k = 1, 6 do
    local q = RAID_GUIA.paginas[k]
    local boton = hijo_guia(pestanas[k])
    window.show(boton, q ~= nil)
    if q then
      window.settitle(boton, q[1])
      window.seticon(boton, (k == i) and 59865 or 59864)     -- la pestana elegida, encendida
    end
  end
  window.settitle(hijo_guia(59886), p[2])
  for k = 0, 12 do
    window.settitle(hijo_guia(59887 + k), (p[4] and p[4][k + 1]) or "")
  end
  local retrato = hijo_guia(59900)
  if p[3] and p[3] > 0 then
    -- 1..3 los de la Flamefang (59861..59863); 4..12 los de las demas raids (60301..60309, tools/parche_raid.py)
    window.seticon(retrato, (p[3] <= 3) and (59860 + p[3]) or (60297 + p[3]))
    window.show(retrato, true)
  else
    window.show(retrato, false)
  end
end

-- El banner de la guia: el de la raid i (0..3, orden del CATALOGO de server/raid.py).
function RaidGuiaImagen(i)
  if window.isexist(WND_RAID_GUIA) then
    window.seticon(hijo_guia(60322), 60338 + (i or 0))
  end
end

function RaidGuia(titulo, paginas)
  RAID_GUIA.paginas = paginas
  if window.isexist(WND_RAID_GUIA) then
    window.setforeground(WND_RAID_GUIA)
  else
    WND_RAID_GUIA = window.create(59880, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_RAID_GUIA) then
      return
    end
    window.move(WND_RAID_GUIA, SYSTEM_SCREEN_WIDTH / 2 - 214, SYSTEM_SCREEN_HEIGHT / 2 - 177)
  end
  window.settitle(WND_RAID_GUIA, titulo)
  RaidGuiaPagina(1)
end

function OnRaidGuiaPestana1(dwID, dwCmdID, dwParam, pParam) RaidGuiaPagina(1) return 1 end
function OnRaidGuiaPestana2(dwID, dwCmdID, dwParam, pParam) RaidGuiaPagina(2) return 1 end
function OnRaidGuiaPestana3(dwID, dwCmdID, dwParam, pParam) RaidGuiaPagina(3) return 1 end
function OnRaidGuiaPestana4(dwID, dwCmdID, dwParam, pParam) RaidGuiaPagina(4) return 1 end
function OnRaidGuiaPestana5(dwID, dwCmdID, dwParam, pParam) RaidGuiaPagina(5) return 1 end
function OnRaidGuiaPestana6(dwID, dwCmdID, dwParam, pParam) RaidGuiaPagina(6) return 1 end

function OnRaidGuiaCerrar(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_RAID_GUIA) then
    window.destroy(WND_RAID_GUIA)
  end
  WND_RAID_GUIA = 0
  return 1
end

-- "Guide" en AOF Raids (la raid elegida) y en la ventana de la raid (Flamefang, la 0 del catalogo).
function OnRaidListaGuia(dwID, dwCmdID, dwParam, pParam)
  local sel = RAID_LISTA.sel or 1
  game.netcommand2(CMD_RAID, 32, sel - 1)
  return 1
end

function OnRaidGuia(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_RAID, 32, 99)                  -- 99: la de la ventana (la raid del grupo o la elegida)
  return 1
end
