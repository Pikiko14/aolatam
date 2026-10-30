'use strict';
/* Eventos del mapa en español: constructor visual de la logica de un .mpc (disparadores, condiciones, acciones).
   Lee y escribe el mismo XML de FAO que M.eventos; lo que no entiende (ALIAS, DEFINE, atributos raros) se conserva.
   Se carga despues de editor.js y usa sus globales (M, el, push, panelRefresh, msg, S). */

// ---------------------------------------------------------------------------------------------------- catalogo
const EV_COMPARA = [[0, '='], [1, '<'], [2, '>'], [3, '≤'], [4, '≥'], [5, '≠']];
const EV_MODOS = {
  0: 'Automático (el servidor lo revisa solo)', 1: 'Al pisar la casilla', 2: 'Al hacer clic en el objeto o NPC', 3: 'Al caminar sobre el objeto',
  4: 'Al morir un grupo de monstruos', 5: 'Cada cierto tiempo', 6: 'Clic (versión alma)', 7: 'Al mirarlo', 8: 'Pisar (versión alma)',
  9: 'Caminar (versión alma)', 10: 'Al crearse el objeto', 11: 'Al morir un monstruo', 12: 'Al recolectar', 13: 'Al recolectar (grupo)',
};
const EV_PARES = Array.from({ length: 10 }, (_, i) => (i % 2 ? 'Cantidad ' : 'Objeto ') + (1 + (i >> 1)));
// [nombre, [etiquetas de parametros]]. Una etiqueta que empieza por "Comparar" se elige de una lista (=, <, >...).
const EV_ACC_ES = {
  1: ['Detener (no ejecutar lo que sigue)', []],
  3: ['Ir a otro mapa', ['Mapa (número)', 'Punto de llegada (tag)']],
  4: ['Poner el paso de una misión', ['Misión (número)', 'Paso (empieza en 0)']],
  7: ['Sumar a un atributo', ['Atributo (0 vida, 2 maná, 4 SP, 29 nivel, 32 experiencia)', 'Cantidad']],
  8: ['Fijar un atributo', ['Atributo (0 vida, 2 maná, 4 SP, 29 nivel, 32 experiencia)', 'Valor']],
  9: ['Quitar objetos', EV_PARES], 10: ['Dar objetos', EV_PARES], 51: ['Dar objetos (diario)', EV_PARES], 81: ['Dar objetos atados', EV_PARES],
  12: ['Mostrar premios', EV_PARES], 13: ['Elegir un premio', EV_PARES],
  14: ['Abrir una tienda', ['Tienda (número)']], 18: ['Abrir fabricación', ['Estación (número)']],
  19: ['Dar oro', ['Oro']], 20: ['Quitar oro', ['Oro']], 22: ['Abrir el banco', ['Tipo (0 personal, 1 liga)']],
  24: ['Cerrar el diálogo', []], 25: ['Abrir un diálogo del mapa', ['Diálogo (número)']],
  29: ['Cambiar de facción', ['Facción']], 30: ['Mandar una nota', ['Mensaje (número de msg.xml)']],
  31: ['Generar monstruos de una zona', ['Zona (tag)', 'Posición (0 generador, 1 objeto)']],
  33: ['Encender o apagar una zona', ['Zona (tag)', 'Estado (1 encender, 0 apagar)']],
  36: ['Crear un tesoro', ['Tesoro (número)']], 39: ['Volver al punto de reaparición', []],
  41: ['Contar bajas para avanzar la misión', ['Misión (número)', 'Paso (desde 0)', 'Objeto oculto que cuenta', 'Suma por baja', 'Probabilidad %', 'Total para completar']],
  42: ['Soltar objeto de misión', ['Misión', 'Paso', 'Objeto', 'Cantidad', 'Probabilidad %', 'Máximo']],
  47: ['Elegir un premio (extendido)', EV_PARES], 50: ['Ir a la región de la liga', []],
  52: ['Cambiar un objeto estático', ['Tag', 'Objeto (número)']], 53: ['Ir a un punto del mapa', ['Punto (tag)']],
  54: ['Lanzar una magia', ['Magia (número)', 'Objetivo (0 el que dispara, 1 el grupo, 2 el lanzador)', 'Extra']],
  55: ['Decir en el chat', ['Tipo', 'Mensaje 1', 'Mensaje 2', 'Mensaje 3', 'Mensaje 4', 'Mensaje 5']],
  56: ['Fijar variable del mapa', ['Mapa', 'Variable', 'Valor']], 57: ['Sumar a variable del mapa', ['Mapa', 'Variable', 'Valor']],
  104: ['Restar a variable del mapa', ['Mapa', 'Variable', 'Valor']],
  60: ['Encender un temporizador', ['Temporizador (tag)', 'Activar (1) / parar (0)', 'Extra']],
  67: ['Soltar un botín', ['Botín (número)']], 72: ['Cambiar de evento', ['Evento (número)']], 37: ['Ir a un mapa paralelo', ['Mapa', 'Paralelo', 'Punto (tag)']],
  16: ['Revivir aquí', ['Tipo']], 63: ['Carrera de bajas (1 empieza, 0 termina)', ['Estado']], 78: ['Un NPC dice', ['Mensaje 1', 'Mensaje 2', 'Mensaje 3', 'Mensaje 4', 'Mensaje 5']],
};
const EV_COND_ES = {
  1: ['Sexo', ['Comparar', 'Sexo (0 / 1)']], 2: ['La misión está en el paso', ['Misión (número)', 'Paso (empieza en 0)']],
  3: ['Atributo del jugador', ['Atributo (29 nivel, 51 rango)', 'Comparar', 'Valor']], 4: ['Nivel de una habilidad', ['Habilidad', 'Comparar', 'Nivel']],
  5: ['Objeto equipado', ['Objeto', 'Comparar', 'Cantidad']], 6: ['Objeto en la mochila', ['Objeto', 'Comparar', 'Cantidad']],
  7: ['Objeto de misión', ['Objeto', 'Comparar', 'Cantidad']], 8: ['Huecos libres en la mochila', ['Comparar', 'Huecos']],
  10: ['Probabilidad', ['Probabilidad %']], 11: ['Misión terminada', ['Misión (número)']], 12: ['Facción', ['Facción']],
  13: ['Misión en curso', ['Misión (número)']], 14: ['Monstruos vivos de una zona', ['Zona (tag)', 'Comparar', 'Cantidad']],
  15: ['Zona encendida', ['Zona (tag)', 'Comparar', 'Estado (1 encendida)']], 16: ['Es el dueño del tesoro', []],
  17: ['Oro del jugador', ['Comparar', 'Oro']], 20: ['Es GM', []], 21: ['Tiene liga', []], 28: ['Tiene región de liga', []],
  29: ['Variable del mapa', ['Mapa', 'Variable', 'Comparar', 'Valor']], 30: ['Temporizador encendido', ['Temporizador', 'Comparar', 'Estado']],
  31: ['Veces que sonó el temporizador', ['Temporizador', 'Comparar', 'Veces']], 39: ['Grupo', ['Qué', 'Comparar', 'Valor']], 56: ['Está vivo', []],
};
const evNombreAcc = n => (EV_ACC_ES[n] ? EV_ACC_ES[n][0] : (EV_ACC_EN[n] || ('Acción ' + n)) + ' (sin traducir)');
const evNombreCond = n => (EV_COND_ES[n] ? EV_COND_ES[n][0] : (EV_COND_EN[n] || ('Condición ' + n)) + ' (sin traducir)');
const evEtq = (tabla, n, i) => ((tabla[n] || [])[1] || [])[i] || ('Parámetro ' + (i + 1));
const evNumParams = (tabla, n) => ((tabla[n] || [])[1] || []).length;

