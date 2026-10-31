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

        public static string Url(string archivo)
        {
            string host = Config.Servidor, puerto = Config.Puerto.ToString();
            // launcher.ini (opcional, junto al exe) puede cambiar a donde mira: Servidor = ..., Puerto = ...
            string ini = Path.Combine(Carpeta, "launcher.ini");
            if (File.Exists(ini))
            {
                foreach (string linea in File.ReadAllLines(ini))
                {
                    string[] kv = linea.Split(new[] { '=' }, 2);
                    if (kv.Length != 2) continue;
                    string k = kv[0].Trim().ToLowerInvariant(), v = kv[1].Trim();
                    if (k == "servidor" && v.Length > 0) host = v;
                    if (k == "puerto" && v.Length > 0) puerto = v;
                }
            }
            return "http://" + host + ":" + puerto + "/" + archivo;
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

        public static void LanzarJuego()
        {
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
