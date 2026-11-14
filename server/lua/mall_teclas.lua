-- Alt+I y el icono del Item Mall abren el Item Mall nuevo (14/11/2026, "al presionar alt i o el icono de item mall
-- debe abrir este"). El icono de la barra (wnd01.xml, 12600) llama a OnCommandMall; el exe, para abrir su mall, llama a
-- CreateMallWnd. Las dos piden al servidor la ventana 61000 (server/mall_nuevo.py, comando 173, accion 1), que llega
-- con su Lua. La ventana vieja ya no se crea: WND_MALL se queda sin ventana y el exe no la refresca.
local CMD = 173

local function abierta()
  return WND_AOLAT_MALL ~= nil and WND_AOLAT_MALL ~= 0 and window.isexist(WND_AOLAT_MALL)
end

local function pedir()
  game.netcommand2(CMD, 1, 0)
end

-- El icono y la tecla: abre, o cierra si ya estaba abierta.
function OnCommandMall(dwID, dwCmdID, dwParam, pParam)
  if abierta() and OnMallCerrar then
    OnMallCerrar()
  else
    pedir()
  end
  return 1
end

-- Lo que llama el exe para su mall: solo abre (si ya esta abierta, la trae al frente).
function CreateMallWnd()
  if abierta() then
    window.setforeground(WND_AOLAT_MALL)
  else
    pedir()
  end
  return 0
end
