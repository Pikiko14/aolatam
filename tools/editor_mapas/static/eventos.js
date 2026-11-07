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
  3: ['Ir a otro mapa', ['Mapa (número)', 'Punto de llegada: tag, o casilla como x*1000+y (160036 = casilla 160,36)']],
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
  52: ['Cambiar un objeto estático', ['Tag', 'Objeto (número)']], 53: ['Ir a un punto del mapa', ['Punto: tag, o casilla como x*1000+y (160036 = casilla 160,36)']],
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

// ---------------------------------------------------------------------------------------------------- selectores
// En vez de escribir el numero a mano: un buscador de objetos (corpus/content.db), de monstruos (catalogo del
// cliente + los propios) o de mapas (los stage del servidor). El numero sigue visible y editable.
const EV_NOM_ITEM = {};
function evPedirNombres(ids) {
  const faltan = [...new Set(ids.map(Number))].filter(i => i > 0 && !(i in EV_NOM_ITEM));
  if (!faltan.length) return;
  faltan.forEach(i => { EV_NOM_ITEM[i] = '…'; });
  api('/api/ao/nombres_items?ids=' + faltan.join(',')).then(r => { Object.assign(EV_NOM_ITEM, r); panelRefresh(); }).catch(() => { });
}
function evNombreDe(tipo, v) {
  if (tipo === 'item') { if (!(v in EV_NOM_ITEM)) evPedirNombres([v]); return EV_NOM_ITEM[v] || ''; }
  if (tipo === 'mapa') return STAGE[v] || STAGE[String(v)] || '';
  if (tipo === 'mob') {
    if (!AOCAT) return '';
    const m = AOCAT.find(c => (typeof v === 'string' && isNaN(+v) ? c.propio === v : (c.monstruo && c.id === +v && !c.propio)));
    return m ? `${m.nombre} (Lv${m.nivel})${m.propio ? ' [propio]' : ''}` : '';
  }
  return '';
}
async function evOpciones(tipo, q) {
  q = q.trim().toLowerCase();
  if (tipo === 'item') return q ? (await api('/api/ao/items?q=' + encodeURIComponent(q))).map(x => [x.id, `${x.nombre}  · Lv${x.nivel} ${x.clase}`]) : [];
  if (tipo === 'mapa') return Object.entries(STAGE).filter(([k, v]) => !q || k.startsWith(q) || String(v).toLowerCase().includes(q)).slice(0, 80).map(([k, v]) => [+k, v]);
  if (tipo === 'mob') {
    if (!AOCAT) AOCAT = await api('/api/ao/catalogo');
    return AOCAT.filter(c => c.monstruo && (!q || c.nombre.toLowerCase().includes(q) || String(c.id).startsWith(q) || (c.propio || '').includes(q)))
      .slice(0, 80).map(c => [c.propio || c.id, `${c.nombre} · Lv${c.nivel}${c.propio ? ' [propio]' : ' #' + c.id}`]);
  }
  return [];
}
// Campo con numero + nombre + lupa. alCambiar recibe el numero (o el id de texto de un monstruo propio).
function evSelector(tipo, valor, alCambiar, ancho) {
  const w = el('span'); w.style.cssText = 'display:inline-flex;gap:4px;align-items:center;position:relative;flex-wrap:wrap';
  const num = el('input', { type: 'text', value: valor }); num.style.width = ancho || '80px';
  num.onchange = () => alCambiar(tipo === 'mob' && isNaN(+num.value) ? num.value.trim() : (+num.value | 0));
  const nom = el('span', { className: 'mu' }, ''); nom.textContent = valor ? (evNombreDe(tipo, valor) || '¿?') : '—';
  nom.style.cssText = 'max-width:170px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
  const lupa = el('button', { className: 'btn sm' }, '🔍'); lupa.title = { item: 'Buscar objeto', mob: 'Buscar monstruo', mapa: 'Buscar mapa' }[tipo];
  lupa.onclick = ev => {
    ev.preventDefault();
    if (w.querySelector('.evpop')) { w.querySelector('.evpop').remove(); return; }
    const pop = el('div', { className: 'evpop' });
    pop.style.cssText = 'position:absolute;top:100%;left:0;z-index:50;background:var(--p1,#222);border:1px solid var(--ac);border-radius:6px;padding:4px;width:300px;max-height:260px;overflow:auto;box-shadow:0 4px 14px #0008';
    const bus = el('input', { type: 'text', placeholder: tipo === 'item' ? 'nombre o número del objeto…' : 'buscar…' }); bus.style.width = '100%';
    const lista = el('div');
    let t = 0;
    const pintar = async () => {
      const mio = ++t, ops = await evOpciones(tipo, bus.value).catch(() => []);
      if (mio !== t) return;
      lista.innerHTML = ops.length ? '' : `<div class="mu">${bus.value ? 'Nada.' : 'Escribe para buscar.'}</div>`;
      for (const [v, txt] of ops) {
        const f = el('div', {}, ''); f.textContent = txt; f.style.cssText = 'cursor:pointer;padding:2px 4px;border-radius:4px';
        f.onmouseenter = () => { f.style.background = 'var(--p2)'; }; f.onmouseleave = () => { f.style.background = ''; };
        f.onclick = () => { pop.remove(); if (tipo === 'item') EV_NOM_ITEM[v] = txt.split('  ·')[0]; alCambiar(v); };
        lista.append(f);
      }
    };
    bus.oninput = () => setTimeout(pintar, 150);
    pop.append(bus, lista); w.append(pop); bus.focus(); pintar();
  };
  w.append(num, lupa, nom); return w;
}
// Que selector lleva un parametro, por su etiqueta.
const evTipoDeEtiqueta = etq => /^Objeto/.test(etq) ? 'item' : /^Mapa/.test(etq) ? 'mapa' : /^Monstruo/.test(etq) ? 'mob' : null;

