// Crear cuenta: usuario, contrasena y confirmacion (server/web_registro.py). La contrasena es la misma del juego.
// Textos en dos idiomas (i18n.js); a la API se le pasa el idioma para que conteste en el mismo.
const accountForm = document.getElementById('account-form');
const accountInput = document.getElementById('account-username');
const passInput = document.getElementById('account-password');
const confirmInput = document.getElementById('account-confirm');
const accountStatus = document.getElementById('account-status');
const accountButton = accountForm.querySelector('button');
const CONTRASENA_VALIDA = /^[\x21-\x7e]{4,16}$/;   // lo que acepta el cliente del juego: sin espacios ni acentos
const tc = (en, es) => (window.t ? window.t(en, es) : en);
const idioma = () => (window.getLang ? window.getLang() : 'en');
let comprobando = null;

function ponEstado(texto, tipo) {
  accountStatus.textContent = texto;
  if (tipo) accountStatus.dataset.tipo = tipo; else delete accountStatus.dataset.tipo;
}
// Al cambiar de idioma, el aviso que hubiera quedaria en el otro: se borra.
document.addEventListener('langchange', () => ponEstado(''));

async function comprobarDisponibilidad(usuario) {
  try {
    const resp = await fetch('/api/cuenta/disponible?usuario=' + encodeURIComponent(usuario) + '&lang=' + idioma());
    return await resp.json();
  } catch {
    return null;
  }
}

accountInput.addEventListener('input', () => {
  delete accountInput.dataset.estado;
  const usuario = accountInput.value.trim();
  clearTimeout(comprobando);
  if (!usuario) { ponEstado(''); return; }
  comprobando = setTimeout(async () => {
    const r = await comprobarDisponibilidad(usuario);
    if (!r) { ponEstado(''); return; }
    if (accountInput.value.trim() !== usuario) return; // el usuario siguio escribiendo
    if (r.motivo && !r.disponible) {
      accountInput.dataset.estado = 'ocupado';
      ponEstado(r.motivo, 'error');
    } else if (r.disponible) {
      accountInput.dataset.estado = 'libre';
      ponEstado(tc('Username available.', 'Usuario libre.'), 'ok');
    }
  }, 400);
});

function problemaContrasena() {
  const pw = passInput.value, conf = confirmInput.value;
  if (!pw) return tc('Enter a password.', 'Escribe una contraseña.');
  if (!CONTRASENA_VALIDA.test(pw)) return tc('The password must be 4 to 16 characters, with no spaces or accented letters.',
                                             'La contraseña debe tener de 4 a 16 caracteres, sin espacios ni acentos.');
  if (pw !== conf) return tc("The passwords don't match.", 'Las contraseñas no coinciden.');
  return null;
}

// Marca en vivo si la confirmacion coincide.
function revisarConfirmacion() {
  delete passInput.dataset.estado;
  delete confirmInput.dataset.estado;
  if (passInput.value) passInput.dataset.estado = CONTRASENA_VALIDA.test(passInput.value) ? 'libre' : 'ocupado';
  if (confirmInput.value) confirmInput.dataset.estado = confirmInput.value === passInput.value ? 'libre' : 'ocupado';
}
passInput.addEventListener('input', revisarConfirmacion);
confirmInput.addEventListener('input', revisarConfirmacion);

accountForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const usuario = accountInput.value.trim();
  if (!usuario) { ponEstado(tc('Enter a username.', 'Escribe un nombre de usuario.'), 'error'); return; }
  const problema = problemaContrasena();
  if (problema) { ponEstado(problema, 'error'); return; }
  accountButton.disabled = true;
  ponEstado(tc('Creating your account…', 'Creando tu cuenta…'));
  try {
    const resp = await fetch('/api/cuenta/registrar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario, password: passInput.value, confirmar: confirmInput.value, lang: idioma() }),
    });
    const r = await resp.json();
    ponEstado(r.mensaje, r.ok ? 'ok' : 'error');
    if (r.ok) {
      accountForm.reset();
      [accountInput, passInput, confirmInput].forEach(i => delete i.dataset.estado);
    }
  } catch {
    ponEstado(tc('Could not connect to the server. Please try again in a moment.',
                 'No se pudo conectar con el servidor. Intenta de nuevo en un momento.'), 'error');
  } finally {
    accountButton.disabled = false;
  }
});
