-- El panel de las misiones diarias (server/misiones_diarias.py): la ventana 58800 de wnd03.xml (tools/ventana_misiones.py).
-- El servidor llama a MDAbrir y MDDatos; el boton de la barra (59007) contesta con game.netcommand2(176, 1, 0).
local CMD_MD = 176
WND_MD = WND_MD or 0

local L_TITULO, L_RACHA, L_RACHA2, L_PIE = 58801, 58802, 58803, 58804
local L_TEXTO, L_ESTADO, L_BARRA = 58810, 58820, 58830
local MW = 428

local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

local function en(id)
  return window.find(WND_MD, id)
end

-- titulo, racha, racha2, pie: textos; filas: {{texto, estado, porcentaje}, ...} (3 diarias y 3 semanales).
function MDDatos(titulo, racha, racha2, pie, filas)
  if not window.isexist(WND_MD) then
    game.netcommand2(CMD_MD, 0, 0)               -- la cerraron con la X: que el servidor deje de mandar
    return
  end
  window.settitle(en(L_TITULO), corto(titulo, 70))
  window.settitle(en(L_RACHA), corto(racha, 70))
  window.settitle(en(L_RACHA2), corto(racha2, 75))
  window.settitle(en(L_PIE), corto(pie, 80))
  for i = 0, 5 do
    local f = filas[i + 1]
    window.show(en(L_TEXTO + i), f ~= nil)
    window.show(en(L_ESTADO + i), f ~= nil)
    window.show(en(L_BARRA + i), f ~= nil)
    if f then
      window.settitle(en(L_TEXTO + i), corto(f[1], 46))
      window.settitle(en(L_ESTADO + i), corto(f[2], 18))
      window.setrange(en(L_BARRA + i), 0, 100)
      window.setpos(en(L_BARRA + i), f[3])
    end
  end
end

function MDAbrir(titulo, racha, racha2, pie, filas)
  if window.isexist(WND_MD) then
    window.setforeground(WND_MD)
  else
    WND_MD = window.create(58800, 0, 0, SYSTEM_HANDLER)
    -- Al servidor: 8 = creada, 9 = no se pudo (cliente sin el parche): entonces lo manda por el chat.
    game.netcommand2(CMD_MD, window.isexist(WND_MD) and 8 or 9, WND_MD or 0)
    if not window.isexist(WND_MD) then
      return
    end
    window.move(WND_MD, SYSTEM_SCREEN_WIDTH / 2 - MW / 2, 110)
    window.regsetting(WND_MD, "WND_MISIONES")      -- recuerda donde la deja el jugador
  end
  window.settitle(WND_MD, "Daily Missions")
  MDDatos(titulo, racha, racha2, pie, filas)
end

function MDCerrar()
  if window.isexist(WND_MD) then
    window.destroy(WND_MD)
  end
  WND_MD = 0
end
