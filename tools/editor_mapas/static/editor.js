'use strict';
/* Editor de mapas FAO (.mpc) / Dos Coronas. Todo en un archivo; el servidor (editor_mapas.py) entrega tilesets, sprites y lee/escribe .mpc. */
const $ = s => document.querySelector(s);
const el = (t, p = {}, h = '') => { const e = document.createElement(t); Object.assign(e, p); if (h) e.innerHTML = h; return e; };
const api = async (p, o) => { const r = await fetch(p, o); if (!r.ok) throw new Error((await r.text()).slice(0, 300)); return r.json(); };
const CELL = 32, CH = 16;                       // celda en px; chunk de 16x16 celdas (el periodo de las texturas de pincel)
const ATT = { 0: null, 1: '#e5484d', 2: '#3b82f6', 3: '#f59e0b', 10: '#a855f7' };
const ATT_N = { 0: 'libre', 1: 'obstaculo (arboles, rocas, cajas)', 2: 'agua o risco', 3: 'borde / caso suelto', 10: 'zona suelta del mar' };
const attColor = v => ATT[v] === undefined ? '#9ca3af' : ATT[v];
const b64enc = u8 => { let s = '', n = 0x8000; for (let i = 0; i < u8.length; i += n) s += String.fromCharCode.apply(null, u8.subarray(i, i + n)); return btoa(s); };
const b64dec = s => { if (!s) return new Uint8Array(0); const b = atob(s), u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; };
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const msg = (t, c) => { $('#msg').textContent = t; $('#msg').className = c || ''; };

// ------------------------------------------------------------------------------------------------ estado
let M = null;                                    // mapa abierto
const S = {
  tool: 'pincel', prev: 'pincel', ts: 0, attr: 1, size: 3, forma: 'cuadro', rectModo: 'terreno', cuboModo: 'terreno',
  objId: null, espejo: 0, snap: 'libre', esparcir: false, densidad: 4, radio: 60, zonaId: 71, rutaId: 1, rutaTipo: 3, campTpl: { monstruo: 'seta_azul', cantidad: 4, radio: 4 }, campSel: null, qMons: '',
  capas: { ao: true, camps: true, terreno: true, attr: true, objetos: true, zonas: true, rutas: true, cuadricula: true, transitable: false, extra: false, marcas: true, espejo: false },
  sel: new Set(), ao: { tpl: null, sel: null, q: '', tipo: 'todos', pag: 1, dir: 0 }, tab: 'paleta', filtroObj: { q: '', fuente: 'mapobj', soloSprite: true, usados: false, pag: 1 },
};
const cam = { x: 0, y: 0, z: 0.5 };
let TS = {};                                     // n -> {color, clase, tiles}
let TSIMG = {};                                  // n -> HTMLImageElement
let OBJDEFS = {};                                // id -> [nombre, clase, fuente, bloquea, tieneSprite, flags]
let OBJMETA = {};                                // id -> meta | null | 'pendiente'
let OBJIMG = {};                                 // id -> {img, ok}
let STAGE = {};
let AOCAT = null;                                // catalogo de NPC y monstruos de AO (monster.xml / npc.xml del cliente)
const AOIMG = {};                                // sprite -> {img, ok}
let MONS = null;                                 // criaturas de Dos Coronas (monstruos.xml)
let chunks = new Map(), dirtyAll = true, dirtyChunks = new Set();
let attrCv = null, miniCv = null, extraCv = null, walkCv = null;
let dirty = false;
const cv = $('#map'), ctx = cv.getContext('2d');
const mini = $('#mini'), mctx = mini.getContext('2d');

// ------------------------------------------------------------------------------------------------ historial
const HIST = { u: [], r: [] };
function push(op) { HIST.u.push(op); if (HIST.u.length > 300) HIST.u.shift(); HIST.r = []; setDirty(true); refreshUndo(); }
function undo() { const o = HIST.u.pop(); if (!o) return; o.undo(); HIST.r.push(o); setDirty(true); refreshUndo(); redraw(); panelRefreshLight(); }
function redo() { const o = HIST.r.pop(); if (!o) return; o.redo(); HIST.u.push(o); setDirty(true); refreshUndo(); redraw(); panelRefreshLight(); }
function refreshUndo() { $('#bUndo').disabled = !HIST.u.length; $('#bRedo').disabled = !HIST.r.length; }
function setDirty(v) { dirty = v; $('#dirty').textContent = v ? '● sin guardar' : ''; }

// ------------------------------------------------------------------------------------------------ carga
async function iniciar() {
  const [tl, od] = await Promise.all([api('/api/tslist'), api('/api/objdefs')]);
  for (const t of tl) TS[t.n] = t;
  OBJDEFS = od;
  try { const m = await api('/api/mapas'); STAGE = m.stage || {}; } catch (e) { }
  buildTools(); buildTabs(); resize(); refreshUndo();
  msg(Object.keys(TS).length + ' tilesets y ' + Object.keys(OBJDEFS).length + ' definiciones de objetos. Abre un mapa o crea uno nuevo.');
  dialogoAbrir();
}

function cargarMapa(j) {
  M = {
    nombre: j.nombre, origen: j.origen, w: j.w, h: j.h, cab: j.cabecera, cel: b64dec(j.celdas), extra: b64dec(j.extra), hueco: j.hueco || '',
    ts: j.tilesets.slice(), objs: j.objetos.map(o => ({ id: o[0], x: o[1], y: o[2], a: o[3], e: o[4], c: o[5], r: o[6] || '' })),
    eventos: j.eventos, dialogos: j.dialogos, rutas: j.rutas, puntos: j.puntos, resto: j.resto || '', camps: (j.campamentos || []).map(c => ({ ...c })),
  };
  S.campSel = null; S.ao.sel = null; M.ao = []; M.aoOk = false; M.aoDirty = false; cargarSpawnsAO();
  if (M.cel.length !== M.w * M.h * 6) { msg('El mapa trae una cuadricula de tamano raro', 'mal'); }
  HIST.u = []; HIST.r = []; refreshUndo(); S.sel.clear();
  dirtyAll = true; chunks.clear(); attrCv = miniCv = extraCv = walkCv = null; S.capas.transitable = false;
  precargarTilesets(); precargarObjetos();
  reconstruirCapas();
  $('#titulo').textContent = M.nombre + ' (' + M.w + '×' + M.h + ', ' + M.objs.length + ' objetos)';
  setDirty(false);
  ajustar(); panelRefresh(); redraw();
  const num = (M.nombre.match(/(\d+)/) || [])[1];
  msg('Abierto ' + M.nombre + (num && STAGE[+num] ? ' — ' + STAGE[+num] : '') + '. Version del formato 0x' + M.cab[3].toString(16) + '.');
}

function mapaAJson() {
  return {
    w: M.w, h: M.h, cabecera: M.cab, celdas: b64enc(M.cel), extra: b64enc(M.extra), hueco: M.hueco, tilesets: M.ts,
    objetos: M.objs.map(o => [o.id, Math.round(o.x), Math.round(o.y), o.a, o.e, o.c, o.r]),
    eventos: M.eventos, dialogos: M.dialogos, rutas: M.rutas, puntos: M.puntos, resto: M.resto, nombre: M.nombre, origen: M.origen, campamentos: M.camps,
  };
}

function precargarTilesets() {
  const usados = new Set(); for (let i = 0; i < M.w * M.h; i++) usados.add(M.cel[i * 6]);
  usados.forEach(n => cargarTex(n));
}
function cargarTex(n) {
  if (TSIMG[n]) return TSIMG[n];
  const im = new Image(); im.onload = () => { im.ok = true; dirtyAll = true; redraw(); }; im.src = '/api/ts?n=' + n; TSIMG[n] = im; return im;
}

function precargarObjetos() {
  const ids = [...new Set(M.objs.map(o => o.id))].filter(i => OBJMETA[i] === undefined);
  ids.forEach(i => { OBJMETA[i] = 'pendiente'; });
  const lotes = []; for (let i = 0; i < ids.length; i += 80) lotes.push(ids.slice(i, i + 80));
  lotes.reduce((p, l) => p.then(async () => {
    const r = await api('/api/objmeta?ids=' + l.join(','));
    for (const k in r) { OBJMETA[k] = r[k]; if (r[k]) cargarImgObj(+k); }
    redraw();
  }), Promise.resolve()).catch(e => msg('Objetos: ' + e.message, 'mal'));
}
function cargarImgObj(id) {
  if (OBJIMG[id]) return OBJIMG[id];
  const o = OBJIMG[id] = { img: new Image(), ok: false };
  o.img.onload = () => { o.ok = true; redraw(); }; o.img.src = '/api/obj?id=' + id; return o;
}
function metaObj(id) {
  const m = OBJMETA[id];
  if (m === undefined) { OBJMETA[id] = 'pendiente'; api('/api/objmeta?ids=' + id).then(r => { OBJMETA[id] = r[id]; if (r[id]) cargarImgObj(id); redraw(); }); return null; }
  return m && m !== 'pendiente' ? m : null;
}

// ------------------------------------------------------------------------------------------------ capas derivadas (atributo, minimapa)
function reconstruirCapas() {
  attrCv = el('canvas'); attrCv.width = M.w; attrCv.height = M.h;
  miniCv = el('canvas'); miniCv.width = M.w; miniCv.height = M.h;
  const a = attrCv.getContext('2d').createImageData(M.w, M.h), m = miniCv.getContext('2d').createImageData(M.w, M.h);
  for (let i = 0; i < M.w * M.h; i++) pintarPx(a, m, i);
  attrCv.getContext('2d').putImageData(a, 0, 0); miniCv.getContext('2d').putImageData(m, 0, 0);
  attrCv._d = a; miniCv._d = m;
}
function hex2rgb(h) { return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]; }
function pintarPx(a, m, i) {
  const t = TS[M.cel[i * 6]], c = t ? t.color : [40, 40, 40];
  m.data[i * 4] = c[0]; m.data[i * 4 + 1] = c[1]; m.data[i * 4 + 2] = c[2]; m.data[i * 4 + 3] = 255;
  const v = M.cel[i * 6 + 1], col = attColor(v);
  if (col) { const r = hex2rgb(col); a.data[i * 4] = r[0]; a.data[i * 4 + 1] = r[1]; a.data[i * 4 + 2] = r[2]; a.data[i * 4 + 3] = 255; }
  else { a.data[i * 4 + 3] = 0; }
}
const dirtyPx = new Set();
function celdaCambio(i) { dirtyPx.add(i); const x = i % M.w, y = (i / M.w) | 0; dirtyChunks.add((x >> 4) + ',' + (y >> 4)); }
function aplicarDirtyPx() {
  if (!dirtyPx.size) return;
  const a = attrCv._d, m = miniCv._d;
  dirtyPx.forEach(i => pintarPx(a, m, i));
  attrCv.getContext('2d').putImageData(a, 0, 0); miniCv.getContext('2d').putImageData(m, 0, 0);
  dirtyPx.clear(); walkCv = null; extraCv = extraCv;
}

// ------------------------------------------------------------------------------------------------ dibujo
let raf = 0;
function redraw() { if (!raf) raf = requestAnimationFrame(() => { raf = 0; dibujar(); }); }
function resize() { const r = $('#cv').getBoundingClientRect(); cv.width = Math.max(1, r.width * devicePixelRatio); cv.height = Math.max(1, r.height * devicePixelRatio); cv.style.width = r.width + 'px'; cv.style.height = r.height + 'px'; redraw(); }
addEventListener('resize', resize);

function chunkCanvas(cx, cy) {
  const k = cx + ',' + cy; let c = chunks.get(k);
  if (c && !dirtyAll && !dirtyChunks.has(k)) return c;
  if (!c) { c = el('canvas'); c.width = c.height = CH * CELL; chunks.set(k, c); }
  const g = c.getContext('2d'); g.clearRect(0, 0, c.width, c.height);
  for (let j = 0; j < CH; j++) for (let i = 0; i < CH; i++) {
    const x = cx * CH + i, y = cy * CH + j; if (x >= M.w || y >= M.h) continue;
    const n = M.cel[(y * M.w + x) * 6], im = cargarTex(n);
    if (im.ok) g.drawImage(im, i * CELL, j * CELL, CELL, CELL, i * CELL, j * CELL, CELL, CELL);
    else { const t = TS[n]; g.fillStyle = t ? `rgb(${t.color})` : '#333'; g.fillRect(i * CELL, j * CELL, CELL, CELL); }
  }
  dirtyChunks.delete(k); return c;
}

function dibujar() {
  if (!M) { ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = '#07080c'; ctx.fillRect(0, 0, cv.width, cv.height); return; }
  aplicarDirtyPx();
  const dpr = devicePixelRatio, z = cam.z * dpr;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = '#07080c'; ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.setTransform(z, 0, 0, z, -cam.x * z, -cam.y * z);
  const vw = cv.width / z, vh = cv.height / z;
  const cx0 = clamp(Math.floor(cam.x / CELL / CH), 0, 1e6), cy0 = clamp(Math.floor(cam.y / CELL / CH), 0, 1e6);
  const cx1 = Math.min(Math.ceil((M.w) / CH) - 1, Math.floor((cam.x + vw) / CELL / CH)), cy1 = Math.min(Math.ceil(M.h / CH) - 1, Math.floor((cam.y + vh) / CELL / CH));
  if (S.capas.terreno) {
    if (cam.z < 0.12) { ctx.imageSmoothingEnabled = false; ctx.drawImage(miniCv, 0, 0, M.w * CELL, M.h * CELL); }
    else {
      ctx.imageSmoothingEnabled = cam.z < 1;
      for (let cy = cy0; cy <= cy1; cy++) for (let cx = cx0; cx <= cx1; cx++) ctx.drawImage(chunkCanvas(cx, cy), cx * CH * CELL, cy * CH * CELL);
      dirtyAll = false;
    }
  } else { ctx.fillStyle = '#1b1f2e'; ctx.fillRect(0, 0, M.w * CELL, M.h * CELL); }
  // borde del mapa
  ctx.strokeStyle = '#fff4'; ctx.lineWidth = 2 / z * dpr; ctx.strokeRect(0, 0, M.w * CELL, M.h * CELL);
  if (S.capas.extra && M.extra.length === M.w * M.h) dibujarExtra();
  if (S.capas.attr) { ctx.imageSmoothingEnabled = false; ctx.globalAlpha = 0.5; ctx.drawImage(attrCv, 0, 0, M.w * CELL, M.h * CELL); ctx.globalAlpha = 1; }
  if (S.capas.transitable) { if (!walkCv) walkCv = calcularTransitable().cv; ctx.imageSmoothingEnabled = false; ctx.globalAlpha = 0.45; ctx.drawImage(walkCv, 0, 0, M.w * CELL, M.h * CELL); ctx.globalAlpha = 1; }
  if (S.capas.cuadricula && cam.z >= 0.45) {
    ctx.lineWidth = 1 / z * dpr; const x0 = Math.max(0, Math.floor(cam.x / CELL)), x1 = Math.min(M.w, Math.ceil((cam.x + vw) / CELL)), y0 = Math.max(0, Math.floor(cam.y / CELL)), y1 = Math.min(M.h, Math.ceil((cam.y + vh) / CELL));
    ctx.beginPath(); for (let x = x0; x <= x1; x++) { ctx.moveTo(x * CELL, y0 * CELL); ctx.lineTo(x * CELL, y1 * CELL); }
    for (let y = y0; y <= y1; y++) { ctx.moveTo(x0 * CELL, y * CELL); ctx.lineTo(x1 * CELL, y * CELL); }
    ctx.strokeStyle = '#ffffff22'; ctx.stroke();
    ctx.beginPath(); for (let x = x0; x <= x1; x++) if (x % 16 === 0) { ctx.moveTo(x * CELL, y0 * CELL); ctx.lineTo(x * CELL, y1 * CELL); }
    for (let y = y0; y <= y1; y++) if (y % 16 === 0) { ctx.moveTo(x0 * CELL, y * CELL); ctx.lineTo(x1 * CELL, y * CELL); }
    ctx.strokeStyle = '#ffffff40'; ctx.stroke();
  }
  if (S.capas.objetos) dibujarObjetos(vw, vh);
  if (S.capas.rutas) dibujarRutas();
  if (S.capas.zonas) dibujarZonas();
  if (S.capas.camps) dibujarCamps();
  if (S.capas.ao) dibujarAO();
  dibujarHerramienta();
  dibujarMini(); hud();
}

