// Botones de descarga: el cliente (downloadUrl) y el launcher (launcherUrl), de config.js.
function prepararDescarga(botonId, estadoId, clave, nombre) {
  const boton = document.getElementById(botonId);
  const estado = document.getElementById(estadoId);
  if (!boton) return;
  boton.addEventListener('click', () => {
    const valor = (window.SERVER_CONFIG?.[clave] || '').trim();
    if (!valor) {
      estado.textContent = 'La descarga de ' + nombre + ' estará disponible próximamente.';
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
      estado.textContent = 'Abriendo la descarga de ' + nombre + '…';
    } catch {
      estado.textContent = 'La descarga no está disponible en este momento.';
    }
  });
}
prepararDescarga('download-game', 'download-status', 'downloadUrl', 'el cliente');
prepararDescarga('download-launcher', 'launcher-status', 'launcherUrl', 'el launcher');

// Noticias. Renderizado seguro: los textos nunca se interpretan como HTML.
const newsList = document.getElementById('news-list');
const entries = Array.isArray(window.SERVER_NEWS) ? [...window.SERVER_NEWS] : [];
entries.sort((a, b) => String(b.date).localeCompare(String(a.date)));
function newsElement(tag, className, text) {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}
if (!entries.length) newsList.append(newsElement('p', 'news-empty', 'Aún no hay noticias publicadas. Vuelve pronto para descubrir las novedades.'));
entries.forEach(entry => {
  const article = newsElement('article', 'news-entry', '');
  const meta = newsElement('div', 'news-meta', '');
  const time = newsElement('time', '', '');
  const date = new Date(`${entry.date}T12:00:00Z`);
  if (!Number.isNaN(date.getTime())) {
    time.dateTime = entry.date;
    time.textContent = new Intl.DateTimeFormat('es', {day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'}).format(date);
  }
  meta.append(newsElement('span', 'news-category', entry.category || 'Noticias'), time);
  article.append(meta, newsElement('h3', '', entry.title), newsElement('p', '', entry.summary));
  if (Array.isArray(entry.paragraphs) && entry.paragraphs.length) {
    const details = newsElement('details', 'news-details', '');
    details.append(newsElement('summary', '', 'Leer noticia completa'));
    entry.paragraphs.forEach(text => details.append(newsElement('p', '', text)));
    article.append(details);
  }
  newsList.append(article);
});
