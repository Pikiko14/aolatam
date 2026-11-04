// Lo que hace el launcher, sin nada de ventanas: lo usa la Ventana desde un hilo aparte y el modo --prueba.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace AngelsLauncher
{
    class Noticia
    {
        public string Fecha, Titulo, Texto;
    }

    class Manifiesto
    {
        public string Version, Pak, Sha256;
        public long Bytes;
        public List<Noticia> Noticias = new List<Noticia>();
        public HashSet<string> Archivos = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        public string LauncherSha256;
        public long LauncherBytes;
        // El exe del juego (angel.dat): el del servidor lleva el canal 0x01A0 de las ventanas propias (la subasta).
        public string JuegoSha256;
        public long JuegoBytes;
    }

    // Avisos hacia la ventana: texto de estado y progreso (0..1, o -1 si no se sabe).
    delegate void Aviso(string estado, double progreso);

    static class Actualizador
    {
        public const string Juego = "angel.dat";
        // Paks que dejaba el START.EXE de IGG, cada version del parche en uno nuevo (el juego carga hasta update31).
        static readonly int[] PaksViejos = { 28, 29, 30, 31 };

        public static string Carpeta
        {
            get { return Path.GetDirectoryName(Application.ExecutablePath); }
        }

        // launcher.ini (opcional, junto al exe) puede cambiar a donde mira: Servidor = ..., Puerto = ...
        static string DelIni(string clave, string porDefecto)
        {
            string ini = Path.Combine(Carpeta, "launcher.ini");
            if (!File.Exists(ini)) return porDefecto;
            foreach (string linea in File.ReadAllLines(ini))
            {
                string[] kv = linea.Split(new[] { '=' }, 2);
                if (kv.Length != 2) continue;
                if (kv[0].Trim().ToLowerInvariant() == clave && kv[1].Trim().Length > 0) porDefecto = kv[1].Trim();
            }
            return porDefecto;
        }

        public static string Host()
        {
            return DelIni("servidor", Config.Servidor);
        }

        public static string Url(string archivo)
        {
            return "http://" + Host() + ":" + DelIni("puerto", Config.Puerto.ToString()) + "/" + archivo;
        }

        public static bool HayJuego()
        {
            return File.Exists(Path.Combine(Carpeta, Juego));
        }

        static HttpWebRequest Peticion(string url)
        {
            var r = (HttpWebRequest)WebRequest.Create(url);
            r.Timeout = 15000;
            r.ReadWriteTimeout = 30000;
            r.UserAgent = "AngelsLauncher/" + Config.VersionLauncher;
            r.Proxy = null;
            return r;
        }

        public static Manifiesto LeerManifiesto()
        {
            string texto;
            using (var resp = Peticion(Url("launcher.json")).GetResponse())
            using (var lector = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                texto = lector.ReadToEnd();
            var d = (Dictionary<string, object>)new JavaScriptSerializer().DeserializeObject(texto);
            var m = new Manifiesto();
            m.Version = Texto(d, "version");
            m.Pak = Texto(d, "pak");
            if (m.Pak.Length == 0) m.Pak = "update27.pak";
            m.Sha256 = Texto(d, "sha256").ToLowerInvariant();
            m.Bytes = Numero(d, "bytes");
            object lista;
            if (d.TryGetValue("noticias", out lista) && lista is IEnumerable)
            {
                foreach (object o in (IEnumerable)lista)
                {
                    var n = o as Dictionary<string, object>;
                    if (n == null) continue;
                    m.Noticias.Add(new Noticia { Fecha = Texto(n, "fecha"), Titulo = Texto(n, "titulo"), Texto = Texto(n, "texto") });
                }
            }
            if (d.TryGetValue("archivos", out lista) && lista is IEnumerable)
                foreach (object o in (IEnumerable)lista) m.Archivos.Add(Convert.ToString(o));
            object l;
            if (d.TryGetValue("launcher", out l) && l is Dictionary<string, object>)
            {
                var ld = (Dictionary<string, object>)l;
                m.LauncherSha256 = Texto(ld, "sha256").ToLowerInvariant();
                m.LauncherBytes = Numero(ld, "bytes");
            }
            if (d.TryGetValue("juego", out l) && l is Dictionary<string, object>)
            {
                var jd = (Dictionary<string, object>)l;
                m.JuegoSha256 = Texto(jd, "sha256").ToLowerInvariant();
                m.JuegoBytes = Numero(jd, "bytes");
            }
            return m;
        }

        static string Texto(Dictionary<string, object> d, string k)
        {
            object v;
            return d.TryGetValue(k, out v) && v != null ? Convert.ToString(v) : "";
        }

        static long Numero(Dictionary<string, object> d, string k)
        {
            object v;
            return d.TryGetValue(k, out v) && v != null ? Convert.ToInt64(v) : 0;
        }

        public static string Sha256DeArchivo(string ruta)
        {
            using (var sha = SHA256.Create())
            using (var f = File.OpenRead(ruta))
                return BitConverter.ToString(sha.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        // Baja `archivo` a `destino`, comprobando tamano y sha256. Nunca deja `destino` a medias.
        static void Bajar(string archivo, string destino, long bytes, string sha, Aviso aviso, string que)
        {
            string tmp = destino + ".descarga";
            using (var resp = Peticion(Url(archivo)).GetResponse())
            using (var entrada = resp.GetResponseStream())
            using (var salida = File.Create(tmp))
            {
                long total = bytes > 0 ? bytes : resp.ContentLength, leidos = 0;
                byte[] buf = new byte[65536];
                int n;
                var reloj = Stopwatch.StartNew();
                while ((n = entrada.Read(buf, 0, buf.Length)) > 0)
                {
                    salida.Write(buf, 0, n);
                    leidos += n;
                    if (reloj.ElapsedMilliseconds > 80 || leidos == total)
                    {
                        reloj.Restart();
                        aviso(string.Format("{0}  {1:0.0} / {2:0.0} MB", que, leidos / 1048576.0, total / 1048576.0),
                              total > 0 ? (double)leidos / total : -1);
                    }
                }
            }
            if (bytes > 0 && new FileInfo(tmp).Length != bytes)
            {
                File.Delete(tmp);
                throw new IOException("La descarga llegó incompleta. Vuelve a intentarlo.");
            }
            if (sha.Length > 0 && Sha256DeArchivo(tmp) != sha)
            {
                File.Delete(tmp);
                throw new IOException("La descarga llegó dañada (no coincide el sha256). Vuelve a intentarlo.");
            }
            if (File.Exists(destino)) File.Delete(destino);
            File.Move(tmp, destino);
        }

        // True si hay un launcher nuevo y ya se ha puesto en su sitio (hay que reiniciarlo).
        public static bool AutoActualizar(Manifiesto m, Aviso aviso)
        {
            if (string.IsNullOrEmpty(m.LauncherSha256)) return false;
            string yo = Application.ExecutablePath;
            if (Sha256DeArchivo(yo) == m.LauncherSha256) return false;
            string nuevo = yo + ".nuevo";
            Bajar(Config.ArchivoLauncher, nuevo, m.LauncherBytes, m.LauncherSha256, aviso, "Actualizando el launcher");
            // Windows deja renombrar un exe en marcha, no borrarlo: el viejo se va a .old y se borra al arrancar.
            string viejo = yo + ".old";
            if (File.Exists(viejo)) File.Delete(viejo);
            File.Move(yo, viejo);
            File.Move(nuevo, yo);
            return true;
        }

        // Retira (a respaldo_launcher\) los update28..31 que dejo el START.EXE, solo si TODO lo que llevan es de este
        // parche: con un numero mas alto pisaban al update27 nuevo. Devuelve los que retiro.
        public static List<string> RetirarPaksViejos(Manifiesto m)
        {
            var retirados = new List<string>();
            foreach (int n in PaksViejos)
            {
                string ruta = Path.Combine(Carpeta, "update" + n + ".pak");
                if (!File.Exists(ruta)) continue;
                List<string> nombres;
                try { nombres = Pak.Nombres(ruta); }
                catch (Exception) { continue; }
                bool nuestro = m.Archivos.Count > 0;
                foreach (string nom in nombres)
                    if (!m.Archivos.Contains(nom)) { nuestro = false; break; }
                if (!nuestro) continue;
                string respaldo = Path.Combine(Carpeta, "respaldo_launcher");
                Directory.CreateDirectory(respaldo);
                string destino = Path.Combine(respaldo, "update" + n + ".pak." + DateTime.Now.ToString("yyyyMMdd_HHmmss"));
                File.Move(ruta, destino);
                retirados.Add("update" + n + ".pak");
            }
            return retirados;
        }

        // True si el pak del parche no esta o no coincide con el del servidor.
        public static bool HaceFaltaParche(Manifiesto m)
        {
            string ruta = Path.Combine(Carpeta, m.Pak);
            if (m.Sha256.Length == 0) return false;
            if (!File.Exists(ruta)) return true;
            if (m.Bytes > 0 && new FileInfo(ruta).Length != m.Bytes) return true;
            return Sha256DeArchivo(ruta) != m.Sha256;
        }

        public static void InstalarParche(Manifiesto m, Aviso aviso)
        {
            string ruta = Path.Combine(Carpeta, m.Pak);
            try
            {
                Bajar(m.Pak, ruta, m.Bytes, m.Sha256, aviso, "Descargando la versión " + m.Version);
            }
            catch (UnauthorizedAccessException)
            {
                throw new IOException("No se puede escribir " + m.Pak + ". Cierra el juego y vuelve a intentarlo.");
            }
            catch (IOException e)
            {
                if (e.Message.StartsWith("La descarga")) throw;
                throw new IOException("No se puede reemplazar " + m.Pak + ". Cierra el juego y vuelve a intentarlo.");
            }
            EscribirVersion(m.Version);
        }

        // True si el angel.dat de la carpeta no es el que anuncia el servidor.
        public static bool HaceFaltaJuego(Manifiesto m)
        {
            if (string.IsNullOrEmpty(m.JuegoSha256)) return false;
            string ruta = Path.Combine(Carpeta, Juego);
            if (!File.Exists(ruta)) return true;
            if (m.JuegoBytes > 0 && new FileInfo(ruta).Length != m.JuegoBytes) return true;
            return Sha256DeArchivo(ruta) != m.JuegoSha256;
        }

        // Pone el angel.dat del servidor. El que habia se guarda en respaldo_launcher\ (el original solo la primera
        // vez, para poder volver a el); la descarga se comprueba entera antes de reemplazarlo.
        public static void InstalarJuego(Manifiesto m, Aviso aviso)
        {
            string ruta = Path.Combine(Carpeta, Juego);
            try
            {
                if (File.Exists(ruta))
                {
                    string respaldo = Path.Combine(Carpeta, "respaldo_launcher");
                    Directory.CreateDirectory(respaldo);
                    string original = Path.Combine(respaldo, Juego + ".original");
                    if (!File.Exists(original)) File.Copy(ruta, original);
                }
                Bajar(Juego, ruta, m.JuegoBytes, m.JuegoSha256, aviso, "Actualizando el juego");
            }
            catch (UnauthorizedAccessException)
            {
                throw new IOException("No se puede reemplazar " + Juego + ". Cierra el juego y vuelve a intentarlo.");
            }
            catch (IOException e)
            {
                if (e.Message.StartsWith("La descarga")) throw;
                throw new IOException("No se puede reemplazar " + Juego + ". Cierra el juego y vuelve a intentarlo.");
            }
        }

        // El juego lee su version de reg.ini. Saltos de linea LF: con CRLF el START.EXE de IGG se rompia.
        public static void EscribirVersion(string version)
        {
            if (string.IsNullOrEmpty(version)) return;
            string ini = Path.Combine(Carpeta, "reg.ini");
            var lineas = new List<string>();
            bool puesta = false;
            if (File.Exists(ini))
            {
                foreach (string l in File.ReadAllText(ini).Replace("\r", "").Split('\n'))
                {
                    if (l.Length == 0) continue;
                    if (l.TrimStart().StartsWith("Version", StringComparison.OrdinalIgnoreCase) && l.Contains("="))
                    {
                        lineas.Add("Version = " + version);
                        puesta = true;
                    }
                    else lineas.Add(l);
                }
            }
            if (lineas.Count == 0) lineas.Add("[PROFILE]");
            if (!puesta) lineas.Add("Version = " + version);
            File.WriteAllText(ini, string.Join("\n", lineas) + "\n", new UTF8Encoding(false));
        }

        // El nombre del servidor que el cliente pinta al entrar ("Impacty(AOF-1)") sale del 名稱 de server.xml. El
        // server.xml va en el zip del cliente con el nombre viejo: se cambia aqui. Y tambien la IP del juego (ip) y la
        // del FTP de parches (fip): son las del servidor del launcher, asi que al mudar el servidor de VPS (77.42.52.122
        // -> 179.66.132.19, 04/11/2026) basta con que el launcher se actualice para que el juego entre en el nuevo.
        public static void PonerNombreServidor()
        {
            string xml = Path.Combine(Carpeta, "server.xml");
            if (!File.Exists(xml)) return;
            byte[] crudo = File.ReadAllBytes(xml);
            bool bom = crudo.Length >= 3 && crudo[0] == 0xEF && crudo[1] == 0xBB && crudo[2] == 0xBF;
            string texto = new UTF8Encoding(false).GetString(crudo, bom ? 3 : 0, crudo.Length - (bom ? 3 : 0));
            string nuevo = System.Text.RegularExpressions.Regex.Replace(texto, "(<伺服器\\s[^>]*?名稱\\s*=\\s*\")[^\"]*(\")",
                m => m.Groups[1].Value + Config.NombreServidor + m.Groups[2].Value);
            string host = Host();
            foreach (string attr in new[] { "ip", "fip" })
                nuevo = System.Text.RegularExpressions.Regex.Replace(nuevo,
                    "(<伺服器\\s[^>]*?\\s" + attr + "\\s*=\\s*\")[^\"]*(\")",
                    m => m.Groups[1].Value + host + m.Groups[2].Value);
            if (nuevo == texto) return;
            File.WriteAllText(xml, nuevo, new UTF8Encoding(bom));
        }

        public static void LanzarJuego()
        {
            try { PonerNombreServidor(); }
            catch (Exception) { }                   // un server.xml de solo lectura no impide jugar
            var info = new ProcessStartInfo(Path.Combine(Carpeta, Juego));
            info.WorkingDirectory = Carpeta;        // el juego lee reg.ini, server.xml y los .pak de ahi
            info.UseShellExecute = false;           // CreateProcess directo: angel.dat es un exe con otra extension
            Process.Start(info);
        }

        // Modo --prueba: lo mismo que la ventana, escrito en consola. 0 = todo bien.
        public static int Prueba(TextWriter salida)
        {
            try
            {
                salida.WriteLine("carpeta: " + Carpeta + (HayJuego() ? "" : "  (SIN angel.dat)"));
                salida.WriteLine("servidor: " + Url("launcher.json"));
                var m = LeerManifiesto();
                salida.WriteLine("version del servidor: " + m.Version + "  pak " + m.Pak + " (" + m.Bytes + " B)");
                foreach (string p in RetirarPaksViejos(m)) salida.WriteLine("retirado: " + p);
                if (HaceFaltaParche(m))
                {
                    InstalarParche(m, (e, p) => { });
                    salida.WriteLine("parche instalado: " + m.Pak);
                }
                else salida.WriteLine("el parche ya esta al dia");
                if (HaceFaltaJuego(m))
                {
                    InstalarJuego(m, (e, p) => { });
                    salida.WriteLine("juego actualizado: " + Juego);
                }
                else salida.WriteLine("el juego ya esta al dia");
                PonerNombreServidor();
                salida.WriteLine("server.xml apunta a " + Host());
                if (HaceFaltaJuego(m))
                {
                    salida.WriteLine("verificado: NO (" + Juego + ")");
                    return 1;
                }
                salida.WriteLine("verificado: " + (HaceFaltaParche(m) ? "NO" : "si"));
                return HaceFaltaParche(m) ? 1 : 0;
            }
            catch (Exception e)
            {
                salida.WriteLine("ERROR: " + e.Message);
                return 2;
            }
        }
    }
}