function dibujarExtra() {
  if (!extraCv) {
    extraCv = el('canvas'); extraCv.width = M.w; extraCv.height = M.h; const g = extraCv.getContext('2d'), d = g.createImageData(M.w, M.h);
    for (let i = 0; i < M.w * M.h; i++) { const v = M.extra[i]; d.data[i * 4] = v * 4 & 255; d.data[i * 4 + 1] = 255 - (v * 6 & 255); d.data[i * 4 + 2] = v * 20 & 255; d.data[i * 4 + 3] = v ? 170 : 0; }
    g.putImageData(d, 0, 0);
  }
  ctx.imageSmoothingEnabled = false; ctx.drawImage(extraCv, 0, 0, M.w * CELL, M.h * CELL);
}

function rectObj(o) {
  const m = metaObj(o.id);
  if (m) return { x: o.x - m.ox, y: o.y - m.oy, w: m.w, h: m.h, m };
  return { x: o.x - 10, y: o.y - 20, w: 20, h: 22, m: null };
}
function colMarca(id) { const d = OBJDEFS[id]; if (!d) return '#ff6b6b'; return d[2] === 'npc' ? '#4de1e1' : d[2] === 'server' ? '#ff5dd3' : d[2] === 'house' ? '#ffb86c' : '#ddd'; }
function dibujarObjetos(vw, vh) {
  const vis = [];
  for (const o of M.objs) { const r = rectObj(o); if (r.x + r.w < cam.x || r.x > cam.x + vw || r.y + r.h < cam.y || r.y > cam.y + vh) continue; vis.push([o, r]); }
  vis.sort((a, b) => a[0].y - b[0].y);
  const z = cam.z * devicePixelRatio;
  ctx.imageSmoothingEnabled = cam.z < 1;
  for (const [o, r] of vis) {
    const oi = OBJIMG[o.id], d = OBJDEFS[o.id];
    if (r.m && oi && oi.ok) {
      if (S.capas.espejo && o.e === 2) { ctx.save(); ctx.translate(o.x, 0); ctx.scale(-1, 1); ctx.drawImage(oi.img, -(r.m.w - r.m.ox) + 0, r.y); ctx.restore(); }
      else ctx.drawImage(oi.img, r.x, r.y);
    } else if (S.capas.marcas) {
      ctx.fillStyle = colMarca(o.id); ctx.globalAlpha = 0.85; ctx.beginPath(); ctx.moveTo(o.x, o.y - 12 / z * 1.5); ctx.lineTo(o.x + 8 / z * 1.5, o.y); ctx.lineTo(o.x, o.y + 12 / z * 1.5); ctx.lineTo(o.x - 8 / z * 1.5, o.y); ctx.closePath(); ctx.fill(); ctx.globalAlpha = 1;
      if (cam.z > 0.5) { ctx.fillStyle = '#fff'; ctx.font = (11 / z * devicePixelRatio) + 'px sans-serif'; ctx.fillText(String(o.id), o.x + 8 / z * 1.5, o.y - 6 / z * 1.5); }
    }
    if (S.capas.huellas && r.m && r.m.b) { }
  }
  // seleccion
  ctx.lineWidth = 2 / z; ctx.strokeStyle = '#ffd24a'; ctx.setLineDash([6 / z, 4 / z]);
  for (const o of S.sel) { const r = rectObj(o); ctx.strokeRect(r.x, r.y, r.w, r.h); ctx.beginPath(); ctx.arc(o.x, o.y, 4 / z, 0, 7); ctx.stroke(); }
  ctx.setLineDash([]);
  // huellas de colision de los objetos que bloquean (con la capa de colision activa)
  if (S.capas.attr && cam.z > 0.3) {
    ctx.strokeStyle = '#ff5a5a'; ctx.lineWidth = 1.5 / z;
    for (const [o, r] of vis) { if (r.m && r.m.b) { const n = r.m.huella || 1, d0 = Math.floor((n - 1) / 2), cx = Math.floor(o.x / CELL), cy = Math.floor(o.y / CELL); ctx.strokeRect((cx - d0) * CELL, (cy - d0) * CELL, n * CELL, n * CELL); } }
  }
}

function dibujarRutas() {
  const z = cam.z * devicePixelRatio; ctx.lineWidth = 2.5 / z;
  for (const r of M.rutas) {
    if (r.puntos.length < 1) continue; ctx.strokeStyle = '#ffd24acc'; ctx.fillStyle = '#ffd24a'; ctx.beginPath();
    r.puntos.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.stroke();
    r.puntos.forEach(p => { ctx.beginPath(); ctx.arc(p[0], p[1], 4 / z, 0, 7); ctx.fill(); });
    const p = r.puntos[0]; ctx.fillStyle = '#fff'; ctx.font = (12 / z) + 'px sans-serif'; ctx.fillText('ruta ' + r.id, p[0] + 6 / z, p[1] - 6 / z);
  }
}
function colZona(id) { return id === 1 || id === 2 ? '#58c27d' : id >= 31 && id <= 44 ? '#ffd24a' : id >= 71 && id <= 83 ? '#4de1e1' : '#e6e8f2'; }
function dibujarZonas() {
  const z = cam.z * devicePixelRatio; ctx.lineWidth = 2 / z;
  for (const s of M.puntos) {
    const c = colZona(s.id); ctx.strokeStyle = c; ctx.fillStyle = c + '30';
    if (s.puntos.length >= 2) { ctx.beginPath(); s.puntos.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); if (s.puntos.length > 2) { ctx.closePath(); ctx.fill(); } ctx.stroke(); }
    ctx.fillStyle = c; s.puntos.forEach(p => { ctx.beginPath(); ctx.arc(p[0], p[1], 5 / z, 0, 7); ctx.fill(); });
    const p = s.puntos[0]; if (p) { ctx.fillStyle = '#fff'; ctx.font = (13 / z) + 'px sans-serif'; ctx.fillText((s.id === 1 || s.id === 2 ? 'salida ' : s.id >= 71 ? 'zona ' : 'punto ') + s.id, p[0] + 7 / z, p[1] - 7 / z); }
  }
}

function colCamp(c) { let h = 7; for (const ch of String(c.monstruo)) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return 'hsl(' + (h % 360) + ' 70% 60%)'; }
function dibujarCamps() {
  const z = cam.z * devicePixelRatio;
  for (const c of M.camps) {
    const px = c.x * CELL, py = c.y * CELL, r = (c.radio || 3) * CELL, col = c.jefe ? '#ff4d4d' : '#ffb347', sel = S.campSel === c;
    ctx.lineWidth = (sel ? 3 : 1.5) / z; ctx.strokeStyle = sel ? '#fff' : col; ctx.fillStyle = col + '26';
    ctx.beginPath(); ctx.arc(px, py, r, 0, 7); ctx.fill(); ctx.stroke();
    ctx.fillStyle = colCamp(c); ctx.beginPath(); ctx.arc(px, py, 7 / z * 1.3, 0, 7); ctx.fill(); ctx.strokeStyle = '#000'; ctx.lineWidth = 1 / z; ctx.stroke();
    if (cam.z > 0.18) { ctx.fillStyle = '#fff'; ctx.font = (12 / z * devicePixelRatio) + 'px sans-serif'; ctx.fillText((c.monstruo || '?') + ' x' + (c.cantidad || 1) + (c.jefe ? ' *' : ''), px + 10 / z, py - 8 / z); }
  }
}

