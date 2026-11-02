-- La ventana de la casa de subastas (el tablon 3501 de wnd03.xml, rehecho por tools/parche_subasta_ventana.py).
-- La manda el servidor por el canal 0x01A0 al abrirla (server/subasta_ventana.py); los datos llegan despues con
-- SubastaLista(...). Lo que pide la ventana va al servidor con game.netcommand2 (c2s 0x002F [u8 cmd][u32 a][u32 b]).
SUBASTA = SUBASTA or {}
local S = SUBASTA
local CMD_BUSCAR, CMD_COMPRAR, CMD_RETIRAR = 161, 162, 163
S.modo = S.modo or 0          -- 0 todo lo que esta en venta, 1 lo mio
S.cat = S.cat or 0
S.niv = S.niv or 0
S.pag = 1
S.paginas = 1
S.filas = {}
S.sel = -1
S.cant = 1

local function hijo(id)
  return window.find(WND_ADTRADE, id)
end

local function estado(texto)
  window.settitle(hijo(3517), texto)
end

local function pintar_pestanas()
  if S.modo == 0 then
    window.seticon(hijo(3502), 3085)
    window.seticon(hijo(3503), 3084)
    estado("Pick an item, set Qty. and press the check to buy.")
  else
    window.seticon(hijo(3502), 3084)
    window.seticon(hijo(3503), 3085)
    estado("Your items for sale: pick one and press the check to take it back.")
  end
end

function SubastaPedir()
  S.sel = -1
  game.netcommand2(CMD_BUSCAR, S.modo * 65536 + S.cat * 256 + S.niv, S.pag)
end

function SubastaAbrir(cats, nivs)
  S.cats = cats
  S.nivs = nivs
  if S.cat >= #cats then S.cat = 0 end
  if S.niv >= #nivs then S.niv = 0 end
  if window.isexist(WND_ADTRADE) then
    window.destroy(WND_ADTRADE)
  end
  WND_ADTRADE = window.create(3501, 0, 0, SYSTEM_HANDLER)
  window.move(WND_ADTRADE, SYSTEM_SCREEN_WIDTH / 2 - 399, SYSTEM_SCREEN_HEIGHT / 2 - 246)
  window.settitle(hijo(3524), cats[S.cat + 1])
  window.settitle(hijo(3527), nivs[S.niv + 1])
  window.show(hijo(3511), true)
  window.show(hijo(3551), false)
  pintar_pestanas()
  S.pag = 1
  SubastaPedir()
end

-- filas: {{id, nombre, cantidad, precio con comas, vendedor}, ...}
function SubastaLista(modo, pag, paginas, filas, oro)
  if not window.isexist(WND_ADTRADE) then
    return
  end
  S.modo = modo
  S.pag = pag
  S.paginas = paginas
  S.filas = filas
  S.sel = -1
  S.cant = 1
  local lista = hijo(3530)
  window.clearlist(lista)
  for i, f in ipairs(filas) do
    window.insertitemstr(lista, f[2], 0)
    window.setsubitemstr(lista, i - 1, 1, tostring(f[3]), 0)
    window.setsubitemstr(lista, i - 1, 2, f[4], 0)
    window.setsubitemstr(lista, i - 1, 3, f[5], 0)
  end
  window.settitle(hijo(3532), tostring(pag) .. " / " .. tostring(paginas))
  window.settitle(hijo(3538), "1")
  window.settitle(hijo(3534), oro)
  pintar_pestanas()
  if #filas == 0 then
    if modo == 0 then
      estado("Nothing for sale with these filters.")
    else
      estado("You have nothing for sale. Open a stall with the message AH to sell.")
    end
  end
end

function SubastaAviso(texto)
  if window.isexist(WND_ADTRADE) then
    estado(texto)
  end
end

-- Pestanas: All / Mine
function OnADTrade_ChaPage_Item(dwID, dwCmdID, dwParam, pParam)
  S.modo = 0
  S.pag = 1
  SubastaPedir()
  return 1
end

function OnADTrade_ChaPage_Player(dwID, dwCmdID, dwParam, pParam)
  S.modo = 1
  S.pag = 1
  SubastaPedir()
  return 1
end

-- Filtros: los desplegables de siempre, con las opciones que manda el servidor.
function OnADTrade_Item_ItemType(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_ITEMTYPE) then
    return 1
  end
  WND_ITEMTYPE = window.create(3581, window.parent(dwID), 0, 0)
  local list = window.find(WND_ITEMTYPE, 3582)
  for _, nombre in ipairs(S.cats) do
    window.insertitemstr(list, nombre, 0)
  end
  return 1
end

function OnADTrade_Item_SelectLV(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_SELECTLV) then
    return 1
  end
  WND_SELECTLV = window.create(3586, window.parent(dwID), 0, 0)
  local list = window.find(WND_SELECTLV, 3587)
  for _, nombre in ipairs(S.nivs) do
    window.insertitemstr(list, nombre, 0)
  end
  return 1
end

function OnADTrade_SelectItemType(dwID, dwCmdID, dwParam, pParam)
  if S.cats[dwParam + 1] then
    S.cat = dwParam
    window.settitle(hijo(3524), S.cats[dwParam + 1])
  end
  window.destroy(window.parent(dwID))
  S.pag = 1
  SubastaPedir()
  return 1
end

function OnADTrade_SelectLV(dwID, dwCmdID, dwParam, pParam)
  if S.nivs[dwParam + 1] then
    S.niv = dwParam
    window.settitle(hijo(3527), S.nivs[dwParam + 1])
  end
  window.destroy(window.parent(dwID))
  S.pag = 1
  SubastaPedir()
  return 1
end

function OnADTrade_Item_Search(dwID, dwCmdID, dwParam, pParam)
  S.pag = 1
  SubastaPedir()
  return 1
end

-- Paginas
function OnSubastaPagAnt(dwID, dwCmdID, dwParam, pParam)
  if S.pag > 1 then
    S.pag = S.pag - 1
    SubastaPedir()
  end
  return 1
end

function OnSubastaPagSig(dwID, dwCmdID, dwParam, pParam)
  if S.pag < S.paginas then
    S.pag = S.pag + 1
    SubastaPedir()
  end
  return 1
end

-- Elegir fila y cantidad
function OnSubastaFila(dwID, dwCmdID, dwParam, pParam)
  local f = S.filas[dwParam + 1]
  if not f then
    return 1
  end
  S.sel = dwParam
  S.cant = 1
  window.settitle(hijo(3538), "1")
  if S.modo == 0 then
    estado(f[2] .. " - " .. f[4] .. " each. Set Qty. and press the check.")
  else
    estado(f[2] .. " - press the check to take it back.")
  end
  return 1
end

local function poner_cantidad(n)
  local f = S.filas[S.sel + 1]
  if not f then
    return
  end
  if n < 1 then n = 1 end
  if n > f[3] then n = f[3] end
  S.cant = n
  window.settitle(hijo(3538), tostring(n))
end

function OnSubastaCantMenos(dwID, dwCmdID, dwParam, pParam)
  poner_cantidad(S.cant - 1)
  return 1
end

function OnSubastaCantMas(dwID, dwCmdID, dwParam, pParam)
  poner_cantidad(S.cant + 1)
  return 1
end

function OnSubastaAceptar(dwID, dwCmdID, dwParam, pParam)
  local f = S.filas[S.sel + 1]
  if not f then
    estado("Pick an item first.")
    return 1
  end
  if S.modo == 0 then
    game.netcommand2(CMD_COMPRAR, f[1], S.cant)
  else
    game.netcommand2(CMD_RETIRAR, f[1], 0)
  end
  return 1
end
