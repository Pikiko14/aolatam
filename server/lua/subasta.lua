-- La ventana de la casa de subastas (el tablon 3501 de wnd03.xml, rehecho por tools/parche_subasta_ventana.py).
-- La manda el servidor por el canal 0x01A0 al abrirla (server/subasta_ventana.py); los datos llegan despues con
-- SubastaLista(...). Lo que pide la ventana va al servidor con game.netcommand2 (c2s 0x002F [u8 cmd][u32 a][u32 b]).
-- El fondo de la pestana ya trae dibujada una rejilla de 10 filas: una fila por objeto, con su icono.
-- Tres pestanas: All (comprar), Mine (lo mio en venta: retirar) y Sell (la mochila: elegir, poner precio y publicar).
SUBASTA = SUBASTA or {}
WND_ADTRADE = WND_ADTRADE or 0    -- un numero: window.isexist(nil) da error (lo define adtrade.lua, pero por si acaso)
local S = SUBASTA
local CMD_BUSCAR, CMD_COMPRAR, CMD_RETIRAR, CMD_PREPARAR, CMD_PUBLICAR = 161, 162, 163, 164, 165
local TODO, MIO, VENDER = 0, 1, 2
local PESTANAS = {[TODO] = 3502, [MIO] = 3503, [VENDER] = 3594}
local VENTA = {3592, 3593, 3576}  -- "G  Qty:", precio y cantidad: solo en Sell (la casilla 3590 ensena lo elegido)
-- Las casillas con el icono de cada fila de la lista (la fila 1 es la primera tras la cabecera).
local ICONOS = {3595, 3596, 3597, 3598, 3599, 3606, 3607, 3608, 3609}
local SANGRIA = "       "         -- el nombre empieza despues de la casilla del icono
S.modo = S.modo or TODO
S.orden = S.orden or 0            -- 0 lo mas nuevo, 1 lo mas barato
S.cat = S.cat or 0
S.niv = S.niv or 0
S.pag = 1
S.paginas = 1
S.filas = {}
S.sel = -1
S.cant = 1
S.venta = nil                     -- lo elegido para vender: {ranura, item, nombre, max}

local function hijo(id)
  return window.find(WND_ADTRADE, id)
end

-- Recorta un texto a `n` letras con ".." al final: nada se sale de su columna o caja.
local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

local function estado(texto)
  window.settitle(hijo(3517), texto)
end

local function rotulo(texto)
  window.settitle(hijo(3591), corto(texto, 26))
end

local function limpiar_venta()
  S.venta = nil
  window.seticon(hijo(3590), 484)          -- la casilla vacia del juego
  window.settitle(hijo(3590), "")
  window.settitle(hijo(3593), "")
  window.settitle(hijo(3576), "")
end

local function pintar_pestanas()
  for modo, id in pairs(PESTANAS) do
    window.seticon(hijo(id), modo == S.modo and 59030 or 2734)   -- las del tema del cliente
  end
  for _, id in ipairs(VENTA) do
    window.show(hijo(id), S.modo == VENDER)
  end
  if S.modo == TODO then
    rotulo("Auction House")
    estado("Pick an item and press the check to buy it.")
  elseif S.modo == MIO then
    rotulo("Your items for sale")
    estado("Pick one and press the check to take it back.")
  elseif S.venta then
    rotulo(S.venta.nombre)
    estado("Write the price and Qty. up here, then the check.")
  else
    rotulo("Pick an item below")
    estado("Pick the item you want to sell.")
  end
end

function SubastaPedir()
  S.sel = -1
  game.netcommand2(CMD_BUSCAR, S.orden * 16777216 + S.modo * 65536 + S.cat * 256 + S.niv, S.pag)
end

local function cambiar_pestana(modo)
  S.modo = modo
  S.pag = 1
  limpiar_venta()
  pintar_pestanas()
  SubastaPedir()
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
  -- Los textos van aqui: wndtext03.xml (la traduccion) pisa los title del XML.
  window.settitle(WND_ADTRADE, "Auction House")
  for id, texto in pairs({[3502] = "All", [3503] = "Mine", [3594] = "Sell", [3522] = "New", [3542] = "Cheap",
                          [3523] = "Category", [3526] = "Level", [3592] = "G   Qty:"}) do
    window.settitle(hijo(id), texto)
  end
  for _, id in ipairs({3512, 3513, 3514, 3515, 3516}) do
    window.show(hijo(id), false)
  end
  window.setradio(hijo(3520), S.orden)
  window.settitle(hijo(3524), cats[S.cat + 1])
  window.settitle(hijo(3527), nivs[S.niv + 1])
  window.show(hijo(3511), true)
  window.show(hijo(3551), false)
  cambiar_pestana(TODO)