// ------------------------------------------------------------------------------------------------ NPC y monstruos de AO (spawns del servidor)
// El servidor guarda cada NPC/monstruo en server/plantillas/<mapa>.json ("spawns", tile [x, y]). Su y cuenta desde ABAJO del mapa: celda y = alto - 1 - tile y
// (medido: el 100% de los spawns de varios mapas caen en casillas libres con la y invertida y casi ninguno sin invertir).
const aoTile = (cx, cy) => [cx, M.h - 1 - cy];
async function cargarSpawnsAO() {
  const nombre = M.nombre, mapa = M;
  try {
    const r = await api('/api/ao/spawns?mapa=' + encodeURIComponent(nombre));
    if (M !== mapa) return;
    M.aoStage = r.stage; M.aoArchivo = r.archivo; M.aoExiste = r.existe;
    M.ao = (r.spawns || []).map(e => ({ entity_id: e.entity_id, nombre: e.nombre || '?', npc_type: e.npc_type, sprite: e.sprite, monstruo: !!e.monstruo, nivel: e.nivel || 0, dir: e.direccion || 0, cx: e.tile[0], cy: M.h - 1 - e.tile[1] }));
    M.aoOk = r.stage != null; M.aoDirty = false;
    if (M.aoOk) msg('Servidor: stage ' + r.stage + ' (' + r.archivo + (r.existe ? '' : ', archivo nuevo') + '), ' + M.ao.length + ' NPC y monstruos.');
    else msg('El mapa no se llama mapNNN: no se sabe a que stage del servidor pertenece, no se podran exportar NPC y monstruos.', 'av');
    panelRefreshLight(); redraw();
  } catch (e) { msg('No se pudieron leer los spawns del servidor: ' + e.message, 'mal'); }
}
function imgAO(sprite) {
  let o = AOIMG[sprite];
  if (!o) { o = AOIMG[sprite] = { img: new Image(), ok: false }; o.img.onload = () => { o.ok = true; redraw(); }; o.img.onerror = () => { o.ok = false; }; o.img.src = '/api/ao/foto?id=' + sprite; }
  return o;
}
function dibujarAO() {
  if (!M.ao) return; const z = cam.z * devicePixelRatio;
  for (const a of M.ao) {
    const px = (a.cx + .5) * CELL, py = (a.cy + .5) * CELL, sel = S.ao.sel === a, col = a.monstruo ? '#ff5a5a' : '#4fd1ff';
    if (cam.z >= 0.25) { const o = imgAO(a.sprite); if (o.ok) { const w = o.img.naturalWidth, h = o.img.naturalHeight; ctx.imageSmoothingEnabled = false; ctx.drawImage(o.img, px - w / 2, py + CELL * .35 - h, w, h); } }
    ctx.lineWidth = (sel ? 3 : 1.5) / z; ctx.strokeStyle = sel ? '#fff' : '#000'; ctx.fillStyle = col;
    ctx.beginPath(); ctx.arc(px, py + CELL * .3, (sel ? 6 : 4.5) / z * 1.3, 0, 7); ctx.fill(); ctx.stroke();
    if (cam.z > 0.3 || sel) { ctx.fillStyle = '#fff'; ctx.strokeStyle = '#000'; ctx.lineWidth = 3 / z; ctx.font = (12 / z * devicePixelRatio) + 'px sans-serif'; const t = a.nombre + (a.monstruo && a.nivel ? ' Lv' + a.nivel : ''); ctx.strokeText(t, px + 9 / z, py - 6 / z); ctx.fillText(t, px + 9 / z, py - 6 / z); }
  }
}
function dibujarPrevAO() {
  if (!cur.sobre || !S.ao.tpl) return; const t = S.ao.tpl, o = imgAO(t.sprite), z = cam.z * devicePixelRatio, px = (cur.cx + .5) * CELL, py = (cur.cy + .5) * CELL;
  ctx.globalAlpha = 0.65; if (o.ok) ctx.drawImage(o.img, px - o.img.naturalWidth / 2, py + CELL * .35 - o.img.naturalHeight); ctx.globalAlpha = 1;
  ctx.strokeStyle = t.monstruo ? '#ff5a5a' : '#4fd1ff'; ctx.lineWidth = 2 / z; ctx.strokeRect(cur.cx * CELL, cur.cy * CELL, CELL, CELL);
}
function aoCerca(wx, wy) { let b = null, bd = 1e9; for (const a of M.ao || []) { const d = Math.hypot((a.cx + .5) * CELL - wx, (a.cy + .5) * CELL - wy); if (d < Math.max(14 / cam.z, CELL * .8) && d < bd) { bd = d; b = a; } } return b; }
function casillaLibre(cx, cy) { return cx >= 0 && cy >= 0 && cx < M.w && cy < M.h && M.cel[(cy * M.w + cx) * 6 + 1] === 0; }
function iniciarAO(e) {
  const a = aoCerca(cur.x, cur.y);
  if (a) { S.ao.sel = a; drag = { ao: a, ant: { cx: a.cx, cy: a.cy } }; setTab('ao'); return; }
  S.ao.sel = null;
  if (!S.ao.tpl) { msg('Elige primero un NPC o monstruo en la pestana "NPC/Monstruos AO".', 'av'); setTab('ao'); return; }
  if (!M.aoOk) { msg('Este mapa no tiene stage del servidor (debe llamarse mapNNN).', 'mal'); return; }
  if (!casillaLibre(cur.cx, cur.cy)) { msg('Esa casilla esta bloqueada o fuera del mapa.', 'mal'); return; }
  const t = S.ao.tpl, n = { entity_id: null, nombre: t.nombre, npc_type: t.id, sprite: t.sprite, monstruo: t.monstruo, nivel: t.nivel, dir: S.ao.dir, cx: cur.cx, cy: cur.cy };
  M.ao.push(n); S.ao.sel = n; M.aoDirty = true;
  push({ undo() { const i = M.ao.indexOf(n); if (i >= 0) M.ao.splice(i, 1); if (S.ao.sel === n) S.ao.sel = null; }, redo() { M.ao.push(n); } }); panelRefresh();
}
function borrarAO(a) {
  const i = M.ao.indexOf(a); if (i < 0) return; M.ao.splice(i, 1); S.ao.sel = null; M.aoDirty = true;
  push({ undo() { M.ao.splice(i, 0, a); }, redo() { const k = M.ao.indexOf(a); if (k >= 0) M.ao.splice(k, 1); } }); panelRefresh(); redraw();
}
async function exportarAO(forzar) {
  if (!M || !M.aoOk || (!M.aoDirty && !forzar)) return null;
  const spawns = M.ao.map(a => ({ entity_id: a.entity_id, nombre: a.nombre, npc_type: a.npc_type, sprite: a.sprite, monstruo: a.monstruo, nivel: a.nivel, direccion: a.dir, tile: aoTile(a.cx, a.cy) }));
  const r = await api('/api/ao/exportar', { method: 'POST', body: JSON.stringify({ mapa: M.nombre, spawns }) });
  await cargarSpawnsAO(); M.aoDirty = false; return r;
}
function resumenAO(r) {
  if (!r) return '';
  if (r.error) return '<br><span class="mal">NPC y monstruos NO exportados: ' + r.error + '</span>';
  return `<br><span class="ok">Servidor: ${r.archivo} (stage ${r.stage}) · ${r.total} NPC y monstruos · ${r.nuevos} nuevos · ${r.borrados} borrados${r.creada ? ' · archivo NUEVO: hay que registrar el stage en login.PLANTILLAS_POR_STAGE' : ''}. Reinicia el servidor para verlos.</span>`;
}
function tabAO() {
  const p = $('#panel'); p.innerHTML = '';
  p.append(el('div', { className: 'mu' }, 'N: elige un NPC o monstruo del catalogo (sale del cliente: monster.xml y npc.xml) y haz clic en el mapa para colocarlo. Clic sobre uno = seleccionarlo y arrastrarlo; Supr lo borra. "Exportar .mpc" tambien escribe estos cambios en el servidor.'));
  if (M && !M.aoOk) p.append(el('div', { className: 'mal' }, 'Este mapa no se llama mapNNN: no se puede exportar al servidor.'));
  const b = el('button', { className: 'btn sm' }, 'Exportar al servidor ahora' + (M && M.aoDirty ? ' ●' : '')); b.onclick = async () => { try { const r = await exportarAO(true); if (r) { msg('Spawns exportados a ' + r.archivo, 'ok'); modal('<h3 style="margin:0 0 8px">Exportado al servidor</h3><div>' + resumenAO(r) + '</div><div class="row"><button class="btn" id="mx3">Cerrar</button></div>'); $('#mx3').onclick = cerrarModal; panelRefresh(); } } catch (e) { msg('No se pudo exportar: ' + e.message, 'mal'); } };
  const rw = el('div', { className: 'row' }); rw.append(b); p.append(rw);
  const sel = S.ao.sel;
  if (sel) {
    p.append(el('h4', {}, 'Seleccionado'));
    p.append(el('div', {}, `<b>${sel.nombre}</b> · npc_type ${sel.npc_type} · ${sel.monstruo ? 'monstruo Lv' + sel.nivel : 'NPC'} · casilla ${sel.cx},${sel.cy}${sel.entity_id ? ' · entidad ' + sel.entity_id : ' · nuevo'}`));
    const r = el('div', { className: 'row' }); r.append(el('span', { className: 'mu' }, 'Direccion'));
    const d = el('select'); for (let i = 0; i < 8; i++) d.append(el('option', { value: i, selected: sel.dir === i }, i)); d.onchange = () => { const o = sel.dir, n = +d.value; sel.dir = n; M.aoDirty = true; push({ undo() { sel.dir = o; }, redo() { sel.dir = n; } }); };
    const bb = el('button', { className: 'btn sm' }, 'Borrar'); bb.onclick = () => borrarAO(sel); r.append(d, bb); p.append(r);
  }
  p.append(el('h4', {}, 'Para colocar' + (S.ao.tpl ? ': ' + S.ao.tpl.nombre + ' (' + S.ao.tpl.id + ')' : '')));
  const f = el('div', { className: 'row' }); const q = el('input', { type: 'text', placeholder: 'buscar nombre, id o nivel', value: S.ao.q }); q.oninput = () => { S.ao.q = q.value; S.ao.pag = 1; pintar(); };
  const tp = el('select'); for (const [v, n] of [['todos', 'Todos'], ['monstruo', 'Monstruos'], ['npc', 'NPC']]) tp.append(el('option', { value: v, selected: S.ao.tipo === v }, n)); tp.onchange = () => { S.ao.tipo = tp.value; S.ao.pag = 1; pintar(); };
  const dd = el('select', { title: 'Direccion al colocar' }); for (let i = 0; i < 8; i++) dd.append(el('option', { value: i, selected: S.ao.dir === i }, 'dir ' + i)); dd.onchange = () => { S.ao.dir = +dd.value; };
  f.append(q, tp, dd); p.append(f);
  const caja = el('div', { className: 'olist' }), nav = el('div', { className: 'row' }); p.append(caja, nav);
  const pintar = () => {
    if (!AOCAT) { caja.innerHTML = '<div class="mu">Cargando catalogo…</div>'; return; }
    const s = S.ao.q.toLowerCase().trim(), l = AOCAT.filter(c => (S.ao.tipo === 'todos' || (S.ao.tipo === 'monstruo') === c.monstruo) && (!s || (c.id + ' ' + c.nombre + ' lv' + c.nivel + ' ' + c.sprite).toLowerCase().includes(s)));
    const PAG = 30, pags = Math.max(1, Math.ceil(l.length / PAG)); S.ao.pag = clamp(S.ao.pag, 1, pags);
    caja.innerHTML = '';
    for (const c of l.slice((S.ao.pag - 1) * PAG, S.ao.pag * PAG)) {
      const it = el('div', { className: 'oit' + (S.ao.tpl && S.ao.tpl.id === c.id && S.ao.tpl.monstruo === c.monstruo ? ' on' : ''), title: c.nombre + ' · id ' + c.id + ' · sprite ' + c.sprite });
      it.innerHTML = `<div class="th"><img loading="lazy" src="/api/ao/foto?id=${c.sprite}" onerror="this.style.display='none'"></div><div class="nm">${c.nombre}<br>${c.monstruo ? 'Lv' + c.nivel : 'NPC'} · ${c.id}</div>`;
      it.onclick = () => { S.ao.tpl = c; if (S.tool !== 'ao') setTool('ao'); else panelRefresh(); }; caja.append(it);
    }
    nav.innerHTML = ''; const a = el('button', { className: 'btn sm' }, '◀'), n = el('button', { className: 'btn sm' }, '▶');
    a.onclick = () => { S.ao.pag--; pintar(); }; n.onclick = () => { S.ao.pag++; pintar(); }; nav.append(a, el('span', { className: 'mu' }, `${S.ao.pag}/${pags} · ${l.length} entradas`), n);
  };
  if (!AOCAT) api('/api/ao/catalogo').then(l => { AOCAT = l; if (S.tab === 'ao') pintar(); }).catch(e => { caja.innerHTML = '<div class="mal">' + e.message + '</div>'; }); else pintar();
  p.append(el('h4', {}, 'En este mapa (' + ((M && M.ao) ? M.ao.length : 0) + ')'));
  const tb = el('table', { className: 'tbl' }); p.append(tb);
  (M.ao || []).slice(0, 400).forEach(a => { const tr = el('tr', { className: S.ao.sel === a ? 'sel' : '' }, `<td>${a.nombre}</td><td>${a.monstruo ? 'Lv' + a.nivel : 'NPC'}</td><td>${a.cx},${a.cy}</td>`); tr.onclick = () => { S.ao.sel = a; cam.x = (a.cx + .5) * CELL - cv.width / cam.z / devicePixelRatio / 2; cam.y = (a.cy + .5) * CELL - cv.height / cam.z / devicePixelRatio / 2; panelRefresh(); redraw(); }; tb.append(tr); });
  if ((M.ao || []).length > 400) p.append(el('div', { className: 'mu' }, 'Solo se listan los primeros 400.'));
}

function campCerca(wx, wy) { let b = null, bd = 1e9; for (const c of M.camps) { const d = Math.hypot(c.x * CELL - wx, c.y * CELL - wy); if (d < Math.max(14 / cam.z, CELL * .7) && d < bd) { bd = d; b = c; } } return b; }
function dibujarPrevCamp() { if (!cur.sobre) return; const z = cam.z * devicePixelRatio, t = S.campTpl; ctx.strokeStyle = '#ffb347'; ctx.lineWidth = 2 / z; ctx.setLineDash([6 / z, 4 / z]); ctx.beginPath(); ctx.arc((cur.cx + .5) * CELL, (cur.cy + .5) * CELL, (t.radio || 3) * CELL, 0, 7); ctx.stroke(); ctx.setLineDash([]); }

let cur = { x: 0, y: 0, cx: 0, cy: 0, sobre: false };
let drag = null;
function dibujarHerramienta() {
  const z = cam.z * devicePixelRatio;
  if (S.tool === 'zona' || S.tool === 'ruta') { if (drag && drag.pts) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 2 / z; ctx.beginPath(); drag.pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.lineTo(cur.x, cur.y); ctx.stroke(); drag.pts.forEach(p => { ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(p[0], p[1], 5 / z, 0, 7); ctx.fill(); }); } return; }
  if (!cur.sobre) return;
  ctx.lineWidth = 2 / z;
  if (S.tool === 'camp') { dibujarPrevCamp(); return; }
  if (S.tool === 'ao') { dibujarPrevAO(); return; }
  if (S.tool === 'pincel' || S.tool === 'attr') {
    ctx.strokeStyle = S.tool === 'attr' ? attColor(S.attr) || '#fff' : '#fff'; const r = S.size / 2;
    if (S.forma === 'circulo') { ctx.beginPath(); ctx.ellipse((cur.cx + .5) * CELL, (cur.cy + .5) * CELL, r * CELL, r * CELL, 0, 0, 7); ctx.stroke(); }
    else { const o = Math.floor(S.size / 2); ctx.strokeRect((cur.cx - o) * CELL, (cur.cy - o) * CELL, S.size * CELL, S.size * CELL); }
  } else if (S.tool === 'rect' && drag && drag.a) {
    const [x0, x1] = [Math.min(drag.a.cx, cur.cx), Math.max(drag.a.cx, cur.cx)], [y0, y1] = [Math.min(drag.a.cy, cur.cy), Math.max(drag.a.cy, cur.cy)];
    ctx.strokeStyle = '#fff'; ctx.strokeRect(x0 * CELL, y0 * CELL, (x1 - x0 + 1) * CELL, (y1 - y0 + 1) * CELL);
  } else if (S.tool === 'cubo' || S.tool === 'cuentagotas') { ctx.strokeStyle = '#fff'; ctx.strokeRect(cur.cx * CELL, cur.cy * CELL, CELL, CELL); }
  else if (S.tool === 'objeto' && S.objId != null) {
    const p = snapPt(cur.x, cur.y), oi = cargarImgObj(S.objId), m = metaObj(S.objId);
    ctx.globalAlpha = 0.65;
    if (m && oi.ok) ctx.drawImage(oi.img, p.x - m.ox, p.y - m.oy); else { ctx.fillStyle = '#fff'; ctx.fillRect(p.x - 8, p.y - 8, 16, 16); }
    ctx.globalAlpha = 1; ctx.strokeStyle = '#fff'; ctx.beginPath(); ctx.arc(p.x, p.y, 4 / z, 0, 7); ctx.stroke();
    if (S.esparcir) { ctx.setLineDash([6 / z, 5 / z]); ctx.beginPath(); ctx.arc(p.x, p.y, S.radio, 0, 7); ctx.stroke(); ctx.setLineDash([]); }
  } else if (S.tool === 'sel' && drag && drag.box) {
    const b = drag.box; ctx.fillStyle = '#6ea8ff22'; ctx.strokeStyle = '#6ea8ff'; ctx.fillRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0); ctx.strokeRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0);
  } else if (S.tool === 'borrar') { ctx.strokeStyle = '#ff6b6b'; ctx.beginPath(); ctx.arc(cur.x, cur.y, S.size * CELL / 2, 0, 7); ctx.stroke(); }
}

function dibujarMini() {
  mctx.fillStyle = '#000'; mctx.fillRect(0, 0, mini.width, mini.height);
  if (!M) return;
  const k = Math.min(mini.width / M.w, mini.height / M.h), w = M.w * k, h = M.h * k, ox = (mini.width - w) / 2, oy = (mini.height - h) / 2;
  mctx.imageSmoothingEnabled = false; mctx.drawImage(miniCv, ox, oy, w, h);
  if (S.capas.attr) { mctx.globalAlpha = 0.5; mctx.drawImage(attrCv, ox, oy, w, h); mctx.globalAlpha = 1; }
  const vw = cv.width / (cam.z * devicePixelRatio) / CELL, vh = cv.height / (cam.z * devicePixelRatio) / CELL;
  mctx.strokeStyle = '#fff'; mctx.lineWidth = 1.5; mctx.strokeRect(ox + cam.x / CELL * k, oy + cam.y / CELL * k, vw * k, vh * k);
  mini._k = { k, ox, oy };
}
function hud() {
  if (!M) return;
  $('#hud').textContent = `celda ${cur.cx},${cur.cy} · px ${Math.round(cur.x)},${Math.round(cur.y)} · zoom ${Math.round(cam.z * 100)}%` + (M && inB(cur.cx, cur.cy) ? ` · tileset ${M.cel[(cur.cy * M.w + cur.cx) * 6]} (${(TS[M.cel[(cur.cy * M.w + cur.cx) * 6]] || {}).clase || '?'}) · atributo ${M.cel[(cur.cy * M.w + cur.cx) * 6 + 1]}` : '');
  $('#zlbl').textContent = Math.round(cam.z * 100) + '%';
}

// ------------------------------------------------------------------------------------------------ camara
function ajustar() { if (!M) return; const r = $('#cv').getBoundingClientRect(); if (r.width < 50 || r.height < 50) { setTimeout(ajustar, 120); return; } cam.z = clamp(Math.min(r.width / (M.w * CELL), r.height / (M.h * CELL)), 0.03, 4); cam.x = (M.w * CELL - r.width / cam.z) / 2; cam.y = (M.h * CELL - r.height / cam.z) / 2; redraw(); }
function zoomEn(f, px, py) {
  const r = $('#cv').getBoundingClientRect(); px = px ?? r.width / 2; py = py ?? r.height / 2;
  const wx = cam.x + px / cam.z, wy = cam.y + py / cam.z; cam.z = clamp(cam.z * f, 0.03, 6); cam.x = wx - px / cam.z; cam.y = wy - py / cam.z; redraw();
}
function aMundo(ev) { const r = cv.getBoundingClientRect(); return { x: cam.x + (ev.clientX - r.left) / cam.z, y: cam.y + (ev.clientY - r.top) / cam.z }; }
const inB = (x, y) => M && x >= 0 && y >= 0 && x < M.w && y < M.h;
function snapPt(x, y) {
  if (S.snap === 'celda') return { x: (Math.floor(x / CELL) + .5) * CELL, y: (Math.floor(y / CELL) + 1) * CELL - 2 };
  if (S.snap === 'mitad') return { x: Math.round(x / 16) * 16, y: Math.round(y / 16) * 16 };
  return { x: Math.round(x), y: Math.round(y) };
}

