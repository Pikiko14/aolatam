// Launcher propio de Angels Online (aolatam). Reemplaza al START.EXE de IGG:
//   * pide GET /launcher.json al servidor de parches (puerto 2121, que tambien habla HTTP)
//   * baja update27.pak ENTERO, lo verifica con su sha256 y lo pone siempre en el mismo sitio
//     (sin el limite update28..update31 del START.EXE, que solo instalaba en un pak nuevo)
//   * retira los update28..update31 que dejo el START.EXE con versiones viejas del parche
//   * se actualiza a si mismo y lanza angel.dat
// Se compila con tools/compilar_launcher.py (csc de .NET Framework 4.8, sin instalar nada). C# 5.
using System;
using System.IO;
using System.Windows.Forms;

namespace AngelsLauncher
{
    static class Programa
    {
        [STAThread]
        static void Main(string[] args)
        {
            // Restos de una auto-actualizacion: el exe viejo se renombra a .old y se borra en el siguiente arranque.
            try
            {
                string viejo = Application.ExecutablePath + ".old";
                if (File.Exists(viejo)) File.Delete(viejo);
            }
            catch (Exception) { }

            if (Array.IndexOf(args, "--prueba") >= 0)
            {
                // Sin ventana: comprueba, actualiza y dice que hizo (lo usa tools/compilar_launcher.py --probar).
                Environment.ExitCode = Actualizador.Prueba(Console.Out);
                return;
            }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new Ventana());
        }
    }
}
