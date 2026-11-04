// Back office (server/panel_web.py, /api/panel/*). La sesion va en una cookie HttpOnly: aqui no se guarda nada.
// Textos en dos idiomas (../i18n.js): t(en, es) y el evento 'langchange'.
const T = (en, es) => (window.t ? window.t(en, es) : en);
const L = () => (window.getLang ? window.getLang() : 'en');
const $ = id => document.getElementById(id);
let yo = null;            // {usuario, admin, ag, personajes}
let calendario = null;    // {eventos, ahora}
let cuentaAdmin = null;   // la cuenta abierta en el admin

async function api(metodo, ruta, datos) {
  const op = { method: metodo, credentials: 'same-origin', headers: {} };
  if (datos) {
    op.headers['Content-Type'] = 'application/json';
    op.body = JSON.stringify({ ...datos, lang: L() });
  }
  const sep = ruta.includes('?') ? '&' : '?';
  try {
    const r = await fetch('/api/panel/' + ruta + (metodo === 'GET' ? sep + 'lang=' + L() : ''), op);
    const cuerpo = await r.json().catch(() => ({ ok: false }));
    // Sin sesion: al login. Solo se avisa si se habia entrado (expiro); en la primera visita, sin mensaje.
    if (r.status === 401 && ruta !== 'login') { mostrarLogin(yo ? cuerpo.mensaje : ''); return { ok: false }; }
    return cuerpo;
  } catch {
    return { ok: false, mensaje: T('Could not connect to the server. Please try again in a moment.',
                                   'No se pudo conectar con el servidor. Intenta de nuevo en un momento.') };
  }
}

function estado(id, texto, tipo) {
  const e = $(id);
  e.textContent = texto || '';
  if (tipo) e.dataset.tipo = tipo; else delete e.dataset.tipo;
}

const num = n => Number(n || 0).toLocaleString(L() === 'es' ? 'es' : 'en');

// ---------------------------------------------------------------- entrar / salir

function mostrarLogin(aviso) {
  yo = null;
  $('vista-panel').hidden = true;
  $('vista-login').hidden = false;
  $('quien').hidden = $('salir').hidden = true;
  estado('login-estado', aviso || '', aviso ? 'error' : null);
  $('login-usuario').focus();
}

async function mostrarPanel(datos) {
  const r = datos || await api('GET', 'yo');
  if (!r.ok) return;
  yo = r;
  $('vista-login').hidden = true;
  $('vista-panel').hidden = false;
  $('quien').hidden = $('salir').hidden = false;
  $('quien').textContent = yo.usuario + (yo.admin ? ' · Admin' : '');
  document.querySelectorAll('.solo-admin').forEach(e => { e.hidden = !yo.admin; });
  pintarYo();
  irA(location.hash.slice(1) || 'personajes');
}

$('form-login').addEventListener('submit', async ev => {
  ev.preventDefault();
  const boton = ev.target.querySelector('button');
  boton.disabled = true;
  estado('login-estado', T('Logging in…', 'Entrando…'));
  const r = await api('POST', 'login', { usuario: $('login-usuario').value.trim(), password: $('login-clave').value });
  boton.disabled = false;
  if (!r.ok) { estado('login-estado', r.mensaje, 'error'); return; }
  $('login-clave').value = '';
  estado('login-estado', '');
  mostrarPanel();
});

$('salir').addEventListener('click', async () => {
  await api('POST', 'logout', {});
  history.replaceState(null, '', location.pathname);
  mostrarLogin();
});

// ---------------------------------------------------------------- pestanas

const VISTAS = ['personajes', 'recargar', 'contrasena', 'eventos', 'admin'];
function irA(vista) {
  if (!VISTAS.includes(vista) || (vista === 'admin' && !(yo && yo.admin))) vista = 'personajes';
  VISTAS.forEach(v => { $('vista-' + v).hidden = v !== vista; });
  document.querySelectorAll('.panel-pestanas button').forEach(b => {
    b.setAttribute('aria-current', String(b.dataset.vista === vista));
  });
  if (location.hash.slice(1) !== vista) history.replaceState(null, '', '#' + vista);
  if (vista === 'eventos') cargarEventos();
}
document.querySelectorAll('.panel-pestanas button').forEach(b => b.addEventListener('click', () => irA(b.dataset.vista)));

// ---------------------------------------------------------------- personajes y saldo

function fichaPersonaje(p) {
  const art = document.createElement('article');
  art.className = 'panel-personaje';
  const h = document.createElement('h3'); h.textContent = p.nombre;
  const sub = document.createElement('p'); sub.className = 'pj-sub';
  sub.textContent = T('Level', 'Nivel') + ' ' + p.nivel + ' · ' + p.clase;
  const dl = document.createElement('dl');
  [[T('Faction', 'Facción'), p.faccion], [T('Map', 'Mapa'), p.mapa], [T('Gold', 'Oro'), num(p.oro)]].forEach(([k, v]) => {
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    dl.append(dt, dd);
  });
  art.append(h, sub, dl);
  return art;
}

function pintarPersonajes(caja, lista) {
  caja.replaceChildren();
  if (!lista || !lista.length) {
    const p = document.createElement('p');
    p.className = 'panel-vacio';
    p.textContent = T('No characters yet. Create one in the game.', 'Aún no hay personajes. Crea uno en el juego.');
    caja.append(p);
    return;
  }
  lista.forEach(p => caja.append(fichaPersonaje(p)));
}

