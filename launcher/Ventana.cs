// La ventana del launcher, dibujada a mano (GDI+): fondo animado, noticias, progreso y botones.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

namespace AngelsLauncher
{
    class Ventana : Form
    {
        // ---- colores
        static readonly Color CieloArriba = Color.FromArgb(11, 20, 52);
        static readonly Color CieloAbajo = Color.FromArgb(52, 28, 98);
        static readonly Color Rosa = Color.FromArgb(255, 126, 179);
        static readonly Color Oro = Color.FromArgb(255, 205, 96);
        static readonly Color OroOscuro = Color.FromArgb(232, 128, 44);
        static readonly Color TextoSuave = Color.FromArgb(214, 214, 236);

        // ---- zonas
        Rectangle rCerrar, rMinimizar, rJugar, rReparar, rCarpeta, rNoticias, rBarra;

        // ---- estado (lo tocan el hilo de trabajo y el de la ventana: se lee y escribe con lock)
        readonly object cerrojo = new object();
        string estado = "Conectando con el servidor...";
        double progreso = -1;
        bool listo, trabajando, conError;
        string versionServidor = "", versionLocal = "";
        List<Noticia> noticias = new List<Noticia>();
        string sobre = "";                       // boton bajo el raton

        // ---- particulas del fondo
        class Particula { public float X, Y, R, V, Fase; }
        readonly List<Particula> particulas = new List<Particula>();
        readonly Random azar = new Random(7);
        readonly System.Windows.Forms.Timer reloj = new System.Windows.Forms.Timer();
        float tiempo;

        public Ventana()
        {
            Text = Config.Titulo;
            ClientSize = new Size(980, 580);
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterScreen;
            DoubleBuffered = true;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint, true);
            BackColor = CieloArriba;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }
            using (var camino = Redondeado(new Rectangle(0, 0, Width, Height), 18))
                Region = new Region(camino);

            rCerrar = new Rectangle(Width - 46, 14, 30, 30);
            rMinimizar = new Rectangle(Width - 84, 14, 30, 30);
            rNoticias = new Rectangle(40, 168, 540, 290);
            rJugar = new Rectangle(640, 330, 300, 78);
            rReparar = new Rectangle(640, 420, 144, 38);
            rCarpeta = new Rectangle(796, 420, 144, 38);
            rBarra = new Rectangle(40, 520, 900, 12);

            for (int i = 0; i < 70; i++) particulas.Add(NuevaParticula(true));
            reloj.Interval = 33;
            reloj.Tick += (s, e) => { Animar(); Invalidate(); };
            reloj.Start();

