-- La votacion semanal (server/votacion.py): usa la ventana del panel de misiones (58800, misiones.lua) con su titulo.
-- Si el cliente no tiene la ventana contesta game.netcommand2(177, 9, 0) y el servidor lo manda por el chat.
function VTAbrir(titulo, linea1, linea2, pie, filas)
  if window.isexist(WND_MD) then
    window.setforeground(WND_MD)
  else
    WND_MD = window.create(58800, 0, 0, SYSTEM_HANDLER)
    if not window.isexist(WND_MD) then
      game.netcommand2(177, 9, 0)
      return
    end
    window.move(WND_MD, SYSTEM_SCREEN_WIDTH / 2 - 214, 110)
    window.regsetting(WND_MD, "WND_MISIONES")
  end
  window.settitle(WND_MD, "Weekly Vote")
  MDDatos(titulo, linea1, linea2, pie, filas)
end
