'use strict';
/* Editor de mapas de Dos Coronas: edita los mapas que genera compartido/dominio/mapa.lua (volcados con dcdump) y los exporta como .json / .lua (capas en RLE). */
const $ = s => document.querySelector(s);
const el = (t, p = {}, h = '') => { const e = document.createElement(t); Object.assign(e, p); if (h) e.innerHTML = h; return e; };
const api = async (p, o) => { const r = await fetch(p, o); if (!r.ok) throw new Error((await r.text()).slice(0, 300)); return r.json(); };
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const msg = (t, c) => { $('#msg').textContent = t; $('#msg').className = c || ''; };
const CELL = 16, CH = 32;
const SUELO_COL = { agua: '#2f6fb4', arena: '#e8d49a', hierba: '#5da04a', tierra: '#9a7449', pantano: '#4f6b4a', bosque: '#2e6b3a', nieve: '#eef3f8', montana: '#8a8d94', hierba_osc: '#3f6a3a', muralla: '#555a66', adoquin: '#a8a39a', calle: '#bdb7a9', teja_umbra: '#6a3d5e', fachada: '#c9b99a', cicatriz: '#6b2d2d', plaza: '#d8cdb4', teja: '#b5533c', camino: '#c4a574', madera: '#8c6a3f', roca: '#777b82' };
const hash = s => { let h = 7; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h; };
const colHash = s => `hsl(${hash(s) % 360} 60% 55%)`;
const sueloCol = n => SUELO_COL[n] || colHash(n);
const hex2rgb = c => { if (c[0] === '#') return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)]; const m = c.match(/hsl\((\d+) (\d+)% (\d+)%\)/); const h = +m[1] / 360, s = +m[2] / 100, l = +m[3] / 100; const a = s * Math.min(l, 1 - l), f = n => { const k = (n + h * 12) % 12; return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)); }; return [f(0) * 255, f(8) * 255, f(4) * 255].map(Math.round); };
const KNOWN = new Set(['nombre', 'w', 'h', 'suelos', 'suelo', 'biomas', 'bioma', 'lados', 'lado', 'bloque', 'props', 'campamentos', 'edificios', 'ciudades']);

let D = null, MONS = null;
const S = {
  tool: 'pincel', prev: 'pincel', capa: 'suelo', val: { suelo: 'hierba', bioma: 'campos', lado: '', bloque: 1 }, size: 5, forma: 'circulo',
  prop: 'arbol_pino', campTpl: null, esparcir: true, densidad: 3, radio: 6,
  ver: { suelo: true, bioma: false, lado: false, bloque: true, props: true, camps: true, edifs: true, ciudades: true, otros: true, cuadricula: true, transitable: false },
  sel: new Set(), tab: 'pincel',
};
const cam = { x: 0, y: 0, z: 0.5 };
const cv = $('#map'), ctx = cv.getContext('2d'), mini = $('#mini'), mctx = mini.getContext('2d');
let chunks = new Map(), dirtyAll = true, dirtyChunks = new Set(), ovCv = {}, miniCv = null, walkCv = null, cur = { x: 0, y: 0, cx: 0, cy: 0, sobre: false }, drag = null, dirty = false;

// ------------------------------------------------------------------------------------------ historial
const HIST = { u: [], r: [] };
function push(op) { HIST.u.push(op); if (HIST.u.length > 250) HIST.u.shift(); HIST.r = []; setDirty(true); ru(); }
function undo() { const o = HIST.u.pop(); if (o) { o.undo(); HIST.r.push(o); setDirty(true); ru(); redraw(); panelLight(); } }
function redo() { const o = HIST.r.pop(); if (o) { o.redo(); HIST.u.push(o); setDirty(true); ru(); redraw(); panelLight(); } }
function ru() { $('#bUndo').disabled = !HIST.u.length; $('#bRedo').disabled = !HIST.r.length; }
function setDirty(v) { dirty = v; $('#dirty').textContent = v ? '● sin guardar' : ''; }
$('#bUndo').onclick = undo; $('#bRedo').onclick = redo;

// ------------------------------------------------------------------------------------------ carga
async function iniciar() { buildTools(); buildTabs(); resize(); ru(); dialogoAbrir(); }
function cargar(j, nombre) {
  const n = j.w * j.h;
  const dec = (rle, def) => { const a = new Uint8Array(n); if (rle) { let p = 0; for (let i = 0; i < rle.length; i += 2) { a.fill(rle[i], p, p + rle[i + 1]); p += rle[i + 1]; } } return a; };
  const plano = (flat, tipo) => { if (!flat) return new Uint8Array(n); return Uint8Array.from(flat); };
  D = {
    nombre: nombre || j.nombre, w: j.w, h: j.h, suelos: j.suelos.slice(), biomas: j.biomas.slice(), lados: j.lados.slice(),
    suelo: j.suelo_rle ? dec(j.suelo_rle) : plano(j.suelo), bioma: j.bioma_rle ? dec(j.bioma_rle) : plano(j.bioma), lado: j.lado_rle ? dec(j.lado_rle) : plano(j.lado), bloque: j.bloque_rle ? dec(j.bloque_rle) : plano(j.bloque),
    props: j.props || [], camps: j.campamentos || [], edifs: j.edificios || [], ciudades: j.ciudades || [], resto: {},
  };
  for (const k in j) if (!KNOWN.has(k) && !k.endsWith('_rle')) D.resto[k] = j[k];
  HIST.u = []; HIST.r = []; ru(); S.sel.clear(); chunks.clear(); dirtyAll = true; ovCv = {}; walkCv = null; miniCv = null;
  S.val.suelo = D.suelos.includes('hierba') ? 'hierba' : D.suelos[0]; S.val.bioma = D.biomas[0]; S.val.lado = D.lados[0] ?? '';
  S.prop = (D.props[0] && D.props[0].tipo) || S.prop; S.campTpl = D.camps[0] ? { monstruo: D.camps[0].monstruo, cantidad: D.camps[0].cantidad || 4, radio: D.camps[0].radio || 4 } : { monstruo: 'seta_azul', cantidad: 4, radio: 4 };
  $('#titulo').textContent = `${D.nombre} (${D.w}×${D.h}, ${D.props.length} props, ${D.camps.length} campamentos)`; setDirty(false);
  ajustar(); setTimeout(ajustar, 60); setTimeout(ajustar, 400); panel(); redraw(); msg('Abierto ' + D.nombre + '.');
}
function idx(arr, v) { let i = arr.indexOf(v); if (i < 0) { arr.push(v); i = arr.length - 1; } return i; }
function rleEnc(a) { const o = []; let prev = -1, c = 0; for (let i = 0; i < a.length; i++) { if (a[i] === prev) c++; else { if (c) o.push(prev, c); prev = a[i]; c = 1; } } if (c) o.push(prev, c); return o; }
function aJson() {
  const j = { nombre: D.nombre, w: D.w, h: D.h, suelos: D.suelos, biomas: D.biomas, lados: D.lados, suelo_rle: rleEnc(D.suelo), bioma_rle: rleEnc(D.bioma), lado_rle: rleEnc(D.lado), bloque_rle: rleEnc(D.bloque),
    props: D.props, campamentos: D.camps, edificios: D.edifs, ciudades: D.ciudades };
  for (const k in D.resto) j[k] = D.resto[k]; return j;
}

// ------------------------------------------------------------------------------------------ dibujo
let raf = 0; function redraw() { if (!raf) raf = requestAnimationFrame(() => { raf = 0; dibujar(); }); }
function resize() { const r = $('#cv').getBoundingClientRect(); cv.width = Math.max(1, r.width * devicePixelRatio); cv.height = Math.max(1, r.height * devicePixelRatio); redraw(); }
addEventListener('resize', resize);
function chunkCanvas(cx, cy) {
  const k = cx + ',' + cy; let c = chunks.get(k); if (c && !dirtyAll && !dirtyChunks.has(k)) return c;
  if (!c) { c = el('canvas'); c.width = c.height = CH * CELL; chunks.set(k, c); }
  const g = c.getContext('2d'); g.clearRect(0, 0, c.width, c.height); const cols = D.suelos.map(sueloCol);
  for (let j = 0; j < CH; j++) for (let i = 0; i < CH; i++) { const x = cx * CH + i, y = cy * CH + j; if (x >= D.w || y >= D.h) continue; g.fillStyle = cols[D.suelo[y * D.w + x]] || '#000'; g.fillRect(i * CELL, j * CELL, CELL, CELL); }
  dirtyChunks.delete(k); return c;
}
function overlay(nombre, fn) {
  if (ovCv[nombre] && !ovCv[nombre]._sucio) return ovCv[nombre]; const c = ovCv[nombre] || el('canvas'); c.width = D.w; c.height = D.h; const g = c.getContext('2d'), d = g.createImageData(D.w, D.h);
  for (let i = 0; i < D.w * D.h; i++) { const col = fn(i); if (col) { d.data[i * 4] = col[0]; d.data[i * 4 + 1] = col[1]; d.data[i * 4 + 2] = col[2]; d.data[i * 4 + 3] = col[3] ?? 255; } }
  g.putImageData(d, 0, 0); c._sucio = false; return ovCv[nombre] = c;
}
function invalidar(nombre) { if (ovCv[nombre]) ovCv[nombre]._sucio = true; }
function celdaCambio(capa, i) { const x = i % D.w, y = (i / D.w) | 0; if (capa === 'suelo') dirtyChunks.add((x >> 5) + ',' + (y >> 5)); invalidar(capa); if (capa === 'suelo' || capa === 'bloque') walkCv = null; miniCv = null; }

