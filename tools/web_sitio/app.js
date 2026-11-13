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
// Son las de news.js mas las del launcher (data/noticias.json, GET /api/cuenta/estado, 13/11/2026): asi cada subida
// sale aqui sola. Se ven NOTICIAS_VISIBLES; el resto, con "Ver mas noticias".
const NOTICIAS_VISIBLES = 6;
const newsList = document.getElementById('news-list');
const newsMore = document.getElementById('news-more');
let mostrarTodas = false;
const entries = Array.isArray(window.SERVER_NEWS) ? [...window.SERVER_NEWS] : [];
function ordenarNoticias() { entries.sort((a, b) => String(b.date).localeCompare(String(a.date))); }
ordenarNoticias();
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
  entries.forEach((entry, i) => {
    const texto = es && entry.es ? {...entry, ...entry.es} : entry;
    const article = newsElement('article', 'news-entry' + (!mostrarTodas && i >= NOTICIAS_VISIBLES ? ' oculta' : ''), '');
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
  if (newsMore) newsMore.hidden = mostrarTodas || entries.length <= NOTICIAS_VISIBLES;
}
pintarNoticias();
document.addEventListener('langchange', pintarNoticias);
if (newsMore) newsMore.addEventListener('click', () => { mostrarTodas = true; pintarNoticias(); });

// La version del juego y las noticias del launcher. Sin la API (abierta como archivo, o caida) se queda lo de news.js.
fetch('/api/cuenta/estado').then(r => (r.ok ? r.json() : null)).then(estado => {
  if (!estado) return;
  const version = document.getElementById('dato-version');
  if (version && estado.version) version.textContent = estado.version.replace(/^0\.0\.0\./, 'v');
  if (version && estado.version) document.getElementById('dato-version-caja').hidden = false;
  const ya = new Set(entries.map(e => e.title));
  (estado.noticias || []).forEach(n => {
    if (!n.titulo || ya.has(n.titulo)) return;
    const m = /^(Update|Fix|Hotfix)\b/i.exec(n.titulo);
    entries.push({date: n.fecha, category: m ? m[1] : 'News', title: n.titulo, summary: n.texto,
                  es: {category: m ? ({update: 'Actualización', fix: 'Arreglo', hotfix: 'Arreglo'})[m[1].toLowerCase()] : 'Noticias'}});
  });
  ordenarNoticias();
  pintarNoticias();
}).catch(() => {});

// Cabecera: solida al bajar de la portada, y el menu de movil.
const cabecera = document.getElementById('cabecera');
if (cabecera) {
  const solida = () => cabecera.classList.toggle('solida', window.scrollY > 60);
  solida();
  window.addEventListener('scroll', solida, {passive: true});
  const boton = document.getElementById('menu-boton');
  const menu = document.getElementById('menu');
  if (boton && menu) {
    const cerrar = () => { menu.classList.remove('abierto'); boton.setAttribute('aria-expanded', 'false'); };
    boton.addEventListener('click', () => {
      const abierto = menu.classList.toggle('abierto');
      boton.setAttribute('aria-expanded', String(abierto));
    });
    menu.addEventListener('click', e => { if (e.target.closest('a')) cerrar(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') cerrar(); });
  }
}
