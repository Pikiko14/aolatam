-- El arbol de evolucion de la mascota (server/arbol_mascotas.py): la ventana 59400 de wnd03.xml
-- (tools/parche_arbol_mascotas.py). El servidor la abre con ArbolAbrir(titulo, formas, actual, elegido, aviso):
-- formas son 15 fichas (o false donde no hay forma) en orden de monton, los hijos de i son 2i+1 y 2i+2.
local CMD_ARBOL = 170
WND_ARBOL = WND_ARBOL or 0        -- un numero desde el principio: window.isexist(nil) da error
ARBOL = ARBOL or {}
local A = ARBOL

-- Colores de window.setbgcolor: azul, verde, rojo, alfa.
-- El fondo es el del tema (59545, tools/parche_arbol_mascotas.py): las cajas normales solo lo oscurecen y las del
-- camino lo aclaran, asi se ven bien con cualquier color de ventana.
local NORMAL = {0, 0, 0, 90}
local CAMINO = {255, 255, 255, 45}
local ELEGIDO = {200, 150, 40, 255}    -- la forma pulsada
local ACTUAL = {30, 150, 215, 255}     -- la forma de la mascota (dorado)
local LINEA = {180, 180, 180, 255}

local function hijo(id)
  return window.find(WND_ARBOL, id)
end

local function color(w, c)
  window.setbgcolor(w, c[1], c[2], c[3], c[4])
end

local function corto(texto, n)
  texto = tostring(texto or "")
  if string.len(texto) > n then
    return string.sub(texto, 1, n - 2) .. ".."
  end
  return texto
end

local function padre(i)
  return math.floor((i - 1) / 2)
end

-- Si el nodo j cuelga del i (o es el mismo).
local function cuelga(i, j)
  while j > i do
    j = padre(j)
  end
  return j == i
end

local function forma(i)
  return A.formas and A.formas[i + 1]
end

local function estado(texto)
  window.settitle(hijo(59542), corto(texto, 58))
end

local function pintar()
  for i = 0, 14 do
    local d = forma(i)
    local hay = d and true or false
    window.show(hijo(59470 + i), hay)
    window.show(hijo(59410 + i), hay)
    window.show(hijo(59430 + i), hay)
    window.show(hijo(59450 + i), hay)
    local icono = hijo(59550 + i)        -- la imagen pequena de la forma
    window.show(icono, d and (d.icono or 0) > 0 or false)
    if d and (d.icono or 0) > 0 then
      window.seticon(icono, d.icono)
    end
    if d then
      window.settitle(hijo(59430 + i), corto(d.nombre, 14))   -- cabe al lado de la imagen
      window.settitle(hijo(59450 + i), "Lv " .. tostring(d.nivel) .. "  " .. tostring(d.clase))
      local c = NORMAL
      if A.elegido >= 0 and i ~= A.actual and cuelga(A.actual, i) and cuelga(i, A.elegido) then
        c = CAMINO
      end
      if i == A.visto then
        c = ELEGIDO
      end
      if i == A.actual then
        c = ACTUAL
      end
      color(hijo(59470 + i), c)
    end
  end
  for p = 0, 6 do
    local b = 59490 + 5 * p
    local uno = forma(p) and forma(2 * p + 1) and true or false
    local dos = forma(p) and forma(2 * p + 2) and true or false
    window.show(hijo(b), uno or dos)
    window.show(hijo(b + 1), uno)
    window.show(hijo(b + 2), dos)
    window.show(hijo(b + 3), uno)
    window.show(hijo(b + 4), dos)
    for k = 0, 4 do
      color(hijo(b + k), LINEA)
    end
  end
end

-- La ficha de abajo con la forma i.
local function ficha(i)
  local d = forma(i)
  if not d then
    return
  end
  A.visto = i
  window.seticon(hijo(59530), d.retrato)
  window.settitle(hijo(59531), corto(d.nombre, 30))
  window.settitle(hijo(59532), corto(d.texto, 44))
  window.settitle(hijo(59533), d.stats1)
  window.settitle(hijo(59534), d.stats2)
  for k = 0, 2 do
    local h = d.habilidades and d.habilidades[k + 1]
    local boton, nombre = hijo(59536 + k), hijo(59539 + k)
    window.show(boton, h and true or false)
    window.show(nombre, h and true or false)
    if h then
      window.seticon(boton, h[1])
      window.settooltiptext(boton, h[2] .. ": " .. h[3])
      window.settitle(nombre, corto(h[2], 9))
    end
  end
end

function ArbolAbrir(titulo, formas, actual, elegido, aviso)
  A.formas = formas
  A.actual = actual
  A.elegido = elegido
  if window.isexist(WND_ARBOL) then
    window.setforeground(WND_ARBOL)
  else
    WND_ARBOL = window.create(59400, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_ARBOL) then
      return
    end
    window.move(WND_ARBOL, SYSTEM_SCREEN_WIDTH / 2 - 287, SYSTEM_SCREEN_HEIGHT / 2 - 201)
  end
  window.settitle(WND_ARBOL, corto(titulo, 40))
  window.settitle(hijo(59401), "Click a form to see it below, then press Evolve to grow your pet that way.")
  window.settitle(hijo(59535), "Abilities")
  window.settitle(hijo(59543), "Evolve")
  window.settitle(hijo(59544), "Close")
  if elegido >= 0 then
    ficha(elegido)
  else
    ficha(actual)
  end
  pintar()
  if aviso and aviso ~= "" then
    estado(aviso)
  else
    estado("Gold: your pet now. Pick the form you want it to become.")
  end
end

function ArbolCerrar()
  if window.isexist(WND_ARBOL) then
    window.destroy(WND_ARBOL)
  end
  WND_ARBOL = 0
end

function OnArbolNodo(dwID, dwCmdID, dwParam, pParam)
  local i = window.getappdata(dwID)
  if not forma(i) then
    return 1
  end
  ficha(i)
  pintar()
  if i == A.actual then
    estado("This is your pet now.")
  elseif cuelga(A.actual, i) then
    estado("Press Evolve to grow your pet into " .. corto(forma(i).nombre, 20) .. ".")
  else
    estado("Your pet cannot reach this form from its current one.")
  end
  return 1
end

function OnArbolEvolve(dwID, dwCmdID, dwParam, pParam)
  if not A.visto or A.visto == A.actual or not cuelga(A.actual, A.visto) then
    estado("Pick a form that your pet can still become.")
    return 1
  end
  game.netcommand2(CMD_ARBOL, 2, A.visto)
  return 1
end

function OnArbolCerrar(dwID, dwCmdID, dwParam, pParam)
  ArbolCerrar()
  return 1
end