function dibujar() {
  if (!D) { ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = '#07080c'; ctx.fillRect(0, 0, cv.width, cv.height); return; }
  const dpr = devicePixelRatio, z = cam.z * dpr; ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = '#07080c'; ctx.fillRect(0, 0, cv.width, cv.height); ctx.setTransform(z, 0, 0, z, -cam.x * z, -cam.y * z);
  const vw = cv.width / z, vh = cv.height / z, W = D.w * CELL, H = D.h * CELL;
  if (S.ver.suelo) {
    const cx0 = clamp(Math.floor(cam.x / CELL / CH), 0, 1e6), cy0 = clamp(Math.floor(cam.y / CELL / CH), 0, 1e6), cx1 = Math.min(Math.ceil(D.w / CH) - 1, Math.floor((cam.x + vw) / CELL / CH)), cy1 = Math.min(Math.ceil(D.h / CH) - 1, Math.floor((cam.y + vh) / CELL / CH));
    ctx.imageSmoothingEnabled = cam.z < 1;
    for (let cy = cy0; cy <= cy1; cy++) for (let cx = cx0; cx <= cx1; cx++) ctx.drawImage(chunkCanvas(cx, cy), cx * CH * CELL, cy * CH * CELL);
    dirtyAll = false;
  }
  ctx.strokeStyle = '#fff4'; ctx.lineWidth = 2 / z; ctx.strokeRect(0, 0, W, H);
  ctx.imageSmoothingEnabled = false;
  if (S.ver.bioma) { ctx.globalAlpha = .4; ctx.drawImage(overlay('bioma', i => { const n = D.biomas[D.bioma[i]]; return n ? [...hex2rgb(colHash(n)), 255] : null; }), 0, 0, W, H); ctx.globalAlpha = 1; }
  if (S.ver.lado) { ctx.globalAlpha = .35; ctx.drawImage(overlay('lado', i => { const n = D.lados[D.lado[i]]; return n ? (n === 'albor' ? [255, 220, 90, 255] : n === 'umbra' ? [190, 90, 255, 255] : [...hex2rgb(colHash(n)), 255]) : null; }), 0, 0, W, H); ctx.globalAlpha = 1; }
  if (S.ver.bloque) { ctx.globalAlpha = .55; ctx.drawImage(overlay('bloque', i => (D.bloque[i] && D.suelos[D.suelo[i]] !== 'agua') ? [229, 72, 77, 255] : null), 0, 0, W, H); ctx.globalAlpha = 1; }
  if (S.ver.transitable) { if (!walkCv) walkCv = calcularTransitable().cv; ctx.globalAlpha = .45; ctx.drawImage(walkCv, 0, 0, W, H); ctx.globalAlpha = 1; }
  if (S.ver.cuadricula && cam.z >= 1.4) { ctx.lineWidth = 1 / z; ctx.beginPath(); const x0 = Math.max(0, Math.floor(cam.x / CELL)), x1 = Math.min(D.w, Math.ceil((cam.x + vw) / CELL)), y0 = Math.max(0, Math.floor(cam.y / CELL)), y1 = Math.min(D.h, Math.ceil((cam.y + vh) / CELL)); for (let x = x0; x <= x1; x++) { ctx.moveTo(x * CELL, y0 * CELL); ctx.lineTo(x * CELL, y1 * CELL); } for (let y = y0; y <= y1; y++) { ctx.moveTo(x0 * CELL, y * CELL); ctx.lineTo(x1 * CELL, y * CELL); } ctx.strokeStyle = '#ffffff22'; ctx.stroke(); }
  entidades(vw, vh, z);
  herramienta(z);
  dibujarMini(); hud();
}
const PROPCOL = t => /arbol|pino|seco/.test(t) ? '#1d7a36' : /montana|roca|risco/.test(t) ? '#c8c8d0' : /flor|matas|arbusto|hierba|cultivo/.test(t) ? '#e86ab8' : /farol|fogata/.test(t) ? '#ffd24a' : /bandera|estatua|columna/.test(t) ? '#ff9f43' : colHash(t);
function entidades(vw, vh, z) {
  const px = 1 / z, vx0 = cam.x / CELL - 2, vy0 = cam.y / CELL - 2, vx1 = (cam.x + vw) / CELL + 2, vy1 = (cam.y + vh) / CELL + 2;
  if (S.ver.ciudades) for (const c of D.ciudades) { if (c.x == null) continue; ctx.strokeStyle = '#4de1e1'; ctx.fillStyle = '#4de1e114'; ctx.lineWidth = 2 * px; ctx.fillRect(c.x * CELL, c.y * CELL, c.w * CELL, c.h * CELL); ctx.strokeRect(c.x * CELL, c.y * CELL, c.w * CELL, c.h * CELL); ctx.fillStyle = '#fff'; ctx.font = (14 * px) + 'px sans-serif'; ctx.fillText((c.nombre || c.id) + (c.capital ? ' ★' : ''), c.x * CELL + 4 * px, c.y * CELL + 16 * px); }
  if (S.ver.edifs) for (const e of D.edifs) { if (e.x > vx1 || e.y > vy1 || e.x + e.w < vx0 || e.y + e.h < vy0) continue; ctx.fillStyle = (e.faccion === 'umbra' ? '#a85ad8' : '#e0b24a') + '66'; ctx.strokeStyle = e.faccion === 'umbra' ? '#c78bff' : '#ffd77a'; ctx.lineWidth = 1.5 * px; ctx.fillRect(e.x * CELL, e.y * CELL, e.w * CELL, e.h * CELL); ctx.strokeRect(e.x * CELL, e.y * CELL, e.w * CELL, e.h * CELL); if (e.puertaX != null) { ctx.fillStyle = '#fff'; ctx.fillRect(e.puertaX * CELL, e.puertaY * CELL, CELL, CELL); } if (cam.z > 1) { ctx.fillStyle = '#fff'; ctx.font = (11 * px) + 'px sans-serif'; ctx.fillText(e.rotulo || e.tienda || '', e.x * CELL + 2 * px, e.y * CELL + 11 * px); } }
  if (S.ver.props) {
    const n = D.props.length; ctx.imageSmoothingEnabled = true;
    for (let i = 0; i < n; i++) { const p = D.props[i]; if (p.x < vx0 || p.x > vx1 || p.y < vy0 || p.y > vy1) continue; const r = p.tipo && /montana/.test(p.tipo) ? CELL * .9 : CELL * .42; ctx.fillStyle = PROPCOL(p.tipo || '?'); ctx.beginPath(); if (cam.z < 0.5) ctx.fillRect((p.x + .5) * CELL - 2 * px, (p.y + .5) * CELL - 2 * px, 4 * px, 4 * px); else { ctx.arc((p.x + .5) * CELL, (p.y + .5) * CELL, r, 0, 7); ctx.fill(); } }
  }
  if (S.ver.camps) for (const c of D.camps) { if (c.x < vx0 - 6 || c.x > vx1 + 6 || c.y < vy0 - 6 || c.y > vy1 + 6) continue; ctx.strokeStyle = c.jefe ? '#ff4d4d' : '#ffb347'; ctx.fillStyle = (c.jefe ? '#ff4d4d' : '#ffb347') + '22'; ctx.lineWidth = 1.5 * px; ctx.beginPath(); ctx.arc(c.x * CELL, c.y * CELL, (c.radio || 3) * CELL, 0, 7); ctx.fill(); ctx.stroke(); ctx.fillStyle = c.jefe ? '#ff4d4d' : '#ffb347'; ctx.beginPath(); ctx.arc(c.x * CELL, c.y * CELL, 4 * px * 1.4, 0, 7); ctx.fill(); if (cam.z > .7) { ctx.fillStyle = '#fff'; ctx.font = (11 * px) + 'px sans-serif'; ctx.fillText((c.monstruo || '?') + ' ×' + (c.cantidad || 1), c.x * CELL + 6 * px, c.y * CELL - 6 * px); } }
  if (S.ver.otros) {
    ctx.fillStyle = '#ff5dd3'; ctx.strokeStyle = '#fff';
    for (const k of ['puestos', 'jefes', 'puertos', 'npcsMapa', 'escaleras', 'mazmorras']) { const l = D.resto[k]; if (!Array.isArray(l)) continue; for (const o of l) { if (typeof o.x !== 'number' || typeof o.y !== 'number') continue; ctx.beginPath(); ctx.moveTo(o.x * CELL, o.y * CELL - 7 * px * 1.5); ctx.lineTo(o.x * CELL + 6 * px * 1.5, o.y * CELL); ctx.lineTo(o.x * CELL, o.y * CELL + 7 * px * 1.5); ctx.lineTo(o.x * CELL - 6 * px * 1.5, o.y * CELL); ctx.closePath(); ctx.fill(); if (cam.z > .6) { ctx.fillStyle = '#fff'; ctx.font = (10 * px) + 'px sans-serif'; ctx.fillText(k.replace('npcsMapa', 'npc') + ' ' + (o.id || o.nombre || ''), o.x * CELL + 8 * px, o.y * CELL - 4 * px); ctx.fillStyle = '#ff5dd3'; } } }
    const pt = D.resto.portal; if (pt) { ctx.fillStyle = '#7dff7d'; ctx.strokeStyle = '#000'; ctx.lineWidth = px; ctx.beginPath(); for (let k = 0; k < 10; k++) { const r = k % 2 ? 6 : 13, a = k * Math.PI / 5 - Math.PI / 2; ctx.lineTo(pt.x * CELL + Math.cos(a) * r * px * 1.4, pt.y * CELL + Math.sin(a) * r * px * 1.4); } ctx.closePath(); ctx.fill(); ctx.stroke(); }
  }
  ctx.lineWidth = 2 * px; ctx.strokeStyle = '#ffd24a'; ctx.setLineDash([5 * px, 4 * px]);
  for (const s of S.sel) { const b = cajaEnt(s); ctx.strokeRect(b.x, b.y, b.w, b.h); }
  ctx.setLineDash([]);
}
function cajaEnt(s) {
  const o = s.o; if (s.k === 'edif' || s.k === 'ciudad') return { x: o.x * CELL, y: o.y * CELL, w: o.w * CELL, h: o.h * CELL };
  if (s.k === 'camp') { const r = (o.radio || 3) * CELL; return { x: o.x * CELL - r, y: o.y * CELL - r, w: 2 * r, h: 2 * r }; }
  return { x: o.x * CELL - 2, y: o.y * CELL - 2, w: CELL + 4, h: CELL + 4 };
}
function herramienta(z) {
  const px = 1 / z; if (!cur.sobre && !(drag && drag.pts)) return; ctx.lineWidth = 2 * px;
  if (S.tool === 'pincel' || S.tool === 'rect' || S.tool === 'cubo' || S.tool === 'cuentagotas') {
    if (S.tool === 'pincel') { ctx.strokeStyle = '#fff'; const r = S.size / 2; if (S.forma === 'circulo') { ctx.beginPath(); ctx.arc((cur.cx + .5) * CELL, (cur.cy + .5) * CELL, r * CELL, 0, 7); ctx.stroke(); } else { const o = Math.floor(S.size / 2); ctx.strokeRect((cur.cx - o) * CELL, (cur.cy - o) * CELL, S.size * CELL, S.size * CELL); } }
    else if (S.tool === 'rect' && drag && drag.a) { const x0 = Math.min(drag.a.cx, cur.cx), x1 = Math.max(drag.a.cx, cur.cx), y0 = Math.min(drag.a.cy, cur.cy), y1 = Math.max(drag.a.cy, cur.cy); ctx.strokeStyle = '#fff'; ctx.strokeRect(x0 * CELL, y0 * CELL, (x1 - x0 + 1) * CELL, (y1 - y0 + 1) * CELL); }
    else { ctx.strokeStyle = '#fff'; ctx.strokeRect(cur.cx * CELL, cur.cy * CELL, CELL, CELL); }
  } else if (S.tool === 'prop') { ctx.strokeStyle = PROPCOL(S.prop); ctx.beginPath(); ctx.arc((cur.cx + .5) * CELL, (cur.cy + .5) * CELL, CELL * .45, 0, 7); ctx.stroke(); if (S.esparcir) { ctx.setLineDash([5 * px, 4 * px]); ctx.beginPath(); ctx.arc((cur.cx + .5) * CELL, (cur.cy + .5) * CELL, S.radio * CELL, 0, 7); ctx.stroke(); ctx.setLineDash([]); } }
  else if (S.tool === 'camp' && S.campTpl) { ctx.strokeStyle = '#ffb347'; ctx.beginPath(); ctx.arc((cur.cx + .5) * CELL, (cur.cy + .5) * CELL, (S.campTpl.radio || 3) * CELL, 0, 7); ctx.stroke(); }
  else if (S.tool === 'sel' && drag && drag.box) { const b = drag.box; ctx.fillStyle = '#6ea8ff22'; ctx.strokeStyle = '#6ea8ff'; ctx.fillRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0); ctx.strokeRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0); }
  else if (S.tool === 'borrar') { ctx.strokeStyle = '#ff6b6b'; ctx.beginPath(); ctx.arc(cur.x, cur.y, S.size * CELL / 2, 0, 7); ctx.stroke(); }
  else if (S.tool === 'portal') { ctx.strokeStyle = '#7dff7d'; ctx.beginPath(); ctx.arc((cur.cx + .5) * CELL, (cur.cy + .5) * CELL, 10 * px * 1.4, 0, 7); ctx.stroke(); }
}
function dibujarMini() {
  mctx.fillStyle = '#000'; mctx.fillRect(0, 0, mini.width, mini.height); if (!D) return;
  if (!miniCv) { miniCv = el('canvas'); miniCv.width = D.w; miniCv.height = D.h; const g = miniCv.getContext('2d'), d = g.createImageData(D.w, D.h), cols = D.suelos.map(n => hex2rgb(sueloCol(n))); for (let i = 0; i < D.w * D.h; i++) { const c = cols[D.suelo[i]] || [0, 0, 0]; d.data[i * 4] = c[0]; d.data[i * 4 + 1] = c[1]; d.data[i * 4 + 2] = c[2]; d.data[i * 4 + 3] = 255; } g.putImageData(d, 0, 0); }
  const k = Math.min(mini.width / D.w, mini.height / D.h), w = D.w * k, h = D.h * k, ox = (mini.width - w) / 2, oy = (mini.height - h) / 2; mctx.imageSmoothingEnabled = false; mctx.drawImage(miniCv, ox, oy, w, h);
  const vw = cv.width / (cam.z * devicePixelRatio) / CELL, vh = cv.height / (cam.z * devicePixelRatio) / CELL; mctx.strokeStyle = '#fff'; mctx.lineWidth = 1.5; mctx.strokeRect(ox + cam.x / CELL * k, oy + cam.y / CELL * k, vw * k, vh * k); mini._k = { k, ox, oy };
}
function hud() { if (!D) return; const i = cur.cy * D.w + cur.cx, ok = inB(cur.cx, cur.cy); $('#hud').textContent = `celda ${cur.cx},${cur.cy} · zoom ${Math.round(cam.z * 100)}%` + (ok ? ` · ${D.suelos[D.suelo[i]]} · bioma ${D.biomas[D.bioma[i]]} · ${D.lados[D.lado[i]] || 'sin bando'}${D.bloque[i] ? ' · BLOQUEADA' : ''}` : ''); $('#zlbl').textContent = Math.round(cam.z * 100) + '%'; }

