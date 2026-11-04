// Ingles / espanol. El ingles va en el HTML; el espanol en data-es (contenido) y data-es-<atributo> (placeholder, alt,
// aria-label, content). La primera vez se elige por el idioma del navegador; despues, el de la banderita pulsada.
// El selector es <span class="lang-flags"></span>: aqui se ponen las dos banderas (SVG: Windows no pinta los emoji de
// bandera). app.js, cuenta.js y panel.js usan window.t(en, es) y escuchan 'langchange' para lo que pintan ellos.
(function () {
  const CLAVE = 'aof-lang';
  const ATRIBUTOS = ['placeholder', 'alt', 'aria-label', 'content'];
  const BANDERAS = {
    en: { nombre: 'English', svg: '<svg viewBox="0 0 19 10" aria-hidden="true"><rect width="19" height="10" fill="#b22234"/>'
      + '<path d="M0 1.15h19M0 2.69h19M0 4.23h19M0 5.77h19M0 7.31h19M0 8.85h19" stroke="#fff" stroke-width=".77"/>'
      + '<rect width="7.6" height="5.38" fill="#3c3b6e"/></svg>' },
    es: { nombre: 'Español', svg: '<svg viewBox="0 0 3 2" aria-hidden="true"><rect width="3" height="2" fill="#aa151b"/>'
      + '<rect y=".5" width="3" height="1" fill="#f1bf00"/></svg>' },
  };
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
    document.querySelectorAll('.lang-flags button').forEach(b => {
      b.setAttribute('aria-pressed', String(b.dataset.lang === lang));
    });
    document.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
  }

  function elegir(nuevo) {
    if (nuevo === lang) return;
    lang = nuevo;
    try { localStorage.setItem(CLAVE, lang); } catch { /* sigue funcionando sin recordarlo */ }
    aplicar();
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.lang-flags').forEach(caja => {
      caja.setAttribute('role', 'group');
      caja.setAttribute('aria-label', 'Language / Idioma');
      caja.replaceChildren();
      Object.entries(BANDERAS).forEach(([codigo, b]) => {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.dataset.lang = codigo;
        boton.lang = codigo;
        boton.title = b.nombre;
        boton.setAttribute('aria-label', b.nombre);
        boton.innerHTML = b.svg;
        boton.addEventListener('click', () => elegir(codigo));
        caja.append(boton);
      });
    });
    aplicar();
  });
})();
