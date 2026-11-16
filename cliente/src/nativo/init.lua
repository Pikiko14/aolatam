-- Arranque de los scripts originales del cliente sobre la capa nativa (window.* / game.*).
local M = {}
local window = require('src.nativo.window')

-- Scripts originales del cliente (se ignoran los que falten).
local SCRIPTS = { 'achievement.lua', 'actboard.lua', 'adtrade.lua', 'autoassist.lua', 'autofight.lua', 'automall.lua', 'autoother.lua', 'autopet.lua', 'autosupply.lua', 'bank.lua', 'battlefield.lua', 'battlepass.lua', 'captcha.lua', 'card.lua', 'charinfo.lua', 'chat.lua', 'collection.lua', 'command.lua', 'cutesung.lua', 'dailyevent.lua', 'dead.lua', 'emotion.lua', 'equip.lua', 'exchange.lua', 'farm.lua', 'finaltower.lua', 'fjjtestwnd04.lua', 'friend.lua', 'fuse.lua', 'game01.lua', 'game02.lua', 'game03.lua', 'game04.lua', 'gather.lua', 'global.lua', 'group.lua', 'guild.lua', 'gvg.lua', 'house.lua', 'item.lua', 'jumpmap.lua', 'loginreward.lua', 'mail.lua', 'main.lua', 'make.lua', 'mall.lua', 'marry.lua', 'message.lua', 'onlinereward.lua', 'petinfo.lua', 'pvp.lua', 'quest.lua', 'question.lua', 'quickcmd.lua', 'repair.lua', 'roulette.lua', 'safepwd.lua', 'safeverify.lua', 'sale.lua', 'salon.lua', 'skill.lua', 'skills.lua', 'starcard.lua', 'sys.lua', 'system.lua', 'test.lua', 'trade.lua', 'tuition.lua', 'word.lua' }

local G = { faltantes = {}, defs = {}, itemwnds = {} }
-- Los defines con que se compilo angel.dat: la lista que compara isdef (0x599780, strcmp uno a uno). Sin ellos los
-- scripts creen que no hay casas, logros, coleccion, GvG... y no montan esas ventanas.
for _, n in ipairs({ '__USA', '__DATA1', '__DATA2MAP', '__SERVERMALL', '__ROBOT', '__ROBOT2', '__CARD', '__MARRY',
  '__WIDE_SCREEN', '__ROBOT_MALL', '__BATTLEFIELD', '__DATA3MAP', '__ROBOT2_PLUS', '__MALL_EXTRALINK', '__080415MALL',
  '__MY_HOUSE', '__DATA4MAP', '__DATA5MAP', '__NEW_SKILL', '__WATERMELON', '__ITEM_FUSE', '__DATA6MAP', '__DATA7MAP',
  '__DATA8MAP', '__DATA9MAP', '__DATA10MAP', '__DATA11', '__DATA11MAP', '__DATA12', '__DATA12MAP', '__DATA13',
  '__DATA13MAP', '__DATA14', '__DATA14MAP', '__DATA15', '__DATA15MAP', '__DATA16', '__DATA16MAP', '__DATA17',
  '__DATA17MAP', '__DATA18', '__DATA18MAP', '__DATA19', '__DATA19MAP', '__DATA20', '__DATA20MAP', '__DATA21',
  '__DATA21MAP', '__DATA22', '__DATA22MAP', '__DATA23', '__DATA23MAP', '__DATA24', '__DATA24MAP', '__DATA25',
  '__DATA25MAP', '__DATA26', '__DATA26MAP', '__DATA27', '__DATA27MAP', '__DATA28', '__DATA28MAP', '__ACHIEVEMENT',
  '__COLLECTION', '__DAILY_EVENT', '__V10_JUMPMAP', '__FINAL_TOWER', '__QUESTION', '__ONLINEREWARD', '__LOGINREWARD',
  '__EXTEND_STORAGE2', '__GVG', '__EQUIP_PET_NEW', '__V16_PET_SUIT', '__PEAK_LV_SYSTEM', '__SPEECH_BUBBLE' }) do
  G.defs[n] = true
