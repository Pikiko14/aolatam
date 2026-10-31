// Crear cuenta: solo reserva el nombre de usuario (ver server/web_registro.py sobre por que no pide contrasena aqui).
const accountForm = document.getElementById('account-form');
const accountInput = document.getElementById('account-username');
const accountStatus = document.getElementById('account-status');
const accountButton = accountForm.querySelector('button');
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

accountForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const usuario = accountInput.value.trim();
  if (!usuario) { ponEstado('Escribe un nombre de usuario.', 'error'); return; }
  accountButton.disabled = true;
  ponEstado('Creando tu cuenta…');
  try {
    const resp = await fetch('/api/cuenta/registrar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario }),
    });
    const r = await resp.json();
    ponEstado(r.mensaje, r.ok ? 'ok' : 'error');
    if (r.ok) { accountInput.dataset.estado = 'ocupado'; accountForm.reset(); }
  } catch {
    ponEstado('No se pudo conectar con el servidor. Intenta de nuevo en un momento.', 'error');
  } finally {
    accountButton.disabled = false;
  }
});