// ------------------------------------------------------------------------------------------ camara
function ajustar() { if (!D) return; const r = $('#cv').getBoundingClientRect(); if (r.width < 50 || r.height < 50) { setTimeout(ajustar, 120); return; } cam.z = clamp(Math.min(r.width / (D.w * CELL), r.height / (D.h * CELL)), 0.02, 6); cam.x = (D.w * CELL - r.width / cam.z) / 2; cam.y = (D.h * CELL - r.height / cam.z) / 2; redraw(); }
function zoomEn(f, px, py) { const r = $('#cv').getBoundingClientRect(); px = px ?? r.width / 2; py = py ?? r.height / 2; const wx = cam.x + px / cam.z, wy = cam.y + py / cam.z; cam.z = clamp(cam.z * f, 0.02, 8); cam.x = wx - px / cam.z; cam.y = wy - py / cam.z; redraw(); }
function aMundo(e) { const r = cv.getBoundingClientRect(); return { x: cam.x + (e.clientX - r.left) / cam.z, y: cam.y + (e.clientY - r.top) / cam.z }; }
const inB = (x, y) => D && x >= 0 && y >= 0 && x < D.w && y < D.h;
$('#bZoomM').onclick = () => zoomEn(1 / 1.25); $('#bZoomP').onclick = () => zoomEn(1.25); $('#bAjustar').onclick = ajustar;