// ------------------------------------------------------------------------------------------------ edicion de celdas
let stroke = null;
function ensureStroke() { if (!stroke) stroke = new Map(); }
function setCelda(x, y, ts, attr) {
  if (!inB(x, y)) return; const i = y * M.w + x;
  if (ts != null && M.cel[i * 6] === ts && (attr == null || M.cel[i * 6 + 1] === attr)) return;
  if (ts == null && attr != null && M.cel[i * 6 + 1] === attr) return;
  ensureStroke(); if (!stroke.has(i)) stroke.set(i, M.cel.slice(i * 6, i * 6 + 6));
  if (ts != null) { M.cel[i * 6] = ts; if (!M.ts.includes(ts)) M.ts.push(ts); }
  if (attr != null) M.cel[i * 6 + 1] = attr;
  celdaCambio(i);
}
function cerrarTrazo(etq) {
  if (!stroke || !stroke.size) { stroke = null; return; }
  const antes = stroke, despues = new Map(); antes.forEach((_, i) => despues.set(i, M.cel.slice(i * 6, i * 6 + 6)));
  const tsAntes = M.ts.slice();
  const aplicar = mp => { mp.forEach((v, i) => { M.cel.set(v, i * 6); celdaCambio(i); }); };
  push({ undo() { aplicar(antes); }, redo() { aplicar(despues); } }); stroke = null;
  const usados = new Set(); despues.forEach(v => usados.add(v[0])); usados.forEach(cargarTex);
  redraw();
}
function pintarDisco(cx, cy, fn) {
  const r = S.size / 2, o = Math.floor(S.size / 2);
  if (S.forma === 'circulo') { for (let y = -Math.ceil(r); y <= Math.ceil(r); y++) for (let x = -Math.ceil(r); x <= Math.ceil(r); x++) if (x * x + y * y <= r * r + .25) fn(cx + x, cy + y); }
  else for (let y = -o; y < S.size - o; y++) for (let x = -o; x < S.size - o; x++) fn(cx + x, cy + y);
}
function linea(a, b, fn) { let x0 = a.cx, y0 = a.cy; const x1 = b.cx, y1 = b.cy, dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1; let e = dx + dy; for (; ;) { fn(x0, y0); if (x0 === x1 && y0 === y1) break; const e2 = 2 * e; if (e2 >= dy) { e += dy; x0 += sx; } if (e2 <= dx) { e += dx; y0 += sy; } } }
function rellenar(cx, cy, modo) {
  if (!inB(cx, cy)) return; const k = modo === 'terreno' ? 0 : 1, objetivo = M.cel[(cy * M.w + cx) * 6 + k], nuevo = modo === 'terreno' ? S.ts : S.attr;
  if (objetivo === nuevo) return; const pila = [cy * M.w + cx], vis = new Uint8Array(M.w * M.h); let n = 0;
  while (pila.length && n < 400000) {
    const i = pila.pop(); if (vis[i]) continue; vis[i] = 1; if (M.cel[i * 6 + k] !== objetivo) continue; n++;
    const x = i % M.w, y = (i / M.w) | 0; if (modo === 'terreno') setCelda(x, y, nuevo, null); else setCelda(x, y, null, nuevo);
    if (x > 0) pila.push(i - 1); if (x < M.w - 1) pila.push(i + 1); if (y > 0) pila.push(i - M.w); if (y < M.h - 1) pila.push(i + M.w);
  }
  cerrarTrazo(); msg('Relleno: ' + n + ' celdas.');
}

// ------------------------------------------------------------------------------------------------ edicion de objetos
function addObjs(list) { M.objs.push(...list); push({ undo() { list.forEach(o => { const i = M.objs.indexOf(o); if (i >= 0) M.objs.splice(i, 1); S.sel.delete(o); }); }, redo() { M.objs.push(...list); } }); redraw(); panelRefreshLight(); }
function delObjs(list) {
  if (!list.length) return; const idx = list.map(o => M.objs.indexOf(o));
  list.forEach(o => { const i = M.objs.indexOf(o); if (i >= 0) M.objs.splice(i, 1); S.sel.delete(o); });
  push({ undo() { list.forEach(o => M.objs.push(o)); }, redo() { list.forEach(o => { const i = M.objs.indexOf(o); if (i >= 0) M.objs.splice(i, 1); S.sel.delete(o); }); } }); redraw(); panelRefreshLight();
}
function moverObjs(list, dx, dy, registrar = true) {
  list.forEach(o => { o.x += dx; o.y += dy; });
  if (registrar) push({ undo() { list.forEach(o => { o.x -= dx; o.y -= dy; }); }, redo() { list.forEach(o => { o.x += dx; o.y += dy; }); } }); redraw();
}
function modObj(o, props) { const antes = {}; for (const k in props) antes[k] = o[k]; Object.assign(o, props); push({ undo() { Object.assign(o, antes); }, redo() { Object.assign(o, props); } }); redraw(); }
function nuevoObj(id, x, y) { return { id, x: Math.round(x), y: Math.round(y), a: 0, e: S.espejo, c: 192, r: '00'.repeat(50) }; }
function objetoEn(wx, wy) {
  let mejor = null, md = 1e9;
  for (const o of M.objs) { const r = rectObj(o); if (wx >= r.x && wx <= r.x + r.w && wy >= r.y && wy <= r.y + r.h) { const d = Math.abs(o.y - wy) + Math.abs(o.x - wx) * .1; if (o.y >= (mejor ? mejor.y : -1) && d < md + 400) { if (!mejor || o.y >= mejor.y) { mejor = o; md = d; } } } }
  return mejor;
}
let portapapeles = [];

// ------------------------------------------------------------------------------------------------ zonas y rutas
function terminarForma() {
  if (!drag || !drag.pts) return; const pts = drag.pts; drag = null;
  if (S.tool === 'zona') {
    if (pts.length < 1) return; const s = { id: S.zonaId, puntos: pts.map(p => [Math.round(p[0]), Math.round(p[1])]) };
    M.puntos.push(s); push({ undo() { M.puntos.splice(M.puntos.indexOf(s), 1); }, redo() { M.puntos.push(s); } });
  } else if (S.tool === 'ruta') {
    if (pts.length < 2) return; const r = { id: S.rutaId, uno: 1, cero: 0, puntos: pts.map(p => [Math.round(p[0]), Math.round(p[1]), S.rutaTipo, 0, 0, 0]) };
    M.rutas.push(r); S.rutaId++; push({ undo() { M.rutas.splice(M.rutas.indexOf(r), 1); }, redo() { M.rutas.push(r); } });
  }
  panelRefresh(); redraw();
}
function puntoCerca(wx, wy) {
  const tol = 9 / cam.z;
  for (const s of M.puntos) for (let i = 0; i < s.puntos.length; i++) { const p = s.puntos[i]; if (Math.hypot(p[0] - wx, p[1] - wy) < tol) return { s, i, tipo: 'zona' }; }
  for (const r of M.rutas) for (let i = 0; i < r.puntos.length; i++) { const p = r.puntos[i]; if (Math.hypot(p[0] - wx, p[1] - wy) < tol) return { s: r, i, tipo: 'ruta' }; }
  return null;
}

// ------------------------------------------------------------------------------------------------ transitabilidad (reglas de Dos Coronas)
function calcularTransitable() {
  const w = M.w, h = M.h, libre = new Uint8Array(w * h);
  for (let i = 0; i < w * h; i++) { const t = TS[M.cel[i * 6]]; libre[i] = (M.cel[i * 6 + 1] === 0 && t) ? 1 : 0; }
  for (const o of M.objs) {
    const m = OBJMETA[o.id]; if (!m || m === 'pendiente' || !m.b) continue; const n = m.huella || 1, d0 = Math.floor((n - 1) / 2), cx = Math.floor(o.x / CELL), cy = Math.floor(o.y / CELL);
    for (let y = cy - d0; y < cy - d0 + n; y++) for (let x = cx - d0; x < cx - d0 + n; x++) if (x >= 0 && y >= 0 && x < w && y < h) libre[y * w + x] = 0;
  }
  for (let x = 0; x < w; x++) { libre[x] = 0; libre[(h - 1) * w + x] = 0; } for (let y = 0; y < h; y++) { libre[y * w] = 0; libre[y * w + w - 1] = 0; }
  const comp = new Int32Array(w * h), tam = [0]; let n = 0;
  for (let i = 0; i < w * h; i++) if (libre[i] && !comp[i]) {
    n++; let c = 0; const pila = [i]; comp[i] = n;
    while (pila.length) { const k = pila.pop(); c++; const x = k % w; if (x > 0 && libre[k - 1] && !comp[k - 1]) { comp[k - 1] = n; pila.push(k - 1); } if (x < w - 1 && libre[k + 1] && !comp[k + 1]) { comp[k + 1] = n; pila.push(k + 1); } if (k >= w && libre[k - w] && !comp[k - w]) { comp[k - w] = n; pila.push(k - w); } if (k < w * (h - 1) && libre[k + w] && !comp[k + w]) { comp[k + w] = n; pila.push(k + w); } }
    tam[n] = c;
  }
  let mayor = 1; for (let i = 1; i <= n; i++) if (tam[i] > tam[mayor]) mayor = i;
  const c = el('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'), d = g.createImageData(w, h);
  for (let i = 0; i < w * h; i++) { const col = !libre[i] ? [255, 60, 60] : comp[i] === mayor ? [60, 220, 120] : [255, 200, 40]; d.data[i * 4] = col[0]; d.data[i * 4 + 1] = col[1]; d.data[i * 4 + 2] = col[2]; d.data[i * 4 + 3] = !libre[i] ? 120 : 160; }
  g.putImageData(d, 0, 0);
  return { cv: c, comp, tam, mayor, libre, n };
}

// ------------------------------------------------------------------------------------------------ entrada
let espacio = false;
cv.addEventListener('contextmenu', e => e.preventDefault());
cv.addEventListener('wheel', e => { e.preventDefault(); const r = cv.getBoundingClientRect(); zoomEn(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top); }, { passive: false });
function actualizarCursor(e) { const w = aMundo(e); cur.x = w.x; cur.y = w.y; cur.cx = Math.floor(w.x / CELL); cur.cy = Math.floor(w.y / CELL); cur.sobre = true; }
cv.addEventListener('pointerdown', e => {
  if (!M) return; cv.setPointerCapture(e.pointerId); actualizarCursor(e);
  if (e.button === 1 || e.button === 2 || espacio || S.tool === 'mano') { drag = { pan: true, sx: e.clientX, sy: e.clientY, cx: cam.x, cy: cam.y }; cv.style.cursor = 'grabbing'; return; }
  if (e.altKey) { cuentagotas(); return; }
  const t = S.tool;
  if (t === 'pincel' || t === 'attr') {
    drag = { paint: true, last: { cx: cur.cx, cy: cur.cy } };
    const fn = (x, y) => t === 'pincel' ? setCelda(x, y, S.ts, null) : setCelda(x, y, null, S.attr);
    if (e.shiftKey && S.ultimo) linea(S.ultimo, cur, (x, y) => pintarDisco(x, y, fn)); else pintarDisco(cur.cx, cur.cy, fn);
    S.ultimo = { cx: cur.cx, cy: cur.cy };
  } else if (t === 'rect') drag = { a: { cx: cur.cx, cy: cur.cy } };
  else if (t === 'cubo') rellenar(cur.cx, cur.cy, S.cuboModo);
  else if (t === 'cuentagotas') cuentagotas(true);
  else if (t === 'objeto') colocarObjeto(e);
  else if (t === 'sel') iniciarSeleccion(e);
  else if (t === 'zona' || t === 'ruta') iniciarForma(e);
  else if (t === 'camp') iniciarCamp(e);
  else if (t === 'ao') iniciarAO(e);
  else if (t === 'borrar') { drag = { borrar: true }; borrarEn(cur.x, cur.y); }
  redraw();
});
cv.addEventListener('pointermove', e => {
  if (!M) return; actualizarCursor(e);
  if (drag && drag.pan) { cam.x = drag.cx - (e.clientX - drag.sx) / cam.z; cam.y = drag.cy - (e.clientY - drag.sy) / cam.z; redraw(); return; }
  if (drag && drag.paint) {
    const fn = (x, y) => S.tool === 'pincel' ? setCelda(x, y, S.ts, null) : setCelda(x, y, null, S.attr);
    linea(drag.last, cur, (x, y) => pintarDisco(x, y, fn)); drag.last = { cx: cur.cx, cy: cur.cy };
  } else if (drag && drag.borrar) borrarEn(cur.x, cur.y);
  else if (drag && drag.objDrag) {
    const dx = cur.x - drag.px, dy = cur.y - drag.py; if (Math.abs(dx) + Math.abs(dy) >= 1) { moverObjs([...S.sel], Math.round(dx), Math.round(dy), false); drag.tot.x += Math.round(dx); drag.tot.y += Math.round(dy); drag.px += Math.round(dx); drag.py += Math.round(dy); }
  } else if (drag && drag.box) { drag.box.x1 = cur.x; drag.box.y1 = cur.y; }
  else if (drag && drag.vert) { const p = drag.vert.s.puntos[drag.vert.i]; p[0] = Math.round(cur.x); p[1] = Math.round(cur.y); }
  else if (drag && drag.scatter) { scatter(e); }
  else if (drag && drag.ao) { const a = drag.ao; a.cx = clamp(Math.floor(cur.x / CELL), 0, M.w - 1); a.cy = clamp(Math.floor(cur.y / CELL), 0, M.h - 1); }
  else if (drag && drag.camp) { const c = drag.camp; c.x = Math.floor(cur.x / CELL) + .5; c.y = Math.floor(cur.y / CELL) + .5; }
  tip(e); redraw();
});
cv.addEventListener('pointerup', e => {
  if (!M) return; actualizarCursor(e);
  if (drag && drag.pan) { cv.style.cursor = 'crosshair'; drag = null; return; }
  if (drag && drag.paint) { cerrarTrazo(); drag = null; }
  else if (drag && drag.a && S.tool === 'rect') {
    const [x0, x1] = [Math.min(drag.a.cx, cur.cx), Math.max(drag.a.cx, cur.cx)], [y0, y1] = [Math.min(drag.a.cy, cur.cy), Math.max(drag.a.cy, cur.cy)];
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) S.rectModo === 'terreno' ? setCelda(x, y, S.ts, null) : setCelda(x, y, null, S.attr);
    cerrarTrazo(); drag = null; msg('Rectangulo ' + (x1 - x0 + 1) + '×' + (y1 - y0 + 1));
  } else if (drag && drag.borrar) { drag = null; }
  else if (drag && drag.objDrag) { const t = drag.tot, lista = [...S.sel]; if (t.x || t.y) push({ undo() { lista.forEach(o => { o.x -= t.x; o.y -= t.y; }); }, redo() { lista.forEach(o => { o.x += t.x; o.y += t.y; }); } }); drag = null; panelRefreshLight(); }
  else if (drag && drag.box) {
    const b = drag.box, x0 = Math.min(b.x0, b.x1), x1 = Math.max(b.x0, b.x1), y0 = Math.min(b.y0, b.y1), y1 = Math.max(b.y0, b.y1);
    if (!b.add) S.sel.clear();
    if (x1 - x0 < 3 && y1 - y0 < 3) { const o = objetoEn(b.x0, b.y0); if (o) { if (b.add && S.sel.has(o)) S.sel.delete(o); else S.sel.add(o); } }
    else for (const o of M.objs) if (o.x >= x0 && o.x <= x1 && o.y >= y0 && o.y <= y1) S.sel.add(o);
    drag = null; panelRefreshLight(); setTab('sel', true);
  } else if (drag && drag.vert) { const v = drag.vert, ant = drag.ant; const nuevo = v.s.puntos[v.i].slice(); if (ant[0] !== nuevo[0] || ant[1] !== nuevo[1]) push({ undo() { v.s.puntos[v.i][0] = ant[0]; v.s.puntos[v.i][1] = ant[1]; }, redo() { v.s.puntos[v.i][0] = nuevo[0]; v.s.puntos[v.i][1] = nuevo[1]; } }); drag = null; }
  else if (drag && drag.scatter) { cerrarScatter(); drag = null; }
  else if (drag && drag.ao) { const a = drag.ao, o = drag.ant, n = { cx: a.cx, cy: a.cy }; if (o.cx !== n.cx || o.cy !== n.cy) { M.aoDirty = true; push({ undo() { a.cx = o.cx; a.cy = o.cy; }, redo() { a.cx = n.cx; a.cy = n.cy; } }); } drag = null; panelRefreshLight(); }
  else if (drag && drag.camp) { const c = drag.camp, a = drag.ant, n = { x: c.x, y: c.y }; if (a.x !== n.x || a.y !== n.y) push({ undo() { c.x = a.x; c.y = a.y; }, redo() { c.x = n.x; c.y = n.y; } }); drag = null; panelRefreshLight(); }
  redraw();
});
cv.addEventListener('pointerleave', () => { cur.sobre = false; $('#tip').style.display = 'none'; redraw(); });
cv.addEventListener('dblclick', e => { if (S.tool === 'zona' || S.tool === 'ruta') terminarForma(); });

