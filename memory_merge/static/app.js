'use strict';
const $ = id => document.getElementById(id), NS = 'http://www.w3.org/2000/svg';
const CATS = ['fact', 'decision', 'preference', 'procedure', 'lesson', 'knowledge'];
const RELS = ['supports', 'contradicts', 'supersedes', 'related'];
const COLORS = {fact: '#166858', decision: '#2f5fa7', preference: '#a56521', procedure: '#6b4fa3', lesson: '#a33a2c', knowledge: '#4d7d2f'};
const I18N = {
  en: {eyebrow: 'LOCAL MEMORY / EVIDENCE FIRST', tagline: 'From conversations to traceable long-term memory. Only reviewed memories are shown.',
    project: 'Project', includeUser: 'include personal scope', load: 'Load', category: 'Category', relation: 'Relations', tag: 'Tag', all: 'all',
    filter: 'Filter', filterPh: 'text or category', search: 'Search', searchPh: 'query the index', graph: 'Graph', timeline: 'Timeline',
    reset: 'Reset', export: 'Export JSON', network: 'Relation network', hint: 'drag to pan · wheel to zoom · click a node', more: 'Load more',
    review: 'Review queue', detail: 'Memory detail', detailEmpty: 'Select a node to see its text, source and relations.', index: 'Index',
    footer: 'SQLite source of truth · Markdown mirror · loopback-only viewer · no CDN, no model calls',
    loading: 'Loading local data…', failed: 'Could not load: check the project name and that the server is running.',
    nodes: (n, e, t) => `${n} reviewed nodes / ${e} relations` + (t ? ` (showing ${n} of ${t}: refine the filter)` : ''),
    none: 'No matching nodes. Capture and approve memories via CLI or MCP first.', hits: n => `${n} search results highlighted`,
    source: 'Source', created: 'Created', updated: 'Updated', support: 'Independent sources', provenance: 'Provenance', tags: 'Tags', edges: 'Relations',
    approve: 'Approve', reject: 'Reject', queueEmpty: 'Nothing pending.', injection: 'resembles instructions to an AI', legend: 'Edges are recorded relations, not proof. Dashed red outline: do-not-repeat memory; orange outline: personal scope.'},
  zh: {eyebrow: '本地记忆 / 证据优先', tagline: '从一次对话，到可追溯的长期记忆。仅显示已审核条目。',
    project: '项目', includeUser: '包含个人范围', load: '载入', category: '分类', relation: '关系', tag: '标签', all: '全部',
    filter: '筛选', filterPh: '正文 / 分类', search: '检索', searchPh: '查询索引', graph: '图谱', timeline: '时间线',
    reset: '复位', export: '导出 JSON', network: '关系网络', hint: '拖动平移 · 滚轮缩放 · 点击查看', more: '加载更多',
    review: '待审队列', detail: '记忆详情', detailEmpty: '选择节点，查看正文、来源和关系。', index: '节点索引',
    footer: 'SQLite 真源 · Markdown 镜像 · 仅本机只读界面 · 不加载 CDN，不调用模型',
    loading: '正在读取本地数据…', failed: '读取失败，请检查项目名和服务状态。',
    nodes: (n, e, t) => `${n} 个已审核节点 / ${e} 条关系` + (t ? `（共 ${t} 个，仅显示 ${n} 个，请缩小筛选）` : ''),
    none: '暂无匹配节点。先通过 CLI 或 MCP 写入并审核记忆。', hits: n => `已高亮 ${n} 条检索结果`,
    source: '来源', created: '创建', updated: '更新', support: '独立来源数', provenance: '出处', tags: '标签', edges: '关系',
    approve: '批准', reject: '驳回', queueEmpty: '没有待审条目。', injection: '内容像是给 AI 的指令', legend: '连线是记录的关系，不是自动证明。红色虚线：不应重复的教训；橙色外圈：个人范围。'}
};
let lang = (navigator.language || 'en').toLowerCase().startsWith('zh') ? 'zh' : 'en';
let data = {nodes: [], edges: []}, hits = new Set(), scale = 1, dx = 0, dy = 0, drag = null, pos = new Map(), session = {review: false};
let cursor = null, view = 'graph';
const t = (k, ...a) => { const v = I18N[lang][k]; return typeof v === 'function' ? v(...a) : (v ?? k); };