// ------------------------------------------------------------------------------------------ edicion de casillas
let stroke = null;
function setCelda(capa, x, y, v) {
  if (!inB(x, y)) return; const i = y * D.w + x, a = D[capa]; if (a[i] === v) return;
  stroke = stroke || { capa, m: new Map() }; if (!stroke.m.has(i)) stroke.m.set(i, a[i]); a[i] = v; celdaCambio(capa, i);
}
function cerrarTrazo() {
  if (!stroke || !stroke.m.size) { stroke = null; return; } const { capa, m } = stroke, a = D[capa], antes = new Map(m), despues = new Map(); m.forEach((_, i) => despues.set(i, a[i]));
  const ap = mp => mp.forEach((v, i) => { D[capa][i] = v; celdaCambio(capa, i); }); push({ undo() { ap(antes); }, redo() { ap(despues); } }); stroke = null; redraw();
}
function valorActual() { const c = S.capa; if (c === 'suelo') return idx(D.suelos, S.val.suelo); if (c === 'bioma') return idx(D.biomas, S.val.bioma); if (c === 'lado') return idx(D.lados, S.val.lado); return S.val.bloque ? 1 : 0; }
function disco(cx, cy, fn) { const r = S.size / 2, o = Math.floor(S.size / 2); if (S.forma === 'circulo') { for (let y = -Math.ceil(r); y <= Math.ceil(r); y++) for (let x = -Math.ceil(r); x <= Math.ceil(r); x++) if (x * x + y * y <= r * r + .25) fn(cx + x, cy + y); } else for (let y = -o; y < S.size - o; y++) for (let x = -o; x < S.size - o; x++) fn(cx + x, cy + y); }
function linea(a, b, fn) { let x0 = a.cx, y0 = a.cy; const x1 = b.cx, y1 = b.cy, dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1; let e = dx + dy; for (; ;) { fn(x0, y0); if (x0 === x1 && y0 === y1) break; const e2 = 2 * e; if (e2 >= dy) { e += dy; x0 += sx; } if (e2 <= dx) { e += dx; y0 += sy; } } }
function relleno(cx, cy) {
  if (!inB(cx, cy)) return; const capa = S.capa, a = D[capa], v = valorActual(), obj = a[cy * D.w + cx]; if (obj === v) return; const pila = [cy * D.w + cx], vis = new Uint8Array(D.w * D.h); let n = 0;
  while (pila.length && n < 2000000) { const i = pila.pop(); if (vis[i]) continue; vis[i] = 1; if (a[i] !== obj) continue; n++; const x = i % D.w, y = (i / D.w) | 0; setCelda(capa, x, y, v); if (x > 0) pila.push(i - 1); if (x < D.w - 1) pila.push(i + 1); if (y > 0) pila.push(i - D.w); if (y < D.h - 1) pila.push(i + D.w); }
  cerrarTrazo(); msg('Relleno de ' + n + ' casillas');
}

// ------------------------------------------------------------------------------------------ entidades
const LISTAS = { prop: () => D.props, camp: () => D.camps, edif: () => D.edifs, ciudad: () => D.ciudades };
function entEn(wx, wy) {
  const cx = wx / CELL, cy = wy / CELL;
  if (S.ver.props) { let b = null, bd = 1e9; for (const p of D.props) { const d = Math.hypot(p.x + .5 - cx, p.y + .5 - cy); if (d < (/montana/.test(p.tipo || '') ? 1.2 : .7) && d < bd) { bd = d; b = p; } } if (b) return { k: 'prop', o: b }; }
  if (S.ver.camps) for (const c of D.camps) if (Math.hypot(c.x - cx, c.y - cy) < .9) return { k: 'camp', o: c };
  if (S.ver.edifs) for (const e of D.edifs) if (cx >= e.x && cx <= e.x + e.w && cy >= e.y && cy <= e.y + e.h) return { k: 'edif', o: e };
  if (S.ver.ciudades) for (const c of D.ciudades) if (c.x != null && cx >= c.x && cx <= c.x + c.w && cy >= c.y && cy <= c.y + c.h) return { k: 'ciudad', o: c };
  return null;
}
const selTiene = (k, o) => [...S.sel].some(s => s.o === o);
function addEnts(lista) { lista.forEach(s => LISTAS[s.k]().push(s.o)); push({ undo() { lista.forEach(s => { const L = LISTAS[s.k](), i = L.indexOf(s.o); if (i >= 0) L.splice(i, 1); }); S.sel.clear(); }, redo() { lista.forEach(s => LISTAS[s.k]().push(s.o)); } }); redraw(); panelLight(); }
function delEnts(lista) {
  if (!lista.length) return; const pos = lista.map(s => ({ s, i: LISTAS[s.k]().indexOf(s.o) }));
  lista.forEach(s => { const L = LISTAS[s.k](), i = L.indexOf(s.o); if (i >= 0) L.splice(i, 1); }); S.sel.clear();
  push({ undo() { pos.slice().reverse().forEach(p => LISTAS[p.s.k]().splice(Math.max(0, p.i), 0, p.s.o)); }, redo() { lista.forEach(s => { const L = LISTAS[s.k](), i = L.indexOf(s.o); if (i >= 0) L.splice(i, 1); }); } }); redraw(); panelLight();
}
function mover(lista, dx, dy, reg = true) {
  const f = (s, sx, sy) => { const o = s.o; o.x += sx; o.y += sy; if (s.k === 'edif') { if (o.puertaX != null) { o.puertaX += sx; o.puertaY += sy; } } };
  lista.forEach(s => f(s, dx, dy)); if (reg) push({ undo() { lista.forEach(s => f(s, -dx, -dy)); }, redo() { lista.forEach(s => f(s, dx, dy)); } }); redraw();
}
function modEnt(o, props) { const antes = {}; for (const k in props) antes[k] = o[k]; Object.assign(o, props); for (const k in props) if (props[k] === undefined) delete o[k]; push({ undo() { for (const k in antes) { if (antes[k] === undefined) delete o[k]; else o[k] = antes[k]; } }, redo() { Object.assign(o, props); } }); redraw(); }
function nuevaProp(x, y) { return { tipo: S.prop, x, y }; }
function poner(cx, cy) { if (!inB(cx, cy)) return; addEnts([{ k: 'prop', o: nuevaProp(cx, cy) }]); }
let escNuevos = null;
function esparcir() {
  const d = drag; if (d.ultimo && Math.hypot(cur.x - d.ultimo.x, cur.y - d.ultimo.y) < S.radio * CELL * 0.6) return; d.ultimo = { x: cur.x, y: cur.y };
  for (let k = 0; k < S.densidad; k++) { const a = Math.random() * 6.283, r = Math.sqrt(Math.random()) * S.radio, x = Math.floor(cur.x / CELL + Math.cos(a) * r), y = Math.floor(cur.y / CELL + Math.sin(a) * r); if (!inB(x, y)) continue; const p = nuevaProp(x, y); d.nuevos.push({ k: 'prop', o: p }); D.props.push(p); }
}

