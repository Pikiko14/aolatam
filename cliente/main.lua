-- Punto de entrada.
--   love cliente                                                  juego normal: login, personaje y mundo
--   love cliente --pruebas                                         pruebas de la capa de red
--   love cliente --sonda host puerto usuario [ranura] [segundos]   login + mundo sin ventana
--   love cliente --mapa NOMBRE [x y] [captura.png]                 dibuja un mapa del cliente instalado (C:/AO/Angels Online)
local Sesion = require('src.sesion')

local modo, args = nil, {}
for i, a in ipairs(arg or {}) do
  if a == '--pruebas' then modo = 'pruebas' end
  if a == '--sonda' or a == '--mapa' or a == '--vivo' or a == '--hoja' or a == '--vestir' or a == '--cuadros' or a == '--ventana' or a == '--hud' or a == '--superponer' or a == '--luas' or a == '--nativo' then modo = a:sub(3); for j = i + 1, #arg do args[#args + 1] = arg[j] end; break end
end

-- Sin argumentos: modo normal de juego, con pantalla de login.
local pantalla = nil            -- 'login' | 'conectando' | 'seleccion' | nil (ya jugando)
local login, filas_seleccion, pendiente_carga, cuadros_login = nil, nil, false, 0
local crear_auto, crear_ok, ver_creacion
local login_auto, slot_auto, foto_hecha, item_hecho, item_informado, vendido, vendido_info
local filas_barra, enfriando, magia_hecha, magia_info = nil, {}, false, false
local minimapa_grande = false
local audio, audio_info
local invitado, aceptado, amigos_info
local grupo_invitado, grupo_dicho, grupo_aceptado, grupo_info
local filas_menu
local ultimo_clic_nat
local nv2_hecho, ni_hecho, dbg_dim, nl_hecho
local nativo_listo, nd_hecho, nv_hecho, nv_info
local casillas_banco, ultimo_clic_banco = nil, { t = 0, casilla = nil }
local mascota_abierta = os.getenv('AO_MASCOTA') ~= nil
local amigos_abiertos, amigo_sel, filas_amigos = os.getenv('AO_AMIGOS') ~= nil, 1, nil
if not modo then modo = 'vivo'; pantalla = 'login' end
local CLIENTE = os.getenv('AO_CLIENTE') or 'C:/AO/Angels Online'
local inventario, equipo_abierto, opciones_dialogo = os.getenv('AO_INV') ~= nil, os.getenv('AO_EQUIPO') ~= nil, nil
local hablado, atacado, ultimo_paso
local filas_tienda = nil
local casillas_inv, arrastre, ultimo_clic = nil, nil, { t = 0, casilla = nil }
local misiones_abiertas, mision_sel, filas_misiones = os.getenv('AO_MISIONES') ~= nil, 1, nil
local comprado, informado_compra, opcion_elegida, opcion2_elegida, t_opcion, banco_info
local banco_sacado, banco_guardado, banco_fin, t_banco
local dialogo_visto, seq_i, t_seq
local capturado, depurado, equipo, clicado, informado, dicho, informado_chat
local sesion, t0, vistos, orden, tiempo_mundo, visor, cuadros, mundo, mapa_visto = nil, 0, nil, nil, nil, nil, 0, nil, -1