end
function G.isdef(nombre) return G.defs[nombre] == true end
-- Textos de setting/eng/string.xml (174 llamadas en los scripts: titulos, botones, ayudas)
function G.getstring(id)
  local ui = window.ui
  return ui and ui.cadena and ui:cadena(id) or ''
end
-- Variables del bot automatico (autofight/autosupply/autoassist...): el motor solo las guarda y las devuelve.
-- Las listas son por nombre: robotvar_add_list(nombre, v), robotvar_getnum_list(nombre), robotvar_get_list(nombre, i)...
local VARS, LISTAS = {}, {}
function G.setrobotvar_bool(k, v) VARS[k] = v and v ~= 0 end
function G.getrobotvar_bool(k) return VARS[k] == true end
function G.setrobotvar_int(k, v) VARS[k] = tonumber(v) or 0 end
function G.getrobotvar_int(k) return tonumber(VARS[k]) or 0 end
function G.setrobotvar_str(k, v) VARS[k] = tostring(v or '') end
function G.getrobotvar_str(k) return VARS[k] ~= nil and tostring(VARS[k]) or '' end
local function lista(k) LISTAS[k] = LISTAS[k] or {}; return LISTAS[k] end
function G.robotvar_clear_list(k) LISTAS[k] = {} end
function G.robotvar_add_list(k, v) local l = lista(k); l[#l + 1] = v end
G.robotvar_add_intlist = G.robotvar_add_list
G.robotvar_add_stringlist = G.robotvar_add_list
function G.robotvar_getnum_list(k) return #lista(k) end
function G.robotvar_get_list(k, i) return lista(k)[(tonumber(i) or 0) + 1] or 0 end
function G.robotvar_del_list(k, i) table.remove(lista(k), (tonumber(i) or 0) + 1) end
function G.openmap(_, h) G.minimapa = h end
function G.friendwnd(h) G.amigos_wnd = h end
function G.inititemwnd(h, tipo)
  G.itemwnds = G.itemwnds or {}
  G.itemwnds[h] = G.itemwnds[h] or {}
  G.itemwnds[h][tipo or 0] = true
  if (tipo or 0) == 0 then G.itemwnd = h end
end
-- ventanas que el motor rellena por su cuenta: se guarda el handle para que el cliente las pinte
function G.initquestlist(h) G.questlist = h end
function G.initquickkeywnd(h) G.quickkey = h end
function G.inittreasuremap(h) G.treasuremap = h end
-- linea de sistema en el chat (como el aviso del original)
function G.addsystemmessage(texto)
  local m = window.mundo
  if m and m.linea then m:linea(tostring(texto or '')) end
end
-- Ordenes al servidor desde los scripts (y desde el Lua que manda el servidor por el canal 0x01A0):
--   game.netcommand(cmd, a)      -> c2s 0x002E [u32 cmd][u32 a]
--   game.netcommand2(cmd, a, b)  -> c2s 0x002F [u8 cmd][u32 a][u32 b]   (ventanas propias: mall 173, subasta 160..165...)
-- main.lua pone G.enviar = function(mensaje) sesion:enviar(mensaje) end al conectar.
local function u32le(v)
  v = math.floor(tonumber(v) or 0) % 4294967296
  return string.char(v % 256, math.floor(v / 256) % 256, math.floor(v / 65536) % 256, math.floor(v / 16777216) % 256)
end
function G.netcommand(cmd, a)
  if G.enviar then G.enviar(string.char(0x2E, 0x00) .. u32le(cmd) .. u32le(a)) end
end
function G.netcommand2(cmd, a, b)
  if G.enviar then G.enviar(string.char(0x2F, 0x00, math.floor(tonumber(cmd) or 0) % 256) .. u32le(a) .. u32le(b)) end
end
-- Codigo Lua del servidor (s2c 0x01A0, server/canal_lua.py): se ejecuta en el entorno global, como los scripts.
function M.ejecutar(codigo)
  local f, err = loadstring(codigo, '=canal')
  if not f then window.trazas[#window.trazas + 1] = 'canal: ' .. tostring(err); return false end
  local ok, e = pcall(f)
  if not ok then window.trazas[#window.trazas + 1] = 'canal: ' .. tostring(e) end
  return ok
end
setmetatable(G, { __index = function(_, nombre)
  return function()
    G.faltantes[nombre] = (G.faltantes[nombre] or 0) + 1
  end
end })

-- Carpeta de los scripts: AO_LUAS, o 'luas' dentro del directorio de datos de LOVE / del paquete (portable: sin io.popen).
function M.leer_script(carpeta, nombre)
  if carpeta then
    local fh = io.open(carpeta .. '/' .. nombre, 'rb')
    if fh then local d = fh:read('*a'); fh:close(); return d end
  end
  if love.filesystem.getInfo('luas/' .. nombre) then return love.filesystem.read('luas/' .. nombre) end
end

function M.carpeta_luas() return os.getenv('AO_LUAS') or 'C:/trabajo/marcos/aolatam/extracted_luas' end

-- Carga todos los .lua de la carpeta (en el entorno global, como el cliente) y devuelve cuantos compilaron / fallaron.
function M.cargar(carpeta, lista)
  rawset(_G, 'window', window.api)
  rawset(_G, 'game', G)
  local an, al = love.graphics.getDimensions()
  rawset(_G, 'SYSTEM_SCREEN_WIDTH', an)
  rawset(_G, 'SYSTEM_SCREEN_HEIGHT', al)
  M.tam = { an, al }
  lista = lista or {}
  if #lista == 0 then for _, n in ipairs(SCRIPTS) do lista[#lista + 1] = n end end
  local ok, mal = 0, {}
  -- sys.lua y global.lua primero: definen las variables que usan los demas
  table.sort(lista, function(a, b)
    local pa = (a == 'global.lua' and 0) or (a == 'sys.lua' and 1) or 2
    local pb = (b == 'global.lua' and 0) or (b == 'sys.lua' and 1) or 2
    if pa ~= pb then return pa < pb end
    return a < b
  end)
  for _, f in ipairs(lista) do
    local src = M.leer_script(carpeta, f)
    local fn, err = loadstring(src or '', '@' .. f)
    if fn then
      local c, e = pcall(fn)
      if c then ok = ok + 1 else mal[#mal + 1] = f .. ': ' .. tostring(e) end
    else
      mal[#mal + 1] = f .. ': ' .. tostring(err)
    end
  end
  -- global.lua / sys.lua fijan SYSTEM_SCREEN_* a 800x600 por defecto: se vuelve a poner la medida real despues de cargarlos
  rawset(_G, 'SYSTEM_SCREEN_WIDTH', an)
  rawset(_G, 'SYSTEM_SCREEN_HEIGHT', al)
  return ok, mal
end

-- Recoloca la interfaz al cambiar el tamano de la ventana: los scripts originales calculan las posiciones (anclas al borde derecho/inferior)
-- una sola vez con SYSTEM_SCREEN_WIDTH/HEIGHT, asi que se destruyen las ventanas y se vuelve a montar la principal.
function M.relayout(handler)
  if os.getenv('AO_NDEBUG') then print('relayout', love.graphics.getDimensions()) end
  local an, al = love.graphics.getDimensions()
  rawset(_G, 'SYSTEM_SCREEN_WIDTH', an)
  rawset(_G, 'SYSTEM_SCREEN_HEIGHT', al)
  for i = #window.raices, 1, -1 do window.api.destroy(window.raices[i].h) end
  window.raices = {}
  -- las posiciones "recordadas" (WND_xxx_X / _Y) vuelven a -1 para que los scripts recalculen las anclas
  for k, v in pairs(_G) do
    if type(k) == 'string' and type(v) == 'number' and k:match('^WND_[%w_]+_[XY]$') then rawset(_G, k, -1) end
  end
  local ok, e = pcall(CreateMainWnd, handler or 1)
  if not ok then print('relayout', e) end
  M.tam = { an, al }
end

M.window, M.game = window, G
return M
