-- La bendicion de la Torre de Babel roguelike (server/torre_roguelike.py; ventana 58960 de tools/ventana_mecanicas.py).
-- Tres cartas: el nombre es el boton; debajo lo bueno (verde) y lo malo (rojo). El clic va con game.netcommand2(179, i).
local CMD_TR = 179
WND_TB = WND_TB or 0
local TB_TITULO, TB_PIE, TB_NOMBRE, TB_BUENO, TB_MALO = 58961, 58962, 58963, 58966, 58969

local function tb(id)
  return window.find(WND_TB, id)
end

local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

function TBAbrir(titulo, opciones, pie)
  if window.isexist(WND_TB) then
    window.setforeground(WND_TB)
  else
    WND_TB = window.create(58960, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_TB) then
      return
    end
    window.move(WND_TB, SYSTEM_SCREEN_WIDTH / 2 - 222, 140)
  end
  window.settitle(WND_TB, "Tower Blessing")
  window.settitle(tb(TB_TITULO), corto(titulo, 70))
  window.settitle(tb(TB_PIE), corto(pie, 80))
  for i = 0, 2 do
    local o = opciones[i + 1]
    window.show(tb(TB_NOMBRE + i), o ~= nil)
    window.show(tb(TB_BUENO + i), o ~= nil)
    window.show(tb(TB_MALO + i), o ~= nil)
    if o then
      window.settitle(tb(TB_NOMBRE + i), corto(o[1], 20))
      window.settitle(tb(TB_BUENO + i), corto(o[2], 24))
      window.settitle(tb(TB_MALO + i), corto(o[3], 24))
    end
  end
end

function TBCerrar()
  if window.isexist(WND_TB) then
    window.destroy(WND_TB)
  end
  WND_TB = 0
end

function OnTorreBendicion(dwID, dwCmdID, dwParam, pParam)
  for i = 0, 2 do
    if tb(TB_NOMBRE + i) == dwID then
      game.netcommand2(CMD_TR, i + 1, 0)
      TBCerrar()
      return 1
    end
  end
  return 1
end
