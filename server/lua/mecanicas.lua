-- La ventana Challenges (57000, tools/ventana_mecanicas.py; server/mecanicas_ui.py): Contracts, Pet Tournament y
-- Hardcore. El servidor manda CHAbrir / CHDatos(pestana, datos); los botones van con game.netcommand2(180, a, b).
local CMD_CH = 180
WND_CH = WND_CH or 0
CH = CH or {pestana = 1}

local TABS = {57001, 57002, 57003}
local AYUDA = 57004
local C_FILA, C_BOTON = 57010, 57016
local GRUPOS = {
  {57010, 57011, 57012, 57013, 57014, 57015, 57016, 57017, 57018, 57019, 57020, 57021, 57022, 57023, 57024, 57025,
   57026, 57027, 57028, 57029, 57030, 57031, 57032, 57033, 57034, 57035, 57036, 57037, 57038, 57039},
  {57040, 57041, 57042, 57043, 57044, 57045, 57046, 57047, 57048, 57050, 57051, 57052, 57053, 57054, 57055, 57056, 57057},
  {57060, 57061, 57062, 57063, 57064, 57065, 57066, 57067, 57068, 57069, 57070, 57071, 57072, 57073, 57074},
}

local function ch(id)
  return window.find(WND_CH, id)
end

local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

local function lineas(base, n, lista, largo)
  for i = 0, n - 1 do
    window.settitle(ch(base + i), corto((lista or {})[i + 1] or "", largo))
  end
end

local function mandar_texto(texto, base)
  for t = 0, 3 do
    local v = 0
    for k = 4, 1, -1 do
      v = v * 256 + (string.byte(texto, t * 4 + k) or 0)
    end
    game.netcommand2(CMD_CH, base + t, v)
  end
end

function OnCommandChallenges(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_CH, 1, CH.pestana or 1)
  return 1
end

-- d: la pestana 1 {ayuda, filas {{texto, boton}}, pagina, tipo, resultado, con_cantidad}
--                2 {ayuda, lineas, estrategias_visibles, salir_visible, resultados}
--                3 {ayuda, lineas, empezar_visible, ranking}
function CHDatos(pestana, d)
  if not window.isexist(WND_CH) then
    game.netcommand2(CMD_CH, 0, 0)
    return
  end
  CH.pestana = pestana
  for i = 1, 3 do
    window.seticon(ch(TABS[i]), i == pestana and 57098 or 57099)   -- la elegida, encendida
  end
  for g = 1, 3 do
    for _, id in ipairs(GRUPOS[g]) do
      window.show(ch(id), g == pestana)
    end
  end
  window.settitle(ch(AYUDA), corto(d[1], 72))
  if pestana == 1 then
    for i = 0, 5 do
      local f = d[2][i + 1]
      window.settitle(ch(C_FILA + i), corto(f and f[1] or "", 56))
      window.show(ch(C_BOTON + i), f ~= nil and f[2] ~= "")
      window.settitle(ch(C_BOTON + i), f and f[2] or "")
    end
    window.settitle(ch(57024), corto(d[3], 60))
    window.settitle(ch(57025), d[4])
    window.settitle(ch(57030), corto(d[5], 72))
    window.show(ch(57031), d[6] == 1)
    window.show(ch(57032), d[6] == 1)
    window.show(ch(57038), d[6] == 1)
  elseif pestana == 2 then
    lineas(57040, 5, d[2], 72)
    for i = 0, 2 do
      window.show(ch(57045 + i), d[3] == 1)
    end
    window.show(ch(57048), d[4] == 1)
    lineas(57050, 8, d[5], 74)
  else
    lineas(57060, 4, d[2], 72)
    window.show(ch(57064), d[3] == 1)
    lineas(57065, 10, d[4], 74)
  end
end

function CHAbrir(pestana, d)
  if window.isexist(WND_CH) then
    window.setforeground(WND_CH)
  else
    WND_CH = window.create(57000, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_CH) then
      game.netcommand2(CMD_CH, 9, 0)
      return
    end
    window.move(WND_CH, SYSTEM_SCREEN_WIDTH / 2 - 224, 100)
    window.regsetting(WND_CH, "WND_CHALLENGES")
  end
  window.settitle(WND_CH, "Challenges")
  CHDatos(pestana, d)
end

local function cual(dwID, base, n)
  for i = 0, n - 1 do
    if ch(base + i) == dwID then
      return i
    end
  end
  return -1
end

function OnCHPestana(dwID, dwCmdID, dwParam, pParam)
  local i = cual(dwID, 57001, 3)
  if i >= 0 then
    game.netcommand2(CMD_CH, 1, i + 1)
  end
  return 1
end

function OnCHFila(dwID, dwCmdID, dwParam, pParam)
  local i = cual(dwID, C_BOTON, 6)
  if i >= 0 then
    game.netcommand2(CMD_CH, 10 + i, 0)
  end
  return 1
end

function OnCHPagAnt(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_CH, 20, 0) return 1 end
function OnCHPagSig(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_CH, 21, 0) return 1 end
function OnCHTipo(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_CH, 22, 0) return 1 end
function OnCHResAnt(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_CH, 28, 0) return 1 end
function OnCHResSig(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_CH, 29, 0) return 1 end

function OnCHBuscar(dwID, dwCmdID, dwParam, pParam)
  mandar_texto(window.gettitle(ch(57026)) or "", 23)
  game.netcommand2(CMD_CH, 27, 0)
  return 1
end

function OnCHPublicar(dwID, dwCmdID, dwParam, pParam)
  game.netcommand2(CMD_CH, 31, tonumber(window.gettitle(ch(57032))) or 1)
  game.netcommand2(CMD_CH, 30, tonumber(window.gettitle(ch(57034))) or 0)
  return 1
end

function OnCHEstrategia(dwID, dwCmdID, dwParam, pParam)
  local i = cual(dwID, 57045, 3)
  if i >= 0 then
    game.netcommand2(CMD_CH, 40 + i, 0)
  end
  return 1
end

function OnCHSalirTorneo(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_CH, 43, 0) return 1 end
function OnCHHardcore(dwID, dwCmdID, dwParam, pParam) game.netcommand2(CMD_CH, 50, 0) return 1 end