function iniciarCamp(e) {
  const c = campCerca(cur.x, cur.y);
  if (c) { S.campSel = c; drag = { camp: c, ant: { x: c.x, y: c.y } }; setTab('camps'); return; }
  if (!inB(cur.cx, cur.cy)) return; const n = { ...S.campTpl, x: cur.cx + .5, y: cur.cy + .5 }; M.camps.push(n); S.campSel = n;
  push({ undo() { const i = M.camps.indexOf(n); if (i >= 0) M.camps.splice(i, 1); if (S.campSel === n) S.campSel = null; }, redo() { M.camps.push(n); } }); panelRefresh();
}
function borrarCamp(c) { const i = M.camps.indexOf(c); if (i < 0) return; M.camps.splice(i, 1); S.campSel = null; push({ undo() { M.camps.splice(i, 0, c); }, redo() { const k = M.camps.indexOf(c); if (k >= 0) M.camps.splice(k, 1); } }); panelRefresh(); redraw(); }
function cuentagotas(volver) {
  if (!inB(cur.cx, cur.cy)) return; const i = (cur.cy * M.w + cur.cx) * 6; S.ts = M.cel[i]; S.attr = M.cel[i + 1]; if (volver && S.prev !== 'cuentagotas') setTool(S.prev); panelRefresh();
  msg('Tomado: tileset ' + S.ts + ', atributo ' + S.attr);
}
function colocarObjeto(e) {
  if (S.objId == null) { msg('Elige un objeto en la pestana Objetos', 'av'); return; }
  if (S.esparcir) { drag = { scatter: true, nuevos: [], ultimo: null }; scatter(e); return; }
  const p = snapPt(cur.x, cur.y); addObjs([nuevoObj(S.objId, p.x, p.y)]);
}
function scatter(e) {
  const d = drag; if (d.ultimo && Math.hypot(cur.x - d.ultimo.x, cur.y - d.ultimo.y) < S.radio * 0.6) return; d.ultimo = { x: cur.x, y: cur.y };
  for (let k = 0; k < S.densidad; k++) {
    const a = Math.random() * 6.283, r = Math.sqrt(Math.random()) * S.radio, p = snapPt(cur.x + Math.cos(a) * r, cur.y + Math.sin(a) * r);
    if (!inB(Math.floor(p.x / CELL), Math.floor(p.y / CELL))) continue; const o = nuevoObj(S.objId, p.x, p.y); d.nuevos.push(o); M.objs.push(o);
  }
}
function cerrarScatter() { const l = drag.nuevos; if (!l.length) return; push({ undo() { l.forEach(o => { const i = M.objs.indexOf(o); if (i >= 0) M.objs.splice(i, 1); S.sel.delete(o); }); }, redo() { M.objs.push(...l); } }); msg(l.length + ' objetos colocados'); }
function iniciarSeleccion(e) {
  const o = objetoEn(cur.x, cur.y);
  if (o && S.sel.has(o) && !e.shiftKey) { drag = { objDrag: true, px: cur.x, py: cur.y, tot: { x: 0, y: 0 } }; return; }
  if (o && !e.shiftKey && !S.sel.has(o)) { S.sel.clear(); S.sel.add(o); drag = { objDrag: true, px: cur.x, py: cur.y, tot: { x: 0, y: 0 } }; panelRefreshLight(); setTab('sel', true); return; }
  drag = { box: { x0: cur.x, y0: cur.y, x1: cur.x, y1: cur.y, add: e.shiftKey } };
}
function iniciarForma(e) {
  const v = puntoCerca(cur.x, cur.y);
  if (v && !drag) { if (e.shiftKey) { eliminarVertice(v); return; } drag = { vert: v, ant: v.s.puntos[v.i].slice() }; return; }
  if (!drag || !drag.pts) drag = { pts: [] }; drag.pts.push([cur.x, cur.y]);
}
function eliminarVertice(v) {
  const p = v.s.puntos.splice(v.i, 1)[0]; push({ undo() { v.s.puntos.splice(v.i, 0, p); }, redo() { v.s.puntos.splice(v.i, 1); } }); redraw();
}
function borrarEn(wx, wy) {
  const r = S.size * CELL / 2, quita = M.objs.filter(o => Math.hypot(o.x - wx, o.y - wy) <= r); if (quita.length) delObjs(quita);
}
function tip(e) {
  const t = $('#tip'); const w = aMundo(e); let txt = '';
  if (S.capas.objetos) { const o = objetoEn(w.x, w.y); if (o) { const d = OBJDEFS[o.id]; txt = `objeto ${o.id}` + (d ? ' · ' + d[0] + ' · ' + d[1] : ''); } }
  if (!txt && (S.tool === 'zona' || S.tool === 'ruta')) { const v = puntoCerca(w.x, w.y); if (v) txt = (v.tipo === 'zona' ? 'zona/punto ' : 'ruta ') + v.s.id + ' vertice ' + (v.i + 1) + ' (Shift+clic: quitar)'; }
  if (txt) { const r = $('#cv').getBoundingClientRect(); t.style.display = 'block'; t.style.left = (e.clientX - r.left + 14) + 'px'; t.style.top = (e.clientY - r.top + 14) + 'px'; t.textContent = txt; } else t.style.display = 'none';
}
mini.addEventListener('pointerdown', e => {
  if (!M) return; const go = ev => { const r = mini.getBoundingClientRect(), k = mini._k; if (!k) return; const mx = (ev.clientX - r.left) * mini.width / r.width, my = (ev.clientY - r.top) * mini.height / r.height; const wx = (mx - k.ox) / k.k * CELL, wy = (my - k.oy) / k.k * CELL; const vw = cv.width / (cam.z * devicePixelRatio), vh = cv.height / (cam.z * devicePixelRatio); cam.x = wx - vw / 2; cam.y = wy - vh / 2; redraw(); };
  go(e); mini.setPointerCapture(e.pointerId); mini.onpointermove = go; mini.onpointerup = () => { mini.onpointermove = null; };
});
addEventListener('keydown', e => {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
  const k = e.key.toLowerCase();
  if (k === ' ') { espacio = true; cv.style.cursor = 'grab'; e.preventDefault(); return; }
  if (e.ctrlKey && k === 'z') { e.preventDefault(); undo(); return; } if (e.ctrlKey && (k === 'y' || (e.shiftKey && k === 'z'))) { e.preventDefault(); redo(); return; }
  if (e.ctrlKey && k === 's') { e.preventDefault(); guardarProyecto(); return; }
  if (e.ctrlKey && k === 'c') { portapapeles = [...S.sel].map(o => ({ ...o })); msg(portapapeles.length + ' objetos copiados'); return; }
  if (e.ctrlKey && k === 'v') { if (!M || !portapapeles.length) return; const nuevos = portapapeles.map(o => ({ ...o, x: o.x + 32, y: o.y + 32 })); portapapeles = nuevos.map(o => ({ ...o })); addObjs(nuevos); S.sel = new Set(nuevos); panelRefreshLight(); return; }
  if (e.ctrlKey && k === 'a') { e.preventDefault(); S.sel = new Set(M.objs); panelRefreshLight(); redraw(); return; }
  if (k === 'delete' || k === 'backspace') { if (S.tool === 'ao' && S.ao.sel) { borrarAO(S.ao.sel); return; } if (S.campSel) { borrarCamp(S.campSel); return; } if (S.sel.size) delObjs([...S.sel]); return; }
  if (k === 'enter') { terminarForma(); return; } if (k === 'escape') { drag = null; S.sel.clear(); panelRefreshLight(); redraw(); return; }
  if (S.sel.size && k.startsWith('arrow')) { const s = e.ctrlKey ? 32 : e.shiftKey ? 8 : 1, d = { arrowleft: [-s, 0], arrowright: [s, 0], arrowup: [0, -s], arrowdown: [0, s] }[k]; moverObjs([...S.sel], d[0], d[1]); e.preventDefault(); panelRefreshLight(); return; }
  const map = { h: 'mano', b: 'pincel', t: 'attr', r: 'rect', g: 'cubo', i: 'cuentagotas', o: 'objeto', v: 'sel', z: 'zona', x: 'ruta', c: 'camp', n: 'ao', e: 'borrar' };
  if (map[k] && !e.ctrlKey) { setTool(map[k]); return; }
  if (k === '[') { S.size = clamp(S.size - 1, 1, 40); panelRefreshLight(); redraw(); } if (k === ']') { S.size = clamp(S.size + 1, 1, 40); panelRefreshLight(); redraw(); }
  if (k === 'f' && S.sel.size) { const l = [...S.sel]; l.forEach(o => modObj(o, { e: o.e === 2 ? 0 : 2 })); panelRefreshLight(); }
});
addEventListener('keyup', e => { if (e.key === ' ') { espacio = false; cv.style.cursor = 'crosshair'; } });

// ------------------------------------------------------------------------------------------------ herramientas y pestanas
const TOOLS = [['mano', '✋', 'Mano (H)'], ['pincel', '🖌', 'Terreno (B)'], ['attr', '⛔', 'Atributo/colision (T)'], ['rect', '▭', 'Rectangulo (R)'], ['cubo', '🪣', 'Relleno (G)'], ['cuentagotas', '💧', 'Cuentagotas (I, o Alt+clic)'],
  ['objeto', '🌲', 'Colocar objeto (O)'], ['sel', '⬚', 'Seleccionar/mover (V)'], ['zona', '⬡', 'Zonas, puntos y salidas (Z)'], ['ruta', '〰', 'Rutas (X)'], ['camp', '🐺', 'Criaturas (C)'], ['ao', '🧙', 'NPC y monstruos AO (N)'], ['borrar', '🗑', 'Borrar objetos (E)']];
function buildTools() {
  const t = $('#tools'); t.innerHTML = '';
  for (const [id, ic, nom] of TOOLS) { const b = el('button', { className: 'btn' + (S.tool === id ? ' on' : ''), title: nom }, `<span>${ic}</span>${nom.split(' (')[0].split('/')[0]}`); b.dataset.t = id; b.onclick = () => setTool(id); t.appendChild(b); }
}
function setTool(id) { if (S.tool !== id) { S.prev = S.tool; S.tool = id; } drag = null; buildTools(); const t = { pincel: 'paleta', attr: 'atributos', objeto: 'objetos', sel: 'sel', zona: 'zonas', ruta: 'rutas', camp: 'camps', ao: 'ao' }[id]; if (t) setTab(t, true); redraw(); }
const TABS = [['paleta', 'Terreno'], ['atributos', 'Colision'], ['objetos', 'Objetos'], ['sel', 'Seleccion'], ['zonas', 'Zonas'], ['rutas', 'Rutas'], ['camps', 'Criaturas'], ['ao', 'NPC/Monstruos AO'], ['eventos', 'Eventos'], ['dialogos', 'Dialogos'], ['capas', 'Capas'], ['mapa', 'Mapa'], ['validar', 'Validar']];
function buildTabs() { const t = $('#tabs'); t.innerHTML = ''; for (const [id, nom] of TABS) { const b = el('button', { className: 'btn' + (S.tab === id ? ' on' : '') }, nom); b.onclick = () => setTab(id); b.dataset.tab = id; t.appendChild(b); } }
function setTab(id, quiet) { S.tab = id; document.querySelectorAll('#tabs .btn').forEach(b => b.classList.toggle('on', b.dataset.tab === id)); panelRefresh(); }
function panelRefreshLight() { if (['sel', 'mapa', 'zonas', 'rutas', 'camps', 'ao'].includes(S.tab)) panelRefresh(); }

function sliderFila(txt, id, min, max, val, onch) { const r = el('div', { className: 'row' }, `<span class="mu">${txt}</span>`); const i = el('input', { type: 'range', min, max, value: val }); const v = el('span', {}, String(val)); i.oninput = () => { v.textContent = i.value; onch(+i.value); }; r.append(i, v); return r; }

