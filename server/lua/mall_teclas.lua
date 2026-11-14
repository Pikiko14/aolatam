-- Alt+I y el icono del Item Mall abren el Item Mall nuevo (14/11/2026, "al presionar alt i o el icono de item mall
-- debe abrir este"). El icono de la barra (wnd01.xml, 12600) llama a OnCommandMall (script\command.l), que llama a
-- CreateMallWnd (script\mall.l); Alt+I es la accion 0x1A del exe (0x5B7706), que llama a CreateMallWnd. Las dos piden
-- al servidor la ventana 61000 (server/mall_nuevo.py, comando 173, accion 1; b = 1 tecla, 2 icono).
-- Los scripts del juego pueden volver a definir esas dos funciones despues de esto: por eso no se guardan en _G sino
-- que salen de su metatabla (__index), y si alguien las redefine (__newindex) lo suyo va a AOLAT_MALL_ORIG.
local CMD = 173

local function abierta()
  return WND_AOLAT_MALL ~= nil and WND_AOLAT_MALL ~= 0 and window.isexist(WND_AOLAT_MALL)
end

local NUESTRAS = {}

-- El icono: abre, o cierra si ya estaba abierta.
NUESTRAS.OnCommandMall = function(dwID, dwCmdID, dwParam, pParam)
  if abierta() and OnMallCerrar then
    OnMallCerrar()
  else
    game.netcommand2(CMD, 1, 2)
  end
  return 1
end

-- Alt+I (y lo que el juego use para abrir su mall): abre, o cierra si ya estaba abierta.
NUESTRAS.CreateMallWnd = function()
  if abierta() and OnMallCerrar then
    OnMallCerrar()
  else
    game.netcommand2(CMD, 1, 1)
  end
  return 0
end

AOLAT_MALL_NUESTRAS = NUESTRAS
AOLAT_MALL_ORIG = AOLAT_MALL_ORIG or {}
for k, f in pairs(NUESTRAS) do
  local v = rawget(_G, k)
  if v ~= nil then
    AOLAT_MALL_ORIG[k] = v
  end
  rawset(_G, k, nil)
end

if not AOLAT_MALL_GUARDA then
  AOLAT_MALL_GUARDA = 1
  local mt = getmetatable(_G) or {}
  local idx, nidx = mt.__index, mt.__newindex
  mt.__index = function(t, k)
    local f = AOLAT_MALL_NUESTRAS[k]
    if f then
      return f
    end
    if type(idx) == "function" then
      return idx(t, k)
    elseif idx then
      return idx[k]
    end
    return nil
  end
  mt.__newindex = function(t, k, v)
    if AOLAT_MALL_NUESTRAS[k] then
      AOLAT_MALL_ORIG[k] = v
      return
    end
    if type(nidx) == "function" then
      return nidx(t, k, v)
    elseif nidx then
      nidx[k] = v
      return
    end
    rawset(t, k, v)
  end
  setmetatable(_G, mt)
end