end

-- filas: {{id, nombre, cantidad, precio, vendedor, item}, ...}; en Sell el id es la ranura de la mochila y el
-- precio y el vendedor van vacios. total = cuantas hay con estos filtros.
function SubastaLista(modo, pag, paginas, filas, oro, total)
  if not window.isexist(WND_ADTRADE) then
    return
  end
  S.modo = modo
  S.pag = pag
  S.paginas = paginas
  S.filas = filas
  S.sel = -1
  if not S.venta then
    S.cant = 1
  end
  local lista = hijo(3530)
  window.clearlist(lista)
  -- La primera fila es la cabecera: dice que es cada columna. Elegirla no hace nada (OnSubastaFila).
  window.insertitemstr(lista, "Item", 0)
  if modo == VENDER then
    window.setsubitemstr(lista, 0, 0, "Qty.", 0)
    window.setsubitemstr(lista, 0, 1, "", 0)
    window.setsubitemstr(lista, 0, 2, "", 0)
  else
    window.setsubitemstr(lista, 0, 0, "Qty.", 0)
    window.setsubitemstr(lista, 0, 1, "Price each", 0)
    window.setsubitemstr(lista, 0, 2, "Seller", 0)
  end
  -- Los iconos van en sus casillas (ICONOS), no en la lista: insertitemstrappnum pintaba ademas un numero sin
  -- sentido junto al nombre.
  for k, id in ipairs(ICONOS) do
    local f = filas[k]
    if f then
      window.seticon(hijo(id), game.getitemicon(f[6]))
      window.settitle(hijo(id), f[3] > 1 and tostring(f[3]) or "")
    else
      window.seticon(hijo(id), 0)
      window.settitle(hijo(id), "")
    end
  end
  for i, f in ipairs(filas) do
    -- Cuatro columnas de ~195 px: el nombre (tras la casilla del icono) cabe en 14 letras y el vendedor en 18.
    window.insertitemstr(lista, SANGRIA .. corto(f[2], 14), 0)
    window.setsubitemstr(lista, i, 0, "x" .. tostring(f[3]), 0)
    window.setsubitemstr(lista, i, 1, f[4] ~= "" and (f[4] .. " G") or "", 0)
    window.setsubitemstr(lista, i, 2, corto(f[5], 18), 0)
  end
  window.settitle(hijo(3532), tostring(pag) .. " / " .. tostring(paginas))
  window.settitle(hijo(3538), tostring(S.cant))
  window.settitle(hijo(3534), oro)
  if modo == VENDER then
    window.settitle(hijo(3535), tostring(total or #filas) .. " items")
  else
    window.settitle(hijo(3535), tostring(total or #filas) .. " listed")
  end
  pintar_pestanas()
  if #filas == 0 and not S.venta then
    if modo == TODO then
      estado("Nothing for sale with these filters.")
    elseif modo == MIO then
      estado("You have nothing for sale. Use the Sell tab.")
    else
      estado("Nothing in your backpack can be sold here.")
    end
  end
end

function SubastaAviso(texto)
  if window.isexist(WND_ADTRADE) then
    estado(texto)
  end
end

-- Vender: el objeto elegido en Sell, ya comprobado por el servidor.
function SubastaPreparada(ranura, item, nombre, max)
  if not window.isexist(WND_ADTRADE) then
    return
  end
  S.venta = {ranura = ranura, item = item, nombre = nombre, max = max}
  S.cant = 1                                      -- empieza en 1: se escribe en 3576 o se sube con las flechas
  window.seticon(hijo(3590), game.getitemicon(item))
  window.settitle(hijo(3590), max > 1 and tostring(max) or "")
  window.settitle(hijo(3538), "1")
  window.settitle(hijo(3576), "1")
  pintar_pestanas()
  window.setfocus(hijo(3593))
end

function SubastaPublicada(texto)
  if window.isexist(WND_ADTRADE) then
    limpiar_venta()
    pintar_pestanas()
    estado(texto)
  end
end

-- Pestanas
function OnADTrade_ChaPage_Item(dwID, dwCmdID, dwParam, pParam)
  cambiar_pestana(TODO)
  return 1
end

function OnADTrade_ChaPage_Player(dwID, dwCmdID, dwParam, pParam)
  cambiar_pestana(MIO)
  return 1
end

function OnSubastaPestanaVender(dwID, dwCmdID, dwParam, pParam)
  cambiar_pestana(VENDER)
  return 1
end

-- Orden: los dos circulos de arriba (eran Sell / Buy).
function OnADTrade_Item_BuyType(dwID, dwCmdID, dwParam, pParam)
  S.orden = window.getappdata(dwID)
  window.setradio(hijo(3520), S.orden)
  S.pag = 1
  SubastaPedir()
  return 1
end

-- Los dos botones de arriba (eran susurro y carta): susurrar al vendedor y refrescar.
function OnSubastaSusurrar(dwID, dwCmdID, dwParam, pParam)
  local f = S.filas[S.sel + 1]
  if f and S.modo == TODO then
    SetTell(f[5])
  else
    estado("Pick an item in All to whisper its seller.")
  end
  return 1
end

function OnSubastaRefrescar(dwID, dwCmdID, dwParam, pParam)
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
-- Pulsar el icono de una fila es como pulsar la fila.
-- Al pasar el cursor por la casilla de una fila: la ficha del item (game.setitemtooltip, como loginreward.lua).
function OnSubastaTooltip(dwID, dwCmdID, dwParam, pParam)
  local f = S.filas and S.filas[window.getappdata(dwID)]
  if f then
    game.setitemtooltip(dwID, f[6])
  end
  return 1
end

function OnSubastaIcono(dwID, dwCmdID, dwParam, pParam)
  return OnSubastaFila(dwID, dwCmdID, window.getappdata(dwID), pParam)
end

function OnSubastaFila(dwID, dwCmdID, dwParam, pParam)
  local f = S.filas[dwParam]          -- la fila 0 es la cabecera
  if not f then
    return 1
  end
  S.sel = dwParam - 1
  S.cant = 1
  window.settitle(hijo(3538), "1")
  if S.modo == VENDER then
    -- El servidor lo comprueba y contesta SubastaPreparada (o un aviso de por que no se puede).
    game.netcommand2(CMD_PREPARAR, f[1], f[6])
    return 1
  end
  rotulo(f[2])
  window.seticon(hijo(3590), game.getitemicon(f[6]))
  window.settitle(hijo(3590), f[3] > 1 and tostring(f[3]) or "")
  if S.modo == TODO then
    estado(f[4] .. " G each. Set Qty. and press the check.")
  else
    estado("Press the check to take it back.")
  end
  return 1
end

local function poner_cantidad(n)
  local max
  if S.modo == VENDER and S.venta then
    max = S.venta.max
  elseif S.modo == TODO and S.filas[S.sel + 1] then
    max = S.filas[S.sel + 1][3]
  else
    return
  end
  if n < 1 then n = 1 end
  if n > max then n = max end
  S.cant = n
  window.settitle(hijo(3538), tostring(n))
  if S.modo == VENDER and S.venta then
    window.settitle(hijo(3576), tostring(n))
  end
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
  -- La cantidad escrita a mano, dentro de lo que hay.
  if S.modo == VENDER and S.venta then
    poner_cantidad(tonumber(window.gettitle(hijo(3576))) or S.cant)
  end
  if S.modo == VENDER then
    if not S.venta then
      estado("Pick the item you want to sell.")
      return 1
    end
    local precio = tonumber(window.gettitle(hijo(3593))) or 0
    if precio <= 0 then
      estado("Write the price for each unit first.")
      window.setfocus(hijo(3593))
      return 1
    end
    game.netcommand2(CMD_PUBLICAR, S.venta.ranura * 65536 + S.cant, precio)
    return 1
  end
  local f = S.filas[S.sel + 1]
  if not f then
    estado("Pick an item first.")
    return 1
  end
  if S.modo == TODO then
    game.netcommand2(CMD_COMPRAR, f[1], S.cant)
  else
    game.netcommand2(CMD_RETIRAR, f[1], 0)
  end
  return 1
end