// ------------------------------------------------------------------------------------------ entrada
let espacio = false; cv.addEventListener('contextmenu', e => e.preventDefault());
cv.addEventListener('wheel', e => { e.preventDefault(); const r = cv.getBoundingClientRect(); zoomEn(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top); }, { passive: false });
function act(e) { const w = aMundo(e); cur.x = w.x; cur.y = w.y; cur.cx = Math.floor(w.x / CELL); cur.cy = Math.floor(w.y / CELL); cur.sobre = true; }
cv.addEventListener('pointerdown', e => {
  if (!D) return; cv.setPointerCapture(e.pointerId); act(e);
  if (e.button === 1 || e.button === 2 || espacio || S.tool === 'mano') { drag = { pan: true, sx: e.clientX, sy: e.clientY, cx: cam.x, cy: cam.y }; return; }
  if (e.altKey) { gotero(); return; }
  const t = S.tool;
  if (t === 'pincel') { drag = { paint: true, last: { cx: cur.cx, cy: cur.cy } }; const v = valorActual(); disco(cur.cx, cur.cy, (x, y) => setCelda(S.capa, x, y, v)); }
  else if (t === 'rect') drag = { a: { cx: cur.cx, cy: cur.cy } };
  else if (t === 'cubo') relleno(cur.cx, cur.cy);
  else if (t === 'cuentagotas') gotero(true);
  else if (t === 'prop') { if (S.esparcir) { drag = { scatter: true, nuevos: [], ultimo: null }; esparcir(); } else poner(cur.cx, cur.cy); }
  else if (t === 'camp') { const c = JSON.parse(JSON.stringify(S.campTpl || { monstruo: 'seta_azul', cantidad: 4, radio: 4 })); c.x = cur.cx + .5; c.y = cur.cy + .5; addEnts([{ k: 'camp', o: c }]); }
  else if (t === 'portal') { const antes = D.resto.portal ? { ...D.resto.portal } : null, n = { x: cur.cx + .5, y: cur.cy + .5 }; D.resto.portal = n; push({ undo() { if (antes) D.resto.portal = antes; else delete D.resto.portal; }, redo() { D.resto.portal = n; } }); }
  else if (t === 'sel') {
    const s = entEn(cur.x, cur.y);
    if (s && selTiene(s.k, s.o) && !e.shiftKey) drag = { mover: true, px: cur.cx, py: cur.cy, tot: { x: 0, y: 0 }, fx: cur.x / CELL, fy: cur.y / CELL };
    else if (s && !e.shiftKey) { S.sel.clear(); S.sel.add(s); drag = { mover: true, px: cur.cx, py: cur.cy, tot: { x: 0, y: 0 } }; panelLight(); setTab('sel'); }
    else drag = { box: { x0: cur.x, y0: cur.y, x1: cur.x, y1: cur.y, add: e.shiftKey } };
  } else if (t === 'borrar') { drag = { borrar: true }; borrarEn(); }
  redraw();
});
cv.addEventListener('pointermove', e => {
  if (!D) return; act(e);
  if (drag && drag.pan) { cam.x = drag.cx - (e.clientX - drag.sx) / cam.z; cam.y = drag.cy - (e.clientY - drag.sy) / cam.z; redraw(); return; }
  if (drag && drag.paint) { const v = valorActual(); linea(drag.last, cur, (x, y) => disco(x, y, (a, b) => setCelda(S.capa, a, b, v))); drag.last = { cx: cur.cx, cy: cur.cy }; }
  else if (drag && drag.scatter) esparcir();
  else if (drag && drag.borrar) borrarEn();
  else if (drag && drag.mover) { const dx = cur.cx - drag.px, dy = cur.cy - drag.py; if (dx || dy) { mover([...S.sel], dx, dy, false); drag.tot.x += dx; drag.tot.y += dy; drag.px = cur.cx; drag.py = cur.cy; } }
  else if (drag && drag.box) { drag.box.x1 = cur.x; drag.box.y1 = cur.y; }
  tip(e); redraw();
});
cv.addEventListener('pointerup', e => {
  if (!D) return; act(e);
  if (drag && drag.pan) { drag = null; return; }
  if (drag && drag.paint) { cerrarTrazo(); drag = null; }
  else if (drag && drag.a && S.tool === 'rect') { const x0 = Math.min(drag.a.cx, cur.cx), x1 = Math.max(drag.a.cx, cur.cx), y0 = Math.min(drag.a.cy, cur.cy), y1 = Math.max(drag.a.cy, cur.cy), v = valorActual(); for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) setCelda(S.capa, x, y, v); cerrarTrazo(); drag = null; }
  else if (drag && drag.scatter) { const l = drag.nuevos; if (l.length) push({ undo() { l.forEach(s => { const i = D.props.indexOf(s.o); if (i >= 0) D.props.splice(i, 1); }); }, redo() { l.forEach(s => D.props.push(s.o)); } }); msg(l.length + ' props colocados'); drag = null; panelLight(); }
  else if (drag && drag.mover) { const t = drag.tot, l = [...S.sel]; if (t.x || t.y) push({ undo() { l.forEach(s => { s.o.x -= t.x; s.o.y -= t.y; if (s.k === 'edif' && s.o.puertaX != null) { s.o.puertaX -= t.x; s.o.puertaY -= t.y; } }); }, redo() { l.forEach(s => { s.o.x += t.x; s.o.y += t.y; if (s.k === 'edif' && s.o.puertaX != null) { s.o.puertaX += t.x; s.o.puertaY += t.y; } }); } }); drag = null; panelLight(); }
  else if (drag && drag.box) {
    const b = drag.box, x0 = Math.min(b.x0, b.x1) / CELL, x1 = Math.max(b.x0, b.x1) / CELL, y0 = Math.min(b.y0, b.y1) / CELL, y1 = Math.max(b.y0, b.y1) / CELL; if (!b.add) S.sel.clear();
    if (x1 - x0 < .2 && y1 - y0 < .2) { const s = entEn(b.x0, b.y0); if (s) { const ex = [...S.sel].find(q => q.o === s.o); if (ex && b.add) S.sel.delete(ex); else S.sel.add(s); } }
    else { if (S.ver.props) D.props.forEach(p => { if (p.x >= x0 && p.x <= x1 && p.y >= y0 && p.y <= y1) S.sel.add({ k: 'prop', o: p }); }); if (S.ver.camps) D.camps.forEach(p => { if (p.x >= x0 && p.x <= x1 && p.y >= y0 && p.y <= y1) S.sel.add({ k: 'camp', o: p }); }); if (S.ver.edifs) D.edifs.forEach(p => { if (p.x >= x0 && p.x <= x1 && p.y >= y0 && p.y <= y1) S.sel.add({ k: 'edif', o: p }); }); }
    drag = null; panelLight(); setTab('sel');
  } else if (drag && drag.borrar) drag = null; redraw();
});
cv.addEventListener('pointerleave', () => { cur.sobre = false; $('#tip').style.display = 'none'; redraw(); });
function borrarEn() { const r = S.size / 2; const q = []; for (const p of D.props) if (Math.hypot(p.x + .5 - cur.x / CELL, p.y + .5 - cur.y / CELL) <= r) q.push({ k: 'prop', o: p }); for (const c of D.camps) if (Math.hypot(c.x - cur.x / CELL, c.y - cur.y / CELL) <= r) q.push({ k: 'camp', o: c }); if (q.length) delEnts(q); }
function gotero(volver) { if (!inB(cur.cx, cur.cy)) return; const i = cur.cy * D.w + cur.cx; S.val.suelo = D.suelos[D.suelo[i]]; S.val.bioma = D.biomas[D.bioma[i]]; S.val.lado = D.lados[D.lado[i]]; S.val.bloque = D.bloque[i]; if (volver) setTool(S.prev === 'cuentagotas' ? 'pincel' : S.prev); panel(); msg('Tomado: ' + S.val.suelo + ' / ' + S.val.bioma); }
function tip(e) { const t = $('#tip'), w = aMundo(e), s = entEn(w.x, w.y); if (!s) { t.style.display = 'none'; return; } const o = s.o; const r = $('#cv').getBoundingClientRect(); t.style.display = 'block'; t.style.left = (e.clientX - r.left + 14) + 'px'; t.style.top = (e.clientY - r.top + 14) + 'px'; t.textContent = s.k + ' · ' + (o.tipo || o.monstruo || o.rotulo || o.nombre || o.id || '') + ` (${o.x},${o.y})`; }
mini.addEventListener('pointerdown', e => { if (!D) return; const go = ev => { const r = mini.getBoundingClientRect(), k = mini._k; if (!k) return; const mx = (ev.clientX - r.left) * mini.width / r.width, my = (ev.clientY - r.top) * mini.height / r.height; const wx = (mx - k.ox) / k.k * CELL, wy = (my - k.oy) / k.k * CELL; cam.x = wx - cv.width / (cam.z * devicePixelRatio) / 2; cam.y = wy - cv.height / (cam.z * devicePixelRatio) / 2; redraw(); }; go(e); mini.setPointerCapture(e.pointerId); mini.onpointermove = go; mini.onpointerup = () => { mini.onpointermove = null; }; });
let portap = [];
addEventListener('keydown', e => {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return; const k = e.key.toLowerCase();
  if (k === ' ') { espacio = true; e.preventDefault(); return; }
  if (e.ctrlKey && k === 'z') { e.preventDefault(); undo(); return; } if (e.ctrlKey && (k === 'y' || (e.shiftKey && k === 'z'))) { e.preventDefault(); redo(); return; }
  if (e.ctrlKey && k === 's') { e.preventDefault(); dialogoGuardar(); return; }
  if (e.ctrlKey && k === 'c') { portap = [...S.sel].map(s => ({ k: s.k, o: JSON.parse(JSON.stringify(s.o)) })); msg(portap.length + ' copiados'); return; }
  if (e.ctrlKey && k === 'v') { if (!D || !portap.length) return; const n = portap.map(s => { const o = JSON.parse(JSON.stringify(s.o)); o.x += 2; o.y += 2; if (o.puertaX != null) { o.puertaX += 2; o.puertaY += 2; } return { k: s.k, o }; }); portap = n.map(s => ({ k: s.k, o: JSON.parse(JSON.stringify(s.o)) })); addEnts(n); S.sel = new Set(n); panelLight(); return; }
  if (k === 'delete' || k === 'backspace') { if (S.sel.size) delEnts([...S.sel]); return; }
  if (k === 'escape') { drag = null; S.sel.clear(); panelLight(); redraw(); return; }
  if (S.sel.size && k.startsWith('arrow')) { const s = e.shiftKey ? 8 : 1, d = { arrowleft: [-s, 0], arrowright: [s, 0], arrowup: [0, -s], arrowdown: [0, s] }[k]; mover([...S.sel], d[0], d[1]); e.preventDefault(); panelLight(); return; }
  const map = { h: 'mano', b: 'pincel', r: 'rect', g: 'cubo', i: 'cuentagotas', p: 'prop', c: 'camp', v: 'sel', e: 'borrar' }; if (map[k] && !e.ctrlKey) { setTool(map[k]); return; }
  if (k === '[') { S.size = clamp(S.size - 1, 1, 60); panelLight(); } if (k === ']') { S.size = clamp(S.size + 1, 1, 60); panelLight(); }
});
addEventListener('keyup', e => { if (e.key === ' ') espacio = false; });