// ---------------------------------------------------------------------------------------------------- modelo
function evParsear(xml) {
  const d = new DOMParser().parseFromString(xml || '<root/>', 'application/xml');
  if (d.querySelector('parsererror')) return null;
  const ser = new XMLSerializer();
  const otros = [...d.documentElement.children].filter(e => !['事件', 'head'].includes(e.tagName)).map(e => ser.serializeToString(e).replace(/ xmlns="[^"]*"/g, ''));
  const eventos = [...d.querySelectorAll('root > 事件')].map(e => ({
    id: +e.getAttribute('編號') || 0, cursor: +e.getAttribute('游標') || 0, extra: e.getAttribute('只在客戶端') ? 1 : 0,
    trig: [...e.children].filter(t => t.tagName === '觸發器').map(t => ({
      modo: +t.getAttribute('觸發') || 0, veces: +t.getAttribute('次數') || 0, basta: !!t.querySelector(':scope > 旗標'),
      cond: [...t.children].filter(c => c.tagName === '條件').map(c => ({ n: +c.getAttribute('編號'), neg: c.getAttribute('反向') === '1', p: [...c.children].filter(q => q.tagName === '參數').map(q => +q.getAttribute('數值') || 0) })),
      acc: [...t.children].filter(c => c.tagName === '動作').map(c => ({ n: +c.getAttribute('編號'), p: [...c.children].filter(q => q.tagName === '參數').map(q => +q.getAttribute('數值') || 0) })),
    })),
  }));
  return { eventos, otros };
}
function evSerializar(mod) {
  const L = ['<?xml version="1.0" encoding="UTF-8" ?>', '<root>', '\t<head version="1.0"/>'];
  const par = p => p.map(v => `\t\t\t\t<參數 數值="${v | 0}"/>`);
  for (const e of mod.eventos) {
    L.push(`\t<事件 編號="${e.id}" 游標="${e.cursor}" 觸發器="${e.trig.length}">`);
    e.trig.forEach((t, i) => {
      L.push(`\t\t<觸發器 編號="${i}" 觸發="${t.modo}" 次數="${t.veces}"${t.cond.length ? ` 條件="${t.cond.length}"` : ''}${t.acc.length ? ` 動作="${t.acc.length}"` : ''}>`);
      if (t.basta) L.push('\t\t\t<旗標 一項成立算成立=""/>');
      for (const c of t.cond) { L.push(`\t\t\t<條件 編號="${c.n}"${c.neg ? ' 反向="1"' : ''}>`, ...par(c.p), '\t\t\t</條件>'); }
      for (const a of t.acc) { L.push(`\t\t\t<動作 編號="${a.n}">`, ...par(a.p), '\t\t\t</動作>'); }
      L.push('\t\t</觸發器>');
    });
    L.push('\t</事件>');
  }
  for (const o of mod.otros) L.push('\t' + o);
  L.push('</root>', '');
  return L.join('\n');
}

// ---------------------------------------------------------------------------------------------------- plantillas
function evIdLibre(mod) { return mod.eventos.reduce((m, e) => Math.max(m, e.id), 0) + 1; }
const EV_PLANTILLAS = [
  ['Salida a otro mapa (al caminar encima)', mod => ({ id: evIdLibre(mod), cursor: 0, extra: 0, trig: [{ modo: 3, veces: 0, basta: false, cond: [], acc: [{ n: 3, p: [41, 1] }] }] })],
  ['Dar un objeto al hacer clic', mod => ({ id: evIdLibre(mod), cursor: 0, extra: 0, trig: [{ modo: 2, veces: 0, basta: false, cond: [{ n: 8, neg: false, p: [4, 1] }], acc: [{ n: 10, p: [0, 1, 0, 0, 0, 0, 0, 0, 0, 0] }] }] })],
  ['Dar oro al hacer clic', mod => ({ id: evIdLibre(mod), cursor: 0, extra: 0, trig: [{ modo: 2, veces: 0, basta: false, cond: [], acc: [{ n: 19, p: [1000] }] }] })],
  ['Cobrar oro y dar un objeto', mod => ({ id: evIdLibre(mod), cursor: 0, extra: 0, trig: [{ modo: 2, veces: 0, basta: false, cond: [{ n: 17, neg: false, p: [4, 1000] }, { n: 8, neg: false, p: [4, 1] }], acc: [{ n: 20, p: [1000] }, { n: 10, p: [0, 1, 0, 0, 0, 0, 0, 0, 0, 0] }] }] })],
  ['Abrir una tienda al hacer clic', mod => ({ id: evIdLibre(mod), cursor: 0, extra: 0, trig: [{ modo: 2, veces: 0, basta: false, cond: [], acc: [{ n: 14, p: [1] }] }] })],
  ['Misión: el paso 1 se cumple al matar N monstruos', mod => {
    const id = evIdLibre(mod), q = 9000 + id;
    return { id, cursor: 0, extra: 0, trig: [{ modo: 11, veces: 0, basta: false, cond: [{ n: 2, neg: false, p: [q, 0] }], acc: [{ n: 41, p: [q, 0, 497, 1, 100, 10] }] }] };
  }],
  ['Evento vacío', mod => ({ id: evIdLibre(mod), cursor: 0, extra: 0, trig: [{ modo: 2, veces: 0, basta: false, cond: [], acc: [] }] })],
];

// ---------------------------------------------------------------------------------------------------- interfaz
const EVU = { abiertos: new Set(), avanzado: false };

function evCommit(mod, antes) {
  const nuevo = evSerializar(mod);
  if (nuevo === antes) return;
  M.eventos = nuevo;
  push({ undo() { M.eventos = antes; }, redo() { M.eventos = nuevo; } });
  panelRefresh();
}

function evCampoParam(tabla, n, i, valor, alCambiar) {
  const etq = evEtq(tabla, n, i);
  const w = el('label', { className: 'row' }); w.style.cssText = 'gap:6px;margin:2px 0';
  w.append(el('span', { className: 'mu' }, etq));
  let c;
  if (etq.startsWith('Comparar')) {
    c = el('select'); for (const [v, t] of EV_COMPARA) c.append(new Option(t, v)); c.value = String(valor);
  } else { c = el('input', { type: 'number', value: valor }); c.style.width = '90px'; }
  c.onchange = () => alCambiar(+c.value | 0);
  w.append(c); return w;
}

function evBloqueFila(tabla, nombres, fila, tipo, alCambiar, alBorrar, soportados, hijoExtra) {
  const caja = el('div'); caja.style.cssText = 'border:1px solid var(--bd);border-radius:6px;padding:4px 6px;margin:4px 0;background:var(--p2)';
  const cab = el('div', { className: 'row' }); cab.style.margin = '0';
  const sel = el('select'); sel.style.maxWidth = '210px';
  const claves = [...new Set([...Object.keys(tabla).map(Number), ...Object.keys(tipo === 'acc' ? EV_ACC_EN : EV_COND_EN).map(Number), fila.n])].sort((a, b) => a - b);
  for (const k of claves) {
    const ok = soportados.includes(k);
    const o = new Option((ok ? '' : '⚠ ') + nombres(k), k); sel.append(o);
  }
  sel.value = String(fila.n);
  sel.onchange = () => { fila.n = +sel.value; fila.p = Array.from({ length: evNumParams(tabla, fila.n) }, () => 0); alCambiar(); };
  const x = el('button', { className: 'btn sm' }, '✕'); x.title = 'Quitar'; x.onclick = alBorrar;
  cab.append(sel, x); caja.append(cab);
  if (hijoExtra) caja.append(hijoExtra);
  const n = Math.max(evNumParams(tabla, fila.n), fila.p.length);
  for (let i = 0; i < n; i++) caja.append(evCampoParam(tabla, fila.n, i, fila.p[i] || 0, v => { fila.p[i] = v; alCambiar(); }));
  if (!soportados.includes(fila.n)) caja.append(el('div', { className: 'av' }, '⚠ El servidor todavía no ejecuta esto: se guarda en el mapa pero no hace nada.'));
  return caja;
}

function evTarjeta(p, mod, ev, antes) {
  const abierto = EVU.abiertos.has(ev.id);
  const cab = el('div', { className: 'att' + (abierto ? ' on' : '') });
  cab.innerHTML = `<b>Evento #${ev.id}</b><span class="mu">${ev.trig.length} disparador(es)</span>`;
  cab.onclick = () => { abierto ? EVU.abiertos.delete(ev.id) : EVU.abiertos.add(ev.id); panelRefresh(); };
  p.append(cab);
  if (!abierto) return;
  const caja = el('div'); caja.style.cssText = 'margin:0 0 8px 8px;border-left:2px solid var(--bd);padding-left:8px';
  const guardar = () => evCommit(mod, antes);
  const fid = el('div', { className: 'row' }, '<span class="mu">Número del evento</span>'); const ii = el('input', { type: 'number', value: ev.id });
  ii.onchange = () => { const v = +ii.value | 0; if (v > 0 && !mod.eventos.some(e => e !== ev && e.id === v)) { EVU.abiertos.delete(ev.id); ev.id = v; EVU.abiertos.add(v); guardar(); } else ii.value = ev.id; };
  fid.append(ii); caja.append(fid);
  ev.trig.forEach((t, ti) => {
    const tb = el('div'); tb.style.cssText = 'border:1px solid var(--ac);border-radius:8px;padding:6px;margin:6px 0';
    tb.append(el('h4', {}, `Disparador ${ti + 1}`));
    const rm = el('div', { className: 'row' }, '<span class="mu">Cuándo</span>'); const sm = el('select');
    for (const [k, v] of Object.entries(EV_MODOS)) sm.append(new Option(v, k)); sm.value = String(t.modo); sm.onchange = () => { t.modo = +sm.value; guardar(); };
    rm.append(sm); tb.append(rm);
    const rv = el('div', { className: 'row' }, '<span class="mu">Veces máx. (0 = siempre)</span>'); const iv = el('input', { type: 'number', value: t.veces }); iv.onchange = () => { t.veces = Math.max(0, +iv.value | 0); guardar(); };
    rv.append(iv); tb.append(rv);
    tb.append(el('h4', {}, 'Si… (condiciones)'));
    if (t.cond.length > 1) {
      const rb = el('label', { className: 'row' }); const cb = el('input', { type: 'checkbox', checked: t.basta }); cb.onchange = () => { t.basta = cb.checked; guardar(); };
      rb.append(cb, el('span', { className: 'mu' }, 'basta con que se cumpla UNA (si no, deben cumplirse todas)')); tb.append(rb);
    }
    t.cond.forEach((c, ci) => {
      const neg = el('label', { className: 'row' }); const cn = el('input', { type: 'checkbox', checked: c.neg }); cn.onchange = () => { c.neg = cn.checked; guardar(); };
      neg.append(cn, el('span', { className: 'mu' }, 'al revés (se cumple si NO pasa)'));
      tb.append(evBloqueFila(EV_COND_ES, evNombreCond, c, 'cond', guardar, () => { t.cond.splice(ci, 1); guardar(); }, EV_COND_SERV, neg));
    });
    const bc = el('button', { className: 'btn sm' }, '+ Condición'); bc.onclick = () => { t.cond.push({ n: 2, neg: false, p: [0, 0] }); guardar(); }; tb.append(bc);
    tb.append(el('h4', {}, 'Entonces… (acciones, en orden)'));
    t.acc.forEach((a, ai) => tb.append(evBloqueFila(EV_ACC_ES, evNombreAcc, a, 'acc', guardar, () => { t.acc.splice(ai, 1); guardar(); }, EV_ACC_SERV)));
    const ba = el('button', { className: 'btn sm' }, '+ Acción'); ba.onclick = () => { t.acc.push({ n: 3, p: [0, 0] }); guardar(); }; tb.append(ba);
    if (ev.trig.length > 1) { const bq = el('button', { className: 'btn sm' }, 'Quitar disparador'); bq.style.marginLeft = '8px'; bq.onclick = () => { ev.trig.splice(ti, 1); guardar(); }; tb.append(bq); }
    caja.append(tb);
  });
  const r = el('div', { className: 'row' });
  const bt = el('button', { className: 'btn sm' }, '+ Disparador'); bt.onclick = () => { ev.trig.push({ modo: 2, veces: 0, basta: false, cond: [], acc: [] }); guardar(); };
  const bd = el('button', { className: 'btn sm' }, 'Borrar evento'); bd.onclick = () => { if (confirm('¿Borrar el evento #' + ev.id + '?')) { mod.eventos.splice(mod.eventos.indexOf(ev), 1); EVU.abiertos.delete(ev.id); guardar(); } };
  r.append(bt, bd); caja.append(r); p.append(caja);
}

EVU.tab = function (p, xmlEditor) {
  p.append(el('div', { className: 'mu' }, 'Eventos del mapa en español. Un evento es "cuando pase X, si se cumple Y, haz Z". Para que un objeto o NPC lo dispare, enlázalo en la pestaña Selección (campo Evento). Los ⚠ son cosas que el servidor aún no ejecuta.'));
  const r = el('div', { className: 'row' });
  const bav = el('button', { className: 'btn sm' + (EVU.avanzado ? ' on' : '') }, 'XML avanzado'); bav.onclick = () => { EVU.avanzado = !EVU.avanzado; panelRefresh(); };
  r.append(bav); p.append(r);
  if (EVU.avanzado) { xmlEditor(p, 'eventos', 'Eventos', 'XML de FAO tal cual.', d => `${d.querySelectorAll('事件').length} eventos`); return; }
  const mod = evParsear(M.eventos);
  if (!mod) { p.append(el('div', { className: 'mal' }, 'El XML de eventos no es válido: arréglalo en "XML avanzado".')); return; }
  const antes = M.eventos;
  const rn = el('div', { className: 'row' }); const sp = el('select'); sp.append(new Option('+ Evento nuevo desde plantilla…', ''));
  EV_PLANTILLAS.forEach(([nom], i) => sp.append(new Option(nom, i)));
  sp.onchange = () => { if (sp.value === '') return; const ev = EV_PLANTILLAS[+sp.value][1](mod); mod.eventos.push(ev); EVU.abiertos.add(ev.id); evCommit(mod, antes); };
  rn.append(sp); p.append(rn);
  p.append(el('h4', {}, `${mod.eventos.length} evento(s)`));
  mod.eventos.forEach(ev => evTarjeta(p, mod, ev, antes));
};

// Campo "Evento" del objeto seleccionado: el numero va en los 4 primeros bytes (little-endian) del registro extra del objeto.
EVU.eventoDe = o => { const h = (o.r || '').padEnd(100, '0'); return parseInt(h.slice(6, 8) + h.slice(4, 6) + h.slice(2, 4) + h.slice(0, 2), 16) || 0; };
EVU.campoEvento = function (p, o) {
  const f = el('div', { className: 'row' }, '<span class="mu" style="width:60px">evento</span>');
  const i = el('input', { type: 'number', value: EVU.eventoDe(o) });
  i.onchange = () => {
    const v = Math.max(0, +i.value | 0) >>> 0, antes = o.r, h = (o.r || '').padEnd(100, '0');
    const b = [v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >>> 24) & 255].map(x => x.toString(16).padStart(2, '0')).join('');
    const nuevo = b + h.slice(8); o.r = nuevo;
    push({ undo() { o.r = antes; }, redo() { o.r = nuevo; } }); msg('Evento ' + v + ' enlazado al objeto', 'ok');
  };
  f.append(i, el('span', { className: 'mu' }, ' 0 = sin evento')); p.append(f);
};