function el(tag, attrs = {}, text) {
  const e = tag === 'svg' || ['g', 'line', 'circle', 'text'].includes(tag) ? document.createElementNS(NS, tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
}
function applyLang() {
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  document.querySelectorAll('[data-i18n]').forEach(n => { n.textContent = t(n.dataset.i18n); });
  document.querySelectorAll('[data-i18n-ph]').forEach(n => { n.placeholder = t(n.dataset.i18nPh); });
  $('lang').textContent = lang === 'zh' ? 'English' : '中文';
  $('legend').textContent = t('legend');
  render();
}
function fillSelect(sel, values) { for (const v of values) sel.append(el('option', {value: v}, v)); }
function q(params) { return Object.entries(params).filter(([, v]) => v !== '' && v != null).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&'); }
async function api(path, params) {
  const r = await fetch(`${path}?${q(params)}`);
  if (!r.ok) throw new Error(t('failed'));
  return r.json();
}
function visible() {
  const f = $('filter').value.toLowerCase();
  return data.nodes.filter(n => !f || (n.content + ' ' + n.category + ' ' + (n.tags || []).join(' ')).toLowerCase().includes(f));
}
function layout(nodes, edges) {
  // Deterministic force layout: category anchors pull related memories together, edges act as springs.
  pos = new Map();
  const anchor = {}; CATS.forEach((c, i) => { const a = i / CATS.length * 2 * Math.PI; anchor[c] = {x: 450 + Math.cos(a) * 190, y: 310 + Math.sin(a) * 170}; });
  nodes.forEach((n, i) => { const a = i * 2.39996, r = 30 + Math.sqrt(i) * 14, c = anchor[n.category]; pos.set(n.id, {x: c.x + Math.cos(a) * r, y: c.y + Math.sin(a) * r, vx: 0, vy: 0}); });
  const steps = nodes.length > 400 ? 40 : 160, list = [...pos.values()];
  for (let s = 0; s < steps; s++) {
    for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
      const a = list[i], b = list[j], ddx = a.x - b.x, ddy = a.y - b.y, d2 = ddx * ddx + ddy * ddy + 0.01;
      if (d2 > 6400) continue;
      const f = 140 / d2; a.vx += ddx * f; a.vy += ddy * f; b.vx -= ddx * f; b.vy -= ddy * f;
    }
    for (const e of edges) { const a = pos.get(e.a), b = pos.get(e.b); if (!a || !b) continue; const ddx = b.x - a.x, ddy = b.y - a.y; a.vx += ddx * 0.01; a.vy += ddy * 0.01; b.vx -= ddx * 0.01; b.vy -= ddy * 0.01; }
    nodes.forEach(n => { const p = pos.get(n.id), c = anchor[n.category]; p.vx += (c.x - p.x) * 0.004; p.vy += (c.y - p.y) * 0.004; p.x += Math.max(-8, Math.min(8, p.vx)); p.y += Math.max(-8, Math.min(8, p.vy)); p.vx *= 0.6; p.vy *= 0.6; });
  }
}
function render() {
  const layer = $('layer'); layer.replaceChildren(); $('list').replaceChildren();
  const nodes = visible(), ids = new Set(nodes.map(n => n.id)), rel = $('relation').value;
  const edges = data.edges.filter(e => ids.has(e.a) && ids.has(e.b) && (!rel || e.relation === rel));
  if (pos.size !== data.nodes.length) layout(data.nodes, data.edges);
  for (const e of edges) {
    const a = pos.get(e.a), b = pos.get(e.b);
    layer.append(el('line', {x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: `edge ${e.relation}`}));
    layer.append(el('text', {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, class: 'edge-label'}, e.relation));
  }
  for (const n of nodes) {
    const p = pos.get(n.id), cls = ['node', n.polarity === 'negative' ? 'negative' : '', n.scope === 'user' || n.project === ':user' ? 'user' : '', hits.has(n.id) ? 'hit' : ''].join(' ');
    const c = el('circle', {cx: p.x, cy: p.y, r: 11, class: cls, fill: COLORS[n.category] || '#666', tabindex: 0, role: 'button', 'aria-label': n.content.slice(0, 70)});
    if (hits.size && !hits.has(n.id)) c.classList.add('dim');
    c.addEventListener('click', () => show(n));
    c.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); show(n); } });
    layer.append(c, el('text', {x: p.x + 15, y: p.y + 4, class: 'node-label' + (hits.size && !hits.has(n.id) ? ' dim' : '')}, n.content.slice(0, 16)));
    const b = el('button', {type: 'button'}, `${n.category} / ${n.content.slice(0, 60)}`); b.onclick = () => show(n); $('list').append(b);
  }
  $('status').textContent = nodes.length ? t('nodes', nodes.length, edges.length, data.truncated ? data.total : 0) + (hits.size ? ' · ' + t('hits', hits.size) : '') : t('none');
  $('layer').setAttribute('transform', `translate(${dx} ${dy}) scale(${scale})`);
}
async function show(n) {
  let m = n;
  try { m = await api('/api/memory', {project: n.project, id: n.id}); } catch (e) { /* keep the node data we have */ }
  const lines = [`${m.category} · ${m.status} · ${m.polarity || 'positive'}`, '', m.content, '', `${t('source')}: ${m.source}`, `${t('created')}: ${m.created}`, `${t('updated')}: ${m.updated}`];
  if (m.tags && m.tags.length) lines.push(`${t('tags')}: ${m.tags.join(', ')}`);
  if (m.support) lines.push(`${t('support')}: ${m.support}`);
  if (m.locator) lines.push(`${t('provenance')}: ${JSON.stringify(m.locator)}`);
  lines.push(`ID: ${m.id}`);
  $('detail').textContent = lines.join('\n');
  $('edges').replaceChildren();
  for (const e of m.edges || []) {
    const other = e.a === m.id ? e.b : e.a, target = data.nodes.find(x => x.id === other);
    const b = el('button', {type: 'button'}, `${e.a === m.id ? '→' : '←'} ${e.relation}: ${target ? target.content.slice(0, 50) : other}`);
    if (target) b.onclick = () => show(target);
    $('edges').append(b);
  }
}
async function load() {
  $('status').textContent = t('loading'); $('load').disabled = true; hits = new Set();
  try {
    data = await api('/api/graph', {project: $('project').value, include_user: $('includeUser').checked ? 1 : '', category: $('category').value, tag: $('tag').value});
    pos = new Map(); $('detail').textContent = t('detailEmpty'); $('edges').replaceChildren();
    render(); if (view === 'timeline') loadTimeline(true); if (session.review) loadQueue();
  } catch (e) { $('status').textContent = e.message; } finally { $('load').disabled = false; }
}
async function loadTimeline(fresh) {
  if (fresh) { cursor = null; $('timeline').replaceChildren(); }
  try {
    const page = await api('/api/timeline', {project: $('project').value, cursor});
    let day = $('timeline').dataset.day || '';
    for (const m of page.items) {
      const d = m.created.slice(0, 10);
      if (d !== day) { $('timeline').append(el('div', {class: 'day'}, d)); day = d; }
      const b = el('button', {type: 'button'}, `${m.created.slice(11, 16)} · ${m.category} · ${m.content.slice(0, 80)}`); b.onclick = () => show(m); $('timeline').append(b);
    }
    $('timeline').dataset.day = day; cursor = page.next_cursor; $('more').classList.toggle('hidden', !cursor);
  } catch (e) { $('status').textContent = e.message; }
}
async function loadQueue() {
  const box = $('queue'); box.replaceChildren();
  try {
    const page = await api('/api/queue', {project: $('project').value});
    if (!page.items.length) { box.append(el('p', {}, t('queueEmpty'))); return; }
    for (const m of page.items) {
      const item = el('div', {class: 'item'}); item.append(el('div', {}, `${m.mode} · ${m.category} · ${m.content.slice(0, 160)}`), el('div', {class: 'note'}, m.source));
      const actions = el('div', {class: 'actions'});
      for (const action of ['approve', 'reject']) { const b = el('button', {type: 'button'}, t(action)); b.onclick = () => decide(m, action); actions.append(b); }
      item.append(actions); box.append(item);
    }
  } catch (e) { $('status').textContent = e.message; }
}
async function decide(m, action) {
  const r = await fetch('/api/review', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-MM-Token': session.token}, body: JSON.stringify({project: m.project, id: m.id, action})});
  if (!r.ok) { $('status').textContent = t('failed'); return; }
  load();
}
async function search(ev) {
  ev.preventDefault();
  const qtext = $('search').value.trim();
  if (!qtext) { hits = new Set(); render(); return; }
  try { const r = await api('/api/search', {project: $('project').value, q: qtext}); hits = new Set(r.results.map(x => x.id)); render(); } catch (e) { $('status').textContent = e.message; }
}
function exportJson() {
  const blob = new Blob([JSON.stringify({project: $('project').value, exported: new Date().toISOString(), nodes: visible(), edges: data.edges}, null, 2)], {type: 'application/json'});
  const a = el('a', {href: URL.createObjectURL(blob), download: `memory-merge-${$('project').value}.json`});
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function setView(v) {
  view = v; $('viewGraph').classList.toggle('on', v === 'graph'); $('viewTimeline').classList.toggle('on', v === 'timeline');
  $('graphPanel').classList.toggle('hidden', v !== 'graph'); $('timelinePanel').classList.toggle('hidden', v !== 'timeline');
  if (v === 'timeline') loadTimeline(true);
}
function zoom(f) { scale = Math.max(0.3, Math.min(4, scale * f)); render(); }

fillSelect($('category'), CATS); fillSelect($('relation'), RELS);
$('lang').onclick = () => { lang = lang === 'zh' ? 'en' : 'zh'; applyLang(); };
$('load').onclick = load; $('filter').oninput = render; $('relation').onchange = render; $('category').onchange = load;
$('searchForm').onsubmit = search; $('export').onclick = exportJson; $('more').onclick = () => loadTimeline(false);
$('viewGraph').onclick = () => setView('graph'); $('viewTimeline').onclick = () => setView('timeline');
$('zoomIn').onclick = () => zoom(1.2); $('zoomOut').onclick = () => zoom(1 / 1.2); $('reset').onclick = () => { scale = 1; dx = dy = 0; render(); };
$('graph').addEventListener('wheel', e => { e.preventDefault(); zoom(e.deltaY < 0 ? 1.1 : 0.9); }, {passive: false});
$('graph').onpointerdown = e => { if (e.target.tagName === 'circle') return; drag = {x: e.clientX, y: e.clientY, dx, dy}; $('graph').setPointerCapture(e.pointerId); };
$('graph').onpointermove = e => { if (!drag) return; const ratio = 900 / $('graph').clientWidth; dx = drag.dx + (e.clientX - drag.x) * ratio; dy = drag.dy + (e.clientY - drag.y) * ratio; $('layer').setAttribute('transform', `translate(${dx} ${dy}) scale(${scale})`); };
$('graph').onpointerup = () => { drag = null; }; $('graph').onpointercancel = () => { drag = null; };
fetch('/api/session').then(r => r.json()).then(s => { session = s; $('reviewBox').classList.toggle('hidden', !s.review); }).catch(() => {}).finally(() => { applyLang(); load(); });
