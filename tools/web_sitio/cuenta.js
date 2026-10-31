// Crear cuenta: usuario, contrasena y confirmacion (server/web_registro.py). La contrasena es la misma del juego.
const accountForm = document.getElementById('account-form');
const accountInput = document.getElementById('account-username');
const passInput = document.getElementById('account-password');
const confirmInput = document.getElementById('account-confirm');
const accountStatus = document.getElementById('account-status');
const accountButton = accountForm.querySelector('button');
const CONTRASENA_VALIDA = /^[\x21-\x7e]{4,16}$/;   // lo que acepta el cliente del juego: sin espacios ni acentos
let comprobando = null;

function ponEstado(texto, tipo) {
  accountStatus.textContent = texto;
  if (tipo) accountStatus.dataset.tipo = tipo; else delete accountStatus.dataset.tipo;
}

async function comprobarDisponibilidad(usuario) {
  try {
    const resp = await fetch('/api/cuenta/disponible?usuario=' + encodeURIComponent(usuario));
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
      ponEstado('Usuario libre.', 'ok');
    }
  }, 400);
});

function problemaContrasena() {
  const pw = passInput.value, conf = confirmInput.value;
  if (!pw) return 'Escribe una contraseña.';
  if (!CONTRASENA_VALIDA.test(pw)) return 'La contraseña debe tener de 4 a 16 caracteres, sin espacios ni acentos.';
  if (pw !== conf) return 'Las contraseñas no coinciden.';
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
  if (!usuario) { ponEstado('Escribe un nombre de usuario.', 'error'); return; }
  const problema = problemaContrasena();
  if (problema) { ponEstado(problema, 'error'); return; }
  accountButton.disabled = true;
  ponEstado('Creando tu cuenta…');
  try {
    const resp = await fetch('/api/cuenta/registrar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario, password: passInput.value, confirmar: confirmInput.value }),
    });
    const r = await resp.json();
    ponEstado(r.mensaje, r.ok ? 'ok' : 'error');
    if (r.ok) {
      accountForm.reset();
      [accountInput, passInput, confirmInput].forEach(i => delete i.dataset.estado);
    }
  } catch {
    ponEstado('No se pudo conectar con el servidor. Intenta de nuevo en un momento.', 'error');
  } finally {
    accountButton.disabled = false;
  }
});
