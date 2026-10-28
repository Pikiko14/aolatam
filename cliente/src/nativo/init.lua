-- Arranque de los scripts originales del cliente sobre la capa nativa (window.* / game.*).
local M = {}
local window = require('src.nativo.window')

-- Scripts originales del cliente (se ignoran los que falten).
local SCRIPTS = { 'achievement.lua', 'actboard.lua', 'adtrade.lua', 'autoassist.lua', 'autofight.lua', 'automall.lua', 'autoother.lua', 'autopet.lua', 'autosupply.lua', 'bank.lua', 'battlefield.lua', 'battlepass.lua', 'captcha.lua', 'card.lua', 'charinfo.lua', 'chat.lua', 'collection.lua', 'command.lua', 'cutesung.lua', 'dailyevent.lua', 'dead.lua', 'emotion.lua', 'equip.lua', 'exchange.lua', 'farm.lua', 'finaltower.lua', 'fjjtestwnd04.lua', 'friend.lua', 'fuse.lua', 'game01.lua', 'game02.lua', 'game03.lua', 'game04.lua', 'gather.lua', 'global.lua', 'group.lua', 'guild.lua', 'gvg.lua', 'house.lua', 'item.lua', 'jumpmap.lua', 'loginreward.lua', 'mail.lua', 'main.lua', 'make.lua', 'mall.lua', 'marry.lua', 'message.lua', 'onlinereward.lua', 'petinfo.lua', 'pvp.lua', 'quest.lua', 'question.lua', 'quickcmd.lua', 'repair.lua', 'roulette.lua', 'safepwd.lua', 'safeverify.lua', 'sale.lua', 'salon.lua', 'skill.lua', 'skills.lua', 'starcard.lua', 'sys.lua', 'system.lua', 'test.lua', 'trade.lua', 'tuition.lua', 'word.lua' }

local G = { faltantes = {}, defs = {}, itemwnds = {} }
function G.isdef(nombre) return G.defs[nombre] == true end
function G.getstring() return '' end
function G.openmap(_, h) G.minimapa = h end
function G.friendwnd(h) G.amigos_wnd = h end
function G.inititemwnd(h, tipo)
  G.itemwnds = G.itemwnds or {}
  G.itemwnds[h] = G.itemwnds[h] or {}
  G.itemwnds[h][tipo or 0] = true
  if (tipo or 0) == 0 then G.itemwnd = h end
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
