// Botones de descarga: el cliente (downloadUrl) y el launcher (launcherUrl), de config.js. Textos en dos idiomas (i18n.js).
const tr = (en, es) => (window.t ? window.t(en, es) : en);

function prepararDescarga(botonId, estadoId, clave, nombre) {
  const boton = document.getElementById(botonId);
  const estado = document.getElementById(estadoId);
  if (!boton) return;
  boton.addEventListener('click', () => {
    const valor = (window.SERVER_CONFIG?.[clave] || '').trim();
    if (!valor) {
      estado.textContent = tr('The ' + nombre.en + ' download will be available soon.',
                              'La descarga de ' + nombre.es + ' estará disponible próximamente.');
      return;
    }
    try {
      const url = new URL(valor, window.location.href);
      if (!['http:', 'https:'].includes(url.protocol)) throw new Error('protocolo');
      const link = document.createElement('a');
      link.href = url.href;
      link.download = '';
      if (url.origin !== window.location.origin) {
        // Un sitio externo (p.ej. Mediafire) ignora el download y navega: que abra en pestaña nueva.
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
      }
      document.body.appendChild(link);
      link.click();
      link.remove();
      estado.textContent = tr('Opening the ' + nombre.en + ' download…', 'Abriendo la descarga de ' + nombre.es + '…');
    } catch {
      estado.textContent = tr('The download is not available right now.', 'La descarga no está disponible en este momento.');
    }
  });
}
prepararDescarga('download-game', 'download-status', 'downloadUrl', {en: 'client', es: 'el cliente'});
prepararDescarga('download-launcher', 'launcher-status', 'launcherUrl', {en: 'launcher', es: 'el launcher'});
// Al cambiar de idioma, los avisos de descarga que hubiera quedarian en el otro: se borran.
document.addEventListener('langchange', () => {
  document.querySelectorAll('.estado-descarga').forEach(e => { e.textContent = ''; });
});

// Noticias. Renderizado seguro: los textos nunca se interpretan como HTML. Se repintan al cambiar de idioma.
const newsList = document.getElementById('news-list');
const entries = Array.isArray(window.SERVER_NEWS) ? [...window.SERVER_NEWS] : [];
entries.sort((a, b) => String(b.date).localeCompare(String(a.date)));
function newsElement(tag, className, text) {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}
function pintarNoticias() {
  const es = window.getLang && window.getLang() === 'es';
  newsList.replaceChildren();
  if (!entries.length) {
    newsList.append(newsElement('p', 'news-empty', tr("No news yet. Check back soon to see what's new.",
                                                      'Aún no hay noticias publicadas. Vuelve pronto para descubrir las novedades.')));
    return;
  }
  entries.forEach(entry => {
    const texto = es && entry.es ? {...entry, ...entry.es} : entry;
    const article = newsElement('article', 'news-entry', '');
    const meta = newsElement('div', 'news-meta', '');
    const time = newsElement('time', '', '');
    const date = new Date(`${entry.date}T12:00:00Z`);
    if (!Number.isNaN(date.getTime())) {
      time.dateTime = entry.date;
      time.textContent = new Intl.DateTimeFormat(es ? 'es' : 'en', {day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'}).format(date);
    }
    meta.append(newsElement('span', 'news-category', texto.category || tr('News', 'Noticias')), time);
    article.append(meta, newsElement('h3', '', texto.title), newsElement('p', '', texto.summary));
    if (Array.isArray(texto.paragraphs) && texto.paragraphs.length) {
      const details = newsElement('details', 'news-details', '');
      details.append(newsElement('summary', '', tr('Read full story', 'Leer noticia completa')));
      texto.paragraphs.forEach(text => details.append(newsElement('p', '', text)));
      article.append(details);
    }
    newsList.append(article);
  });
}
pintarNoticias();
document.addEventListener('langchange', pintarNoticias);