function panelRefresh() {
  const p = $('#panel'); p.innerHTML = '';
  const f = { paleta: tabPaleta, atributos: tabAtributos, objetos: tabObjetos, sel: tabSel, zonas: tabZonas, rutas: tabRutas, camps: tabCamps, ao: tabAO, eventos: tabEventos, dialogos: tabDialogos, capas: tabCapas, mapa: tabMapa, validar: tabValidar }[S.tab];
  if (!M && S.tab !== 'capas') { p.innerHTML = '<div class="mu">Abre un mapa primero.</div>'; return; }
  f(p);
}
function filaTamano(p, tit) {
  p.append(el('h4', {}, tit || 'Pincel'));
  p.append(sliderFila('tamano', 'sz', 1, 40, S.size, v => { S.size = v; redraw(); }));
  const r = el('div', { className: 'row' }, '<span class="mu">forma</span>'); for (const [id, n] of [['cuadro', 'Cuadrado'], ['circulo', 'Circulo']]) { const b = el('button', { className: 'btn sm' + (S.forma === id ? ' on' : '') }, n); b.onclick = () => { S.forma = id; panelRefresh(); redraw(); }; r.append(b); } p.append(r);
}
function tabPaleta(p) {
  const l = Object.values(TS).sort((a, b) => a.n - b.n);
  p.append(el('div', { className: 'mu' }, 'Elige el tileset (la textura que se pinta). Pincel (B), rectangulo (R), relleno (G). Shift+arrastre = linea recta.'));
  filaTamano(p, 'Pincel de terreno');
  const rr = el('div', { className: 'row' }, '<span class="mu">rectangulo/relleno pintan</span>'); for (const [id, n] of [['terreno', 'terreno'], ['atributo', 'atributo']]) { const b = el('button', { className: 'btn sm' + (S.rectModo === id ? ' on' : '') }, n); b.onclick = () => { S.rectModo = S.cuboModo = id; panelRefresh(); }; rr.append(b); } p.append(rr);
  const clases = [...new Set(l.map(t => t.clase))]; const fr = el('div', { className: 'row' }); const sel = el('select'); sel.append(el('option', { value: '' }, 'todas las clases')); clases.forEach(c => sel.append(el('option', { value: c }, c))); sel.value = S._clase || ''; sel.onchange = () => { S._clase = sel.value; panelRefresh(); }; fr.append(sel);
  const usados = el('label', {}, '<input type="checkbox"> solo los de este mapa'); const ck = usados.querySelector('input'); ck.checked = !!S._soloUsados; ck.onchange = () => { S._soloUsados = ck.checked; panelRefresh(); }; fr.append(usados); p.append(fr);
  const set = new Set(M.ts); const g = el('div', { className: 'grid' });
  for (const t of l) {
    if (S._clase && t.clase !== S._clase) continue; if (S._soloUsados && !set.has(t.n)) continue;
    const d = el('div', { className: 'sw' + (S.ts === t.n ? ' on' : ''), title: `tileset ${t.n} (0x${t.n.toString(16)}) · ${t.clase}` }, `<span>${t.n}</span>`);
    d.style.backgroundImage = `url(/api/ts?n=${t.n})`; d.style.backgroundSize = '200% 200%'; d.style.backgroundPosition = '50% 50%'; d.onclick = () => { S.ts = t.n; cargarTex(t.n); if (S.tool !== 'rect' && S.tool !== 'cubo') setTool('pincel'); panelRefresh(); }; g.append(d);
  }
  p.append(g);
  const sc = TS[S.ts]; p.append(el('div', { className: 'mu', style: 'margin-top:8px' }, `Seleccionado: tileset ${S.ts} · ${sc ? sc.clase : '?'} (clase por color medio: agua profunda bloquea en Dos Coronas).`));
}
function tabAtributos(p) {
  p.append(el('div', { className: 'mu' }, 'El atributo es el 2.º byte de cada celda. En Dos Coronas cualquier valor distinto de 0 cierra el paso. Pincel (T), rectangulo y relleno en modo atributo.'));
  filaTamano(p, 'Pincel de atributo');
  const rr = el('div', { className: 'row' }, '<span class="mu">rectangulo/relleno pintan</span>'); for (const [id, n] of [['terreno', 'terreno'], ['atributo', 'atributo']]) { const b = el('button', { className: 'btn sm' + (S.rectModo === id ? ' on' : '') }, n); b.onclick = () => { S.rectModo = S.cuboModo = id; panelRefresh(); }; rr.append(b); } p.append(rr);
  p.append(el('h4', {}, 'Valor a pintar'));
  for (const v of [0, 1, 2, 3, 10]) { const d = el('div', { className: 'att' + (S.attr === v ? ' on' : '') }, `<i style="background:${attColor(v) || 'transparent'};border:1px solid #555"></i><b>${v}</b> <span class="mu">${ATT_N[v]}</span>`); d.onclick = () => { S.attr = v; if (S.tool !== 'rect' && S.tool !== 'cubo') setTool('attr'); panelRefresh(); }; p.append(d); }
  const r = el('div', { className: 'row' }, '<span class="mu">otro valor</span>'); const i = el('input', { type: 'number', min: 0, max: 255, value: S.attr }); i.onchange = () => { S.attr = clamp(+i.value | 0, 0, 255); panelRefresh(); }; r.append(i); p.append(r);
  p.append(el('h4', {}, 'Herramientas de colision'));
  const b1 = el('button', { className: 'btn' }, 'Marcar obstaculo bajo los objetos que bloquean'); b1.onclick = () => marcarObjetos(); p.append(b1);
  const b2 = el('button', { className: 'btn', style: 'margin-top:4px' }, 'Agua profunda → atributo 2'); b2.onclick = () => aguaProfunda(); p.append(b2);
  const b3 = el('button', { className: 'btn', style: 'margin-top:4px' }, 'Bordes del mapa → atributo 3'); b3.onclick = () => bordes(); p.append(b3);
  p.append(el('div', { className: 'mu', style: 'margin-top:8px' }, 'Capa "Transitable (reglas de Dos Coronas)" en la pestana Capas: verde = zona principal, amarillo = isla aislada, rojo = bloqueado.'));
}
function marcarObjetos() {
  let n = 0; for (const o of M.objs) { const m = OBJMETA[o.id]; if (!m || m === 'pendiente' || !m.b) continue; const k = m.huella || 1, d0 = Math.floor((k - 1) / 2), cx = Math.floor(o.x / CELL), cy = Math.floor(o.y / CELL); for (let y = cy - d0; y < cy - d0 + k; y++) for (let x = cx - d0; x < cx - d0 + k; x++) { if (inB(x, y) && M.cel[(y * M.w + x) * 6 + 1] === 0) { setCelda(x, y, null, 1); n++; } } }
  cerrarTrazo(); msg(n + ' celdas marcadas como obstaculo'); }
function aguaProfunda() { let n = 0; for (let y = 0; y < M.h; y++) for (let x = 0; x < M.w; x++) { const t = TS[M.cel[(y * M.w + x) * 6]]; if (t && t.clase === 'agua' && M.cel[(y * M.w + x) * 6 + 1] === 0) { setCelda(x, y, null, 2); n++; } } cerrarTrazo(); msg(n + ' celdas de agua profunda marcadas'); }
function bordes() { let n = 0; for (let x = 0; x < M.w; x++) for (const y of [0, M.h - 1]) { setCelda(x, y, null, 3); n++; } for (let y = 0; y < M.h; y++) for (const x of [0, M.w - 1]) { setCelda(x, y, null, 3); n++; } cerrarTrazo(); msg('Borde marcado'); }

