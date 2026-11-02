-- La ventana de la casa de subastas (el tablon 3501 de wnd03.xml, rehecho por tools/parche_subasta_ventana.py).
-- La manda el servidor por el canal 0x01A0 al abrirla (server/subasta_ventana.py); los datos llegan despues con
-- SubastaLista(...). Lo que pide la ventana va al servidor con game.netcommand2 (c2s 0x002F [u8 cmd][u32 a][u32 b]).
-- El fondo de la pestana ya trae dibujada una rejilla de 10 filas: una publicacion por fila, con su icono.
SUBASTA = SUBASTA or {}
local S = SUBASTA
local CMD_BUSCAR, CMD_COMPRAR, CMD_RETIRAR, CMD_PREPARAR, CMD_PUBLICAR = 161, 162, 163, 164, 165
local CMD_DIAG = 167             -- diagnostico de soltar: queda en el log del servidor
local VENTA = {3590, 3592, 3593}  -- casilla, "G each" y precio: solo en Mine
S.modo = S.modo or 0              -- 0 todo lo que esta en venta, 1 lo mio
S.orden = S.orden or 0            -- 0 lo mas nuevo, 1 lo mas barato
S.cat = S.cat or 0
S.niv = S.niv or 0
S.pag = 1
S.paginas = 1
S.filas = {}
S.sel = -1
S.cant = 1
S.venta = nil                     -- lo soltado en la casilla: {ranura, item, nombre, max}

local function hijo(id)
  return window.find(WND_ADTRADE, id)
end

local function estado(texto)
  window.settitle(hijo(3517), texto)
end

local function rotulo(texto)
  window.settitle(hijo(3591), texto)
end

local function limpiar_venta()
  S.venta = nil
  window.seticon(hijo(3590), 484)          -- la casilla vacia del juego
  window.settitle(hijo(3590), "")
  window.settitle(hijo(3593), "")
end

local function pintar_pestanas()
  for _, id in ipairs(VENTA) do
    window.show(hijo(id), S.modo == 1)
  end
  if S.modo == 0 then
    window.seticon(hijo(3502), 3085)
    window.seticon(hijo(3503), 3084)
    rotulo("Auction House")
    estado("Pick an item and press the check to buy it.")
  else
    window.seticon(hijo(3502), 3084)
    window.seticon(hijo(3503), 3085)
    if S.venta then
      rotulo(S.venta.nombre)
      estado("Write the price, set Qty. and press the check.")
    else
      rotulo("<- Drag an item here to sell it")
      estado("Drag an item to the box, or pick one to take back.")
    end
  end
end

function SubastaPedir()
  S.sel = -1
  game.netcommand2(CMD_BUSCAR, S.orden * 16777216 + S.modo * 65536 + S.cat * 256 + S.niv, S.pag)
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
  for id, texto in pairs({[3502] = "All", [3503] = "Mine", [3522] = "New", [3542] = "Cheap", [3523] = "Category",
                          [3526] = "Level", [3592] = "G each"}) do
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
  limpiar_venta()
  pintar_pestanas()
  S.pag = 1
  SubastaPedir()
end

-- filas: {{id, nombre, cantidad, precio con comas, vendedor, item}, ...}; total = publicaciones con estos filtros.
function SubastaLista(modo, pag, paginas, filas, oro, total)
  if not window.isexist(WND_ADTRADE) then
    return
  end
  S.modo = modo
  S.pag = pag
  S.paginas = paginas
  S.filas = filas
  S.sel = -1
  if not (modo == 1 and S.venta) then
    S.cant = 1
  end
  local lista = hijo(3530)
  window.clearlist(lista)
  for i, f in ipairs(filas) do
    window.insertitemstrappnum(lista, f[2], game.getitemicon(f[6]), f[1])
    window.setsubitemstr(lista, i - 1, 1, "x" .. tostring(f[3]), 0)
    window.setsubitemstr(lista, i - 1, 2, f[4] .. " G", 0)
    window.setsubitemstr(lista, i - 1, 3, f[5], 0)
  end
  window.settitle(hijo(3532), tostring(pag) .. " / " .. tostring(paginas))
  window.settitle(hijo(3538), tostring(S.cant))
  window.settitle(hijo(3534), oro)
  window.settitle(hijo(3535), tostring(total or #filas) .. " listed")
  pintar_pestanas()
  if #filas == 0 and not S.venta then
    if modo == 0 then
      estado("Nothing for sale with these filters.")
    else
      estado("Nothing for sale yet: drag an item to the box.")
    end
  end
end

function SubastaAviso(texto)
  if window.isexist(WND_ADTRADE) then
    estado(texto)
  end
end

-- Vender: el objeto soltado en la casilla, ya comprobado por el servidor.
function SubastaPreparada(ranura, item, nombre, max)
  if not window.isexist(WND_ADTRADE) then
    return
  end
  S.venta = {ranura = ranura, item = item, nombre = nombre, max = max}
  S.sel = -1
  S.cant = max
  window.seticon(hijo(3590), game.getitemicon(item))
  window.settitle(hijo(3590), max > 1 and tostring(max) or "")
  window.settitle(hijo(3538), tostring(max))
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

function OnSubastaSoltar(dwID, dwCmdID, dwParam, pParam)
  -- Lo primero, avisar de que el juego llamo aqui (167 1): si no llega nada al servidor es que no se llama.
  game.netcommand2(CMD_DIAG, 1, pParam or 0)
  local ok, item, tipo, conjunto, ranura, n = pcall(game.getdropdata, pParam)
  if not ok then
    game.netcommand2(CMD_DIAG, 2, 0)             -- getdropdata fallo
    return 1
  end
  game.netcommand2(CMD_DIAG, 3, tonumber(ranura) or 99999)
  ranura = tonumber(ranura)
  if ranura == nil or ranura < 0 then
    ranura = 65535
  end
  if S.modo ~= 1 then                            -- soltado en All: pasa a Mine
    S.modo = 1
    S.pag = 1
    SubastaPedir()
  end
  game.netcommand2(CMD_PREPARAR, ranura + 65536 * ((tonumber(tipo) or 0) % 256), tonumber(item) or 0)
  return 1
end

function OnSubastaQuitar(dwID, dwCmdID, dwParam, pParam)
  limpiar_venta()
  pintar_pestanas()
  return 1
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
  if f then
    SetTell(f[5])
  else
    estado("Pick an item to whisper its seller.")
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
function OnSubastaFila(dwID, dwCmdID, dwParam, pParam)
  local f = S.filas[dwParam + 1]
  if not f then
    return 1
  end
  if S.venta then
    limpiar_venta()
  end
  S.sel = dwParam
  S.cant = 1
  window.settitle(hijo(3538), "1")
  rotulo(f[2])
  if S.modo == 0 then
    estado(f[4] .. " G each. Set Qty. and press the check.")
  else
    estado("Press the check to take it back.")
  end
  return 1
end

local function poner_cantidad(n)
  local max
  if S.modo == 1 and S.venta then
    max = S.venta.max
  elseif S.filas[S.sel + 1] then
    max = S.filas[S.sel + 1][3]
  else
    return
  end
  if n < 1 then n = 1 end
  if n > max then n = max end
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
  if S.modo == 1 and S.venta then
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
  if S.modo == 0 then
    game.netcommand2(CMD_COMPRAR, f[1], S.cant)
  else
    game.netcommand2(CMD_RETIRAR, f[1], 0)
  end
  return 1
end
