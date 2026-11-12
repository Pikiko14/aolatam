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
        // A juego con el logo de Angels Online Forever: azul noche (ala de angel), carmesi (ala de demonio) y oro (halo).
        static readonly Color CieloArriba = Color.FromArgb(10, 20, 62);
        static readonly Color CieloAbajo = Color.FromArgb(92, 10, 30);
        static readonly Color Rosa = Color.FromArgb(236, 72, 92);
        static readonly Color Oro = Color.FromArgb(255, 205, 96);
        static readonly Color OroOscuro = Color.FromArgb(232, 128, 44);
        static readonly Color TextoSuave = Color.FromArgb(214, 214, 236);
        // Los del emblema (12/11/2026, "que los botones sean tambien fantasiosos"): azul cielo, azul hondo y gema.
        static readonly Color AzulCielo = Color.FromArgb(92, 178, 255);
        static readonly Color AzulHondo = Color.FromArgb(22, 58, 168);
        static readonly Color Gema = Color.FromArgb(120, 220, 255);
        static readonly Color OroClaro = Color.FromArgb(255, 238, 170);

        // ---- zonas
        Rectangle rCerrar, rMinimizar, rJugar, rReparar, rCarpeta, rNoticias, rVersiones, rBarra;

        // ---- estado (lo tocan el hilo de trabajo y el de la ventana: se lee y escribe con lock)
        readonly object cerrojo = new object();
        string estado = "Conectando con el servidor...";
        double progreso = -1;
        bool listo, trabajando, conError;
        string versionServidor = "", versionLocal = "";
        List<Noticia> noticias = new List<Noticia>();
        string sobre = "";                       // boton bajo el raton

        // ---- particulas del fondo
        class Particula { public float X, Y, R, V, Fase, Giro; }
        Bitmap fondo;                            // la imagen con sus sombreados, compuesta una sola vez
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
            // 12/11/2026: con la imagen del cielo los personajes van a la izquierda y todo esto en una columna a la
            // derecha, bajo los botones de la ventana; el emblema esta en fondo.jpg arriba a la izquierda.
            rNoticias = new Rectangle(600, 56, 340, 226);
            rVersiones = new Rectangle(600, 290, 340, 36);
            rJugar = new Rectangle(600, 336, 340, 72);
            rReparar = new Rectangle(600, 418, 164, 38);
            rCarpeta = new Rectangle(776, 418, 164, 38);
            rBarra = new Rectangle(40, 520, 900, 12);

            for (int i = 0; i < 45; i++) particulas.Add(NuevaParticula(true));
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
                if (reparar || Actualizador.HaceFaltaJuego(m))
                    Actualizador.InstalarJuego(m, Avisar);
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
        // Petalos de sakura que caen (a juego con la imagen de fondo).
        Particula NuevaParticula(bool cualquierAltura)
        {
            var p = new Particula();
            p.X = (float)(azar.NextDouble() * (Width + 200)) - 100;
            p.Y = cualquierAltura ? (float)(azar.NextDouble() * Height) : -12;
            p.R = (float)(2.6 + azar.NextDouble() * 3.4);
            p.V = (float)(0.45 + azar.NextDouble() * 0.9);
            p.Fase = (float)(azar.NextDouble() * Math.PI * 2);
            p.Giro = (float)(azar.NextDouble() * 360);
            return p;
        }

        void Animar()
        {
            tiempo += 0.033f;
            for (int i = 0; i < particulas.Count; i++)
            {
                var p = particulas[i];
                p.Y += p.V;
                p.X += 0.35f + (float)Math.Sin(tiempo * 1.3 + p.Fase) * 0.6f;
                p.Giro += 1.5f + p.V;
                if (p.Y > Height + 12 || p.X > Width + 20) particulas[i] = NuevaParticula(false);
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

            Fondo(g);                            // el logo va dentro de fondo.jpg
            BotonVentana(g, rMinimizar, "minimizar");
            BotonVentana(g, rCerrar, "cerrar");
            PanelNoticias(g, nots);
            PanelDerecho(g, vServ, vLoc, ok, ocupado);
            Barra(g, est, prog, fallo);
        }

        // La imagen de fondo (fondo.jpg, metida en el exe al compilar) con sombras para que se lean las noticias y la
        // barra: oscura a la derecha (la columna) y abajo, y limpia a la izquierda, donde estan los personajes.
        Bitmap ComponerFondo()
        {
            var bmp = new Bitmap(Width, Height);
            using (var g = Graphics.FromImage(bmp))
            {
                var todo = new Rectangle(0, 0, Width, Height);
                Image imagen = null;
                try
                {
                    var s = typeof(Ventana).Assembly.GetManifestResourceStream("AngelsLauncher.fondo.jpg");
                    if (s != null) imagen = Image.FromStream(s);
                }
                catch (Exception) { }
                if (imagen != null)
                {
                    g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    g.DrawImage(imagen, todo);
                    imagen.Dispose();
                }
                else
                    using (var b = new LinearGradientBrush(todo, CieloArriba, CieloAbajo, 90f))
                        g.FillRectangle(b, todo);
                var derecha = new Rectangle(540, 0, Width - 540, Height);
                using (var b = new LinearGradientBrush(derecha, Color.FromArgb(0, 8, 12, 36), Color.FromArgb(120, 8, 12, 36), 0f))
                    g.FillRectangle(b, new Rectangle(derecha.X + 1, 0, derecha.Width, Height));
                                var abajo = new Rectangle(0, Height - 150, Width, 150);
                using (var b = new LinearGradientBrush(abajo, Color.FromArgb(0, 10, 8, 26), Color.FromArgb(225, 10, 8, 26), 90f))
                    g.FillRectangle(b, new Rectangle(abajo.X, abajo.Y + 1, abajo.Width, abajo.Height));
            }
            return bmp;
        }

        void Fondo(Graphics g)
        {
            if (fondo == null) fondo = ComponerFondo();
            g.DrawImageUnscaled(fondo, 0, 0);
            var antes = g.Transform;
            // destellos dorados que caen y titilan (antes petalos rosas)
            using (var bc = new SolidBrush(Color.FromArgb(230, 255, 250, 225)))
                foreach (var p in particulas)
                {
                    float brillo = 0.55f + 0.45f * (float)Math.Sin(tiempo * 3 + p.Fase);
                    float r = p.R * 0.8f;
                    g.TranslateTransform(p.X, p.Y);
                    using (var b = new SolidBrush(Color.FromArgb((int)(70 * brillo), 255, 200, 90)))
                        g.FillEllipse(b, -r * 2, -r * 2, r * 4, r * 4);
                    g.FillEllipse(bc, -r * 0.45f, -r * 0.45f, r * 0.9f, r * 0.9f);
                    g.Transform = antes;
                }
            using (var borde = Redondeado(new Rectangle(0, 0, Width - 1, Height - 1), 18))
            using (var pen = new Pen(Color.FromArgb(90, 255, 255, 255), 1.5f))
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
                using (var b = new SolidBrush(Color.FromArgb(165, 8, 10, 30))) g.FillPath(b, camino);
                using (var pen = new Pen(Color.FromArgb(110, 255, 214, 130))) g.DrawPath(pen, camino);
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
            // las dos versiones en una linea, en su franja translucida para que se lean sobre la imagen
            using (var camino = Redondeado(rVersiones, 12))
            {
                using (var b = new SolidBrush(Color.FromArgb(165, 10, 10, 32))) g.FillPath(b, camino);
                using (var pen = new Pen(Color.FromArgb(70, 255, 255, 255))) g.DrawPath(pen, camino);
            }
            using (var f = new Font("Segoe UI", 9))
            using (var fB = new Font("Segoe UI", 9.5f, FontStyle.Bold))
            using (var b = new SolidBrush(TextoSuave))
            using (var bB = new SolidBrush(Color.White))
            {
                int y = rVersiones.Y + 9;
                g.DrawString("Servidor", f, b, rVersiones.X + 14, y);
                g.DrawString(vServ.Length > 0 ? vServ : "--", fB, bB, rVersiones.X + 72, y - 1);
                g.DrawString("Instalada", f, b, rVersiones.X + 178, y);
                g.DrawString(vLoc.Length > 0 ? vLoc : "--", fB, bB, rVersiones.X + 240, y - 1);
            }

            bool activo = ok && !ocupado;
            bool encima = sobre == "jugar" && activo;
            BotonFantasia(g, rJugar, 18, activo, encima, true);
            using (var f = new Font("Georgia", 22, FontStyle.Bold))
            using (var sf = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
            {
                string t = ocupado ? "ESPERA..." : "J U G A R";
                var rt = new RectangleF(rJugar.X, rJugar.Y + 1, rJugar.Width, rJugar.Height);
                using (var sombra = new SolidBrush(Color.FromArgb(150, 8, 20, 70)))
                    g.DrawString(t, f, sombra, new RectangleF(rt.X + 1.5f, rt.Y + 2.5f, rt.Width, rt.Height), sf);
                using (var b = new LinearGradientBrush(rJugar, Color.White, activo ? OroClaro : Color.FromArgb(200, 200, 215), 90f))
                    g.DrawString(t, f, b, rt, sf);
            }
            BotonChico(g, rReparar, "Reparar", "reparar", !ocupado);
            BotonChico(g, rCarpeta, "Carpeta", "carpeta", true);
        }

        void BotonChico(Graphics g, Rectangle r, string texto, string cual, bool activo)
        {
            BotonFantasia(g, r, 10, activo, activo && sobre == cual, false);
            using (var f = new Font("Georgia", 10, FontStyle.Bold))
            using (var sf = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
            {
                using (var sombra = new SolidBrush(Color.FromArgb(160, 6, 14, 50)))
                    g.DrawString(texto, f, sombra, new RectangleF(r.X + 1, r.Y + 2, r.Width, r.Height), sf);
                using (var b = new SolidBrush(activo ? OroClaro : Color.FromArgb(150, 220, 220, 230)))
                    g.DrawString(texto, f, b, r, sf);
            }
        }

        // Un boton de fantasia, a juego con el emblema: cristal azul (cielo arriba, hondo abajo, oscuro el chico), marco
        // de oro doble, una gema en cada punta y un brillo que lo cruza de vez en cuando. Apagado, todo en gris.
        void BotonFantasia(Graphics g, Rectangle r, int radio, bool activo, bool encima, bool grande)
        {
            Color arriba = !activo ? Color.FromArgb(120, 124, 140) : grande ? (encima ? Color.FromArgb(140, 205, 255) : AzulCielo)
                                                                             : Color.FromArgb(encima ? 230 : 200, 40, 74, 160);
            Color abajo = !activo ? Color.FromArgb(70, 72, 90) : grande ? (encima ? Color.FromArgb(40, 90, 210) : AzulHondo)
                                                                         : Color.FromArgb(encima ? 240 : 215, 12, 22, 70);
            if (activo && grande)
                Resplandor(g, new RectangleF(r.X - 34, r.Y - 26, r.Width + 68, r.Height + 52),
                           Color.FromArgb(encima ? 130 : 80, AzulCielo));
            using (var camino = Redondeado(r, radio))
            {
                using (var br = new LinearGradientBrush(r, arriba, abajo, 90f)) g.FillPath(br, camino);
                // el reflejo de cristal de la mitad de arriba
                var brillo = new Rectangle(r.X + 3, r.Y + 2, r.Width - 6, r.Height / 2);
                using (var cb = Redondeado(brillo, Math.Max(4, radio - 3)))
                using (var br = new LinearGradientBrush(brillo, Color.FromArgb(activo ? 95 : 40, 255, 255, 255),
                                                        Color.FromArgb(0, 255, 255, 255), 90f))
                    g.FillPath(br, cb);
                // un destello que cruza el boton cada pocos segundos
                if (activo)
                {
                    double ciclo = (tiempo * (grande ? 0.35 : 0.25) + (r.X % 97) / 97.0) % 1.0;
                    if (ciclo < 0.35)
                    {
                        float x = r.X - 60 + (float)(ciclo / 0.35) * (r.Width + 120);
                        var antes = g.Clip;
                        g.SetClip(camino, CombineMode.Intersect);
                        using (var franja = new GraphicsPath())
                        {
                            franja.AddPolygon(new[] { new PointF(x, r.Bottom), new PointF(x + 24, r.Y),
                                                      new PointF(x + 46, r.Y), new PointF(x + 22, r.Bottom) });
                            using (var b = new SolidBrush(Color.FromArgb(70, 255, 255, 255))) g.FillPath(b, franja);
                        }
                        g.Clip = antes;
                    }
                }
                // marco de oro: el de fuera grueso y otro fino por dentro
                using (var br = new LinearGradientBrush(r, activo ? OroClaro : Color.FromArgb(190, 190, 200),
                                                        activo ? OroOscuro : Color.FromArgb(110, 110, 125), 90f))
                using (var pen = new Pen(br, grande ? 3f : 2f))
                    g.DrawPath(pen, camino);
            }
            var dentro = Rectangle.Inflate(r, grande ? -6 : -4, grande ? -6 : -4);
            using (var camino = Redondeado(dentro, Math.Max(3, radio - 5)))
            using (var pen = new Pen(Color.FromArgb(activo ? 150 : 70, 255, 230, 160), 1f))
                g.DrawPath(pen, camino);
            // las gemas de las puntas, como las del emblema
            float rg = grande ? 9f : 5f;
            Gema4(g, r.X + (grande ? 2 : 1), r.Y + r.Height / 2f, rg, activo, encima);
            Gema4(g, r.Right - (grande ? 2 : 1), r.Y + r.Height / 2f, rg, activo, encima);
        }

        void Gema4(Graphics g, float cx, float cy, float rr, bool activo, bool encima)
        {
            var puntas = new[] { new PointF(cx, cy - rr * 1.35f), new PointF(cx + rr, cy), new PointF(cx, cy + rr * 1.35f),
                                 new PointF(cx - rr, cy) };
            if (activo)
                Resplandor(g, new RectangleF(cx - rr * 2.6f, cy - rr * 2.6f, rr * 5.2f, rr * 5.2f),
                           Color.FromArgb(encima ? 170 : 110, Gema));
            using (var camino = new GraphicsPath())
            {
                camino.AddPolygon(puntas);
                using (var b = new PathGradientBrush(camino))
                {
                    b.CenterColor = activo ? Color.White : Color.FromArgb(220, 220, 230);
                    b.SurroundColors = new[] { activo ? Gema : Color.FromArgb(150, 150, 165), activo ? Color.FromArgb(40, 110, 230) : Color.FromArgb(110, 110, 125),
                                               activo ? Color.FromArgb(20, 60, 170) : Color.FromArgb(90, 90, 105), activo ? Gema : Color.FromArgb(150, 150, 165) };
                    g.FillPath(b, camino);
                }
                using (var pen = new Pen(activo ? Oro : Color.FromArgb(170, 170, 180), rr > 6 ? 2f : 1.4f)) g.DrawPath(pen, camino);
            }
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
                using (var br = new LinearGradientBrush(r, AzulCielo, Oro, 0f))
                    g.FillPath(br, camino);
            }
            else if (prog > 0)
            {
                var r = new Rectangle(rBarra.X, rBarra.Y, Math.Max(12, (int)(rBarra.Width * Math.Min(1, prog))), rBarra.Height);
                using (var camino = Redondeado(r, 6))
                using (var br = new LinearGradientBrush(new Rectangle(rBarra.X, rBarra.Y, rBarra.Width, rBarra.Height), AzulCielo, Oro, 0f))
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