// ------------------------------------------------------------------------------------------ transitabilidad (suelo != agua y sin bloque; igual que Mapa.transitable)
function calcularTransitable() {
  const w = D.w, h = D.h, libre = new Uint8Array(w * h), ag = D.suelos.indexOf('agua');
  for (let i = 0; i < w * h; i++) libre[i] = (!D.bloque[i] && D.suelo[i] !== ag) ? 1 : 0;
  for (let x = 0; x < w; x++) { libre[x] = 0; libre[(h - 1) * w + x] = 0; } for (let y = 0; y < h; y++) { libre[y * w] = 0; libre[y * w + w - 1] = 0; }
  const comp = new Int32Array(w * h), tam = [0]; let n = 0;
  for (let i = 0; i < w * h; i++) if (libre[i] && !comp[i]) { n++; let c = 0; const p = [i]; comp[i] = n; while (p.length) { const k = p.pop(); c++; const x = k % w; if (x > 0 && libre[k - 1] && !comp[k - 1]) { comp[k - 1] = n; p.push(k - 1); } if (x < w - 1 && libre[k + 1] && !comp[k + 1]) { comp[k + 1] = n; p.push(k + 1); } if (k >= w && libre[k - w] && !comp[k - w]) { comp[k - w] = n; p.push(k - w); } if (k < w * (h - 1) && libre[k + w] && !comp[k + w]) { comp[k + w] = n; p.push(k + w); } } tam[n] = c; }
  const pt = D.resto.portal; let mayor = 1; if (pt && comp[Math.floor(pt.y) * w + Math.floor(pt.x)]) mayor = comp[Math.floor(pt.y) * w + Math.floor(pt.x)]; else for (let i = 1; i <= n; i++) if (tam[i] > tam[mayor]) mayor = i;
  const c = el('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'), d = g.createImageData(w, h);
  for (let i = 0; i < w * h; i++) { const col = !libre[i] ? null : comp[i] === mayor ? [60, 220, 120, 150] : [255, 200, 40, 190]; if (col) { d.data[i * 4] = col[0]; d.data[i * 4 + 1] = col[1]; d.data[i * 4 + 2] = col[2]; d.data[i * 4 + 3] = col[3]; } }
  g.putImageData(d, 0, 0); return { cv: c, comp, tam, mayor, libre, n };
}

