-- Cliente propio multiplataforma de Angels Online Forever (LÖVE 11+)
function love.conf(t)
  t.identity = 'angels-cliente'
  t.version = '11.4'
  t.console = false
  t.window.title = 'Angels Online Forever'
  t.window.width = 1280
  t.window.height = 720
  t.window.resizable = true
  t.window.minwidth = 1024
  t.window.minheight = 600
  -- con --pruebas / --sonda no se abre ventana
  if arg then
    for _, a in ipairs(arg) do
      if a == '--pruebas' or a == '--sonda' then t.window = false; t.modules.window = false end
    end
  end
end
