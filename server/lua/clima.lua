-- El clima se puede apagar en System > Display > Weather (server/mundo_vivo.py, 27/11/2026: "haz que el clima se pueda
-- desactivar desde las opciones, en display, me refiero al efecto"). La opcion es del cliente (sys.lua: ShowWeather, 0
-- Open, 1 Close) y el servidor no la ve: este trozo se la dice al cargar y cada vez que se cambia, y el servidor deja de
-- mandar la lluvia / nieve / niebla y los efectos del clima a quien la tiene en Close.
local CMD_CLIMA = 181

local function avisar_clima()
  game.netcommand2(CMD_CLIMA, ShowWeather or 0, 0)
end

if not AOF_CLIMA_OPCION and SaveState_RadioButton then
  AOF_CLIMA_OPCION = true
  local original = SaveState_RadioButton
  SaveState_RadioButton = function(dwID, dwCmdID, dwParam, pParam)
    local r = original(dwID, dwCmdID, dwParam, pParam)
    local appdata = window.getappdata(dwID)
    if appdata == 12040 or appdata == 12041 then
      avisar_clima()
    end
    return r
  end
end

-- Default (RestoreSetting), OK y Cancel de la ventana de opciones tambien la cambian (Cancel devuelve la de antes).
if not AOF_CLIMA_OK then
  AOF_CLIMA_OK = true
  for _, nombre in ipairs({"RestoreSetting", "OnSysChangeOK", "OnSysChangeCancel", "OnSysChangeCancel_X",
                           "OnSysCancelNoSave"}) do
    local f = _G[nombre]
    if f then
      _G[nombre] = function(dwID, dwCmdID, dwParam, pParam)
        local r = f(dwID, dwCmdID, dwParam, pParam)
        avisar_clima()
        return r
      end
    end
  end
end

avisar_clima()