function tabObjetos(p) {
  const F = S.filtroObj;
  p.append(el('div', { className: 'mu' }, 'Elige un objeto y haz clic en el mapa (O). Activa "esparcir" para pintar bosques y adornos.'));
  const r1 = el('div', { className: 'row' }); const q = el('input', { type: 'text', placeholder: 'buscar nombre o id…', value: F.q, style: 'flex:1' }); q.onchange = () => { F.q = q.value; F.pag = 1; panelRefresh(); }; r1.append(q); p.append(r1);
  const r2 = el('div', { className: 'row' }); const fu = el('select'); for (const [v, n] of [['mapobj', 'objetos de mapa'], ['npc', 'NPC'], ['server', 'marcas del servidor'], ['common', 'comunes'], ['house', 'casas'], ['', 'todas las fuentes']]) fu.append(el('option', { value: v }, n)); fu.value = F.fuente; fu.onchange = () => { F.fuente = fu.value; F.pag = 1; panelRefresh(); }; r2.append(fu);
  const cs = el('label', {}, '<input type="checkbox"> solo con sprite'); cs.querySelector('input').checked = F.soloSprite; cs.querySelector('input').onchange = ev => { F.soloSprite = ev.target.checked; F.pag = 1; panelRefresh(); }; r2.append(cs);
  const cu = el('label', {}, '<input type="checkbox"> usados en este mapa'); cu.querySelector('input').checked = F.usados; cu.querySelector('input').onchange = ev => { F.usados = ev.target.checked; F.pag = 1; panelRefresh(); }; r2.append(cu); p.append(r2);
  const r3 = el('div', { className: 'row' }); const ce = el('label', {}, '<input type="checkbox"> esparcir'); ce.querySelector('input').checked = S.esparcir; ce.querySelector('input').onchange = ev => { S.esparcir = ev.target.checked; panelRefresh(); }; r3.append(ce);
  const sn = el('select'); for (const [v, n] of [['libre', 'sin ajuste'], ['mitad', 'ajuste a 16 px'], ['celda', 'base de la celda']]) sn.append(el('option', { value: v }, n)); sn.value = S.snap; sn.onchange = () => { S.snap = sn.value; }; r3.append(sn);
  const es = el('label', {}, '<input type="checkbox"> espejo'); es.querySelector('input').checked = S.espejo === 2; es.querySelector('input').onchange = ev => { S.espejo = ev.target.checked ? 2 : 0; }; r3.append(es); p.append(r3);
  if (S.esparcir) { p.append(sliderFila('cantidad por trazo', 'd', 1, 20, S.densidad, v => S.densidad = v)); p.append(sliderFila('radio px', 'r', 10, 300, S.radio, v => { S.radio = v; redraw(); })); }
  const usados = new Set(M.objs.map(o => o.id)); const qq = F.q.trim().toLowerCase();
  const l = Object.entries(OBJDEFS).filter(([id, d]) => (!F.fuente || d[2] === F.fuente) && (!F.soloSprite || d[4]) && (!F.usados || usados.has(+id)) && (!qq || d[0].toLowerCase().includes(qq) || id.includes(qq) || d[1].toLowerCase().includes(qq))).sort((a, b) => a[0] - b[0]);
  const por = 60, total = l.length, pag = clamp(F.pag, 1, Math.max(1, Math.ceil(total / por)));
  p.append(el('div', { className: 'mu' }, `${total} objetos`));
  const g = el('div', { className: 'olist' });
  for (const [id, d] of l.slice((pag - 1) * por, pag * por)) {
    const it = el('div', { className: 'oit' + (S.objId === +id ? ' on' : ''), title: `${id} · ${d[0]} · ${d[1]}${d[3] ? ' · bloquea' : ''}` }, `<div class="th">${d[4] ? `<img loading="lazy" src="/api/obj?id=${id}">` : '<span class="mu">sin sprite</span>'}</div><div class="nm">${id} ${d[0]}</div>`);
    it.onclick = () => { S.objId = +id; cargarImgObj(+id); metaObj(+id); setTool('objeto'); panelRefresh(); }; g.append(it);
  }
  p.append(g);
  if (total > por) { const nav = el('div', { className: 'row' }); const a = el('button', { className: 'btn sm' }, '◀'), b = el('button', { className: 'btn sm' }, '▶'); a.onclick = () => { F.pag = Math.max(1, pag - 1); panelRefresh(); }; b.onclick = () => { F.pag = Math.min(Math.ceil(total / por), pag + 1); panelRefresh(); }; nav.append(a, el('span', { className: 'mu' }, `${pag}/${Math.ceil(total / por)}`), b); p.append(nav); }
}
function tabSel(p) {
  p.append(el('div', { className: 'mu' }, 'V: clic o arrastre para seleccionar (Shift suma), arrastra para mover, flechas para ajustar (Shift ×8, Ctrl ×32), Supr borra, Ctrl+C/V copia, F espeja.'));
  const l = [...S.sel]; p.append(el('h4', {}, l.length + ' seleccionados'));
  if (!l.length) { const b = el('button', { className: 'btn' }, 'Seleccionar todos'); b.onclick = () => { S.sel = new Set(M.objs); panelRefresh(); redraw(); }; p.append(b); return; }
  const cnt = {}; l.forEach(o => cnt[o.id] = (cnt[o.id] || 0) + 1);
  p.append(el('div', {}, Object.entries(cnt).slice(0, 12).map(([id, n]) => `${n}× ${id} ${OBJDEFS[id] ? OBJDEFS[id][0] : ''}`).join('<br>')));
  const mk = (txt, fn) => { const b = el('button', { className: 'btn sm' }, txt); b.onclick = fn; return b; };
  const r = el('div', { className: 'row' }); r.append(mk('Borrar', () => delObjs(l)), mk('Duplicar', () => { const n = l.map(o => ({ ...o, x: o.x + 32, y: o.y + 32 })); addObjs(n); S.sel = new Set(n); panelRefresh(); }), mk('Espejar', () => { l.forEach(o => modObj(o, { e: o.e === 2 ? 0 : 2 })); panelRefresh(); }), mk('Usar este objeto', () => { S.objId = l[0].id; setTool('objeto'); })); p.append(r);
  if (l.length === 1) {
    const o = l[0], campo = (txt, k) => { const f = el('div', { className: 'row' }, `<span class="mu" style="width:60px">${txt}</span>`); const i = el('input', { type: 'number', value: o[k] }); i.onchange = () => { modObj(o, { [k]: +i.value | 0 }); }; f.append(i); return f; };
    const d = OBJDEFS[o.id]; p.append(el('div', { className: 'mu' }, `${d ? d[0] + ' · ' + d[1] + ' · ' + d[2] : 'id desconocido'}`));
    p.append(campo('id', 'id'), campo('x px', 'x'), campo('y px', 'y'), campo('a', 'a'), campo('espejo', 'e'), campo('c', 'c'));
    if (typeof EVU !== 'undefined') EVU.campoEvento(p, o);
    p.append(el('div', { className: 'mu' }, `celda ${Math.floor(o.x / CELL)},${Math.floor(o.y / CELL)} · los campos a/espejo/c son del formato original (0/50/80/400, 0/1/2, 192 = transparencia)`));
  } else {
    const r2 = el('div', { className: 'row' }); const ci = el('input', { type: 'number', placeholder: 'nuevo id' }); const b = mk('Cambiar id', () => { if (ci.value) { const v = +ci.value | 0; l.forEach(o => modObj(o, { id: v })); precargarObjetos(); panelRefresh(); } }); r2.append(ci, b); p.append(r2);
  }
}
function listaForma(p, arr, nombre, etq) {
  const t = el('table', { className: 'tbl' }, `<tr><th>id</th><th>${etq}</th><th></th></tr>`);
  arr.forEach((s, i) => { const tr = el('tr', {}, `<td>${s.id}</td><td>${s.puntos.length} puntos</td><td></td>`); tr.onclick = () => { const q = s.puntos[0]; if (q) { cam.x = q[0] - cv.width / cam.z / devicePixelRatio / 2; cam.y = q[1] - cv.height / cam.z / devicePixelRatio / 2; redraw(); } }; const b = el('button', { className: 'btn sm' }, '✕'); b.onclick = ev => { ev.stopPropagation(); arr.splice(i, 1); push({ undo() { arr.splice(i, 0, s); }, redo() { arr.splice(arr.indexOf(s), 1); } }); panelRefresh(); redraw(); }; tr.lastChild.append(b); t.append(tr); });
  p.append(t);
}
function tabZonas(p) {
  p.append(el('div', { className: 'mu' }, 'Z: clic = nuevo vertice, doble clic o Enter = terminar. Arrastra un vertice para moverlo (Shift+clic lo quita). En FAO: id 1-2 = salidas (triangulos del borde), 31-44 = puntos sueltos, 71-83 = zonas.'));
  const r = el('div', { className: 'row' }, '<span class="mu">id a crear</span>'); const i = el('input', { type: 'number', value: S.zonaId }); i.onchange = () => { S.zonaId = +i.value | 0; }; r.append(i);
  for (const [v, n] of [[1, 'salida 1'], [2, 'salida 2'], [31, 'punto'], [71, 'zona']]) { const b = el('button', { className: 'btn sm' }, n); b.onclick = () => { S.zonaId = v; setTool('zona'); panelRefresh(); }; r.append(b); } p.append(r);
  const b = el('button', { className: 'btn' + (S.tool === 'zona' ? ' on' : '') }, 'Dibujar (Z)'); b.onclick = () => setTool('zona'); p.append(b);
  listaForma(p, M.puntos, 'zona', 'vertices');
}
function tabCamps(p) {
  p.append(el('div', { className: 'mu' }, 'C: clic = nuevo campamento con la plantilla; clic sobre uno = seleccionarlo y arrastrarlo; Supr lo borra. Un campamento hace aparecer "cantidad" criaturas del tipo elegido en un radio (en casillas). Se guardan aparte (NOMBRE_campamentos.lua) porque el .mpc no trae criaturas.'));
  const sel = S.campSel, t = sel || S.campTpl;
  p.append(el('h4', {}, sel ? 'Campamento seleccionado' : 'Plantilla para los nuevos'));
  for (const k of ['monstruo', 'cantidad', 'radio']) { const r = el('div', { className: 'row' }, `<span class="mu" style="width:70px">${k}</span>`); const i = el('input', { type: k === 'monstruo' ? 'text' : 'number', value: t[k] ?? '' }); i.onchange = () => { const v = k === 'monstruo' ? i.value : +i.value; if (sel) { const a = sel[k]; sel[k] = v; push({ undo() { sel[k] = a; }, redo() { sel[k] = v; } }); } else t[k] = v; redraw(); }; r.append(i); p.append(r); }
  const jf = el('label', { className: 'row' }, '<input type="checkbox"> jefe / elite'); jf.querySelector('input').checked = !!t.jefe; jf.querySelector('input').onchange = ev => { if (ev.target.checked) t.jefe = true; else delete t.jefe; redraw(); }; p.append(jf);
  if (sel) { const b = el('button', { className: 'btn sm' }, 'Borrar campamento'); b.onclick = () => borrarCamp(sel); const b2 = el('button', { className: 'btn sm' }, 'Deseleccionar'); b2.onclick = () => { S.campSel = null; panelRefresh(); redraw(); }; const r = el('div', { className: 'row' }); r.append(b, b2); p.append(r); p.append(el('div', { className: 'mu' }, `en la casilla ${Math.floor(sel.x)},${Math.floor(sel.y)}`)); }
  p.append(el('h4', {}, 'Criaturas del juego (monstruos.xml)'));
  if (!MONS) { p.append(el('div', { className: 'mu' }, 'Cargando criaturas…')); api('/api/dc/monstruos').then(l => { MONS = l; if (S.tab === 'camps') panelRefresh(); }).catch(() => { MONS = []; }); }
  else if (!MONS.length) p.append(el('div', { className: 'mal' }, 'No encuentro monstruos.xml de Dos Coronas (define DOS_CORONAS). Puedes escribir el id a mano arriba.'));
  else {
    const q = el('input', { type: 'text', placeholder: 'buscar criatura, bioma o nivel…', value: S.qMons, style: 'width:100%' }); p.append(q);
    const caja = el('div', { className: 'oit', style: 'max-height:280px;overflow:auto;margin-top:6px;text-align:left;cursor:default' }); p.append(caja);
    const pintar = () => { caja.innerHTML = ''; const s = S.qMons.toLowerCase(); MONS.filter(m => !s || (m.id + ' ' + m.nombre + ' ' + m.bioma + ' nivel ' + m.nivel + (m.jefe ? ' jefe' : '')).toLowerCase().includes(s)).sort((a, b) => a.nivel - b.nivel).forEach(m => { const d = el('div', { className: 'att' + (t.monstruo === m.id ? ' on' : ''), title: m.id + ' · ' + m.bioma }, `<img src="/api/dc/mob?id=${m.id}" style="width:40px;height:40px;object-fit:contain;vertical-align:middle;margin-right:6px" onerror="this.style.visibility='hidden'"><b>${m.nombre}</b> <span class="mu">Nv ${m.nivel}${m.jefe ? ' ★' : ''} · ${m.bioma}</span>`); d.onclick = () => { if (sel) { const a = sel.monstruo, aj = sel.jefe; sel.monstruo = m.id; if (m.jefe) sel.jefe = true; else delete sel.jefe; push({ undo() { sel.monstruo = a; if (aj) sel.jefe = aj; else delete sel.jefe; }, redo() { sel.monstruo = m.id; if (m.jefe) sel.jefe = true; else delete sel.jefe; } }); } else { t.monstruo = m.id; if (m.jefe) t.jefe = true; else delete t.jefe; setTool('camp'); } panelRefresh(); redraw(); }; caja.append(d); }); };
    q.oninput = () => { S.qMons = q.value; pintar(); }; pintar();
  }
  p.append(el('h4', {}, 'Campamentos del mapa (' + M.camps.length + ')'));
  const tb = el('table', { className: 'tbl' }, '<tr><th>criatura</th><th>cant.</th><th>casilla</th><th></th></tr>');
  M.camps.forEach(c => { const tr = el('tr', {}, `<td>${c.monstruo || '?'}${c.jefe ? ' ★' : ''}</td><td>${c.cantidad || 1}</td><td>${Math.floor(c.x)},${Math.floor(c.y)}</td><td><button class="btn sm" title="Borrar este campamento">✕</button></td>`); tr.querySelector('button').onclick = ev => { ev.stopPropagation(); borrarCamp(c); }; tr.onclick = () => { S.campSel = c; cam.x = c.x * CELL - cv.width / cam.z / devicePixelRatio / 2; cam.y = c.y * CELL - cv.height / cam.z / devicePixelRatio / 2; panelRefresh(); redraw(); }; tb.append(tr); });
  p.append(tb);
}
function tabRutas(p) {
  p.append(el('div', { className: 'mu' }, 'X: clic = nuevo punto, doble clic o Enter = terminar. En FAO son rutas de patrulla de criaturas y PNJ (tipo 3 o 5).'));
  const r = el('div', { className: 'row' }, '<span class="mu">siguiente id</span>'); const i = el('input', { type: 'number', value: S.rutaId }); i.onchange = () => { S.rutaId = +i.value | 0; }; r.append(i);
  const t = el('select'); for (const v of [3, 5]) t.append(el('option', { value: v }, 'tipo ' + v)); t.value = S.rutaTipo; t.onchange = () => { S.rutaTipo = +t.value; }; r.append(t); p.append(r);
  const b = el('button', { className: 'btn' + (S.tool === 'ruta' ? ' on' : '') }, 'Dibujar (X)'); b.onclick = () => setTool('ruta'); p.append(b);
  listaForma(p, M.rutas, 'ruta', 'puntos');
}
function xmlEditor(p, clave, tit, nota, resumen) {
  p.append(el('div', { className: 'mu' }, nota));
  const ta = el('textarea', { className: 'big', value: M[clave], spellcheck: false }); p.append(ta);
  const r = el('div', { className: 'row' }); const b = el('button', { className: 'btn' }, 'Aplicar'); const st = el('span', { className: 'mu' });
  b.onclick = () => { const d = new DOMParser().parseFromString(ta.value, 'application/xml'); if (d.querySelector('parsererror')) { st.textContent = 'XML no valido'; st.className = 'mal'; return; } const antes = M[clave], nuevo = ta.value; if (antes !== nuevo) { M[clave] = nuevo; push({ undo() { M[clave] = antes; }, redo() { M[clave] = nuevo; } }); } st.textContent = 'aplicado'; st.className = 'ok'; panelRefresh(); };
  r.append(b, st); p.append(r);
  try { const d = new DOMParser().parseFromString(M[clave], 'application/xml'); p.append(el('h4', {}, 'Resumen')); p.append(el('div', {}, resumen(d))); } catch (e) { }
}
function tabEventos(p) {
  if (typeof EVU !== 'undefined') return EVU.tab(p, xmlEditor);
  xmlEditor(p, 'eventos', 'Eventos', 'Eventos del mapa (XML de FAO). Las salidas 1 y 2 usan la accion 3 con (mapa, punto). En Dos Coronas solo se leen; no se conectan todavia.', d => {
    const ev = [...d.querySelectorAll('事件')]; return `${ev.length} eventos<br>` + ev.map(e => `#${e.getAttribute('編號')} cursor ${e.getAttribute('游標')} · ${[...e.querySelectorAll('動作')].map(a => 'accion ' + a.getAttribute('編號') + '(' + [...a.querySelectorAll('參數')].map(q => q.getAttribute('數值')).join(',') + ')').join(' ')}`).join('<br>');
  });
}
function tabDialogos(p) {
  xmlEditor(p, 'dialogos', 'Dialogos', 'Dialogos del mapa (XML de FAO): cada uno apunta a un mensaje de setting/eng/msg.xml.', d => { const dl = [...d.querySelectorAll('對話')]; return `${dl.length} dialogos<br>` + dl.slice(0, 80).map(e => `#${e.getAttribute('編號')} mensaje ${e.getAttribute('訊息')}`).join('<br>'); });
}
function tabCapas(p) {
  const L = [['ao', 'NPC y monstruos de AO (servidor)'], ['camps', 'Campamentos de criaturas'], ['terreno', 'Terreno'], ['attr', 'Colision (atributo)'], ['transitable', 'Transitable (reglas de Dos Coronas)'], ['objetos', 'Objetos'], ['marcas', 'Marcas de objetos sin sprite (NPC, servidor)'], ['zonas', 'Zonas, puntos y salidas'], ['rutas', 'Rutas'], ['cuadricula', 'Cuadricula'], ['extra', 'Capa extra (formato v6)'], ['espejo', 'Aplicar espejo a los objetos con espejo = 2 (hipotesis)']];
  for (const [k, n] of L) { const l = el('label', { className: 'row' }, `<input type="checkbox"> ${n}`); const c = l.querySelector('input'); c.checked = S.capas[k]; c.onchange = () => { S.capas[k] = c.checked; if (k === 'transitable') walkCv = null; redraw(); }; p.append(l); }
}
function tabMapa(p) {
  p.append(el('h4', {}, 'Informacion'));
  const n = (a) => a.toLocaleString();
  p.append(el('div', {}, `<b>${M.nombre}</b> (${M.origen})<br>${M.w} × ${M.h} celdas = ${n(M.w * M.h)} · ${M.w * CELL}×${M.h * CELL} px<br>version del formato 0x${M.cab[3].toString(16)}${M.cab[3] >= 0x10006 ? ' (v6: con capa extra; <span class="av">el lector actual de Dos Coronas esta hecho para v5: se conserva, pero revisa la carga</span>)' : ''}<br>${M.objs.length} objetos · ${M.puntos.length} puntos/zonas · ${M.rutas.length} rutas<br>tilesets en la lista: ${M.ts.join(', ')}`));
  p.append(el('h4', {}, 'Cambiar tamano'));
  const f = el('div', { className: 'row' }); const iw = el('input', { type: 'number', value: M.w, min: 8, max: 1024 }), ih = el('input', { type: 'number', value: M.h, min: 8, max: 1024 }); f.append(el('span', { className: 'mu' }, 'ancho'), iw, el('span', { className: 'mu' }, 'alto'), ih); p.append(f);
  const f2 = el('div', { className: 'row' }); const ix = el('input', { type: 'number', value: 0 }), iy = el('input', { type: 'number', value: 0 }); f2.append(el('span', { className: 'mu' }, 'mover contenido (celdas) x'), ix, el('span', { className: 'mu' }, 'y'), iy); p.append(f2);
  const f3 = el('div', { className: 'row' }); const it = el('input', { type: 'number', value: S.ts, min: 0, max: 255 }); f3.append(el('span', { className: 'mu' }, 'tileset para el espacio nuevo'), it); p.append(f3);
  const b = el('button', { className: 'btn' }, 'Aplicar tamano'); b.onclick = () => { redimensionar(clamp(+iw.value | 0, 8, 1024), clamp(+ih.value | 0, 8, 1024), +ix.value | 0, +iy.value | 0, +it.value | 0); }; p.append(b);
  p.append(el('h4', {}, 'Nombre del mapa al exportar'));
  const nm = el('input', { type: 'text', value: M.nombre, style: 'width:100%' }); nm.onchange = () => { M.nombre = nm.value.replace(/[^0-9A-Za-z_\-]/g, ''); $('#titulo').textContent = M.nombre + ' (' + M.w + '×' + M.h + ')'; }; p.append(nm);
  p.append(el('h4', {}, 'Estadisticas de objetos'));
  const cnt = {}; M.objs.forEach(o => { const d = OBJDEFS[o.id]; const k = d ? d[2] + ' / ' + d[1] : 'sin definicion'; cnt[k] = (cnt[k] || 0) + 1; });
  p.append(el('div', { className: 'mu' }, Object.entries(cnt).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${v} · ${k}`).join('<br>')));
}
function redimensionar(nw, nh, dx, dy, tsNuevo) {
  const antes = { w: M.w, h: M.h, cel: M.cel, extra: M.extra, objs: M.objs.map(o => ({ ...o })), puntos: JSON.parse(JSON.stringify(M.puntos)), rutas: JSON.parse(JSON.stringify(M.rutas)), ts: M.ts.slice() };
  const hacer = () => {
    const cel = new Uint8Array(nw * nh * 6), ex = antes.extra.length === antes.w * antes.h ? new Uint8Array(nw * nh) : antes.extra;
    for (let i = 0; i < nw * nh; i++) cel[i * 6] = tsNuevo;
    for (let y = 0; y < antes.h; y++) for (let x = 0; x < antes.w; x++) { const nx = x + dx, ny = y + dy; if (nx < 0 || ny < 0 || nx >= nw || ny >= nh) continue; cel.set(antes.cel.subarray((y * antes.w + x) * 6, (y * antes.w + x) * 6 + 6), (ny * nw + nx) * 6); if (ex.length === nw * nh) ex[ny * nw + nx] = antes.extra[y * antes.w + x]; }
    M.w = nw; M.h = nh; M.cel = cel; M.extra = ex; if (!M.ts.includes(tsNuevo)) M.ts.push(tsNuevo);
    M.objs = antes.objs.map(o => ({ ...o, x: o.x + dx * CELL, y: o.y + dy * CELL })).filter(o => o.x >= 0 && o.y >= 0 && o.x < nw * CELL && o.y < nh * CELL);
    M.puntos = JSON.parse(JSON.stringify(antes.puntos)).map(s => ({ ...s, puntos: s.puntos.map(q => [q[0] + dx * CELL, q[1] + dy * CELL]) }));
    M.rutas = JSON.parse(JSON.stringify(antes.rutas)).map(s => ({ ...s, puntos: s.puntos.map(q => [q[0] + dx * CELL, q[1] + dy * CELL, ...q.slice(2)]) }));
    S.sel.clear(); reconstruirCapas(); chunks.clear(); dirtyAll = true; walkCv = null; extraCv = null; cargarTex(tsNuevo);
  };
  const deshacer = () => { M.w = antes.w; M.h = antes.h; M.cel = antes.cel; M.extra = antes.extra; M.objs = antes.objs.map(o => ({ ...o })); M.puntos = JSON.parse(JSON.stringify(antes.puntos)); M.rutas = JSON.parse(JSON.stringify(antes.rutas)); M.ts = antes.ts.slice(); S.sel.clear(); reconstruirCapas(); chunks.clear(); dirtyAll = true; walkCv = null; extraCv = null; };
  hacer(); push({ undo() { deshacer(); }, redo() { hacer(); } }); $('#titulo').textContent = M.nombre + ' (' + M.w + '×' + M.h + ', ' + M.objs.length + ' objetos)'; panelRefresh(); ajustar(); msg(`Tamano ${nw}×${nh}.`);
}

function tabValidar(p) {
  const b = el('button', { className: 'btn' }, 'Revisar el mapa'); const out = el('div'); p.append(b, out);
  b.onclick = () => {
    const res = []; const add = (nivel, txt, x, y) => res.push({ nivel, txt, x, y });
    const sin = new Set(); const fuera = [];
    for (const o of M.objs) { if (o.x < 0 || o.y < 0 || o.x >= M.w * CELL || o.y >= M.h * CELL) fuera.push(o); if (!OBJDEFS[o.id]) sin.add(o.id); }
    if (fuera.length) add('mal', fuera.length + ' objetos fuera del mapa', fuera[0].x, fuera[0].y);
    if (sin.size) add('av', 'Ids de objeto sin definicion en los .obd: ' + [...sin].slice(0, 12).join(', '));
    const usados = new Set(); for (let i = 0; i < M.w * M.h; i++) usados.add(M.cel[i * 6]); const faltan = [...usados].filter(t => !M.ts.includes(t));
    if (faltan.length) add('av', 'Tilesets usados que no estan en la lista del mapa (se anadiran al exportar si es necesario): ' + faltan.join(', '));
    const noTS = [...usados].filter(t => !TS[t]); if (noTS.length) add('mal', 'Tilesets que no existen en los .pak: ' + noTS.join(', '));
    const w1 = M.puntos.filter(s => s.id === 1 || s.id === 2); if (w1.length < 2) add('av', 'Faltan salidas: en FAO los puntos 1 y 2 son los triangulos de salida (hay ' + w1.length + ')');
    const T = calcularTransitable(); const total = T.libre.reduce((a, v) => a + v, 0);
    add('ok', `Transitable: ${total} celdas (${(100 * total / (M.w * M.h)).toFixed(0)}%), ${T.n} zonas conectadas; la principal tiene ${T.tam[T.mayor] || 0}.`);
    const islas = []; for (let i = 1; i <= T.n; i++) if (i !== T.mayor && T.tam[i] > 40) islas.push(i); if (islas.length) add('av', islas.length + ' zonas transitables aisladas de mas de 40 celdas (amarillo en la capa Transitable)');
    for (const s of M.puntos.filter(s => s.id === 1 || s.id === 2)) { const q = s.puntos[0]; if (!q) continue; const cx = Math.floor(q[0] / CELL), cy = Math.floor(q[1] / CELL); let ok = false; for (let dy = -3; dy <= 3 && !ok; dy++) for (let dx = -3; dx <= 3; dx++) { const x = cx + dx, y = cy + dy; if (inB(x, y) && T.comp[y * M.w + x] === T.mayor) { ok = true; break; } } add(ok ? 'ok' : 'av', `Salida ${s.id}: ${ok ? 'se puede alcanzar desde la zona principal' : 'NO se alcanza desde la zona principal'}`, q[0], q[1]); }
    const ob = M.objs.filter(o => { const m = OBJMETA[o.id]; return m && m !== 'pendiente' && m.b; }).length; add('ok', `${M.objs.length} objetos, ${ob} bloquean el paso`);
    for (const r of M.rutas) if (r.puntos.length < 2) add('av', 'La ruta ' + r.id + ' tiene menos de 2 puntos');
    if (M.camps.length) { let malc = 0, aisl = 0, fu = 0; for (const c of M.camps) { const cx = Math.floor(c.x), cy = Math.floor(c.y); if (!inB(cx, cy)) { fu++; continue; } const i = cy * M.w + cx; if (!T.libre[i]) { malc++; if (malc === 1) add('mal', 'Campamento sobre una casilla no transitable (' + c.monstruo + ')', c.x * CELL, c.y * CELL); } else if (T.comp[i] !== T.mayor) aisl++; } if (fu) add('mal', fu + ' campamentos fuera del mapa'); if (malc) add('mal', malc + ' campamentos sobre casillas no transitables'); if (aisl) add('av', aisl + ' campamentos en zonas aisladas de la principal'); if (!malc && !fu) add('ok', M.camps.length + ' campamentos con ' + M.camps.reduce((a, c) => a + (c.cantidad || 1), 0) + ' criaturas'); }
    out.innerHTML = ''; for (const r of res) { const d = el('div', { className: 'row ' + r.nivel }, (r.nivel === 'ok' ? '✔ ' : r.nivel === 'mal' ? '✖ ' : '⚠ ') + r.txt); if (r.x != null) { d.style.cursor = 'pointer'; d.onclick = () => { cam.x = r.x - cv.width / cam.z / devicePixelRatio / 2; cam.y = r.y - cv.height / cam.z / devicePixelRatio / 2; redraw(); }; } out.append(d); }
  };
  b.click();
}

// ------------------------------------------------------------------------------------------------ archivo
function modal(html) { $('#modalbox').innerHTML = html; $('#modal').style.display = 'flex'; }
function cerrarModal() { $('#modal').style.display = 'none'; }
$('#modal').addEventListener('pointerdown', e => { if (e.target === $('#modal')) cerrarModal(); });
async function dialogoAbrir() {
  const [m, pr] = await Promise.all([api('/api/mapas'), api('/api/proyectos')]); STAGE = m.stage || STAGE;
  modal('<h3 style="margin:0 0 8px">Abrir mapa</h3><div class="row"><input id="mf" type="text" placeholder="filtrar (nombre, numero…)" style="flex:1"><button class="btn" id="mx">Cerrar</button></div><div id="ml" style="max-height:60vh;overflow:auto"></div>');
  $('#mx').onclick = cerrarModal; const pintar = () => {
    const q = $('#mf').value.toLowerCase(), L = $('#ml'); L.innerHTML = '';
    const grupos = [['Mis proyectos (.json)', pr.map(n => ({ origen: 'proyecto', nombre: n }))], ['Exportados (salida\\)', m.mapas.filter(x => x.origen === 'salida')], ['Carpeta map\\ del cliente', m.mapas.filter(x => x.origen === 'carpeta')], ['Dentro de los .pak', m.mapas.filter(x => x.origen === 'pak')]];
    for (const [t, arr] of grupos) {
      const f = arr.filter(x => { const num = (x.nombre.match(/(\d+)/) || [])[1]; const nom = num && STAGE[+num] ? STAGE[+num] : ''; return !q || (x.nombre + ' ' + nom).toLowerCase().includes(q); }); if (!f.length) continue;
      L.append(el('h4', {}, `${t} (${f.length})`)); const g = el('div', { className: 'row' });
      f.slice(0, 400).forEach(x => { const num = (x.nombre.match(/(\d+)/) || [])[1]; const nom = num && STAGE[+num] ? ' · ' + STAGE[+num] : ''; const b = el('button', { className: 'btn sm' }, x.nombre + nom); b.onclick = () => abrirMapa(x); g.append(b); }); L.append(g);
    }
  };
  $('#mf').oninput = pintar; pintar(); $('#mf').focus();
}
async function abrirMapa(x) {
  msg('Abriendo ' + x.nombre + '…'); cerrarModal();
  try {
    const j = x.origen === 'proyecto' ? await api('/api/abrir_proyecto?n=' + encodeURIComponent(x.nombre)) : await api(`/api/abrir?o=${x.origen}&n=${encodeURIComponent(x.nombre)}`);
    cargarMapa(j);
  } catch (e) { msg('No se pudo abrir: ' + e.message, 'mal'); }
}
$('#bAbrir').onclick = () => { if (!dirty || confirm('Hay cambios sin guardar. ¿Abrir otro mapa?')) dialogoAbrir(); };
$('#bNuevo').onclick = () => {
  const o = Object.values(TS).sort((a, b) => a.n - b.n).map(t => `<option value="${t.n}">${t.n} · ${t.clase}</option>`).join('');
  modal(`<h3 style="margin:0 0 8px">Mapa nuevo</h3><div class="row"><span class="mu">nombre</span><input id="nn" type="text" value="mapa900"></div><div class="row"><span class="mu">ancho</span><input id="nw" type="number" value="120"><span class="mu">alto</span><input id="nh" type="number" value="90"></div><div class="row"><span class="mu">terreno base</span><select id="nt">${o}</select></div><div class="row"><button class="btn on" id="nok">Crear</button><button class="btn" id="nc">Cancelar</button></div><div class="mu">Se crea en formato v5 (el que lee Dos Coronas), sin objetos, con el terreno base y sin colision.</div>`);
  $('#nt').value = TS[0] ? 0 : Object.keys(TS)[0]; $('#nc').onclick = cerrarModal;
  $('#nok').onclick = async () => { const w = clamp(+$('#nw').value | 0, 8, 1024), h = clamp(+$('#nh').value | 0, 8, 1024), n = $('#nn').value.replace(/[^0-9A-Za-z_\-]/g, '') || 'mapa'; cerrarModal(); cargarMapa(await api(`/api/nuevo?w=${w}&h=${h}&ts=${$('#nt').value}&n=${n}`)); };
};
async function guardarProyecto() {
  if (!M) return; try { const r = await api('/api/guardar_proyecto?n=' + encodeURIComponent(M.nombre), { method: 'POST', body: JSON.stringify(mapaAJson()) }); setDirty(false); const pk = r.pack; msg('Proyecto guardado en proyectos\\' + r.nombre + '.json' + (pk ? (pk.ok ? ' · mapa en ' + pk.pack + ' (' + pk.mapas + ' mapas)' : ' · NO se pudo mandar a ' + pk.pack + ': ' + pk.error) : ''), pk && !pk.ok ? 'mal' : 'ok'); } catch (e) { msg('No se pudo guardar: ' + e.message, 'mal'); }
}
$('#bGuardar').onclick = guardarProyecto;
$('#bExportar').onclick = async () => {
  if (!M) return; try {
    const r = await api('/api/exportar?n=' + encodeURIComponent(M.nombre), { method: 'POST', body: JSON.stringify(mapaAJson()) });
    let ao = null; try { ao = await exportarAO(); } catch (e) { ao = { error: e.message }; }
    msg(`Exportado ${r.archivo} (${r.bytes} bytes, ${r.w}×${r.h}, ${r.objetos} objetos). Releido OK. Esta en ${r.ruta}`, 'ok');
    modal(`<h3 style="margin:0 0 8px">Exportado</h3><div>${r.archivo} · ${r.bytes.toLocaleString()} bytes · ${r.w}×${r.h} · ${r.objetos} objetos${r.campamentos ? ' · ' + r.campamentos + ' campamentos de criaturas' : ''}<br><span class="mu">${r.ruta}</span>${r.campamentos_lua ? '<br><span class="mu">' + r.campamentos_lua + '</span>' : ''}<br><span class="ok">Se comprobo releyendo el archivo escrito.</span>${resumenAO(ao)}${r.pack ? (r.pack.ok ? '<br><span class="ok">Mapa guardado en el pack ' + r.pack.pack + ' (' + r.pack.mapas + ' mapas): el juego lo usa al abrirlo de nuevo.</span><br><span class="mu">' + r.pack.ruta + '</span>' : '<br><span class="mal">No se pudo mandar al pack ' + r.pack.pack + ': ' + r.pack.error + '</span>') : ''}</div><div class="row"><a class="btn" href="/api/descargar?n=${encodeURIComponent(r.archivo)}">Descargar</a><button class="btn" id="mx2">Cerrar</button></div><div class="mu">Para usarlo en Dos Coronas pulsa "Enviar a Dos Coronas" (copia el .mpc y hornea sus datos y atlas con hornear_mpc.py).</div>`); $('#mx2').onclick = cerrarModal;
  } catch (e) { msg('No se pudo exportar: ' + e.message, 'mal'); }
};
$('#bDC').onclick = () => {
  if (!M) return; const num = (M.nombre.match(/(\d+)/) || [])[1] || '900';
  modal(`<h3 style="margin:0 0 8px">Enviar a Dos Coronas</h3><div class="row"><span class="mu">numero del mapa</span><input id="dn" type="number" value="${num}"><span class="mu">nombre del comando</span><input id="dm" type="text" value="${(M.nombre || 'mapa').toLowerCase().replace(/[^a-z0-9_]/g, '')}"></div><div class="mu">Exporta, copia a compartido/datos/mapas_fao/ y ejecuta herramientas/generar_mapa/hornear_mpc.py (atlas del suelo y de objetos + mapNNN_datos.lua) en el proyecto. Despues hay que anadir una linea a M.MAPAS en compartido/dominio/mapas_fao.lua.</div><div class="row"><button class="btn on" id="dok">Enviar</button><button class="btn" id="dc">Cancelar</button></div><pre id="dout" style="white-space:pre-wrap;font-size:11px"></pre>`);
  $('#dc').onclick = cerrarModal; $('#dok').onclick = async () => { $('#dout').textContent = 'Horneando… (puede tardar un minuto)'; try { const r = await api(`/api/a_dos_coronas?num=${$('#dn').value}&n=${encodeURIComponent($('#dm').value)}`, { method: 'POST', body: JSON.stringify(mapaAJson()) }); $('#dout').textContent = (r.ok ? 'OK\n' : 'ERROR\n') + (r.error || '') + (r.salida || '') + '\n' + (r.siguiente || ''); } catch (e) { $('#dout').textContent = e.message; } };
};
$('#bUndo').onclick = undo; $('#bRedo').onclick = redo; $('#bZoomM').onclick = () => zoomEn(1 / 1.25); $('#bZoomP').onclick = () => zoomEn(1.25); $('#bAjustar').onclick = ajustar;
setInterval(() => { if (M && dirty) api('/api/guardar_proyecto?n=_auto_' + encodeURIComponent(M.nombre), { method: 'POST', body: JSON.stringify(mapaAJson()) }).catch(() => { }); }, 90000);
addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
iniciar();
