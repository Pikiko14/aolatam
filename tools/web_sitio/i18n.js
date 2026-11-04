// Ingles / espanol. El ingles va en el HTML; el espanol en data-es (contenido) y data-es-<atributo> (placeholder, alt,
// aria-label, content). La primera vez se elige por el idioma del navegador; despues, el que se pulso en el boton del menu.
// app.js y cuenta.js usan window.t(en, es) y escuchan el evento 'langchange' para lo que pintan ellos.
(function () {
  const CLAVE = 'aof-lang';
  const ATRIBUTOS = ['placeholder', 'alt', 'aria-label', 'content'];
  let guardado = null;
  try { guardado = localStorage.getItem(CLAVE); } catch { /* sin almacenamiento: se usa el del navegador */ }
  let lang = guardado === 'es' || guardado === 'en' ? guardado
    : ((navigator.languages || [navigator.language || 'en'])[0] || '').toLowerCase().startsWith('es') ? 'es' : 'en';

  window.t = (en, es) => (lang === 'es' ? es : en);
  window.getLang = () => lang;

  function aplicar() {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-es]').forEach(el => {
      if (el.dataset.en === undefined) el.dataset.en = el.innerHTML;
      el.innerHTML = lang === 'es' ? el.dataset.es : el.dataset.en;
    });
    ATRIBUTOS.forEach(a => {
      document.querySelectorAll('[data-es-' + a + ']').forEach(el => {
        if (!el.hasAttribute('data-en-' + a)) el.setAttribute('data-en-' + a, el.getAttribute(a) || '');
        el.setAttribute(a, el.getAttribute((lang === 'es' ? 'data-es-' : 'data-en-') + a));
      });
    });
    const boton = document.getElementById('lang-toggle');
    if (boton) {
      boton.textContent = lang === 'es' ? 'English' : 'Español';
      boton.lang = lang === 'es' ? 'en' : 'es';
      boton.setAttribute('aria-label', lang === 'es' ? 'Switch to English' : 'Cambiar a español');
    }
    document.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
  }

  document.addEventListener('DOMContentLoaded', () => {
    aplicar();
    const boton = document.getElementById('lang-toggle');
    if (boton) boton.addEventListener('click', () => {
      lang = lang === 'es' ? 'en' : 'es';
      try { localStorage.setItem(CLAVE, lang); } catch { /* sigue funcionando sin recordarlo */ }
      aplicar();
    });
  });
})();
