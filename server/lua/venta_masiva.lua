-- Bulk Sell de la tienda NPC (13/11/2026): la pestana "Bulk" de la ventana 13401 (tools/parche_venta_masiva.py).
-- La lista la lleva el servidor (server/app.py, _venta_masiva): todo el gear y las armas de la mochila, marcados.
-- Pulsar una fila la marca o desmarca; el check (13409) vende lo marcado. Comando 172 de game.netcommand2:
--   172, 1, 0  abrir la pestana    172, 2, fila  marcar/desmarcar    172, 3, 0  vender
VENTA_MASIVA = VENTA_MASIVA or {}
local V = VENTA_MASIVA
local CMD = 172
local PAG_COMPRA, PAG_VENTA, PAG_MASIVA = 13404, 13405, 13407
local BTN_COMPRA, BTN_VENTA, BTN_MASIVA = 13402, 13403, 13406
ICONO_SI, ICONO_NO = 60500, 60501

local function hijo(id)
  if not V.wnd or not window.isexist(V.wnd) then
    V.wnd = WND_NPCSALE
  end
  return window.find(V.wnd, id)
end

-- La lista y sus textos van dentro de la pagina 13407: se buscan desde ella.
local function de_pagina(id)
  return window.find(hijo(PAG_MASIVA), id)
end

local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

local function pagina(cual, quien)
  if quien then
    V.wnd = window.parent(quien)
  end
  window.show(hijo(PAG_COMPRA), cual == PAG_COMPRA)
  window.show(hijo(PAG_VENTA), cual == PAG_VENTA)
  window.show(hijo(PAG_MASIVA), cual == PAG_MASIVA)
  window.seticon(hijo(BTN_COMPRA), cual == PAG_COMPRA and 3085 or 3084)
  window.seticon(hijo(BTN_VENTA), cual == PAG_VENTA and 3085 or 3084)
  window.seticon(hijo(BTN_MASIVA), cual == PAG_MASIVA and 3085 or 3084)
end

-- Las dos pestanas de siempre (sale.lua) tambien tienen que esconder la nueva.
function OnNPCSale_ChaPage_Buy2(dwID, dwCmdID, dwParam, pParam)
  pagina(PAG_COMPRA, dwID)
  return 1
end

function OnNPCSale_ChaPage_Sale2(dwID, dwCmdID, dwParam, pParam)
  pagina(PAG_VENTA, dwID)
  return 1
end

function OnNPCSale_ChaPage_Bulk(dwID, dwCmdID, dwParam, pParam)
  pagina(PAG_MASIVA, dwID)
  window.settitle(de_pagina(13414), "Loading...")
  game.netcommand2(CMD, 1, 0)
  return 1
end

-- filas: {{marcada (1/0), nombre, precio}, ...}
function VentaMasivaLista(filas, total, oro)
  if not V.wnd or not window.isexist(V.wnd) then
    return
  end
  local lista = de_pagina(13408)
  window.clearlist(lista)
  local n = 0
  -- Como la lista de Sell: una fila por marco y en la casilla el icono del objeto (f[4], de itemicon*.xml; si no
  -- tiene, el de marcado 60500 / 60501). Lo que se vende o se queda va en el texto.
  for i, f in ipairs(filas) do
    local icono = f[4]
    if not icono or icono <= 0 then
      icono = f[1] == 1 and ICONO_SI or ICONO_NO
    end
    if f[1] == 1 then
      n = n + 1
      window.insertitemstrappnum(lista, "Sell: " .. corto(f[2], 20) .. " - " .. tostring(f[3]) .. " G", icono, i - 1)
    else
      window.insertitemstrappnum(lista, "Keep: " .. corto(f[2], 20), icono, i - 1)
    end
  end
  window.settitle(de_pagina(13413), tostring(total))
  window.settitle(de_pagina(13417), tostring(oro or 0))
  if #filas == 0 then
    window.settitle(de_pagina(13414), "Nothing to sell")
  else
    window.settitle(de_pagina(13414), tostring(n) .. " of " .. tostring(#filas) .. " selected")
  end
end

function OnVentaMasivaFila(dwID, dwCmdID, dwParam, pParam)
  local i = window.getcheckitem(dwID)
  if i and i >= 0 then
    game.netcommand2(CMD, 2, i)
  end
  return 1
end

function OnVentaMasivaVender(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD, 3, 0)
  return 1
end