// ------------------------------------------------------------------------------------------ herramientas y paneles
const TOOLS = [['mano', '✋', 'Mano (H)'], ['pincel', '🖌', 'Pincel de capa (B)'], ['rect', '▭', 'Rectangulo (R)'], ['cubo', '🪣', 'Relleno (G)'], ['cuentagotas', '💧', 'Cuentagotas (I)'], ['prop', '🌲', 'Colocar prop (P)'], ['camp', '🐺', 'Campamento (C)'], ['sel', '⬚', 'Seleccionar (V)'], ['portal', '🌀', 'Portal'], ['borrar', '🗑', 'Borrar (E)']];
function buildTools() { const t = $('#tools'); t.innerHTML = ''; for (const [id, ic, n] of TOOLS) { const b = el('button', { className: 'btn' + (S.tool === id ? ' on' : ''), title: n }, `<span>${ic}</span>${n.split(' (')[0]}`); b.onclick = () => setTool(id); t.append(b); } }
function setTool(id) { if (S.tool !== id) { S.prev = S.tool; S.tool = id; } drag = null; buildTools(); const t = { pincel: 'pincel', rect: 'pincel', cubo: 'pincel', prop: 'props', camp: 'camps', sel: 'sel' }[id]; if (t) setTab(t); redraw(); }
const TABS = [['pincel', 'Capas'], ['props', 'Props'], ['camps', 'Campam.'], ['sel', 'Seleccion'], ['ver', 'Ver'], ['mapa', 'Mapa'], ['validar', 'Validar']];
function buildTabs() { const t = $('#tabs'); t.innerHTML = ''; for (const [id, n] of TABS) { const b = el('button', { className: 'btn' + (S.tab === id ? ' on' : '') }, n); b.dataset.tab = id; b.onclick = () => setTab(id); t.append(b); } }
function setTab(id) { S.tab = id; document.querySelectorAll('#tabs .btn').forEach(b => b.classList.toggle('on', b.dataset.tab === id)); panel(); }
function panelLight() { if (['sel', 'mapa'].includes(S.tab)) panel(); }
function slider(p, txt, min, max, val, fn) { const r = el('div', { className: 'row' }, `<span class="mu">${txt}</span>`); const i = el('input', { type: 'range', min, max, value: val }); const v = el('span', {}, String(val)); i.oninput = () => { v.textContent = i.value; fn(+i.value); }; r.append(i, v); p.append(r); }
function panel() {
  const p = $('#panel'); p.innerHTML = ''; if (!D) { p.innerHTML = '<div class="mu">Abre un mapa primero.</div>'; return; }
  ({ pincel: tabCapas, props: tabProps, camps: tabCamps, sel: tabSel, ver: tabVer, mapa: tabMapa, validar: tabValidar })[S.tab](p);
}
function tabCapas(p) {
  p.append(el('div', { className: 'mu' }, 'Elige la capa y el valor. Pincel (B), rectangulo (R), relleno (G), cuentagotas (I o Alt+clic). [ y ] cambian el tamano.'));
  const r = el('div', { className: 'chips' }); for (const [id, n] of [['suelo', 'Suelo'], ['bioma', 'Bioma'], ['lado', 'Bando'], ['bloque', 'Bloqueo']]) { const b = el('button', { className: 'btn sm' + (S.capa === id ? ' on' : '') }, n); b.onclick = () => { S.capa = id; S.ver[id] = true; if (id === 'bioma') S.ver.bioma = true; panel(); redraw(); }; r.append(b); } p.append(r);
  p.append(el('h4', {}, 'Tamano y forma')); slider(p, 'tamano', 1, 60, S.size, v => { S.size = v; redraw(); });
  const f = el('div', { className: 'row' }); for (const [id, n] of [['circulo', 'Circulo'], ['cuadro', 'Cuadrado']]) { const b = el('button', { className: 'btn sm' + (S.forma === id ? ' on' : '') }, n); b.onclick = () => { S.forma = id; panel(); }; f.append(b); } p.append(f);
  p.append(el('h4', {}, 'Valor')); const c = el('div', { className: 'chips' });
  if (S.capa === 'bloque') { for (const [v, n] of [[1, 'Bloqueada'], [0, 'Libre']]) { const d = el('div', { className: 'chip' + (S.val.bloque === v ? ' on' : '') }, `<i style="background:${v ? '#e5484d' : 'transparent'}"></i>${n}`); d.onclick = () => { S.val.bloque = v; panel(); }; c.append(d); } }
  else { const lista = S.capa === 'suelo' ? D.suelos : S.capa === 'bioma' ? D.biomas : D.lados; const colf = S.capa === 'suelo' ? sueloCol : n => n === 'albor' ? '#ffd45a' : n === 'umbra' ? '#be5aff' : colHash(n); for (const n of lista) { const d = el('div', { className: 'chip' + (S.val[S.capa] === n ? ' on' : '') }, `<i style="background:${colf(n)}"></i>${n || '(ninguno)'}`); d.onclick = () => { S.val[S.capa] = n; panel(); }; c.append(d); } if (S.capa !== 'lado') { const nv = el('input', { type: 'text', placeholder: 'nuevo valor…' }); nv.onchange = () => { if (nv.value.trim()) { idx(S.capa === 'suelo' ? D.suelos : D.biomas, nv.value.trim()); S.val[S.capa] = nv.value.trim(); panel(); } }; c.append(nv); } }
  p.append(c);
  if (S.capa === 'suelo') p.append(el('div', { className: 'mu', style: 'margin-top:8px' }, 'Nota: "agua" no es transitable en el juego (Mapa.transitable). Para colocar tierra firme usa arena, hierba, etc.; para obstaculos usa la capa Bloqueo.'));
}
function conteoProps() { const c = {}; D.props.forEach(q => c[q.tipo] = (c[q.tipo] || 0) + 1); return c; }
function tabProps(p) {
  p.append(el('div', { className: 'mu' }, 'P: clic coloca; con "esparcir" pinta bosques arrastrando. Supr borra la seleccion. E = borrador de radio.'));
  const r = el('div', { className: 'row' }); const ce = el('label', {}, '<input type="checkbox"> esparcir'); ce.querySelector('input').checked = S.esparcir; ce.querySelector('input').onchange = ev => { S.esparcir = ev.target.checked; panel(); }; r.append(ce); p.append(r);
  if (S.esparcir) { slider(p, 'cantidad por trazo', 1, 20, S.densidad, v => S.densidad = v); slider(p, 'radio (casillas)', 1, 30, S.radio, v => { S.radio = v; redraw(); }); }
  const nv = el('div', { className: 'row' }, '<span class="mu">tipo nuevo</span>'); const i = el('input', { type: 'text', placeholder: 'ej. arbol_pino' }); i.onchange = () => { if (i.value.trim()) { S.prop = i.value.trim(); panel(); } }; nv.append(i); p.append(nv);
  p.append(el('h4', {}, 'Tipos (' + Object.keys(conteoProps()).length + ')')); const c = el('div', { className: 'chips' });
  for (const [t, n] of Object.entries(conteoProps()).sort((a, b) => b[1] - a[1])) { const d = el('div', { className: 'chip' + (S.prop === t ? ' on' : '') }, `<i style="background:${PROPCOL(t)}"></i>${t} <span class="mu">${n}</span>`); d.onclick = () => { S.prop = t; setTool('prop'); panel(); }; c.append(d); } p.append(c);
}
function tabCamps(p) {
  p.append(el('div', { className: 'mu' }, 'C: clic coloca un campamento con la plantilla. Un campamento hace aparecer "cantidad" criaturas del tipo "monstruo" en un radio.'));
  const t = S.campTpl || (S.campTpl = { monstruo: 'seta_azul', cantidad: 4, radio: 4 });
  for (const k of ['monstruo', 'cantidad', 'radio', 'ciudad']) { const r = el('div', { className: 'row' }, `<span class="mu" style="width:70px">${k}</span>`); const i = el('input', { type: k === 'monstruo' || k === 'ciudad' ? 'text' : 'number', value: t[k] ?? '' }); i.onchange = () => { t[k] = k === 'monstruo' || k === 'ciudad' ? (i.value || undefined) : +i.value; if (t[k] === undefined) delete t[k]; redraw(); }; r.append(i); p.append(r); }
  const jf = el('label', { className: 'row' }, '<input type="checkbox"> jefe'); jf.querySelector('input').checked = !!t.jefe; jf.querySelector('input').onchange = ev => { if (ev.target.checked) t.jefe = true; else delete t.jefe; }; p.append(jf);
  // catalogo completo de criaturas del juego (compartido/datos/monstruos.xml), con buscador y filtro por nivel
  p.append(el('h4', {}, 'Todas las criaturas del juego'));
  if (!MONS) { p.append(el('div', { className: 'mu' }, 'Cargando criaturas…')); api('/api/dc/monstruos').then(l => { MONS = l; if (S.tab === 'camps') panel(); }).catch(() => { MONS = []; }); }
  else {
    const q = el('input', { type: 'text', placeholder: 'buscar criatura, bioma o nivel…', value: S.qMons || '', style: 'width:100%' }); q.oninput = () => { S.qMons = q.value; pintarMons(); }; p.append(q);
    const caja = el('div', { className: 'chips', style: 'margin-top:6px;max-height:300px;overflow:auto' }); p.append(caja);
    const pintarMons = () => {
      caja.innerHTML = ''; const s = (S.qMons || '').toLowerCase();
      MONS.filter(m => !s || (m.id + ' ' + m.nombre + ' ' + m.bioma + ' nivel ' + m.nivel + (m.jefe ? ' jefe' : '')).toLowerCase().includes(s)).sort((a, b) => a.nivel - b.nivel).forEach(m => {
        const d = el('div', { className: 'chip' + (t.monstruo === m.id ? ' on' : ''), title: `${m.id} · nivel ${m.nivel} · ${m.bioma}${m.jefe ? ' · jefe/elite' : ''}` }, `<i style="background:${colHash(m.id)}"></i>${m.nombre} <span class="mu">Nv ${m.nivel}${m.jefe ? ' ★' : ''}</span>`);
        d.onclick = () => { t.monstruo = m.id; if (m.jefe) t.jefe = true; else delete t.jefe; setTool('camp'); panel(); }; caja.append(d);
      });
    }; pintarMons();
  }
  p.append(el('h4', {}, 'Criaturas usadas en este mapa')); const cnt = {}; D.camps.forEach(c => cnt[c.monstruo] = (cnt[c.monstruo] || 0) + 1); const ch = el('div', { className: 'chips' });
  for (const [m, n] of Object.entries(cnt).sort((a, b) => b[1] - a[1])) { const d = el('div', { className: 'chip' + (t.monstruo === m ? ' on' : '') }, `<i style="background:${colHash(m)}"></i>${m} <span class="mu">${n}</span>`); d.onclick = () => { t.monstruo = m; setTool('camp'); panel(); }; ch.append(d); } p.append(ch);
}
function inspector(p, o, k) {
  const campos = Object.keys(o); const f = el('div'); p.append(f);
  for (const c of campos) {
    const v = o[c]; const r = el('div', { className: 'row' }, `<span class="mu" style="width:84px;overflow:hidden">${c}</span>`);
    if (typeof v === 'number' || typeof v === 'string') { const i = el('input', { type: typeof v === 'number' ? 'number' : 'text', value: v, style: typeof v === 'string' ? 'flex:1' : '' }); if (typeof v === 'number') i.step = 'any'; i.onchange = () => modEnt(o, { [c]: typeof v === 'number' ? +i.value : i.value }); r.append(i); }
    else if (typeof v === 'boolean') { const i = el('input', { type: 'checkbox', checked: v }); i.onchange = () => modEnt(o, { [c]: i.checked }); r.append(i); }
    else { const ta = el('textarea', { className: 'json', value: JSON.stringify(v), style: 'height:48px;flex:1' }); ta.onchange = () => { try { modEnt(o, { [c]: JSON.parse(ta.value) }); ta.style.borderColor = ''; } catch (e) { ta.style.borderColor = '#e86a6a'; } }; r.append(ta); }
    f.append(r);
  }
  const nr = el('div', { className: 'row' }); const nk = el('input', { type: 'text', placeholder: 'campo nuevo' }), nvv = el('input', { type: 'text', placeholder: 'valor (JSON)' }); const b = el('button', { className: 'btn sm' }, '+'); b.onclick = () => { if (!nk.value) return; let v = nvv.value; try { v = JSON.parse(v); } catch (e) { } modEnt(o, { [nk.value]: v }); panel(); }; nr.append(nk, nvv, b); p.append(nr);
}
function tabSel(p) {
  p.append(el('div', { className: 'mu' }, 'V: clic o caja para seleccionar (Shift suma), arrastra para mover (los edificios llevan su puerta), flechas, Supr, Ctrl+C/V.'));
  const l = [...S.sel]; p.append(el('h4', {}, l.length + ' seleccionados')); if (!l.length) return;
  const cnt = {}; l.forEach(s => { const q = s.k + ' ' + (s.o.tipo || s.o.monstruo || s.o.rotulo || s.o.nombre || ''); cnt[q] = (cnt[q] || 0) + 1; }); p.append(el('div', {}, Object.entries(cnt).slice(0, 14).map(([k, n]) => `${n}× ${k}`).join('<br>')));
  const r = el('div', { className: 'row' }); const b1 = el('button', { className: 'btn sm' }, 'Borrar'); b1.onclick = () => delEnts(l); const b2 = el('button', { className: 'btn sm' }, 'Duplicar'); b2.onclick = () => { const n = l.map(s => { const o = JSON.parse(JSON.stringify(s.o)); o.x += 2; o.y += 2; if (o.puertaX != null) { o.puertaX += 2; o.puertaY += 2; } return { k: s.k, o }; }); addEnts(n); S.sel = new Set(n); panel(); }; r.append(b1, b2);
  if (l.every(s => s.k === 'prop')) { const sel = el('select'); Object.keys(conteoProps()).forEach(t => sel.append(el('option', { value: t }, t))); const b3 = el('button', { className: 'btn sm' }, 'Cambiar tipo'); b3.onclick = () => { l.forEach(s => modEnt(s.o, { tipo: sel.value })); panel(); }; r.append(sel, b3); } p.append(r);
  if (l.length === 1) inspector(p, l[0].o, l[0].k);
}
function tabVer(p) { for (const [k, n] of [['suelo', 'Suelo'], ['bioma', 'Biomas (color)'], ['lado', 'Bandos (albor/umbra)'], ['bloque', 'Casillas bloqueadas'], ['transitable', 'Transitable (verde = zona del portal, amarillo = aislada)'], ['props', 'Props'], ['camps', 'Campamentos'], ['edifs', 'Edificios'], ['ciudades', 'Ciudades'], ['otros', 'Puestos, jefes, puertos, NPC, escaleras, mazmorras y portal'], ['cuadricula', 'Cuadricula (al acercar)']]) { const l = el('label', { className: 'row' }, `<input type="checkbox"> ${n}`); const c = l.querySelector('input'); c.checked = S.ver[k]; c.onchange = () => { S.ver[k] = c.checked; walkCv = null; redraw(); }; p.append(l); } }
function tabMapa(p) {
  p.append(el('div', {}, `<b>${D.nombre}</b><br>${D.w} × ${D.h} casillas<br>${D.props.length} props · ${D.camps.length} campamentos · ${D.edifs.length} edificios · ${D.ciudades.length} ciudades<br>suelos: ${D.suelos.join(', ')}<br>biomas: ${D.biomas.join(', ')}<br>bandos: ${D.lados.map(x => x || '(ninguno)').join(', ')}`));
  p.append(el('h4', {}, 'Otros datos del mapa (se conservan al exportar)')); p.append(el('div', { className: 'mu' }, Object.entries(D.resto).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.length + ' elementos' : typeof v === 'object' ? Object.keys(v).length + ' claves' : v}`).join('<br>')));
  p.append(el('h4', {}, 'Nombre al exportar')); const nm = el('input', { type: 'text', value: D.nombre, style: 'width:100%' }); nm.onchange = () => { D.nombre = nm.value.replace(/[^0-9A-Za-z_\-]/g, '') || 'mapa'; $('#titulo').textContent = D.nombre; }; p.append(nm);
  p.append(el('h4', {}, 'Otros datos'));
  const sel = el('select'); Object.keys(D.resto).forEach(k => sel.append(el('option', { value: k }, k))); p.append(sel); const ta = el('textarea', { className: 'json', style: 'height:220px', spellcheck: false }); p.append(ta); const show = () => { ta.value = JSON.stringify(D.resto[sel.value], null, 1).slice(0, 60000); }; sel.onchange = show; show();
  const b = el('button', { className: 'btn sm' }, 'Aplicar JSON'); const st = el('span', { className: 'mu' }); b.onclick = () => { try { const v = JSON.parse(ta.value), k = sel.value, a = D.resto[k]; D.resto[k] = v; push({ undo() { D.resto[k] = a; }, redo() { D.resto[k] = v; } }); st.textContent = 'aplicado'; st.className = 'ok'; redraw(); } catch (e) { st.textContent = 'JSON no valido'; st.className = 'mal'; } }; p.append(b, st);
}
function tabValidar(p) {
  const b = el('button', { className: 'btn' }, 'Revisar el mapa'); const out = el('div'); p.append(b, out);
  b.onclick = () => {
    const res = [], add = (n, t, x, y) => res.push({ n, t, x, y }); const T = calcularTransitable(), w = D.w;
    const tot = T.libre.reduce((a, v) => a + v, 0); add('ok', `Transitable: ${tot} casillas (${(100 * tot / (D.w * D.h)).toFixed(0)}%), ${T.n} zonas conectadas.`);
    const pt = D.resto.portal; if (!pt) add('av', 'No hay portal definido.'); else if (!T.libre[Math.floor(pt.y) * w + Math.floor(pt.x)]) add('mal', 'El portal esta en una casilla no transitable', pt.x, pt.y);
    let malC = 0, aisl = 0; for (const c of D.camps) { const i = Math.floor(c.y) * w + Math.floor(c.x); if (!inB(Math.floor(c.x), Math.floor(c.y)) || !T.libre[i]) { malC++; if (malC === 1) add('mal', 'Campamento sobre casilla no transitable (' + c.monstruo + ')', c.x, c.y); } else if (T.comp[i] !== T.mayor) aisl++; }
    if (malC) add('mal', malC + ' campamentos sobre casillas no transitables'); if (aisl) add('av', aisl + ' campamentos en zonas aisladas del portal');
    let fuera = D.props.filter(q => !inB(q.x, q.y)); if (fuera.length) add('mal', fuera.length + ' props fuera del mapa', fuera[0].x, fuera[0].y);
    for (const e of D.edifs) { if (e.puertaX != null && !T.libre[e.puertaY * w + e.puertaX]) { add('av', 'Puerta de edificio sin acceso (' + (e.rotulo || e.tienda || '') + ')', e.puertaX, e.puertaY); break; } }
    for (const c of D.ciudades) { if (c.x == null) continue; const ok = c.puerta ? true : true; }
    let agua = 0; D.edifs.forEach(e => { if (D.suelos[D.suelo[e.y * w + e.x]] === 'agua') agua++; }); if (agua) add('av', agua + ' edificios sobre agua');
    out.innerHTML = ''; for (const r of res) { const d = el('div', { className: 'row ' + r.n }, (r.n === 'ok' ? '✔ ' : r.n === 'mal' ? '✖ ' : '⚠ ') + r.t); if (r.x != null) { d.style.cursor = 'pointer'; d.onclick = () => { cam.z = Math.max(cam.z, 1); cam.x = r.x * CELL - cv.width / cam.z / devicePixelRatio / 2; cam.y = r.y * CELL - cv.height / cam.z / devicePixelRatio / 2; redraw(); }; } out.append(d); }
  }; b.click();
}

// ------------------------------------------------------------------------------------------ archivo
function modal(h) { $('#modalbox').innerHTML = h; $('#modal').style.display = 'flex'; } function cerrar() { $('#modal').style.display = 'none'; }
$('#modal').addEventListener('pointerdown', e => { if (e.target === $('#modal')) cerrar(); });
async function dialogoAbrir() {
  const l = await api('/api/dc/lista');
  modal('<h3 style="margin:0 0 8px">Abrir mapa de Dos Coronas</h3><div id="ml"></div><div class="row"><button class="btn" id="bv">Volcar de nuevo los mapas del juego</button><button class="btn" id="bx">Cerrar</button></div><div class="mu" id="mm"></div>');
  $('#bx').onclick = cerrar; const ml = $('#ml');
  const grupo = (t, arr, o) => { if (!arr.length) return; ml.append(el('h4', {}, t)); const g = el('div', { className: 'row' }); arr.forEach(n => { const b = el('button', { className: 'btn' }, n); b.onclick = () => abrir(o, n); g.append(b); }); ml.append(g); };
  grupo('Editados por ti (dc_editados\\)', l.editados, 'editado'); grupo('Mapas actuales del juego (volcados)', l.volcados, 'volcado'); if (!l.volcados.length) ml.append(el('div', { className: 'mal' }, 'Todavia no hay mapas volcados: pulsa "Volcar".'));
  $('#bv').onclick = volcar; $('#mm').textContent = l.dc ? '' : 'No encuentro el proyecto Dos Coronas (variable DOS_CORONAS).';
}
async function volcar() { msg('Volcando los mapas del juego con LOVE…'); try { const r = await api('/api/dc/volcar'); msg(r.ok ? 'Volcado hecho.' : 'Error: ' + (r.error || r.salida), r.ok ? 'ok' : 'mal'); if (r.ok) dialogoAbrir(); } catch (e) { msg(e.message, 'mal'); } }
$('#bVolcar').onclick = volcar;
async function abrir(origen, n) { cerrar(); msg('Abriendo ' + n + '… (el mundo pesa 16 MB)'); try { const j = await api(`/api/dc/abrir?o=${origen}&n=${encodeURIComponent(n)}`); cargar(j, n); } catch (e) { msg('No se pudo abrir: ' + e.message, 'mal'); } }
$('#bAbrir').onclick = () => { if (!dirty || confirm('Hay cambios sin guardar. ¿Abrir otro?')) dialogoAbrir(); };
function dialogoGuardar() {
  if (!D) return; modal(`<h3 style="margin:0 0 8px">Guardar / exportar</h3><div class="row"><span class="mu">nombre</span><input id="gn" type="text" value="${D.nombre}"></div><div class="mu">Escribe dc_editados\\NOMBRE.json (capas en RLE, para volver a abrirlo) y dc_editados\\NOMBRE.lua (tabla "return { … }" lista para cargar desde el juego con dofile/require). Las capas de casillas van en RLE.</div><div class="row"><button class="btn on" id="gok">Guardar</button><button class="btn" id="gc">Cancelar</button></div><pre id="gout" style="white-space:pre-wrap;font-size:11px"></pre>`);
  $('#gc').onclick = cerrar; $('#gok').onclick = async () => { $('#gout').textContent = 'Guardando…'; try { D.nombre = $('#gn').value.replace(/[^0-9A-Za-z_\-]/g, '') || D.nombre; const r = await api('/api/dc/guardar?n=' + encodeURIComponent(D.nombre), { method: 'POST', body: JSON.stringify(aJson()) }); setDirty(false); $('#gout').textContent = `OK\n${r.json}\n${r.lua} (${(r.bytes / 1024).toFixed(0)} KB)`; msg('Guardado ' + D.nombre, 'ok'); } catch (e) { $('#gout').textContent = e.message; } };
}
$('#bGuardar').onclick = dialogoGuardar;
addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
iniciar();