function evCampoParam(tabla, n, i, valor, alCambiar) {
  const etq = evEtq(tabla, n, i), tipo = evTipoDeEtiqueta(etq);
  // Con selector va en un div: dentro de un <label> cada clic en la lista de resultados se iba al primer input.
  const w = el(tipo ? 'div' : 'label', { className: 'row' }); w.style.cssText = 'gap:6px;margin:2px 0';
  w.append(el('span', { className: 'mu' }, etq));
  if (tipo) { w.append(evSelector(tipo, valor, v => alCambiar(+v | 0))); return w; }
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

// ---------------------------------------------------------------------------------------------------- reglas del servidor
// Reglas del servidor: "cuando pase X (matar, entrar al mapa, a una hora), si se cumple Y, haz Z". Viven en
// server/plantillas/eventos_propios.json (server/eventos_propios.py): no van en el .mpc y no necesitan parche del cliente.
const EVR = { datos: null, abiertas: new Set(), sucio: false, errores: null, elegir: null };
const EVR_CUANDO = { matar: '⚔ Al matar monstruos', entrar: '🚪 Al entrar al mapa', horario: '⏰ A una hora / cada N minutos' };
const EVR_PREMIOS = {
  dar: '🎁 Dar un objeto', soltar: '🎲 Soltar uno al azar (con probabilidad)', oro: '💰 Dar oro', ag: '💎 Dar Angel Gold',
  exp: '⭐ Dar experiencia', portal: '🌀 Abrir un portal temporal', monstruo: '👹 Hacer aparecer monstruos',
  llevar: '➡ Llevar al jugador a otro sitio', aviso_global: '📢 Aviso para todo el servidor'
};
const evrStageActual = () => +((typeof M !== 'undefined' && M && (M.aoStageManual || M.aoStage)) || +(((M && M.nombre) || '').match(/(\d+)/) || [])[1] || 0);
const evrPremioNuevo = t => ({
  dar: { tipo: 'dar', item: 0, cantidad: 1 }, soltar: { tipo: 'soltar', items: [[0, 1]], prob: 50 }, oro: { tipo: 'oro', cantidad: 1000 },
  ag: { tipo: 'ag', cantidad: 50 }, exp: { tipo: 'exp', cantidad: 5000 },
  portal: { tipo: 'portal', destino: 0, llegada: [0, 0], donde: 'monstruo', segundos: 120 },
  monstruo: { tipo: 'monstruo', npc_type: 0, cantidad: 1, donde: 'monstruo', segundos: 0 },
  llevar: { tipo: 'llevar', destino: 0, llegada: [0, 0] }, aviso_global: { tipo: 'aviso_global', texto: '' }
})[t];
function evrIdLibre(base) { const ids = new Set((EVR.datos.reglas || []).map(r => r.id)); let n = 1; while (ids.has(base + n)) n++; return base + n; }

// Escenarios listos: eligen disparador, condiciones y premios; solo queda elegir monstruos, objetos o casillas.
const EVR_ESCENARIOS = [
  ['Cazar N monstruos → premio', st => ({ nombre: 'Cazador', cuando: 'matar', stage: st, matar: { mobs: [], cantidad: 30, alcance: 'jugador', repetir: true }, aviso: 'Hunt complete!', premios: [evrPremioNuevo('dar'), evrPremioNuevo('exp')] })],
  ['Matar N entre todos → aparece un jefe', st => ({ nombre: 'Aparece el jefe', cuando: 'matar', stage: st, matar: { mobs: [], cantidad: 50, alcance: 'mapa', repetir: true }, aviso: '', premios: [evrPremioNuevo('monstruo'), { tipo: 'aviso_global', texto: 'A boss has appeared!' }] })],
  ['Matar al jefe → portal de salida', st => ({ nombre: 'Portal del jefe', cuando: 'matar', stage: st, matar: { mobs: [], cantidad: 1, alcance: 'mapa', repetir: true }, aviso: 'A portal has opened!', premios: [{ tipo: 'portal', destino: 0, llegada: [0, 0], donde: 'monstruo', segundos: 300 }] })],
  ['Botín raro: 1 % al matar', st => ({ nombre: 'Botín raro', cuando: 'matar', stage: st, matar: { mobs: [], cantidad: 1, alcance: 'jugador', repetir: true }, si: { prob: 1 }, aviso: 'Lucky drop!', premios: [{ tipo: 'soltar', items: [[0, 1]], prob: 100 }] })],
  ['Caza nocturna: premio extra de 20:00 a 23:59', st => ({ nombre: 'Caza nocturna', cuando: 'matar', stage: st, matar: { mobs: [], cantidad: 20, alcance: 'jugador', repetir: true }, si: { desde: '20:00', hasta: '23:59' }, aviso: 'Night hunt bonus!', premios: [evrPremioNuevo('exp')] })],
  ['Bienvenida: regalo la primera vez que entras', st => ({ nombre: 'Bienvenida', cuando: 'entrar', stage: st, entrar: { repetir: false }, aviso: 'Welcome!', premios: [evrPremioNuevo('dar')] })],
  ['Mapa de nivel: saca a los de poco nivel', st => ({ nombre: 'Solo nivel alto', cuando: 'entrar', stage: st, entrar: { repetir: true }, si: { nivel_max: 39 }, aviso: 'You need level 40 to enter this map.', premios: [evrPremioNuevo('llevar')] })],
  ['Invasión diaria a una hora', st => ({ nombre: 'Invasión', cuando: 'horario', stage: st, horario: { horas: ['20:00'] }, aviso: '', premios: [{ tipo: 'monstruo', npc_type: 0, cantidad: 10, donde: [0, 0], segundos: 1800 }, { tipo: 'aviso_global', texto: 'Monsters are invading!' }] })],
  ['Jefe cada N minutos', st => ({ nombre: 'Jefe periódico', cuando: 'horario', stage: st, horario: { cada_min: 60 }, aviso: '', premios: [{ tipo: 'monstruo', npc_type: 0, cantidad: 1, donde: [0, 0], segundos: 0 }, { tipo: 'aviso_global', texto: 'The boss is back!' }] })],
  ['Lluvia de oro: a todos los del mapa a una hora', st => ({ nombre: 'Lluvia de oro', cuando: 'horario', stage: st, horario: { horas: ['21:00'] }, aviso: 'Gold rain!', premios: [{ tipo: 'oro', cantidad: 5000 }] })],
  ['Regla vacía', st => ({ nombre: 'Regla nueva', cuando: 'matar', stage: st, matar: { mobs: [], cantidad: 10, alcance: 'jugador', repetir: true }, aviso: '', premios: [evrPremioNuevo('dar')] })],
];
function evrDesdeEscenario(i) {
  const r = EVR_ESCENARIOS[i][1](evrStageActual());
  r.id = evrIdLibre(r.cuando === 'matar' ? 'caza' : r.cuando === 'entrar' ? 'entrar' : 'reloj'); r.activa = true;
  return r;
}

function evrCampo(etq, ...hijos) { const r = el('div', { className: 'row' }); r.style.cssText = 'gap:6px;margin:3px 0;flex-wrap:wrap;align-items:center'; r.append(el('span', { className: 'mu' }, etq), ...hijos); return r; }
function evrNum(v, alCambiar, ancho) { const i = el('input', { type: 'number', value: v ?? 0 }); i.style.width = ancho || '70px'; i.onchange = () => { alCambiar(+i.value || 0); evrSucio(); }; return i; }
function evrTxt(v, alCambiar, ancho, ph) { const i = el('input', { type: 'text', value: v || '', placeholder: ph || '' }); i.style.width = ancho || '220px'; i.onchange = () => { alCambiar(i.value); evrSucio(); }; return i; }
function evrSucio() { EVR.sucio = true; panelRefresh(); }
// "📍" = el siguiente clic en el mapa pone esa casilla (en coordenadas del servidor).
function evrPick(alElegir) {
  const b = el('button', { className: 'btn sm' }, '📍 elegir en el mapa'); b.title = 'Haz clic aquí y luego en el mapa';
  b.onclick = () => { EVR.elegir = t => { alElegir(t); evrSucio(); msg('Casilla ' + t[0] + ', ' + t[1] + ' elegida.', 'ok'); }; msg('Haz clic en el mapa para elegir la casilla (Esc cancela).', 'av'); };
  return b;
}
function evrCasilla(etq, par, alCambiar) {
  return evrCampo(etq, el('span', { className: 'mu' }, 'x'), evrNum(par[0], v => { par[0] = v; }, '60px'), el('span', { className: 'mu' }, 'y'),
    evrNum(par[1], v => { par[1] = v; }, '60px'), evrPick(t => { par[0] = t[0]; par[1] = t[1]; if (alCambiar) alCambiar(); }));
}
function evrDonde(b, r, pr, etq) {
  const dn = el('select');
  if ((r.cuando || 'matar') === 'matar') dn.append(new Option('donde murió el último monstruo', 'monstruo'));
  if ((r.cuando || 'matar') !== 'horario') dn.append(new Option('junto al jugador', 'jugador'));
  dn.append(new Option('en una casilla fija', 'casilla'));
  const fija = Array.isArray(pr.donde); dn.value = fija ? 'casilla' : pr.donde;
  if (!fija && ![...dn.options].some(o => o.value === pr.donde)) { pr.donde = dn.options[0].value === 'casilla' ? [0, 0] : dn.options[0].value; }
  dn.onchange = () => { pr.donde = dn.value === 'casilla' ? [0, 0] : dn.value; evrSucio(); };
  b.append(evrCampo(etq, dn));
  if (Array.isArray(pr.donde)) b.append(evrCasilla('Casilla', pr.donde));
}

function evrPremio(caja, r, pr, i) {
  const b = el('div'); b.style.cssText = 'border:1px dashed var(--bd);border-radius:6px;padding:4px 6px;margin:4px 0';
  const sel = el('select'); for (const [k, v] of Object.entries(EVR_PREMIOS)) sel.append(new Option(v, k)); sel.value = pr.tipo;
  sel.onchange = () => { r.premios[i] = evrPremioNuevo(sel.value); evrSucio(); };
  const x = el('button', { className: 'btn sm' }, '✕'); x.title = 'Quitar'; x.onclick = () => { r.premios.splice(i, 1); evrSucio(); };
  b.append(evrCampo('', sel, x));
  const t = pr.tipo;
  if (t === 'dar') b.append(evrCampo('Objeto', evSelector('item', pr.item, v => { pr.item = +v; evrSucio(); })), evrCampo('Cantidad', evrNum(pr.cantidad, v => { pr.cantidad = Math.max(1, v); })));
  if (t === 'soltar') {
    pr.items.forEach((it, j) => {
      const q = el('button', { className: 'btn sm' }, '✕'); q.onclick = () => { pr.items.splice(j, 1); evrSucio(); };
      b.append(evrCampo('Objeto ' + (j + 1), evSelector('item', it[0], v => { it[0] = +v; evrSucio(); }), el('span', { className: 'mu' }, '×'), evrNum(it[1], v => { it[1] = Math.max(1, v); }, '50px'), q));
    });
    const mas = el('button', { className: 'btn sm' }, '+ objeto posible'); mas.onclick = () => { pr.items.push([0, 1]); evrSucio(); };
    b.append(mas, evrCampo('Probabilidad %', evrNum(pr.prob, v => { pr.prob = Math.min(100, Math.max(0, v)); })));
  }
  if (t === 'oro' || t === 'ag' || t === 'exp') b.append(evrCampo('Cantidad', evrNum(pr.cantidad, v => { pr.cantidad = Math.max(1, v); }, '100px')));
  if (t === 'portal' || t === 'llevar') {
    b.append(evrCampo('Lleva al mapa', evSelector('mapa', pr.destino, v => { pr.destino = +v; evrSucio(); })));
    b.append(evrCasilla('Llegada', pr.llegada));
  }
  if (t === 'portal') { evrDonde(b, r, pr, 'Aparece'); b.append(evrCampo('Dura (segundos)', evrNum(pr.segundos, v => { pr.segundos = Math.max(5, v); }))); }
  if (t === 'monstruo') {
    b.append(evrCampo('Monstruo', evSelector('mob', pr.npc_type, v => { pr.npc_type = +v || 0; evrSucio(); }, '70px'), el('span', { className: 'mu' }, '×'), evrNum(pr.cantidad, v => { pr.cantidad = Math.min(50, Math.max(1, v)); }, '50px')));
    evrDonde(b, r, pr, 'Aparece');
    b.append(evrCampo('Se va a los (segundos)', evrNum(pr.segundos, v => { pr.segundos = Math.max(0, v); }, '80px'), el('span', { className: 'mu' }, '0 = se queda hasta que lo maten')));
  }
  if (t === 'aviso_global') b.append(evrCampo('Texto', evrTxt(pr.texto, v => { pr.texto = v; }, '260px', 'sale como cartel para todos los jugadores')));
  caja.append(b);
}

// La regla dicha en una frase, para entenderla sin abrirla.
function evrFrase(r) {
  const c = r.cuando || 'matar', si = r.si || {}, mapa = r.stage ? (STAGE[r.stage] || 'mapa ' + r.stage) : 'cualquier mapa';
  let q;
  if (c === 'matar') {
    const k = r.matar || {}, mobs = (k.mobs || []).length ? k.mobs.map(m => evNombreDe('mob', m) || m).join(', ') : 'cualquier monstruo';
    q = `Al matar ${k.cantidad} × ${mobs} (${k.alcance === 'mapa' ? 'entre todos' : 'cada jugador'}${k.repetir === false ? ', una vez' : ''}) en ${mapa}`;
  } else if (c === 'entrar') q = `Al entrar a ${mapa}${(r.entrar || {}).repetir ? ' (cada vez' + ((r.entrar || {}).enfriamiento_min ? ', cada ' + r.entrar.enfriamiento_min + ' min como mucho' : '') + ')' : ' (la primera vez)'}`;
  else { const h = r.horario || {}; q = (h.horas || []).length ? `A las ${h.horas.join(', ')}` : `Cada ${h.cada_min} min`; q += ` en ${mapa}`; }
  const conds = [];
  if (si.nivel_min) conds.push('nivel ≥ ' + si.nivel_min); if (si.nivel_max) conds.push('nivel ≤ ' + si.nivel_max);
  if (si.desde || si.hasta) conds.push('de ' + (si.desde || '00:00') + ' a ' + (si.hasta || '23:59'));
  if (si.prob != null && si.prob < 100) conds.push(si.prob + ' % de las veces');
  return q + (conds.length ? ', si ' + conds.join(' y ') : '') + ' → ' + (r.premios || []).map(x => (EVR_PREMIOS[x.tipo] || x.tipo).replace(/^\S+ /, '')).join(', ');
}

function evrTarjeta(p, r, idx) {
  const abierta = EVR.abiertas.has(idx);
  const cab = el('div', { className: 'att' + (abierta ? ' on' : '') });
  cab.innerHTML = `<b></b><span class="mu"></span>`;
  cab.firstChild.textContent = (r.activa === false ? '⏸ ' : '') + (r.nombre || r.id) + '  ';
  cab.lastChild.textContent = evrFrase(r);
  cab.onclick = () => { abierta ? EVR.abiertas.delete(idx) : EVR.abiertas.add(idx); panelRefresh(); };
  p.append(cab);
  if (EVR.errores && EVR.errores[r.id]) p.append(el('div', { className: 'mal' }, '⚠ ' + EVR.errores[r.id].join('; ')));
  if (!abierta) return;
  const c = el('div'); c.style.cssText = 'margin:0 0 8px 8px;border-left:2px solid var(--bd);padding-left:8px';
  const id = el('input', { type: 'text', value: r.id }); id.style.width = '110px'; id.onchange = () => { r.id = id.value.trim().replace(/\s+/g, '_'); evrSucio(); };
  const act = el('input', { type: 'checkbox', checked: r.activa !== false }); act.onchange = () => { r.activa = act.checked; evrSucio(); };
  c.append(evrCampo('Nombre', evrTxt(r.nombre, v => { r.nombre = v; })), evrCampo('Id', id, act, el('span', { className: 'mu' }, 'activa')));
  c.append(evrCampo('Mapa', evSelector('mapa', r.stage || 0, v => { r.stage = +v; evrSucio(); }), el('span', { className: 'mu' }, '0 = cualquier mapa')));

  c.append(el('h4', {}, '1. Cuándo'));
  const cu = el('select'); for (const [k, v] of Object.entries(EVR_CUANDO)) cu.append(new Option(v, k)); cu.value = r.cuando || 'matar';
  cu.onchange = () => {
    r.cuando = cu.value;
    if (r.cuando === 'matar' && !r.matar) r.matar = { mobs: [], cantidad: 10, alcance: 'jugador', repetir: true };
    if (r.cuando === 'entrar' && !r.entrar) r.entrar = { repetir: false };
    if (r.cuando === 'horario' && !r.horario) r.horario = { horas: ['20:00'] };
    evrSucio();
  };
  c.append(evrCampo('', cu));
  const cuando = r.cuando || 'matar';
  if (cuando === 'matar') {
    if (!r.matar) r.matar = { mobs: [], cantidad: 10, alcance: 'jugador', repetir: true };
    r.matar.mobs.forEach((m, j) => {
      const q = el('button', { className: 'btn sm' }, '✕'); q.onclick = () => { r.matar.mobs.splice(j, 1); evrSucio(); };
      c.append(evrCampo('Monstruo', evSelector('mob', m, v => { r.matar.mobs[j] = v; evrSucio(); }, '70px'), q));
    });
    const mm = el('button', { className: 'btn sm' }, '+ monstruo'); mm.title = 'Sin monstruos en la lista cuenta cualquiera';
    mm.onclick = () => { r.matar.mobs.push(0); evrSucio(); };
    c.append(mm, el('span', { className: 'mu' }, r.matar.mobs.length ? '' : '  (sin lista: vale cualquier monstruo)'));
    c.append(evrCampo('Cuántos', evrNum(r.matar.cantidad, v => { r.matar.cantidad = Math.max(1, v); })));
    const al = el('select'); al.append(new Option('cada jugador cuenta lo suyo', 'jugador'), new Option('todos los del mapa juntos', 'mapa'));
    al.value = r.matar.alcance || 'jugador'; al.onchange = () => { r.matar.alcance = al.value; evrSucio(); };
    const rep = el('input', { type: 'checkbox', checked: r.matar.repetir !== false }); rep.onchange = () => { r.matar.repetir = rep.checked; evrSucio(); };
    c.append(evrCampo('Cuenta', al), evrCampo('', rep, el('span', { className: 'mu' }, 'se repite (si no, solo una vez)')));
  } else if (cuando === 'entrar') {
    if (!r.entrar) r.entrar = { repetir: false };
    const rep = el('input', { type: 'checkbox', checked: !!r.entrar.repetir }); rep.onchange = () => { r.entrar.repetir = rep.checked; evrSucio(); };
    c.append(evrCampo('', rep, el('span', { className: 'mu' }, 'cada vez que entra (si no, solo la primera vez de cada jugador)')));
    if (r.entrar.repetir) c.append(evrCampo('Como mucho cada (min)', evrNum(r.entrar.enfriamiento_min || 0, v => { r.entrar.enfriamiento_min = Math.max(0, v); }), el('span', { className: 'mu' }, '0 = siempre')));
  } else {
    if (!r.horario) r.horario = { horas: ['20:00'] };
    const modo = el('select'); modo.append(new Option('a estas horas (todos los días)', 'horas'), new Option('cada N minutos', 'cada'));
    modo.value = (r.horario.horas || []).length ? 'horas' : 'cada';
    modo.onchange = () => { r.horario = modo.value === 'horas' ? { horas: ['20:00'] } : { cada_min: 60 }; evrSucio(); };
    c.append(evrCampo('', modo));
    if (modo.value === 'horas') {
      r.horario.horas.forEach((h, j) => {
        const hi = el('input', { type: 'time', value: h }); hi.onchange = () => { r.horario.horas[j] = hi.value; evrSucio(); };
        const q = el('button', { className: 'btn sm' }, '✕'); q.onclick = () => { r.horario.horas.splice(j, 1); evrSucio(); };
        c.append(evrCampo('Hora', hi, q));
      });
      const mh = el('button', { className: 'btn sm' }, '+ hora'); mh.onclick = () => { r.horario.horas.push('12:00'); evrSucio(); };
      c.append(mh, el('span', { className: 'mu' }, '  hora del servidor'));
    } else c.append(evrCampo('Cada (minutos)', evrNum(r.horario.cada_min, v => { r.horario.cada_min = Math.max(1, v); })));
    c.append(el('div', { className: 'mu' }, 'A esa hora no hay un jugador concreto: los premios personales (objetos, oro, exp…) van a todos los que estén en el mapa.'));
  }

  c.append(el('h4', {}, '2. Solo si… (opcional)'));
  const si = r.si || (r.si = {});
  c.append(evrCampo('Nivel del jugador de', evrNum(si.nivel_min || 0, v => { si.nivel_min = Math.max(0, v); }, '60px'), el('span', { className: 'mu' }, 'a'), evrNum(si.nivel_max || 0, v => { si.nivel_max = Math.max(0, v); }, '60px'), el('span', { className: 'mu' }, '0 = sin límite')));
  const de = el('input', { type: 'time', value: si.desde || '' }), ha = el('input', { type: 'time', value: si.hasta || '' });
  de.onchange = () => { si.desde = de.value || undefined; evrSucio(); }; ha.onchange = () => { si.hasta = ha.value || undefined; evrSucio(); };
  const sinH = el('button', { className: 'btn sm' }, 'todo el día'); sinH.onclick = () => { delete si.desde; delete si.hasta; evrSucio(); };
  c.append(evrCampo('Entre las', de, el('span', { className: 'mu' }, 'y las'), ha, sinH));
  c.append(evrCampo('Probabilidad %', evrNum(si.prob ?? 100, v => { si.prob = Math.min(100, Math.max(0, v)); }), el('span', { className: 'mu' }, '100 = siempre')));

  c.append(el('h4', {}, '3. Entonces…'));
  c.append(evrCampo('Mensaje al jugador', evrTxt(r.aviso, v => { r.aviso = v; }, '240px', 'opcional')));
  r.premios.forEach((pr, i) => evrPremio(c, r, pr, i));
  const ap = el('select'); ap.append(new Option('+ añadir…', ''));
  for (const [k, v] of Object.entries(EVR_PREMIOS)) ap.append(new Option(v, k));
  ap.onchange = () => { if (ap.value) { r.premios.push(evrPremioNuevo(ap.value)); evrSucio(); } };
  const dup = el('button', { className: 'btn sm' }, 'Duplicar');
  dup.onclick = () => { const cp = JSON.parse(JSON.stringify(r)); cp.id = evrIdLibre(r.id.replace(/\d+$/, '') || 'regla'); cp.nombre = (r.nombre || '') + ' (copia)'; EVR.datos.reglas.splice(idx + 1, 0, cp); EVR.abiertas = new Set([idx + 1]); evrSucio(); };
  const bd = el('button', { className: 'btn sm' }, 'Borrar regla');
  bd.onclick = () => { if (confirm('¿Borrar la regla ' + (r.nombre || r.id) + '?')) { EVR.datos.reglas.splice(idx, 1); EVR.abiertas.clear(); evrSucio(); } };
  c.append(evrCampo('', ap, dup, bd));
  p.append(c);
}

EVU.reglas = function (p) {
  p.append(el('h4', {}, 'Reglas del servidor'));
  p.append(el('div', { className: 'mu' }, 'Cuando pase algo (matar monstruos, entrar al mapa o a una hora), si se cumplen las condiciones, el servidor da objetos, oro, exp, hace aparecer monstruos, abre portales, mueve al jugador o avisa a todos. No hace falta parche del cliente: el servidor las relee al guardar.'));
  if (!EVR.datos) {
    p.append(el('div', { className: 'mu' }, 'Cargando…'));
    api('/api/ao/reglas').then(d => { EVR.datos = d; EVR.datos.reglas = d.reglas || [];
      evPedirNombres(EVR.datos.reglas.flatMap(r => (r.premios || []).flatMap(x => x.tipo === 'dar' ? [x.item] : x.tipo === 'soltar' ? x.items.map(i => i[0]) : [])));
      if (!AOCAT) api('/api/ao/catalogo').then(l => { AOCAT = l; panelRefresh(); });
      panelRefresh(); }).catch(e => p.append(el('div', { className: 'mal' }, e.message)));
    return;
  }
  const est = evrStageActual(), reglas = EVR.datos.reglas;
  const r = el('div', { className: 'row' });
  const esc = el('select'); esc.append(new Option('+ Regla nueva desde un escenario…', ''));
  EVR_ESCENARIOS.forEach(([nom], i) => esc.append(new Option(nom, i)));
  esc.onchange = () => { if (esc.value === '') return; reglas.push(evrDesdeEscenario(+esc.value)); EVR.abiertas = new Set([reglas.length - 1]); evrSucio(); };
  const guardar = el('button', { className: 'btn sm' + (EVR.sucio ? ' on' : '') }, EVR.sucio ? '💾 Guardar reglas' : 'Guardado');
  guardar.onclick = async () => {
    try {
      const res = await api('/api/ao/reglas', { method: 'POST', body: JSON.stringify({ reglas }) });
      EVR.errores = res.ok ? null : res.errores;
      if (res.ok) { EVR.sucio = false; msg(`Reglas guardadas (${res.total}) en server/plantillas/eventos_propios.json. El servidor las relee solo.`, 'ok'); }
      else { msg('Hay reglas con errores (marcadas con ⚠): no se guardó nada.', 'mal'); reglas.forEach((x, i) => { if (res.errores[x.id]) EVR.abiertas.add(i); }); }
    } catch (e) { msg(e.message, 'mal'); }
    panelRefresh();
  };
  const todas = el('button', { className: 'btn sm' + (EVR.todas ? ' on' : '') }, EVR.todas ? 'ver solo este mapa' : 'ver todas');
  todas.onclick = () => { EVR.todas = !EVR.todas; panelRefresh(); };
  r.append(esc, guardar, todas); p.append(r);
  const deEste = reglas.map((x, i) => [x, i]).filter(([x]) => EVR.todas || !est || !x.stage || +x.stage === est);
  p.append(el('div', { className: 'mu' }, `${deEste.length} de ${reglas.length} regla(s)${!EVR.todas && est ? ' para este mapa (' + (STAGE[est] || est) + ') o cualquiera' : ''}`));
  deEste.forEach(([x, i]) => evrTarjeta(p, x, i));
};

EVU.tab = function (p, xmlEditor) {
  EVU.reglas(p);
  p.append(el('h4', {}, 'Eventos del .mpc'));
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