function love.load()
  if modo == 'pruebas' then
    love.event.quit(require('tests.run') and 0 or 1)
  elseif modo == 'sonda' then
    vistos, orden = {}, {}
    sesion = Sesion.nueva{
      host = args[1], puerto = tonumber(args[2]), usuario = args[3], ranura = tonumber(args[4] or 0),
      alEstado = function(t) print(string.format('[%5.2fs] %s', love.timer.getTime() - t0, t)) end,
      alMensaje = function(op, body, rol)
        local k = rol .. ':0x' .. string.format('%04X', op)
        if not vistos[k] then vistos[k] = { n = 0, largo = #body }; orden[#orden + 1] = k end
        vistos[k].n = vistos[k].n + 1
      end,
    }
    t0 = love.timer.getTime()
    sesion:iniciar()
  elseif modo == 'mapa' then
    local t = love.timer.getTime()
    visor = require('src.visor').nuevo(CLIENTE)
    print(string.format('paks: %d archivos indexados en %.1fs', visor.paks.total, love.timer.getTime() - t))
    local ok = visor:cargar_mapa(args[1] or 'map002')
    print('mapa', args[1], ok and (visor.mapa.w .. 'x' .. visor.mapa.h .. ', ' .. #visor.mapa.objetos .. ' objetos') or 'NO ENCONTRADO')
    visor:centrar(tonumber(args[2]) or (visor.mapa and visor.mapa.w * 16 or 0), tonumber(args[3]) or (visor.mapa and visor.mapa.h * 16 or 0))
    if os.getenv('AO_DEBUG') and visor.mapa then
      local vistos, anim, n = {}, 0, 0
      for _, o in ipairs(visor.mapa.objetos) do
        if not vistos[o.id] then
          vistos[o.id] = true
          n = n + 1
          local f = visor.gfx:objeto_frames(o.id)
          if f and #f > 1 then anim = anim + 1 end
        end
      end
      print('objetos distintos', n, 'animados', anim)
      local sin_def, sin_sprite, ok, total = {}, {}, 0, 0
      local cuenta = {}
      for _, o in ipairs(visor.mapa.objetos) do
        total = total + 1
        local f = visor.gfx:objeto_frames(o.id)
        if f then ok = ok + 1
        else
          local d = visor.gfx:definiciones()[o.id]
          local clave = d and 'SPRITE' or 'SINDEF'
          cuenta[o.id] = (cuenta[o.id] or 0) + 1
          if d then sin_sprite[o.id] = d else sin_def[o.id] = true end
        end
      end
      local nd, ns = 0, 0
      for _ in pairs(sin_def) do nd = nd + 1 end
      for _ in pairs(sin_sprite) do ns = ns + 1 end
      local procs = {}
      for _, o in ipairs(visor.mapa.objetos) do
        local d = visor.gfx:definiciones()[o.id]
        local k = d and d.proceso or '?'
        procs[k] = (procs[k] or 0) + 1
      end
      for k, n in pairs(procs) do print('  proceso', k, n) end
      print('objetos en el mapa', total, 'dibujables', ok, 'tipos sin definicion', nd, 'tipos con def pero sin sprite', ns)
      local lista = {}
      for id, c in pairs(cuenta) do lista[#lista + 1] = { id = id, c = c } end
      table.sort(lista, function(a, b) return a.c > b.c end)
      for i = 1, math.min(12, #lista) do
        local d = sin_sprite[lista[i].id]
        print('  id', lista[i].id, 'x' .. lista[i].c, d and ('dir=' .. d.dir .. ' sprite=' .. d.sprite:sub(1, 80) .. ' nombre=' .. d.nombre) or 'SIN DEFINICION')
      end
    end
  elseif modo == 'hoja' then
    visor = require('src.visor').nuevo(CLIENTE)
  elseif modo == 'ventana' or modo == 'hud' or modo == 'superponer' then
    visor = require('src.visor').nuevo(CLIENTE)
  elseif modo == 'nativo' then
    -- --nativo salida.png : ejecuta los scripts ORIGINALES del cliente sobre la capa nativa y dibuja lo que crean
    visor = require('src.visor').nuevo(CLIENTE)
    local nat = require('src.nativo')
    nat.window.ui = visor.ui
    local carpeta, lista = nat.carpeta_luas(), nil
    local ok, mal = nat.cargar(carpeta, lista)
    print('scripts ejecutados', ok, 'con error', #mal)
    for _, m in ipairs(mal) do print('  ' .. m:sub(1, 160)) end
    local c, e = pcall(CreateMainWnd, 1)
    print('CreateMainWnd', c and 'ok' or e)
  elseif modo == 'cuadros' then
    visor = require('src.visor').nuevo(CLIENTE)
  elseif modo == 'vestir' then
    visor = require('src.visor').nuevo(CLIENTE)
    equipo = require('src.equipo').nuevo(visor.paks, visor.gfx)
  elseif modo == 'vivo' and pantalla == 'login' then
    login = require('src.login').nuevo({ carpeta = (love.filesystem.getInfo and CLIENTE) or CLIENTE })
    love.keyboard.setKeyRepeat(true)
  elseif modo == 'vivo' then
    visor = require('src.visor').nuevo(CLIENTE)
    mundo = require('src.mundo').nuevo()
    iniciar_audio()
    sesion = Sesion.nueva{
      host = args[1], puerto = tonumber(args[2]), usuario = args[3], ranura = tonumber(args[4] or 0),
      alEstado = function(t) print(string.format('[%5.2fs] %s', love.timer.getTime() - t0, t)) end,
      alMensaje = function(op, body, rol) if rol == 'mundo' then mundo:mensaje(op, body) end end,
    }
    t0 = love.timer.getTime()
    sesion:iniciar()
  else
    love.graphics.setBackgroundColor(0.07, 0.09, 0.13)
  end
  -- ampliacion como la de Windows con el cliente original: mundo e interfaz en un lienzo virtual de ~700 de alto (AO_ESCALA=0 la quita)
  if (modo == nil or modo == 'vivo') and os.getenv('AO_ESCALA') ~= '0' then require('src.escala').aplicar() end
end

-- Clic en el mapa: pide al servidor caminar hasta ahi (C2S 0x0004: posicion actual, n = 1 y un waypoint, todo en pixeles).
function lanzar(indice)
  local e = mundo.barra and mundo.barra[indice]
  if not e or e.tipo ~= 1 or not mundo.yo then return end
  if (enfriando[e.id] or 0) > 0 then return end
  local mg = visor.ui:magia(e.id)
  if mg and mundo.stats and mundo.stats.mp < mg.mp then mundo:linea('* Not enough MP'); if audio then audio:efecto('usefail') end; return end
  local net = require('src.net')
  local objetivo = mundo.objetivo or mundo.yo
  sesion:enviar(net.p16(0x0006) .. net.p16(e.id) .. net.p32(objetivo))
  if audio and mg and mg.efecto then audio:efecto(string.format('magic%03d', mg.efecto)) end
  enfriando[e.id] = ((mg and mg.previo or 0) + (mg and mg.posterior or 1000)) / 1000      -- enfriamiento visual; el real lo manda el servidor
  mundo:linea('* ' .. (mg and mg.nombre or ('magic ' .. e.id)))
end

function vender(casilla, todo)
  local inst = mundo.instancias and mundo.instancias[casilla]
  if not inst or not mundo.items[casilla] then return end
  local cant = todo and (mundo.cantidades[casilla] or 1) or 1
  local net = require('src.net')
  sesion:enviar(net.p16(0x0028) .. net.p32(1) .. inst .. net.p32(cant))
end

function love.mousereleased(mx, my, boton)
  if not arrastre then return end
  local a = arrastre
  arrastre = nil
  if pantalla or boton ~= 1 or not casillas_inv then return end
  for _, c in ipairs(casillas_inv) do
    if mx >= c.x and mx < c.x + c.w and my >= c.y and my < c.y + c.h and c.casilla ~= a.casilla then
      local net = require('src.net')
      sesion:enviar(net.p16(0x0012) .. net.p16(a.casilla) .. net.p16(c.casilla))
      return
    end
  end
end

function iniciar_audio()
  if os.getenv('AO_SIN_AUDIO') then return end
  local ok, A = pcall(require, 'src.audio')
  if not ok then return end
  audio = A.nuevo(visor.paks)
  mundo.evento = function(nombre)
    if nombre == 'golpe' then audio:efecto('hit') elseif nombre == 'lvup' then audio:efecto('lvup') end
  end
end

function conectar_desde_login()
  login:guardar()
  login.mensaje = 'Leyendo los recursos del juego...'
  pantalla = 'conectando'
  pendiente_carga = true
end

function terminar_carga()
  pendiente_carga = false
  local ok, err = pcall(function()
    visor = require('src.visor').nuevo(login.valores.carpeta)
  end)
  if not ok or visor.paks.total == 0 then
    login.mensaje = 'No se encontraron .pak en esa carpeta' .. (ok and '' or (': ' .. tostring(err)))
    login.activo = 4
    pantalla = 'login'
    return
  end
  mundo = require('src.mundo').nuevo()
  iniciar_audio()
  local host, puerto = login:datos_conexion()
  t0 = love.timer.getTime()
  sesion = Sesion.nueva{
    host = host, puerto = puerto, usuario = login.valores.usuario, clave = login.valores.clave, esperar_seleccion = true,
    alEstado = function(t) print(string.format('[%5.2fs] %s', love.timer.getTime() - t0, t)); login.mensaje = t end,
    alError = function(_, texto) login.mensaje = texto; pantalla = 'login'; login.fase = 'form' end,
    alLista = function(lista)
      login:mostrar_personajes(Sesion.personajes(lista))
      pantalla = 'seleccion'
    end,
    alCreado = function(error, body)
      local n = login.nuevo
      if error ~= 0 then login.mensaje = 'El servidor rechazo el personaje (codigo ' .. error .. ')'; return end
      for i, pj in ipairs(login.personajes) do
        if pj.ranura == n.ranura then login.personajes[i] = Sesion.ficha_creada(body, n.ranura) end
      end
      login.fase = 'seleccion'
      login.mensaje = 'Personaje creado'
      crear_ok = true
    end,
    alMensaje = function(op, body, rol) if rol == 'mundo' then mundo:mensaje(op, body) end end,
  }
  login.valores.clave = ''
  -- vista previa del personaje que se esta creando: cuerpo base, pelo y ropa inicial, con los recursos del juego
  login.vista_previa = function(px, py, ap, genero)
    local capas = visor.equipo:personaje({ 26, 28, 30 }, ap, genero)
    local t = love.timer.getTime()
    local paso = ({ 1, 2, 3, 2 })[math.floor(t / (8 / 60)) % 4 + 1]
    love.graphics.setColor(1, 1, 1)
    for _, c in ipairs(capas) do
      local sp = visor.gfx:cuadro_anim(c.id, 'wait', 3, paso, c.tinte)
      if sp then love.graphics.draw(sp.img, px - sp.ox, py - sp.oy) end
    end
  end
  sesion:iniciar()
end

function love.mousepressed(mx, my, boton)
  if pantalla == 'seleccion' and filas_seleccion and boton == 1 then
    for _, f in ipairs(filas_seleccion) do
      if mx >= f.x and mx < f.x + f.w and my >= f.y and my < f.y + f.h then
        if f.vacia then login:empezar_creacion(f.ranura); return end
        pantalla = nil
        sesion:entrar(f.ranura)
        return
      end
    end
    return
  end
  if pantalla then return end
  if os.getenv('AO_NATIVO') and nativo_listo and modo == 'vivo' and boton == 1 then
    local nw = require('src.nativo').window
    local casilla = nw.casilla_bajo(mx, my)
    if casilla and mundo.items and mundo.items[casilla] then
      -- doble clic sobre un objeto de la mochila: usar / equipar (como el original)
      local ahora = love.timer.getTime()
      if ultimo_clic_nat and ultimo_clic_nat.casilla == casilla and ahora - ultimo_clic_nat.t < 0.4 then
        local net = require('src.net')
        sesion:enviar(net.p16(0x002E) .. net.p32(casilla) .. string.char(0))
        ultimo_clic_nat = nil
      else
        ultimo_clic_nat = { t = ahora, casilla = casilla }
      end
      return
    end
    if nw.clic(mx, my) then return end
  end
  if modo ~= 'vivo' or boton ~= 1 or sesion.rol ~= 'mundo' or not sesion.conectado then return end
  local yo = mundo.yo and mundo.ents[mundo.yo]
  if not yo then return end
  local w, h = love.graphics.getDimensions()
  local net = require('src.net')
  if filas_menu then
    for _, f in ipairs(filas_menu) do
      if mx >= f.x and mx < f.x + f.w and my >= f.y and my < f.y + f.h then
        if f.accion == 'inventario' then inventario = not inventario
        elseif f.accion == 'misiones' then misiones_abiertas = not misiones_abiertas
        elseif f.accion == 'amigos' then amigos_abiertos = not amigos_abiertos
        elseif f.accion == 'minimapa' then minimapa_grande = not minimapa_grande end
        return
      end
    end
  end
  if filas_barra then
    for _, f in ipairs(filas_barra) do
      if mx >= f.x and mx < f.x + f.w and my >= f.y and my < f.y + f.h then lanzar(f.indice); return end
    end
  end
  if mundo.banco_abierto and casillas_banco then
    for _, c in ipairs(casillas_banco) do
      if mx >= c.x and mx < c.x + c.w and my >= c.y and my < c.y + c.h then
        if mundo.banco and mundo.banco.items[c.casilla] then
          local ahora = love.timer.getTime()
          if ultimo_clic_banco.casilla == c.casilla and ahora - ultimo_clic_banco.t < 0.4 then
            sesion:enviar(net.p16(0x002F) .. string.char(16) .. net.p32(c.casilla) .. net.p32(0))      -- sacar al inventario (C2S 0x002F [contenedor][casilla][4 B])
            ultimo_clic_banco = { t = 0, casilla = nil }
          else
            ultimo_clic_banco = { t = ahora, casilla = c.casilla }
          end
        end
        return
      end
    end
  end
  if inventario and casillas_inv and mundo.tienda then
    for _, c in ipairs(casillas_inv) do
      if mx >= c.x and mx < c.x + c.w and my >= c.y and my < c.y + c.h then
        vender(c.casilla, love.keyboard.isDown('lshift') or love.keyboard.isDown('rshift'))
        return
      end
    end
  end
  if inventario and casillas_inv and not mundo.tienda and not mundo.dialogo then
    for _, c in ipairs(casillas_inv) do
      if mx >= c.x and mx < c.x + c.w and my >= c.y and my < c.y + c.h then
        if mundo.items and mundo.items[c.casilla] then
          local ahora = love.timer.getTime()
          if ultimo_clic.casilla == c.casilla and ahora - ultimo_clic.t < 0.4 then
            if mundo.banco_abierto then
              sesion:enviar(net.p16(0x002F) .. string.char(17) .. net.p32(c.casilla) .. net.p32(0))      -- guardar en el banco
            else
              sesion:enviar(net.p16(0x002E) .. net.p32(c.casilla) .. string.char(0))      -- usar / equipar
            end
            ultimo_clic = { t = 0, casilla = nil }
          else
            ultimo_clic = { t = ahora, casilla = c.casilla }
            arrastre = { casilla = c.casilla, item = mundo.items[c.casilla] }
          end
        end
        return
      end
    end
  end
  if amigos_abiertos and filas_amigos then
    for _, f in ipairs(filas_amigos) do
      if mx >= f.x and mx < f.x + f.w and my >= f.y and my < f.y + f.h then amigo_sel = f.indice; return end
    end
  end
  if misiones_abiertas and filas_misiones then
    for _, f in ipairs(filas_misiones) do
      if mx >= f.x and mx < f.x + f.w and my >= f.y and my < f.y + f.h then mision_sel = f.indice; return end
    end
  end
  if mundo.tienda and filas_tienda then
    for _, f in ipairs(filas_tienda) do
      if mx >= f.x and mx < f.x + f.w and my >= f.y and my < f.y + f.h then
        sesion:enviar(net.p16(0x0027) .. net.p32(1) .. net.p32(f.item) .. net.p32(1))      -- comprar 1
        return
      end
    end
    return
  end
  if mundo.dialogo and opciones_dialogo then
    for _, o in ipairs(opciones_dialogo) do
      if mx >= o.x and mx < o.x + o.w and my >= o.y and my < o.y + o.h then
        sesion:enviar(net.p16(0x000B) .. string.char(o.valor))      -- seguir (1) o elegir (10 + indice)
        return
      end
    end
    return
  end
  local wx, wy = visor.cam.x - w / 2 + mx, visor.cam.y - h / 2 + my
  wy = visor.mapa.h * 32 - wy          -- a coordenadas del servidor (y desde abajo)
  for _, e in pairs(mundo.ents) do
    if not e.yo and e.sprite and not e.muerto and math.abs(wx - e.x) <= 30 and wy >= e.y - 10 and wy <= e.y + 90 then
      -- el mismo C2S 0x0005 sirve para hablar con un NPC y para fijar y atacar a un monstruo: lo decide el servidor
      sesion:enviar(net.p16(0x0005) .. net.p32(e.id) .. net.p16(0))
      if e.clase ~= 200 then mundo.objetivo = e.id end
      return
    end
  end
  caminar_a(wx, wy)
end

function caminar_a(wx, wy)
  local yo = mundo.yo and mundo.ents[mundo.yo]
  local net = require('src.net')
  -- colision: se corta el tramo en la ultima casilla libre (el servidor solo reenvia; la pared la respeta el cliente)
  if visor.mapa then
    local ex, ey, avanza = require('src.mpc').tramo_libre(visor.mapa, yo.x, yo.y, wx, wy)
    if not avanza then mundo:linea('* No se puede pasar'); return end
    wx, wy = ex, ey
  end
  sesion:enviar(net.p16(0x0004) .. net.p16(math.floor(yo.x)) .. net.p16(math.floor(yo.y)) .. string.char(1) .. net.p16(0)
    .. net.p16(math.floor(wx)) .. net.p16(math.floor(wy)))
end

-- Chat: Enter abre la linea, Enter envia (C2S 0x000E, texto en claro terminado en nulo), Escape cancela.
local escribiendo, texto_chat = false, ''

function invitar_amigo(nombre)
  local net = require('src.net')
  sesion:enviar(net.p16(0x0019) .. (nombre:sub(1, 16) .. string.rep('\0', 21)):sub(1, 21))
end

function responder_invitacion(acepta)
  local net = require('src.net')
  if mundo.invitacion_grupo then
    sesion:enviar(net.p16(0x0018) .. string.char(acepta and 1 or 7) .. net.p32(0))      -- 1 aceptar, 7 rechazar
    mundo.invitacion_grupo = nil
    return
  end
  if not mundo.invitacion then return end
  if acepta then sesion:enviar(net.p16(0x001B) .. net.p32(0)) else sesion:enviar(net.p16(0x001C)) end
  mundo.invitacion = nil
end

function enviar_chat(t)
  local net = require('src.net')
  local function propio() local yo = mundo.yo and mundo.ents[mundo.yo]; return yo and yo.nombre or '?' end
  -- /w nombre texto: susurro (C2S 0x0127 [4 B][receptor 17][2 B][texto])
  local dest, txt = t:match('^/w%s+(%S+)%s+(.+)$')
  if dest then
    sesion:enviar(net.p16(0x0127) .. net.p32(0) .. (dest:sub(1, 16) .. string.rep('\0', 17)):sub(1, 17) .. '\0\0' .. txt .. '\0')
    return
  end
  -- /g texto: chat del grupo (C2S 0x0126 [4 B][canal 4][4 B][texto])
  local gtxt = t:match('^/g%s+(.+)$')
  if gtxt then
    if not mundo.grupo then mundo:linea('* You are not a member of any teams.'); return end
    sesion:enviar(net.p16(0x0126) .. net.p32(0) .. string.char(4) .. net.p32(0) .. gtxt .. '\0')
    return
  end
  -- /grupo nombre invita; /salir deja el grupo (C2S 0x0017 nombre ASCIIZ en 34 B; 0x0018 [accion][u32])
  local inv = t:match('^/grupo%s+(%S+)')
  if inv then
    sesion:enviar(net.p16(0x0017) .. (inv:sub(1, 16) .. string.rep('\0', 34)):sub(1, 34))
    mundo:linea('* Team invitation sent to ' .. inv)
    return
  end
  if t == '/salir' then
    sesion:enviar(net.p16(0x0018) .. string.char(4) .. net.p32(0))
    return
  end
  local amigo = t:match('^/amigo%s+(%S+)')
  if amigo then invitar_amigo(amigo); mundo:linea('* Friend invitation sent to ' .. amigo); return end
  if t ~= '' and sesion.rol == 'mundo' and sesion.conectado then
    sesion:enviar(require('src.net').p16(0x000E) .. t .. string.char(0))
    local yo = mundo.yo and mundo.ents[mundo.yo]
    mundo:linea((yo and yo.nombre or '?') .. ': ' .. t)      -- el servidor no devuelve el chat local: se anota aqui
  end
end

function love.textinput(t)
  if pantalla == 'login' or (pantalla == 'seleccion' and login.fase == 'crear') then login:texto(t); return end
  if modo == 'vivo' and escribiendo then texto_chat = texto_chat .. t end
end

function love.keypressed(k)
  if modo ~= 'vivo' then return end
  if pantalla == 'login' and k == 'v' and (love.keyboard.isDown('lctrl') or love.keyboard.isDown('rctrl') or love.keyboard.isDown('lgui')) then
    login:texto((love.system.getClipboardText() or ''):gsub('[\r\n]', ''))
    return
  end
  if pantalla == 'login' then
    if login:tecla(k) == 'enviar' then conectar_desde_login() end
    if k == 'escape' then love.event.quit(0) end
    return
  elseif pantalla == 'seleccion' and login.fase == 'crear' then
    if login:tecla(k) == 'crear' then
      local n = login.nuevo
      sesion:crear(n.ranura, login:apariencia(), n.nombre)
      login.mensaje = 'Creando ' .. n.nombre .. '...'
    end
    return
  elseif pantalla then
    if k == 'escape' then love.event.quit(0) end
    return
  end
  if k == 'return' or k == 'kpenter' then
    if escribiendo then enviar_chat(texto_chat); texto_chat = '' end
    escribiendo = not escribiendo
  elseif k == 'escape' then
    if escribiendo then escribiendo, texto_chat = false, ''
    elseif mundo.tienda then mundo.tienda = nil
    elseif mundo.banco_abierto then mundo.banco_abierto = false
    else love.event.quit(0) end
  elseif (k == '[' or k == ']') and mundo.tienda then
    local n = math.max(1, math.ceil(#visor.ui:stock_tienda(mundo.tienda.id) / 5))
    mundo.tienda.pagina = (mundo.tienda.pagina + (k == ']' and 1 or -1)) % n
  elseif not escribiendo and k:match('^[0-9]$') then
    lanzar(k == '0' and 10 or tonumber(k))
  elseif k == 'i' and not escribiendo then
    inventario = not inventario
  elseif k == 'f' and not escribiendo then
    amigos_abiertos = not amigos_abiertos
  elseif k == 'y' and not escribiendo and (mundo.invitacion or mundo.invitacion_grupo) then
    responder_invitacion(true)
  elseif k == 'n' and not escribiendo and (mundo.invitacion or mundo.invitacion_grupo) then
    responder_invitacion(false)
  elseif k == 'delete' and amigos_abiertos and not escribiendo and mundo.amigos and mundo.amigos[amigo_sel] then
    local net = require('src.net')
    sesion:enviar(net.p16(0x001E) .. net.p32(mundo.amigos[amigo_sel].cid))
    table.remove(mundo.amigos, amigo_sel)
  elseif k == 'q' and not escribiendo then
    misiones_abiertas = not misiones_abiertas
  elseif k == 'm' and not escribiendo then
    minimapa_grande = not minimapa_grande
  elseif k == 'p' and not escribiendo then
    mascota_abierta = not mascota_abierta
  elseif k:match('^f%d+$') and not escribiendo and tonumber(k:sub(2)) <= 12 then
    lanzar(tonumber(k:sub(2)))
  elseif k == 'pause' and audio then
    mundo:linea(audio:alternar_silencio() and '* Sonido apagado' or '* Sonido encendido')
  elseif k == 'e' and not escribiendo and (love.keyboard.isDown('lalt') or love.keyboard.isDown('ralt')) then
    equipo_abierto = not equipo_abierto
  elseif k == 'backspace' and escribiendo then
    texto_chat = texto_chat:sub(1, -2)
  end
end

function love.update(dt)
  -- ganchos de prueba (sin teclado): AO_LOGIN="host:puerto,usuario,clave" y AO_SLOT=n
  if modo == 'vivo' and pantalla == 'login' and os.getenv('AO_LOGIN') and not login_auto then
    login_auto = true
    local h, u, c = os.getenv('AO_LOGIN'):match('^([^,]*),([^,]*),?(.*)$')
    login.valores.servidor, login.valores.usuario, login.valores.clave = h, u, c
    conectar_desde_login()
  end
  if pantalla == 'seleccion' and os.getenv('AO_VER_CREACION') and not ver_creacion and login.fase == 'seleccion' then
    ver_creacion = true      -- prueba: abre la pantalla de creacion (sin enviar nada) con un nombre de ejemplo
    for _, pj in ipairs(login.personajes) do
      if not pj.ocupada then login:empezar_creacion(pj.ranura); login.nuevo.nombre = 'Hera'; login.nuevo.genero = 0; login.nuevo.peinado = 4; break end
    end
  end
  if pantalla == 'seleccion' and os.getenv('AO_CREAR') and not crear_auto and login.fase == 'seleccion' then
    crear_auto = true
    local nom, g, pe, co = os.getenv('AO_CREAR'):match('^([^,]+),(%d),(%d+),(%d+)$')
    for _, pj in ipairs(login.personajes) do
      if not pj.ocupada then
        login:empezar_creacion(pj.ranura)
        login.nuevo.nombre, login.nuevo.genero, login.nuevo.peinado, login.nuevo.color = nom, tonumber(g), tonumber(pe), tonumber(co)
        sesion:crear(pj.ranura, login:apariencia(), nom)
        break
      end
    end
  end
  if pantalla == 'seleccion' and os.getenv('AO_SLOT') and not slot_auto and (not os.getenv('AO_CREAR') or login.fase == 'seleccion') and (not os.getenv('AO_CREAR') or crear_ok) then
    slot_auto = true
    pantalla = nil
    sesion:entrar(tonumber(os.getenv('AO_SLOT')))
  end
  if modo == 'vivo' and pantalla == 'login' then return end
  if modo == 'vivo' and pendiente_carga then
    -- un cuadro para pintar el mensaje y luego se leen los pak (tarda un segundo)
    if (cuadros_login or 0) > 1 then terminar_carga() end
    cuadros_login = (cuadros_login or 0) + 1
    return
  end
  if modo == 'vivo' and not sesion then return end
  if modo == 'vivo' then
    sesion:actualizar()
    mundo:avanzar(dt)
    for id, t in pairs(enfriando) do if t > 0 then enfriando[id] = t - dt end end
    local ap = os.getenv('AO_APAR')      -- prueba: fuerza la apariencia, p.ej. "1,2,0,5,10"
    if ap and mundo.apariencia then
      local t = {}
      for n in ap:gmatch('%d+') do t[#t + 1] = tonumber(n) end
      mundo.apariencia = t
    end
    local hablar = os.getenv('AO_HABLAR')      -- prueba: habla con el NPC de ese nombre
    if hablar and not hablado and love.timer.getTime() - t0 > 3 then
      for _, e in pairs(mundo.ents) do
        if e.nombre == hablar then
          hablado = true
          local net = require('src.net')
          sesion:enviar(net.p16(0x0005) .. net.p32(e.id) .. net.p16(0))
          print('hablando con', e.nombre, e.id)
          break
        end
      end
    end
    local atacar = os.getenv('AO_ATACAR')      -- prueba: ataca al monstruo mas cercano con ese nombre
    if atacar and not atacado and love.timer.getTime() - t0 > 3 and mundo.yo then
      local yo, mejor, md = mundo.ents[mundo.yo], nil, 1e9
      for _, e in pairs(mundo.ents) do
        if e.nombre == atacar and e.clase ~= 200 and not e.muerto then
          local d = math.abs(e.x - yo.x) + math.abs(e.y - yo.y)
          if d < md then mejor, md = e, d end
        end
      end
      if mejor and md > 110 then
        -- lejos: se acerca primero (el servidor respeta el alcance del arma)
        if love.timer.getTime() - (ultimo_paso or 0) > 1 then
          ultimo_paso = love.timer.getTime()
          local vx, vy = mejor.x - yo.x, mejor.y - yo.y
          local d = math.sqrt(vx * vx + vy * vy)
          caminar_a(yo.x + vx / d * (d - 60), yo.y + vy / d * (d - 60))
        end
      elseif mejor then
        atacado = love.timer.getTime()
        print('atacando a', mejor.nombre, mejor.id, 'a', md, 'px')
        local net = require('src.net')
        sesion:enviar(net.p16(0x0005) .. net.p32(mejor.id) .. net.p16(0))
        mundo.objetivo = mejor.id
      end
    end
    local tienda = os.getenv('AO_TIENDA')      -- prueba: habla con el NPC y, con la tienda abierta, compra el primer item
    if tienda and mundo.tienda and filas_tienda and #filas_tienda > 0 and not comprado and love.timer.getTime() - t0 > 6 then
      comprado = true
      print('oro antes', mundo:oro())
      sesion:enviar(require('src.net').p16(0x0027) .. require('src.net').p32(1) .. require('src.net').p32(filas_tienda[1].item) .. require('src.net').p32(1))
    elseif tienda and comprado and not informado_compra and love.timer.getTime() - t0 > 8 then
      informado_compra = true
      print('oro despues', mundo:oro())
    end
    local opcion = tonumber(os.getenv('AO_OPCION') or '')      -- prueba: elige esa opcion del dialogo
    if opcion and mundo.dialogo and #mundo.dialogo.opciones >= opcion and not opcion_elegida then
      opcion_elegida = true
      sesion:enviar(require('src.net').p16(0x000B) .. string.char(10 + opcion - 1))
      t_opcion = love.timer.getTime()
      print('opcion elegida', opcion, 'de', #mundo.dialogo.opciones)
    end
    local usar, mover = os.getenv('AO_USAR'), os.getenv('AO_MOVER')
    if (usar or mover) and mundo.items and not item_hecho and love.timer.getTime() - t0 > 3 then
      item_hecho = true
      local t = {}
      for c, it in pairs(mundo.items) do if c < 20 or c == 21 or c == 22 or c == 20 then t[#t + 1] = c .. '=' .. it end end
      table.sort(t); print('antes', table.concat(t, ' '))
      local net = require('src.net')
      if usar then sesion:enviar(net.p16(0x002E) .. net.p32(tonumber(usar)) .. string.char(0)) end
      if mover then
        local o, d = mover:match('(%d+),(%d+)')
        sesion:enviar(net.p16(0x0012) .. net.p16(tonumber(o)) .. net.p16(tonumber(d)))
      end
    elseif (usar or mover) and item_hecho and not item_informado and love.timer.getTime() - t0 > 6 then
      item_informado = true
      local t = {}
      for c, it in pairs(mundo.items) do if c < 20 or c == 21 or c == 22 or c == 20 then t[#t + 1] = c .. '=' .. it end end
      table.sort(t); print('despues', table.concat(t, ' '))
    end
    local vend = os.getenv('AO_VENDER')      -- prueba: con la tienda abierta, vende 1 de esa casilla
    if vend and mundo.tienda and not vendido and love.timer.getTime() - t0 > 6 then
      vendido = true
      print('oro antes', mundo:oro(), 'casilla', vend, mundo.items[tonumber(vend)], mundo.cantidades[tonumber(vend)])
      vender(tonumber(vend), false)
    elseif vend and vendido and not vendido_info and love.timer.getTime() - t0 > 8 then
      vendido_info = true
      print('oro despues', mundo:oro(), 'casilla', vend, mundo.items[tonumber(vend)], mundo.cantidades[tonumber(vend)])
    end
    local mag = os.getenv('AO_MAGIA')      -- prueba: lanza la ranura N de la barra
    if mag and mundo.barra and mundo.stats and not magia_hecha and love.timer.getTime() - t0 > 3 then
      magia_hecha = true
      local e = mundo.barra[tonumber(mag)]
      print('barra', e and e.id, 'MP antes', mundo.stats.mp, '/', mundo.stats.mp_max)
      lanzar(tonumber(mag))
    elseif mag and magia_hecha and not magia_info and love.timer.getTime() - t0 > 6 then
      magia_info = true
      print('MP despues', mundo.stats.mp)
      for _, l in ipairs(mundo.chat) do print('chat:', l) end
    end
    if os.getenv('AO_AUDIO_INFO') and audio and not audio_info and love.timer.getTime() - t0 > 4 then
      audio_info = true
      local esc = mundo.stage and visor.ui:escena(mundo.stage)
      print('musica', esc and esc.musica, 'sonando', audio:sonando())
      print('efecto hit', audio:efecto('hit'), 'magic029', audio:efecto('magic029'), 'inexistente', audio:efecto('nada_aqui'))
    end
    local gru = os.getenv('AO_GRUPO')      -- prueba: invita a ese jugador al grupo y le manda un susurro y un mensaje de grupo
    if gru and not grupo_invitado and mundo.yo and love.timer.getTime() - t0 > 3 then grupo_invitado = true; enviar_chat('/grupo ' .. gru) end
    if gru and grupo_invitado and not grupo_dicho and mundo.grupo and love.timer.getTime() - t0 > 8 then
      grupo_dicho = true
      enviar_chat('/g hola grupo'); enviar_chat('/w ' .. gru .. ' hola en privado')
    end
    if os.getenv('AO_ACEPTAR') and mundo.invitacion_grupo and not grupo_aceptado then grupo_aceptado = true; print('acepto grupo de', mundo.invitacion_grupo.nombre); responder_invitacion(true) end
    if (gru or os.getenv('AO_ACEPTAR')) and not grupo_info and love.timer.getTime() - t0 > 12 then
      grupo_info = true
      local t = {}
      for _, m in ipairs(mundo.grupo and mundo.grupo.miembros or {}) do t[#t + 1] = m.nombre .. ' Lv' .. tostring(m.nivel) .. ' hp' .. tostring(m.hp) end
      print('grupo', table.concat(t, ', '))
      for _, l in ipairs(mundo.chat) do print('chat:', l) end
    end
    local inv = os.getenv('AO_AMIGO')
    if inv and not invitado and mundo.yo and love.timer.getTime() - t0 > 3 then invitado = true; invitar_amigo(inv); print('invito a', inv) end
    if os.getenv('AO_ACEPTAR') and mundo.invitacion and not aceptado then aceptado = true; print('acepto a', mundo.invitacion.nombre); responder_invitacion(true) end
    if (inv or os.getenv('AO_ACEPTAR')) and not amigos_info and love.timer.getTime() - t0 > 9 then
      amigos_info = true
      local t = {}
      for _, a in ipairs(mundo.amigos or {}) do t[#t + 1] = a.nombre .. (a.conectado and '(on)' or '(off)') end
      print('amigos', table.concat(t, ', '))
    end
    local secuencia = os.getenv('AO_OPCIONES')      -- prueba: elige en orden estas opciones cada vez que llega un dialogo con opciones, p.ej. "1,1,1"
    if secuencia and mundo.dialogo and #mundo.dialogo.opciones > 0 and mundo.dialogo ~= dialogo_visto
       and love.timer.getTime() - (t_seq or 0) > 1.2 then
      dialogo_visto = mundo.dialogo
      seq_i = (seq_i or 0) + 1
      local n = 0
      for v in secuencia:gmatch('%d+') do n = n + 1; if n == seq_i then
        t_seq = love.timer.getTime()
        sesion:enviar(require('src.net').p16(0x000B) .. string.char(10 + tonumber(v) - 1))
        print('opcion', seq_i, v, 'de', #mundo.dialogo.opciones)
      end end
    end
    local opcion2 = tonumber(os.getenv('AO_OPCION2') or '')      -- prueba: segunda opcion del dialogo (p.ej. el banquero)
    if opcion2 and opcion_elegida and mundo.dialogo and #mundo.dialogo.opciones >= opcion2 and not opcion2_elegida
       and love.timer.getTime() - (t_opcion or 0) > 1.5 then
      opcion2_elegida = true
      sesion:enviar(require('src.net').p16(0x000B) .. string.char(10 + opcion2 - 1))
      print('segunda opcion', opcion2, 'de', #mundo.dialogo.opciones)
    end
    local sacar = os.getenv('AO_BANCO_SACAR')      -- prueba: con el banco abierto saca esa casilla y luego guarda la 20 de la mochila
    if sacar and mundo.banco_abierto and not banco_sacado then
      banco_sacado = true
      local net = require('src.net')
      print('banco antes', mundo.banco.items[tonumber(sacar)], 'mochila 20', mundo.items[20])
      sesion:enviar(net.p16(0x002F) .. string.char(16) .. net.p32(tonumber(sacar)) .. net.p32(0))
      t_banco = love.timer.getTime()
    elseif sacar and banco_sacado and not banco_guardado and love.timer.getTime() - t_banco > 2 then
      banco_guardado = true
      local net = require('src.net')
      print('banco despues de sacar', mundo.banco.items[tonumber(sacar)], 'mochila 20', mundo.items[20])
      sesion:enviar(net.p16(0x002F) .. string.char(17) .. net.p32(20) .. net.p32(0))
      t_banco = love.timer.getTime()
    elseif sacar and banco_guardado and not banco_fin and love.timer.getTime() - t_banco > 2 then
      banco_fin = true
      local libre
      for c = 1, 25 do if mundo.banco.items[c] == mundo.items[20] then libre = c end end
      print('despues de guardar: mochila 20', mundo.items[20], 'banco', libre)
    end
    if os.getenv('AO_BANCO_INFO') and not banco_info and love.timer.getTime() - t0 > 12 then
      banco_info = true
      local n = 0
      for _ in pairs(mundo.banco and mundo.banco.items or {}) do n = n + 1 end
      print('banco abierto', tostring(mundo.banco_abierto), 'items', n)
    end
    local say = os.getenv('AO_CHAT')
    if say and not dicho and love.timer.getTime() - t0 > 3 and mundo.yo then dicho = true; enviar_chat(say) end
    if say and dicho and not informado_chat and love.timer.getTime() - t0 > 5 then
      informado_chat = true
      for _, l in ipairs(mundo.chat) do print('chat:', l) end
    end
    local clic = os.getenv('AO_CLIC')
    if clic and not clicado and love.timer.getTime() - t0 > 3 and mundo.yo then
      clicado = true
      local dx, dy = clic:match('(-?%d+),(-?%d+)')
      local yo = mundo.ents[mundo.yo]
      print('antes', yo.x, yo.y, '->', yo.x + dx, yo.y + dy)
      caminar_a(yo.x + dx, yo.y + dy)
    elseif clic and clicado and not informado and love.timer.getTime() - t0 > 6 then
      informado = true
      local yo = mundo.ents[mundo.yo]
      print('despues', yo.x, yo.y, yo.dx, yo.dy)
    end
    if os.getenv('AO_DEBUG') and not depurado and love.timer.getTime() - t0 > 3 then
      depurado = true
      local t = {}
      for c, it in pairs(mundo.items or {}) do if c < 20 or (c >= 167 and c <= 174) then t[#t + 1] = c .. '=' .. it end end
      local cl, ej = {}, {}
      for _, e in pairs(mundo.ents) do
        local k = tostring(e.clase)
        cl[k] = (cl[k] or 0) + 1
        if e.clase ~= 200 and not e.yo and #ej < 4 then ej[#ej + 1] = e.nombre .. '@' .. e.x .. ',' .. e.y .. ' spr' .. tostring(e.sprite) end
      end
      for k, n in pairs(cl) do print('clase', k, n) end
      print('ejemplos', table.concat(ej, ' | '))
      if os.getenv('AO_DUMP') then
        local t = {}
        for _, e in pairs(mundo.ents) do if e.clase == 199 or e.clase == 200 then t[#t + 1] = e.x .. ',' .. e.y end end
        print('POS ' .. table.concat(t, ';'))
        local defs = visor.gfx:definiciones()
        for _, e in pairs(mundo.ents) do
          if e.nombre and (e.nombre:find('Captain') or e.nombre:find('Healer')) then
            local d = e.sprite and defs[e.sprite]
            print('NPC', e.nombre, 'sprite', e.sprite, 'clase', e.clase, d and (d.dir .. ' | ' .. d.sprite) or 'SIN DEF')
          end
        end
      end
      local c2 = visor.equipo:personaje(mundo:puesto(), mundo.apariencia, mundo.genero or 'g')
      print('apariencia', table.concat(mundo.apariencia or {}, ','), 'capas', #c2)
      for _, c in ipairs(c2) do
        local sp = visor.gfx:cuadro_anim(c.id, 'wait', 3, 2, c.tinte)
        print('  capa', c.id, sp and ('ox ' .. sp.ox .. ' oy ' .. sp.oy .. ' w ' .. sp.w .. ' h ' .. sp.h) or 'SIN SPRITE', visor.gfx:ruta_de_id(c.id))
      end
      print('genero', mundo.genero, 'puesto:', table.concat(t, ' '))
      local defs, n = visor.gfx:definiciones(), 0
      for _, e in pairs(mundo.ents) do
        if e.sprite and n < 12 then
          n = n + 1
          local d = defs[e.sprite]
          print(e.nombre, 'sprite', e.sprite, 'clase', e.clase, d and (d.dir .. ' | ' .. d.sprite) or 'SIN DEFINICION')
        end
      end
    end
    if mundo.ver_mapa ~= mapa_visto and mundo.stage then
      mapa_visto = mundo.ver_mapa
      local nombre = string.format('map%03d', mundo.stage)
      print('stage', mundo.stage, visor:cargar_mapa(nombre) and ('mapa ' .. nombre) or 'mapa no encontrado')
      local esc = visor.ui:escena(mundo.stage)
      if audio and esc then audio:musica(esc.musica) end
      local yo = mundo.ents[mundo.yo]
      print('yo', yo.nombre, yo.x, yo.y)
    end
    return
  end
  if modo ~= 'sonda' then return end
  sesion:actualizar()
  local limite = tonumber(args[5] or 8)
  if sesion.rol == 'mundo' and not tiempo_mundo then tiempo_mundo = love.timer.getTime() end
  if (tiempo_mundo and love.timer.getTime() - tiempo_mundo > limite) or love.timer.getTime() - t0 > 30 then
    print('--- mensajes recibidos ---')
    for _, k in ipairs(orden) do print(string.format('%-12s x%-4d (primer cuerpo: %d B)', k, vistos[k].n, vistos[k].largo)) end
    love.event.quit(0)
  end
end

function love.draw()
  if os.getenv('AO_FOTO') and not foto_hecha then
    local seg, arch = os.getenv('AO_FOTO'):match('^([%d%.]+),(.+)$')
    if love.timer.getTime() - (t0 or 0) > tonumber(seg) then foto_hecha = true; love.graphics.captureScreenshot(arch) end
  end
  if modo == 'mapa' and visor then
    local w, h = love.graphics.getDimensions()
    visor:dibujar(w, h)
    if os.getenv('AO_MARCAS') then
      -- prueba de orientacion: cruces en las posiciones dadas (px,py;...) con la y tal cual o volteada (AO_FLIP)
      love.graphics.setColor(1, 0, 0)
      for px, py in os.getenv('AO_MARCAS'):gmatch('(%-?[%d%.]+),(%-?[%d%.]+)') do
        px, py = tonumber(px), tonumber(py)
        if os.getenv('AO_FLIP') then py = visor.mapa.h * 32 - py end
        local sx, sy = px - (visor.cam.x - w / 2), py - (visor.cam.y - h / 2)
        love.graphics.line(sx - 10, sy, sx + 10, sy); love.graphics.line(sx, sy - 10, sx, sy + 10)
      end
    end
    cuadros = cuadros + 1
    if args[4] and cuadros == 2 then
      love.graphics.captureScreenshot(args[4])
    elseif args[4] and cuadros == 6 then
      love.event.quit(0)
    end
  elseif modo == 'luas' then
    -- --luas [carpeta]: intenta compilar los scripts originales del cliente y cuenta los que fallan
    local carpeta = args[1] or 'C:/trabajo/marcos/aolatam/extracted_luas'
    local ok, mal = 0, {}
    local h = io.popen('dir /b "' .. carpeta:gsub('/', string.char(92)) .. string.char(92) .. '*.lua" 2>nul')
    for nombre in h:lines() do
      local f = io.open(carpeta .. '/' .. nombre, 'rb')
      local src = f:read('*a'); f:close()
      local fn, err = loadstring(src, nombre)
      if fn then ok = ok + 1 else mal[#mal + 1] = nombre .. ': ' .. tostring(err):sub(1, 110) end
    end
    h:close()
    print('scripts que compilan', ok, 'fallan', #mal)
    for _, m in ipairs(mal) do print('  ' .. m) end
    love.event.quit(0)
  elseif modo == 'hoja' and os.getenv('AO_AUDITAR') then
    -- auditoria: todos los NPC y criaturas definidos en los obd; cuenta los que no resuelven un cuadro
    local malos, total = {}, 0
    for sid, d in pairs(visor.gfx:definiciones()) do
      if d.proceso == 'SERV_CLASS_NPCOBJ' or d.proceso == 'SERV_CLASS_MONSTER' or d.proceso:find('NPC') then
        total = total + 1
        if not visor.gfx:criatura(sid) and not visor.gfx:objeto(sid) and (os.getenv('AO_AUDITAR') == 'mon' and sid < 100000 and d.nombre:sub(1, 3) ~= 'NPC' or d.nombre:sub(1, 3) == 'NPC' and os.getenv('AO_AUDITAR') ~= 'mon') then malos[#malos + 1] = sid .. ' ' .. d.nombre:sub(1, 8) .. ' ' .. d.dir .. ' | ' .. d.sprite:sub(1, 30) end
      end
    end
    table.sort(malos)
    print('NPC/criaturas', total, 'sin sprite', #malos)
    for i = 1, math.min(60, #malos) do print('  ' .. malos[i]) end
    love.event.quit(0)
  elseif modo == 'hoja' and os.getenv('AO_OFFSETS') then
    for _, a in ipairs(args) do
      local sp = visor.gfx:cuadro_anim(tonumber(a), 'wait', 3, 2)
      if sp then print('offs', a, 'ox', sp.ox, 'oy', sp.oy, 'w', sp.w, 'h', sp.h) end
    end
    love.event.quit(0)
  elseif modo == 'hoja' then
    -- hoja de contactos: cada argumento es un sprite_id; salen en fila con su id
    love.graphics.clear(0.55, 0.6, 0.55)
    for i, a in ipairs(args) do
      if i < #args or not a:match('%.png$') then
        local id = tonumber(a)
        local s = visor.gfx:criatura(id)
        local x, y = 20 + ((i - 1) % 8) * 125, 110 + math.floor((i - 1) / 8) * 200
        love.graphics.setColor(1, 1, 1)
        if s then love.graphics.draw(s.img, x - s.ox, y - s.oy) else love.graphics.print('sin sprite', x - 20, y) end
        love.graphics.print(a, x - 20, y + 60)
      end
    end
    cuadros = cuadros + 1
    if cuadros == 2 then love.graphics.captureScreenshot(args[#args]) elseif cuadros == 6 then love.event.quit(0) end
  elseif modo == 'superponer' then
    -- --superponer id id ... salida.png : dibuja los sprites en el MISMO ancla (cruz roja) con su caja, para comprobar alineacion
    love.graphics.clear(0.55, 0.6, 0.55)
    local ax, ay = 200, 240
    local cols = { { 1, 0, 0 }, { 0, 0, 1 }, { 0, 0.6, 0 }, { 0.8, 0, 0.8 } }
    for i = 1, #args - 1 do
      local sp = visor.gfx:cuadro_anim(tonumber(args[i]), 'wait', 3, 2)
      if sp then
        love.graphics.setColor(1, 1, 1); love.graphics.draw(sp.img, ax - sp.ox, ay - sp.oy)
        love.graphics.setColor(cols[(i - 1) % 4 + 1]); love.graphics.rectangle('line', ax - sp.ox, ay - sp.oy, sp.w, sp.h)
      end
    end
    love.graphics.setColor(1, 0, 0); love.graphics.line(ax - 8, ay, ax + 8, ay); love.graphics.line(ax, ay - 8, ax, ay + 8)
    cuadros = cuadros + 1
    if cuadros == 2 then love.graphics.captureScreenshot(args[#args]) elseif cuadros == 6 then love.event.quit(0) end
  elseif modo == 'nativo' then
    love.graphics.clear(0.3, 0.35, 0.3)
    require('src.nativo').window.dibujar_todo()
    cuadros = cuadros + 1
    local nc = os.getenv('AO_NCLIC')
    if nc and cuadros == 3 then
      local a, b = nc:match('(%d+),(%d+)')
      local w = require('src.nativo').window.clic(tonumber(a), tonumber(b))
      print('clic', nc, w and ('ventana ' .. w.id .. ' check=' .. tostring(w.check)) or 'nada')
      for _, t in ipairs(require('src.nativo').window.trazas) do print('traza', t) end
    end
    if cuadros == 2 then love.graphics.captureScreenshot(args[1] or 'nativo.png')
    elseif cuadros == 6 then
      local nat = require('src.nativo')
      for _, k in ipairs({ 'window', 'game' }) do
        local t = {}
        for n, c in pairs(k == 'window' and nat.window.faltantes or nat.game.faltantes) do t[#t + 1] = n .. ':' .. c end
        table.sort(t)
        print(k .. ' sin implementar (' .. #t .. '): ' .. table.concat(t, ' '))
      end
      love.event.quit(0)
    end
  elseif modo == 'hud' then
    love.graphics.clear(0.35, 0.4, 0.35)
    local w, h = love.graphics.getDimensions()
    visor.ui:marcos_hud(w, h)
    cuadros = cuadros + 1
    if cuadros == 2 then love.graphics.captureScreenshot(args[1] or 'hud_orig.png') elseif cuadros == 6 then love.event.quit(0) end
  elseif modo == 'ventana' then
    -- --ventana id salida.png : dibuja esa ventana del cliente
    love.graphics.clear(0.35, 0.4, 0.35)
    visor.ui:dibujar_generica(tonumber(args[1]), 20, 20)
    cuadros = cuadros + 1
    if cuadros == 2 then love.graphics.captureScreenshot(args[2]) elseif cuadros == 6 then love.event.quit(0) end
  elseif modo == 'cuadros' then
    -- --cuadros ruta_spr nombre1 nombre2 ... salida.png : un cuadro por nombre, en fila
    love.graphics.clear(0.55, 0.6, 0.55)
    local ruta = args[1]
    for i = 2, #args - 1 do
      local c = visor.gfx:cuadro_spr(ruta, args[i])
      local x, y = 60 + (i - 2) * 110, 130
      love.graphics.setColor(1, 1, 1)
      if c then love.graphics.draw(c.img, x - c.ox, y - c.oy) end
      love.graphics.print(args[i], x - 20, y + 30)
    end
    cuadros = cuadros + 1
    if cuadros == 2 then love.graphics.captureScreenshot(args[#args]) elseif cuadros == 6 then love.event.quit(0) end
  elseif modo == 'vestir' then
    -- --vestir g|b item item ... salida.png : compone el personaje con ese equipo
    love.graphics.clear(0.55, 0.6, 0.55)
    local items = {}
    for i = 2, #args - 1 do items[#items + 1] = tonumber(args[i]) end
    local capas, partes = equipo:capas(items, args[1])
    for _, c in ipairs(capas) do
      local s = visor.gfx:cuadro_anim(c.id, 'wait', 3, 1, equipo:tinte_de_item(c.item))
      if s then love.graphics.setColor(1, 1, 1); love.graphics.draw(s.img, 200 - s.ox, 250 - s.oy) end
    end
    local t = {}
    for k, v in pairs(partes) do t[#t + 1] = k .. '=' .. v end
    love.graphics.print(#capas .. ' capas: ' .. table.concat(t, ' '), 10, 10)
    cuadros = cuadros + 1
    if cuadros == 2 then love.graphics.captureScreenshot(args[#args]) elseif cuadros == 6 then love.event.quit(0) end
  elseif modo == 'vivo' and (pantalla == 'login' or pantalla == 'conectando' or pantalla == 'seleccion') then
    filas_seleccion = login:dibujar(love.graphics.getWidth(), love.graphics.getHeight(), { love.mouse.getPosition() })
  elseif modo == 'vivo' then
    local w, h = love.graphics.getDimensions()
    local yo = mundo.yo and mundo.ents[mundo.yo]
    if yo and visor.mapa then
      local cam = os.getenv('AO_CAM')       -- prueba: centra la camara en una posicion del servidor (px,py)
      local cx, cy = (cam or ''):match('(%d+),(%d+)')
      if cx then visor:centrar(tonumber(cx), visor.mapa.h * 32 - tonumber(cy)) else visor:centrar(yo.x, visor.mapa.h * 32 - yo.y) end
    end
    visor:dibujar(w, h, mundo)
    if not inventario then casillas_inv = nil end
    if inventario then
      local mx, my = love.mouse.getPosition()
      casillas_inv = visor.ui:dibujar_inventario(w - 230, 60, mundo, { mx, my })
      if arrastre and love.mouse.isDown(1) then
        local img = visor.ui:icono_item(arrastre.item)
        love.graphics.setColor(1, 1, 1, 0.8)
        if img then love.graphics.draw(img.img, mx - 18, my - 18) end
        love.graphics.setColor(1, 1, 1)
      end
    end
    if equipo_abierto then
      local mx, my = love.mouse.getPosition()
      visor.ui:dibujar_equipo(w - 440, 60, mundo, { mx, my })
    end
    if misiones_abiertas then
      filas_misiones = visor.ui:dibujar_misiones(w / 2 - 280, 80, mundo, mision_sel)
    else
      filas_misiones = nil
    end
    if mascota_abierta and mundo.mascota then visor.ui:dibujar_mascota(w - 230, 330, mundo.mascota) end
    if amigos_abiertos then
      filas_amigos = visor.ui:dibujar_amigos(w - 300, 240, mundo, amigo_sel)
    else
      filas_amigos = nil
    end
    if mundo.invitacion then visor.ui:dibujar_invitacion(w, love.graphics.getHeight(), mundo.invitacion) end
    if mundo.invitacion_grupo then visor.ui:dibujar_invitacion_grupo(w, mundo.invitacion_grupo, mundo.invitacion and 50 or 0) end
    visor.ui:dibujar_grupo(4, 70, mundo)
    do
      local mx, my = love.mouse.getPosition()
      if os.getenv('AO_NATIVO') then
        -- HUD montado por los scripts ORIGINALES del cliente sobre la capa nativa
        local nat = require('src.nativo')
        if not nativo_listo then
          nativo_listo = true
          nat.window.ui = visor.ui
          local carpeta, lista = nat.carpeta_luas(), nil
          nat.cargar(carpeta, lista)
          print('CreateMainWnd', pcall(CreateMainWnd, 1))
          if os.getenv('AO_NDEBUG') then print('CMD', WND_COMMAND_X, WND_COMMAND_Y, window.width(WND_COMMAND), window.left(WND_COMMAND), window.top(WND_COMMAND), SYSTEM_SCREEN_WIDTH, SYSTEM_SCREEN_HEIGHT) end
        end
        do
          local an, al = love.graphics.getDimensions()
          if os.getenv('AO_NDEBUG') and not dbg_dim then dbg_dim = true; print('DIM', an, al, nat.tam and nat.tam[1], nat.tam and nat.tam[2], love.window.getMode()) end
          if nat.tam and (nat.tam[1] ~= an or nat.tam[2] ~= al) then nat.relayout(1) end
          nat.tam = nat.tam or { an, al }
        end
        nat.window.alimentar(mundo)
        nat.window.retrato_fn = nat.window.retrato_fn or function(cx, cy, r)
          -- cabeza del personaje (capas de la ficha vistas de frente) dentro de un circulo: lo que el original pinta en el aro del panel
          local ids = visor.equipo:personaje(mundo:puesto(), mundo.apariencia, mundo.genero or 'g')
          love.graphics.stencil(function() love.graphics.circle('fill', cx, cy, r) end, 'replace', 1)
          love.graphics.setStencilTest('greater', 0)
          love.graphics.setColor(0.12, 0.2, 0.25, 0.9); love.graphics.circle('fill', cx, cy, r)
          love.graphics.setColor(1, 1, 1)
          local k = 1.7
          for _, c in ipairs(ids or {}) do
            local s = visor.gfx:cuadro_anim(c.id, 'wait', 3, 2, c.tinte)
            if s then love.graphics.draw(s.img, cx - s.ox * k, cy + 70 * k - s.oy * k, 0, k, k) end
          end
          love.graphics.setStencilTest()
        end
        if nv_hecho and not nv_info and love.timer.getTime() - t0 > 7 then
          nv_info = true
          local fi, ic = 0, 0
          for _, v in pairs(nat.window.vivas) do if v.itemid then fi = fi + 1; if visor.ui:icono_item(v.itemid) then ic = ic + 1 end end end
          print('despues: casillas', fi, 'con icono', ic)
        end
        local ni = os.getenv('AO_NABRIR')       -- prueba: pulsa los botones del menu con esos ids (119 = misiones, 120 = amigos...)
        if ni and not ni_hecho and love.timer.getTime() - t0 > 5 then
          ni_hecho = true
          for id in ni:gmatch('%d+') do
            for _, w in pairs(nat.window.vivas) do
              if w.id == tonumber(id) and w.visible and w.def and w.def.eventos then
                local x, y = nat.window.abs(w)
                nat.window.clic(x + w.w / 2, y + w.hh / 2)
                print('abierta', id)
                break
              end
            end
          end
        end
        local nl = os.getenv('AO_NLLAMAR')       -- prueba: llama a una funcion global de los scripts originales (p.ej. CreateEquipWnd)
        if nl and not nl_hecho and love.timer.getTime() - t0 > 5 then
          nl_hecho = true
          print('llamar', nl, pcall(_G[nl]))
        end
        local nv2 = os.getenv('AO_NDOBLE')
        if nv2 and not nv2_hecho and nv_hecho and love.timer.getTime() - t0 > 7 then
          nv2_hecho = true
          local a, b = nv2:match('(%d+),(%d+)')
          love.mousepressed(tonumber(a), tonumber(b), 1); love.mousepressed(tonumber(a), tonumber(b), 1)
          print('doble clic nativo en', nv2)
        end
        local nv = os.getenv('AO_NCLIC_VIVO')
        if nv and not nv_hecho and love.timer.getTime() - t0 > 5 then
          nv_hecho = true
          local a, b = nv:match('(%d+),(%d+)')
          local w2 = nat.window.clic(tonumber(a), tonumber(b))
          print('clic nativo', nv, w2 and w2.id or 'nada', 'item wnd', nat.game.itemwnd)
          local n = 0
          for k, v in pairs(mundo.items or {}) do n = n + 1; if n < 4 then print('item', k, v) end end
          print('items en mochila', n)
          local fi = 0
          for _, v in pairs(nat.window.vivas) do if v.itemid then fi = fi + 1 end end
          local b20 = 0
          for k in pairs(mundo.items or {}) do if k >= 20 then b20 = b20 + 1 end end
          local iw = nat.window.vivas[nat.game.itemwnd or 0]
          print('iw', iw and iw.id, iw and #iw.hijos, nat.window.api.find(nat.game.itemwnd, 3101))
          print('casillas con item', fi, 'items >=20', b20)
        end
        if os.getenv('AO_NDEBUG') and not nd_hecho and #mundo.chat > 0 then
          nd_hecho = true
          local c = nat.window.vivas[WND_CHAT_CONTENT_0]
          print('chat content', WND_CHAT_CONTENT_0, c and c.visible, c and c.lineas and #c.lineas, c and c.w, c and c.hh, c and c.def and c.def.class)
        end
        nat.window.dibujar_todo()
        filas_barra, filas_menu = {}, {}
      else
        local r = visor.ui:dibujar_hud_original(w, love.graphics.getHeight(), mundo, enfriando, { mx, my }, minimapa_grande, escribiendo, texto_chat)
        filas_barra, filas_menu = r.barra, r.menu
      end
    end
    if mundo.banco_abierto then
      local mx, my = love.mouse.getPosition()
      casillas_banco = visor.ui:dibujar_banco(60, 80, mundo, { mx, my })
      inventario = true
    else
      casillas_banco = nil
    end
    if mundo.tienda then
      local mx, my = love.mouse.getPosition()
      filas_tienda = visor.ui:dibujar_tienda(60, 120, mundo.tienda, mundo, { mx, my })
    else
      filas_tienda = nil
    end
    if mundo.dialogo then
      local mx, my = love.mouse.getPosition()
      opciones_dialogo = visor.ui:dibujar_dialogo(mundo.dialogo, w, love.graphics.getHeight(), { mx, my })
    else
      opciones_dialogo = nil
    end
    if os.getenv('AO_DEBUG') then love.graphics.print(sesion.estado, 8, 70) end
    cuadros = cuadros + 1
    if os.getenv('AO_FOTO_ATAQUE') and atacado and not capturado and love.timer.getTime() - atacado > 0.9 then
      capturado = true
      love.graphics.captureScreenshot(args[6] or 'vivo.png')
    elseif args[5] and not os.getenv('AO_FOTO_ATAQUE') and love.timer.getTime() - t0 > tonumber(args[5]) and not capturado then
      capturado = true
      love.graphics.captureScreenshot(args[6] or 'vivo.png')
    elseif capturado then
      cuadros = cuadros + 1
      if cuadros > 600 then love.event.quit(0) end
    end
  elseif not modo then
    love.graphics.print('Prototipo: capa de red y sesion listas. Siguiente: dibujar el mapa.', 20, 20)
  end
end