            Shown += (s, e) => Empezar(false);
        }

        // ------------------------------------------------------------------ trabajo
        void Avisar(string texto, double p)
        {
            lock (cerrojo) { estado = texto; progreso = p; }
        }

        void Empezar(bool reparar)
        {
            lock (cerrojo)
            {
                if (trabajando) return;
                trabajando = true; listo = false; conError = false;
            }
            var hilo = new Thread(() => Trabajar(reparar));
            hilo.IsBackground = true;
            hilo.Start();
        }

        void Trabajar(bool reparar)
        {
            bool puedeJugar = false, error = false;
            try
            {
                if (!Actualizador.HayJuego())
                {
                    Avisar("No encuentro angel.dat: copia el launcher en la carpeta del juego.", 0);
                    error = true;
                    return;
                }
                Avisar("Conectando con el servidor...", -1);
                Manifiesto m;
                try { m = Actualizador.LeerManifiesto(); }
                catch (Exception)
                {
                    Avisar("Sin conexión con el servidor de actualizaciones. Puedes jugar igual.", 0);
                    puedeJugar = true;
                    error = true;
                    return;
                }
                lock (cerrojo) { versionServidor = m.Version; noticias = m.Noticias; }

                if (Actualizador.AutoActualizar(m, Avisar))
                {
                    Avisar("Launcher actualizado. Reiniciando...", 1);
                    Process.Start(Application.ExecutablePath);
                    BeginInvoke((MethodInvoker)Close);
                    return;
                }
                Avisar("Revisando los archivos del juego...", -1);
                Actualizador.RetirarPaksViejos(m);
                if (reparar || Actualizador.HaceFaltaParche(m))
                    Actualizador.InstalarParche(m, Avisar);
                else
                    Actualizador.EscribirVersion(m.Version);
                lock (cerrojo) versionLocal = m.Version;
                Avisar("Todo al día. Listo para jugar.", 1);
                puedeJugar = true;
            }
            catch (Exception e)
            {
                Avisar(e.Message, 0);
                error = true;
            }
            finally
            {
                lock (cerrojo) { trabajando = false; listo = puedeJugar; conError = error; }
            }
        }

        void Jugar()
        {
            try
            {
                Actualizador.LanzarJuego();
                Close();
            }
            catch (Exception e)
            {
                Avisar("No se pudo abrir el juego: " + e.Message, 0);
                lock (cerrojo) conError = true;
            }
        }

        // ------------------------------------------------------------------ raton
        [DllImport("user32.dll")] static extern bool ReleaseCapture();
        [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, int msg, int w, int l);

        string BotonEn(Point p)
        {
            if (rCerrar.Contains(p)) return "cerrar";
            if (rMinimizar.Contains(p)) return "minimizar";
            if (rJugar.Contains(p)) return "jugar";
            if (rReparar.Contains(p)) return "reparar";
            if (rCarpeta.Contains(p)) return "carpeta";
            return "";
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            sobre = BotonEn(e.Location);
            Cursor = sobre.Length > 0 ? Cursors.Hand : Cursors.Default;
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            base.OnMouseLeave(e);
            sobre = "";
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
            if (e.Button != MouseButtons.Left) return;
            string b = BotonEn(e.Location);
            bool ocupado, puede;
            lock (cerrojo) { ocupado = trabajando; puede = listo; }
            if (b == "cerrar") Close();
            else if (b == "minimizar") WindowState = FormWindowState.Minimized;
            else if (b == "jugar") { if (puede && !ocupado) Jugar(); }
            else if (b == "reparar") { if (!ocupado) Empezar(true); }
            else if (b == "carpeta") Process.Start("explorer.exe", "\"" + Actualizador.Carpeta + "\"");
            else
            {
                // Arrastrar la ventana desde cualquier sitio libre.
                ReleaseCapture();
                SendMessage(Handle, 0xA1, 2, 0);
            }
        }

        // ------------------------------------------------------------------ animacion
        Particula NuevaParticula(bool cualquierAltura)
        {
            var p = new Particula();
            p.X = (float)(azar.NextDouble() * Width);
            p.Y = cualquierAltura ? (float)(azar.NextDouble() * Height) : Height + 10;
            p.R = (float)(1.0 + azar.NextDouble() * 3.2);
            p.V = (float)(0.15 + azar.NextDouble() * 0.55);
            p.Fase = (float)(azar.NextDouble() * Math.PI * 2);
            return p;
        }

        void Animar()
        {
            tiempo += 0.033f;
            for (int i = 0; i < particulas.Count; i++)
            {
                var p = particulas[i];
                p.Y -= p.V;
                p.X += (float)Math.Sin(tiempo + p.Fase) * 0.2f;
                if (p.Y < -10) particulas[i] = NuevaParticula(false);
            }
        }

        // ------------------------------------------------------------------ dibujo
        static GraphicsPath Redondeado(Rectangle r, int radio)
        {
            var g = new GraphicsPath();
            int d = radio * 2;
            g.AddArc(r.X, r.Y, d, d, 180, 90);
            g.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            g.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            g.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            g.CloseFigure();
            return g;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;

            string est, vServ, vLoc; double prog; bool ok, ocupado, fallo; List<Noticia> nots;
            lock (cerrojo)
            {
                est = estado; prog = progreso; ok = listo; ocupado = trabajando; fallo = conError;
                vServ = versionServidor; vLoc = versionLocal; nots = noticias;
            }

            Fondo(g);
            Titulo(g);
            BotonVentana(g, rMinimizar, "minimizar");
            BotonVentana(g, rCerrar, "cerrar");
            PanelNoticias(g, nots);
            PanelDerecho(g, vServ, vLoc, ok, ocupado);
            Barra(g, est, prog, fallo);
        }

        void Fondo(Graphics g)
        {
            var todo = new Rectangle(0, 0, Width, Height);
            using (var b = new LinearGradientBrush(todo, CieloArriba, CieloAbajo, 90f))
                g.FillRectangle(b, todo);
            // resplandor rosado abajo, y uno dorado tenue arriba a la derecha
            Resplandor(g, new RectangleF(Width * 0.15f, Height * 0.55f, Width * 0.7f, Height * 0.9f), Color.FromArgb(110, Rosa));
            Resplandor(g, new RectangleF(Width * 0.55f, -Height * 0.35f, Width * 0.6f, Height * 0.8f), Color.FromArgb(55, Oro));
            foreach (var p in particulas)
            {
                int a = (int)(90 + 80 * Math.Sin(tiempo * 2 + p.Fase));
                a = Math.Max(20, Math.Min(200, a));
                using (var b = new SolidBrush(Color.FromArgb(a, 255, 240, 250)))
                    g.FillEllipse(b, p.X - p.R, p.Y - p.R, p.R * 2, p.R * 2);
            }
            using (var borde = Redondeado(new Rectangle(0, 0, Width - 1, Height - 1), 18))
            using (var pen = new Pen(Color.FromArgb(70, 255, 255, 255), 1.5f))
                g.DrawPath(pen, borde);
        }

        static void Resplandor(Graphics g, RectangleF r, Color c)
        {
            using (var camino = new GraphicsPath())
            {
                camino.AddEllipse(r);
                using (var b = new PathGradientBrush(camino))
                {
                    b.CenterColor = c;
                    b.SurroundColors = new[] { Color.FromArgb(0, c) };
                    g.FillPath(b, camino);
                }
            }
        }

        void Titulo(Graphics g)
        {
            using (var f = new Font("Georgia", 44, FontStyle.Bold | FontStyle.Italic))
            {
                var pos = new PointF(36, 30);
                // brillo: el mismo texto varias veces, desplazado y transparente
                for (int i = 6; i >= 1; i--)
                    using (var b = new SolidBrush(Color.FromArgb(18, Rosa)))
                        for (int dx = -1; dx <= 1; dx++)
                            g.DrawString(Config.Titulo, f, b, pos.X + dx * i, pos.Y + i * 0.4f);
                using (var b = new LinearGradientBrush(new RectangleF(pos.X, pos.Y, 520, 70), Color.White,
                                                       Color.FromArgb(255, 228, 240), 90f))
                    g.DrawString(Config.Titulo, f, b, pos);
            }
            using (var f = new Font("Segoe UI", 13, FontStyle.Bold))
            using (var b = new SolidBrush(Oro))
                g.DrawString(Espaciado(Config.Subtitulo), f, b, 44, 104);
        }

        static string Espaciado(string s)
        {
            return string.Join(" ", s.ToUpperInvariant().ToCharArray());
        }

        void BotonVentana(Graphics g, Rectangle r, string cual)
        {
            if (sobre == cual)
                using (var b = new SolidBrush(cual == "cerrar" ? Color.FromArgb(200, 220, 60, 90) : Color.FromArgb(60, 255, 255, 255)))
                    g.FillEllipse(b, r);
            using (var pen = new Pen(Color.White, 2f))
            {
                int cx = r.X + r.Width / 2, cy = r.Y + r.Height / 2;
                if (cual == "cerrar")
                {
                    g.DrawLine(pen, cx - 6, cy - 6, cx + 6, cy + 6);
                    g.DrawLine(pen, cx + 6, cy - 6, cx - 6, cy + 6);
                }
                else g.DrawLine(pen, cx - 7, cy + 1, cx + 7, cy + 1);
            }
        }

        void PanelNoticias(Graphics g, List<Noticia> nots)
        {
            using (var camino = Redondeado(rNoticias, 14))
            {
                using (var b = new SolidBrush(Color.FromArgb(120, 8, 10, 30))) g.FillPath(b, camino);
                using (var pen = new Pen(Color.FromArgb(60, 255, 255, 255))) g.DrawPath(pen, camino);
            }
            using (var f = new Font("Segoe UI", 11, FontStyle.Bold))
            using (var b = new SolidBrush(Oro))
                g.DrawString(Espaciado("Noticias"), f, b, rNoticias.X + 20, rNoticias.Y + 14);

            var area = new Rectangle(rNoticias.X + 20, rNoticias.Y + 46, rNoticias.Width - 40, rNoticias.Height - 60);
            var antes = g.Clip;
            g.SetClip(area);
            float y = area.Y;
            if (nots.Count == 0)
                using (var f = new Font("Segoe UI", 10))
                using (var b = new SolidBrush(TextoSuave))
                    g.DrawString("Cargando noticias...", f, b, area.X, y);
            using (var fFecha = new Font("Segoe UI", 8.5f, FontStyle.Bold))
            using (var fTit = new Font("Segoe UI", 12, FontStyle.Bold))
            using (var fTxt = new Font("Segoe UI", 9.5f))
            using (var bFecha = new SolidBrush(Rosa))
            using (var bTit = new SolidBrush(Color.White))
            using (var bTxt = new SolidBrush(TextoSuave))
            {
                foreach (var n in nots)
                {
                    g.DrawString(n.Fecha, fFecha, bFecha, area.X, y);
                    y += 16;
                    g.DrawString(n.Titulo, fTit, bTit, new RectangleF(area.X, y, area.Width, 40));
                    y += g.MeasureString(n.Titulo, fTit, area.Width).Height + 2;
                    var tam = g.MeasureString(n.Texto, fTxt, area.Width);
                    g.DrawString(n.Texto, fTxt, bTxt, new RectangleF(area.X, y, area.Width, tam.Height + 4));
                    y += tam.Height + 16;
                    if (y > area.Bottom) break;
                }
            }
            g.Clip = antes;
        }

        void PanelDerecho(Graphics g, string vServ, string vLoc, bool ok, bool ocupado)
        {
            using (var f = new Font("Segoe UI", 10))
            using (var fB = new Font("Segoe UI", 10, FontStyle.Bold))
            using (var b = new SolidBrush(TextoSuave))
            using (var bB = new SolidBrush(Color.White))
            {
                g.DrawString("Versión del servidor", f, b, 640, 200);
                g.DrawString(vServ.Length > 0 ? vServ : "--", fB, bB, 640, 220);
                g.DrawString("Versión instalada", f, b, 640, 252);
                g.DrawString(vLoc.Length > 0 ? vLoc : "--", fB, bB, 640, 272);
            }

            bool activo = ok && !ocupado;
            bool encima = sobre == "jugar" && activo;
            using (var camino = Redondeado(rJugar, 16))
            {
                Color a = activo ? (encima ? Color.FromArgb(255, 222, 130) : Oro) : Color.FromArgb(120, 120, 140);
                Color c = activo ? (encima ? Color.FromArgb(246, 150, 60) : OroOscuro) : Color.FromArgb(80, 80, 100);
                if (activo)
                    Resplandor(g, new RectangleF(rJugar.X - 30, rJugar.Y - 24, rJugar.Width + 60, rJugar.Height + 48),
                               Color.FromArgb(encima ? 120 : 70, Oro));
                using (var br = new LinearGradientBrush(rJugar, a, c, 90f)) g.FillPath(br, camino);
                using (var pen = new Pen(Color.FromArgb(160, 255, 255, 255), 1.5f)) g.DrawPath(pen, camino);
            }
            using (var f = new Font("Segoe UI", 24, FontStyle.Bold))
            using (var sf = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
            {
                using (var sombra = new SolidBrush(Color.FromArgb(70, 60, 20, 0)))
                    g.DrawString(ocupado ? "ESPERA..." : "JUGAR", f, sombra, new RectangleF(rJugar.X, rJugar.Y + 2, rJugar.Width, rJugar.Height), sf);
                using (var b = new SolidBrush(Color.White))
                    g.DrawString(ocupado ? "ESPERA..." : "JUGAR", f, b, rJugar, sf);
            }
            BotonChico(g, rReparar, "Reparar", "reparar", !ocupado);
            BotonChico(g, rCarpeta, "Carpeta", "carpeta", true);
        }

        void BotonChico(Graphics g, Rectangle r, string texto, string cual, bool activo)
        {
            using (var camino = Redondeado(r, 10))
            {
                int a = !activo ? 25 : (sobre == cual ? 80 : 45);
                using (var b = new SolidBrush(Color.FromArgb(a, 255, 255, 255))) g.FillPath(b, camino);
                using (var pen = new Pen(Color.FromArgb(activo ? 110 : 40, 255, 255, 255))) g.DrawPath(pen, camino);
            }
            using (var f = new Font("Segoe UI", 10, FontStyle.Bold))
            using (var sf = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
            using (var b = new SolidBrush(Color.FromArgb(activo ? 255 : 120, 255, 255, 255)))
                g.DrawString(texto, f, b, r, sf);
        }

        void Barra(Graphics g, string est, double prog, bool fallo)
        {
            using (var f = new Font("Segoe UI", 10))
            using (var b = new SolidBrush(fallo ? Color.FromArgb(255, 170, 170) : TextoSuave))
                g.DrawString(est, f, b, rBarra.X, rBarra.Y - 26);
            using (var camino = Redondeado(rBarra, 6))
            using (var b = new SolidBrush(Color.FromArgb(45, 255, 255, 255)))
                g.FillPath(b, camino);
            if (prog < 0)
            {
                // sin total conocido: un brillo que va y viene
                float ancho = rBarra.Width * 0.22f;
                float x = rBarra.X + (float)((Math.Sin(tiempo * 2.2) + 1) / 2) * (rBarra.Width - ancho);
                var r = new Rectangle((int)x, rBarra.Y, (int)ancho, rBarra.Height);
                using (var camino = Redondeado(r, 6))
                using (var br = new LinearGradientBrush(r, Rosa, Oro, 0f))
                    g.FillPath(br, camino);
            }
            else if (prog > 0)
            {
                var r = new Rectangle(rBarra.X, rBarra.Y, Math.Max(12, (int)(rBarra.Width * Math.Min(1, prog))), rBarra.Height);
                using (var camino = Redondeado(r, 6))
                using (var br = new LinearGradientBrush(new Rectangle(rBarra.X, rBarra.Y, rBarra.Width, rBarra.Height), Rosa, Oro, 0f))
                    g.FillPath(br, camino);
                using (var f = new Font("Segoe UI", 10, FontStyle.Bold))
                using (var b = new SolidBrush(Color.White))
                using (var sf = new StringFormat { Alignment = StringAlignment.Far })
                    g.DrawString(((int)(Math.Min(1, prog) * 100)) + "%", f, b,
                                 new RectangleF(rBarra.X, rBarra.Y - 26, rBarra.Width, 22), sf);
            }
            using (var f = new Font("Segoe UI", 8))
            using (var b = new SolidBrush(Color.FromArgb(120, 255, 255, 255)))
                g.DrawString("Launcher " + Config.VersionLauncher, f, b, rBarra.X, rBarra.Bottom + 10);
        }

        protected override void OnFormClosed(FormClosedEventArgs e)
        {
            reloj.Stop();
            base.OnFormClosed(e);
        }
    }
}
