-- Cliente multiplataforma de Angels Online (LÖVE 11: Windows, Linux, macOS, Android, iOS)
function love.conf(t)
  t.identity = 'angels-cliente'
  t.version = '11.4'
  t.console = false
  t.window.title = 'Angels Online - cliente (prototipo)'
  t.window.width = 1024
  t.window.height = 768
  t.window.resizable = true
  -- con --pruebas no se abre ventana: solo corre las pruebas y sale
  if arg then
    for _, a in ipairs(arg) do
      if a == '--pruebas' or a == '--sonda' then t.window = false; t.modules.window = false end
    end
  end
end
