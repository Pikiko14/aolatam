const downloadButton = document.getElementById('download-game');
const downloadStatus = document.getElementById('download-status');
downloadButton.addEventListener('click', () => {
  const value = (window.SERVER_CONFIG?.downloadUrl || '').trim();
  if (!value) {
    downloadStatus.textContent = 'La descarga del juego estará disponible próximamente.';
    return;
  }
  try {
    const url = new URL(value, window.location.href);
    if (!['http:', 'https:', 'file:'].includes(url.protocol)) throw new Error('Invalid protocol');
    const link = document.createElement('a');
    link.href = url.href;
    link.download = '';
    document.body.appendChild(link);
    link.click();
    link.remove();
    downloadStatus.textContent = 'Abriendo la descarga del juego…';
  } catch {
    downloadStatus.textContent = 'La descarga no está disponible en este momento.';
  }
});

// Renderizado seguro: los textos de las noticias nunca se interpretan como HTML.
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