function pintarYo() {
  if (!yo) return;
  pintarPersonajes($('mis-personajes'), yo.personajes);
  $('mi-ag').textContent = num(yo.ag);
}

// ---------------------------------------------------------------- contrasena

$('form-contrasena').addEventListener('submit', async ev => {
  ev.preventDefault();
  const r = await api('POST', 'contrasena', { actual: $('pw-actual').value, nueva: $('pw-nueva').value,
                                              confirmar: $('pw-confirmar').value });
  estado('pw-estado', r.mensaje, r.ok ? 'ok' : 'error');
  if (r.ok) ev.target.reset();
});

// ---------------------------------------------------------------- eventos

async function cargarEventos() {
  if (!calendario) {
    const r = await api('GET', 'eventos');
    if (!r.ok) return;
    calendario = r;
  }
  pintarEventos();
}

function pintarEventos() {
  const lista = $('lista-eventos');
  lista.replaceChildren();
  if (!calendario) return;
  const ahora = Date.now() / 1000;
  const fmt = new Intl.DateTimeFormat(L() === 'es' ? 'es' : 'en',
    { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
  const proximos = calendario.eventos.filter(e => e.inicio + e.duracion * 60 > ahora);
  if (!proximos.length) {
    const li = document.createElement('li');
    li.textContent = T('No events scheduled.', 'No hay eventos programados.');
    lista.append(li);
    return;
  }
  proximos.forEach(e => {
    const li = document.createElement('li');
    const nombre = document.createElement('span'); nombre.className = 'ev-nombre';
    nombre.textContent = L() === 'es' ? e.es : e.en;
    if (e.inicio <= ahora) {
      const ya = document.createElement('span'); ya.className = 'ev-ahora';
      ya.textContent = T('Now', 'Ahora');
      nombre.append(ya);
    }
    const cuando = document.createElement('span'); cuando.className = 'ev-cuando';
    cuando.textContent = fmt.format(new Date(e.inicio * 1000)) + ' · ' + e.duracion + ' min';
    li.append(nombre, cuando);
    lista.append(li);
  });
}

// ---------------------------------------------------------------- admin

function pintarCuentaAdmin() {
  if (!cuentaAdmin) { $('admin-cuenta').hidden = true; return; }
  $('admin-cuenta').hidden = false;
  $('admin-usuario').textContent = cuentaAdmin.usuario;
  $('admin-ag').textContent = num(cuentaAdmin.ag);
  pintarPersonajes($('admin-personajes'), cuentaAdmin.personajes);
}

async function buscar(q) {
  estado('buscar-estado', T('Searching…', 'Buscando…'));
  const r = await api('GET', 'admin/cuenta?q=' + encodeURIComponent(q));
  if (!r.ok) { cuentaAdmin = null; pintarCuentaAdmin(); estado('buscar-estado', r.mensaje, 'error'); return; }
  cuentaAdmin = r;
  estado('buscar-estado', '');
  ['ag-estado', 'reset-estado'].forEach(id => estado(id, ''));
  pintarCuentaAdmin();
}

$('form-buscar').addEventListener('submit', ev => {
  ev.preventDefault();
  const q = $('buscar-q').value.trim();
  if (q) buscar(q);
});

$('form-ag').addEventListener('submit', async ev => {
  ev.preventDefault();
  if (!cuentaAdmin) return;
  const cantidad = parseInt($('ag-cantidad').value, 10);
  if (!cantidad) { estado('ag-estado', T('Enter a whole number of AG other than 0.', 'Escribe una cantidad entera de AG distinta de 0.'), 'error'); return; }
  const accion = cantidad > 0 ? T('Give', 'Dar') : T('Remove', 'Quitar');
  if (!confirm(accion + ' ' + num(Math.abs(cantidad)) + ' AG — ' + cuentaAdmin.usuario + '?')) return;
  const r = await api('POST', 'admin/ag', { usuario: cuentaAdmin.usuario, cantidad, motivo: $('ag-motivo').value });
  estado('ag-estado', r.mensaje, r.ok ? 'ok' : 'error');
  if (r.ok) {
    cuentaAdmin.ag = r.ag;
    $('admin-ag').textContent = num(r.ag);
    ev.target.reset();
    if (yo && cuentaAdmin.usuario === yo.usuario) { yo.ag = r.ag; pintarYo(); }
  }
});

$('form-reset').addEventListener('submit', async ev => {
  ev.preventDefault();
  if (!cuentaAdmin) return;
  if (!confirm(T('Change the password of ', 'Cambiar la contraseña de ') + cuentaAdmin.usuario + '?')) return;
  const r = await api('POST', 'admin/contrasena', { usuario: cuentaAdmin.usuario, nueva: $('reset-clave').value });
  estado('reset-estado', r.mensaje, r.ok ? 'ok' : 'error');
  if (r.ok) ev.target.reset();
});

// ---------------------------------------------------------------- idioma y arranque

document.addEventListener('langchange', () => {
  ['login-estado', 'pw-estado', 'buscar-estado', 'ag-estado', 'reset-estado'].forEach(id => estado(id, ''));
  pintarYo();
  pintarEventos();
  pintarCuentaAdmin();
});

(async () => {
  const r = await api('GET', 'yo');
  if (r.ok) mostrarPanel(r); else if (!yo) mostrarLogin();
})();
