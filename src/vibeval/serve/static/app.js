/* ================================================================
   Utilities
   ================================================================ */
const $ = (tag, attrs, ...children) => {
  const el = document.createElement(tag);
  if (attrs) Object.entries(attrs).forEach(([k,v]) => {
    if (k === 'className') el.className = v;
    else if (k === 'innerHTML') el.innerHTML = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
    else el.setAttribute(k, v);
  });
  children.flat().forEach(c => {
    if (c == null) return;
    el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  });
  return el;
};

function formatDuration(s) {
  if (!s || s < 0.01) return '<0.01s';
  if (s < 60) return s.toFixed(2) + 's';
  return Math.floor(s/60) + 'm ' + (s%60).toFixed(0) + 's';
}

function formatTime(ts) {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString();
}

function jsonPre(obj) {
  const wrap = $('div', {className: 'json-tree'});
  wrap.appendChild(jsonNode(obj));
  return wrap;
}

function jsonNode(value) {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) ||
        (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed !== null && typeof parsed === 'object') return jsonNode(parsed);
      } catch (e) { /* fall through to string render */ }
    }
    return jsonString(value);
  }
  if (value === null) return $('span', {className: 'jt-null'}, 'null');
  if (value === undefined) return $('span', {className: 'jt-null'}, 'undefined');
  if (typeof value === 'boolean') return $('span', {className: 'jt-bool'}, String(value));
  if (typeof value === 'number') return $('span', {className: 'jt-num'}, String(value));
  if (Array.isArray(value)) return jsonArray(value);
  if (typeof value === 'object') return jsonObject(value);
  return $('span', null, String(value));
}

function jsonString(s) {
  if (s.includes('\n')) {
    return $('div', {className: 'jt-str jt-multiline'}, s);
  }
  return $('span', {className: 'jt-str'}, '"' + s + '"');
}

function jsonCollapsible(summaryText, buildBody) {
  const wrap = $('div', {className: 'jt-coll'});
  const toggle = $('span', {className: 'jt-toggle'}, '▼');
  const summary = $('span', {className: 'jt-summary'}, summaryText);
  const header = $('div', {className: 'jt-header'}, toggle, summary);
  const body = $('div', {className: 'jt-body'});
  buildBody(body);
  let open = true;
  header.addEventListener('click', () => {
    open = !open;
    toggle.textContent = open ? '▼' : '▶';
    body.style.display = open ? '' : 'none';
  });
  wrap.appendChild(header);
  wrap.appendChild(body);
  return wrap;
}

function jsonArray(arr) {
  if (arr.length === 0) return $('span', {className: 'jt-empty'}, '[]');
  return jsonCollapsible('[' + arr.length + ']', (body) => {
    arr.forEach((item, i) => {
      const child = jsonNode(item);
      const isBlock = child.classList && child.classList.contains('jt-coll');
      const row = $('div', {className: 'jt-row'});
      row.appendChild($('span', {className: 'jt-key'}, i + ':'));
      if (isBlock) {
        row.classList.add('jt-row-block');
        row.appendChild(child);
      } else {
        row.appendChild(child);
      }
      body.appendChild(row);
    });
  });
}

function jsonObject(obj) {
  const keys = Object.keys(obj);
  if (keys.length === 0) return $('span', {className: 'jt-empty'}, '{}');
  return jsonCollapsible('{' + keys.length + (keys.length > 1 ? ' fields' : ' field') + '}', (body) => {
    keys.forEach(k => {
      const child = jsonNode(obj[k]);
      const isBlock = child.classList && (child.classList.contains('jt-coll') || child.classList.contains('jt-multiline'));
      const row = $('div', {className: 'jt-row'});
      row.appendChild($('span', {className: 'jt-key'}, k + ':'));
      if (isBlock) {
        row.classList.add('jt-row-block');
        row.appendChild(child);
      } else {
        row.appendChild(child);
      }
      body.appendChild(row);
    });
  });
}

function collapsible(title, content, startOpen) {
  const header = $('div', {className: 'collapsible' + (startOpen ? ' open' : '')});
  if (typeof title === 'string') header.appendChild(document.createTextNode(title));
  else header.appendChild(title);
  const body = $('div', {className: 'collapse-body' + (startOpen ? ' show' : '')});
  if (typeof content === 'function') {
    let rendered = false;
    header.addEventListener('click', () => {
      header.classList.toggle('open');
      body.classList.toggle('show');
      if (!rendered) { body.appendChild(content()); rendered = true; }
    });
    if (startOpen) { body.appendChild(content()); rendered = true; }
  } else {
    body.appendChild(content);
    header.addEventListener('click', () => {
      header.classList.toggle('open');
      body.classList.toggle('show');
    });
  }
  return $('div', null, header, body);
}

function badge(text, cls) { return $('span', {className: 'badge ' + cls}, text); }

function scoreBadge(score, method, scoring) {
  if (method === 'rule' || scoring === 'binary') {
    return badge(score === 1 ? 'PASS' : 'FAIL', score === 1 ? 'badge-pass' : 'badge-fail');
  }
  return badge(score + '/5', 'badge badge-score score-' + score);
}

function statBox(value, label, color) {
  const box = $('div', {className: 'stat-box'});
  box.appendChild($('div', {className: 'value', style: color ? 'color:'+color : ''}, String(value)));
  box.appendChild($('div', {className: 'label'}, label));
  return box;
}

function breadcrumb(...parts) {
  const bc = $('div', {className: 'breadcrumb'});
  parts.forEach((p, i) => {
    if (i > 0) bc.appendChild($('span', {className: 'sep'}, '/'));
    if (p.href) {
      bc.appendChild($('a', {href: p.href, onClick: (e) => { e.preventDefault(); navigate(p.href); }}, p.text));
    } else {
      bc.appendChild($('span', null, p.text));
    }
  });
  return bc;
}

/* ================================================================
   API client
   ================================================================ */
async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch('/api' + path, opts);
  if (res.status === 204) return null;
  const json = await res.json();
  if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
  return json.data;
}

/* ================================================================
   Router
   ================================================================ */
const routes = [];
function addRoute(pattern, handler) {
  const parts = pattern.split('/').filter(Boolean);
  const regex = new RegExp('^' + parts.map(p => p.startsWith(':') ? '([^/]+)' : p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\/') + '$');
  const paramNames = parts.filter(p => p.startsWith(':')).map(p => p.slice(1));
  routes.push({ regex, paramNames, handler });
}

function navigate(hash) {
  window.location.hash = hash;
}

function matchRoute(hash) {
  const path = hash.replace(/^#?\/?/, '');
  for (const route of routes) {
    const m = path.match(route.regex);
    if (m) {
      const params = {};
      route.paramNames.forEach((name, i) => params[name] = decodeURIComponent(m[i + 1]));
      return { handler: route.handler, params };
    }
  }
  return null;
}

async function handleRoute() {
  const hash = window.location.hash || '#/';
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading">LOADING</div>';

  const match = matchRoute(hash);
  const handler = match ? match.handler : renderFeaturesList;
  const params = match ? match.params : {};

  try {
    const content = await handler(params);
    app.innerHTML = '';
    if (content) app.appendChild(content);
  } catch (e) {
    app.innerHTML = '';
    app.appendChild($('div', {className: 'card'}, $('p', {style: 'color:var(--red)'}, 'Error: ' + e.message)));
  }
}

/* ================================================================
   Sidebar
   ================================================================ */
const NAV_ICONS = {
  overview: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></svg>',
  analysis: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="5.5"/><path d="M8 4v4l3 2"/></svg>',
  design: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2L6 8l-2 4 4-2 6-6-2-2z"/><path d="M10 4l2 2"/></svg>',
  trends: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,12 5,7 9,9 14,3"/><circle cx="14" cy="3" r="1" fill="currentColor"/></svg>',
  comparisons: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 2v12M12 2v12M1 8h14"/></svg>',
  home: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 7l6-5 6 5v6a1 1 0 01-1 1H3a1 1 0 01-1-1V7z"/></svg>',
  run: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="5,3 13,8 5,13" fill="currentColor" opacity=".5"/></svg>',
};

function navIcon(name) {
  const span = $('span', {className: 'nav-icon', innerHTML: NAV_ICONS[name] || ''});
  return span;
}

async function updateSidebar(feature) {
  const nav = document.getElementById('nav-links');
  nav.innerHTML = '';

  const home = $('a', {href: '#/', onClick: (e) => { e.preventDefault(); navigate('#/'); }});
  home.appendChild(navIcon('home'));
  home.appendChild(document.createTextNode('All Features'));
  nav.appendChild(home);

  if (feature) {
    nav.appendChild($('div', {className: 'nav-section'}, feature));
    const links = [
      { href: `#/features/${feature}`, text: 'Overview', icon: 'overview' },
      { href: `#/features/${feature}/analysis`, text: 'Analysis', icon: 'analysis' },
      { href: `#/features/${feature}/design`, text: 'Design', icon: 'design' },
      { href: `#/features/${feature}/trends`, text: 'Trends', icon: 'trends' },
      { href: `#/features/${feature}/comparisons`, text: 'Comparisons', icon: 'comparisons' },
    ];
    links.forEach(l => {
      const a = $('a', {href: l.href, onClick: (e) => { e.preventDefault(); navigate(l.href); }});
      a.appendChild(navIcon(l.icon));
      a.appendChild(document.createTextNode(l.text));
      if (window.location.hash === l.href) a.className = 'active';
      nav.appendChild(a);
    });

    try {
      const runs = await api('GET', `/features/${feature}/runs`);
      if (runs.length > 0) {
        nav.appendChild($('div', {className: 'nav-section'}, 'Runs'));
        runs.slice().reverse().forEach(r => {
          const rid = r.run_id || r;
          const a = $('a', {href: `#/features/${feature}/runs/${rid}`, onClick: (e) => { e.preventDefault(); navigate(`#/features/${feature}/runs/${rid}`); }});
          a.appendChild(navIcon('run'));
          a.appendChild(document.createTextNode(rid));
          if (window.location.hash === `#/features/${feature}/runs/${rid}`) a.className = 'active';
          nav.appendChild(a);
        });
      }
    } catch(e) {}
  }
}

/* ================================================================
   Modal helpers
   ================================================================ */
function showModal(title, contentFn, actions) {
  const overlay = $('div', {className: 'modal-overlay'});
  const modal = $('div', {className: 'modal'});
  modal.appendChild($('h3', null, title));
  const body = contentFn();
  modal.appendChild(body);
  const actBar = $('div', {className: 'modal-actions'});
  actBar.appendChild($('button', {className: 'btn', onClick: () => overlay.remove()}, 'Cancel'));
  if (actions) actions.forEach(a => {
    actBar.appendChild($('button', {className: 'btn ' + (a.cls || ''), onClick: async () => {
      try { await a.action(body); overlay.remove(); } catch(e) { alert('Error: ' + e.message); }
    }}, a.text));
  });
  modal.appendChild(actBar);
  overlay.appendChild(modal);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
}

function confirmDialog(title, message, onConfirm) {
  showModal(title, () => $('p', {style:'color:var(--text-secondary)'}, message), [
    { text: 'Delete', cls: 'btn-danger', action: onConfirm }
  ]);
}

/* ================================================================
   Page: Features List
   ================================================================ */
async function renderFeaturesList() {
  updateSidebar(null);
  const features = await api('GET', '/features');
  const wrap = $('div', {className: 'stagger'});
  wrap.appendChild($('div', {className: 'page-title'}, 'Features'));

  if (features.length === 0) {
    wrap.appendChild($('div', {className: 'card'}, $('p', {style:'color:var(--text-secondary)'}, 'No features found. Check that your vibeval_root is configured correctly.')));
    return wrap;
  }

  const grid = $('div', {className: 'feature-grid'});
  features.forEach(f => {
    const card = $('div', {className: 'feature-card', onClick: () => navigate(`#/features/${f.name}`)});
    card.appendChild($('h3', null, f.name));
    const pr = f.latest_pass_rate != null ? (f.latest_pass_rate * 100).toFixed(0) + '%' : '-';
    const prColor = f.latest_pass_rate >= 1 ? 'var(--green)' : f.latest_pass_rate >= 0.8 ? 'var(--yellow)' : f.latest_pass_rate != null ? 'var(--red)' : 'var(--text-dim)';
    card.appendChild($('div', {className: 'meta'},
      $('span', null, f.dataset_count + ' datasets'),
      $('span', null, f.run_count + ' runs'),
      $('span', {style: 'color:' + prColor + ';font-weight:600'}, pr)
    ));
    if (f.latest_run) {
      card.appendChild($('div', {style:'font-size:12px;color:var(--text-dim);margin-top:10px;font-family:var(--font-mono)'}, 'latest: ' + f.latest_run));
    }
    grid.appendChild(card);
  });
  wrap.appendChild(grid);
  return wrap;
}

/* ================================================================
   Page: Feature Detail
   ================================================================ */
async function renderFeatureDetail(params) {
  const feature = params.feature;
  updateSidebar(feature);
  const data = await api('GET', `/features/${feature}`);
  const wrap = $('div', {className: 'stagger'});
  wrap.appendChild(breadcrumb({href:'#/', text:'Features'}, {text: feature}));
  wrap.appendChild($('div', {className: 'page-title'}, feature));

  // Datasets
  const dsCard = $('div', {className: 'card'});
  const dsHeader = $('div', {style:'display:flex;justify-content:space-between;align-items:center'});
  dsHeader.appendChild($('h2', null, 'Datasets'));
  dsHeader.appendChild($('button', {className:'btn btn-primary btn-sm', onClick: () => showCreateDatasetModal(feature)}, '+ New'));
  dsCard.appendChild(dsHeader);

  if (data.datasets.length === 0) {
    dsCard.appendChild($('p', {style:'color:var(--text-dim)'}, 'No datasets yet.'));
  } else {
    data.datasets.forEach(ds => {
      const row = $('div', {style:'display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border);cursor:pointer;transition:background .15s'});
      row.addEventListener('mouseenter', () => row.style.background = 'rgba(255,255,255,.02)');
      row.addEventListener('mouseleave', () => row.style.background = 'transparent');
      row.appendChild($('div', null,
        $('strong', {style:'color:var(--text)'}, ds.name),
        $('span', {style:'color:var(--text-dim);margin-left:10px;font-size:13px'}, ds.description || ''),
        $('span', {style:'color:var(--text-dim);margin-left:10px;font-size:12px;font-family:var(--font-mono)'}, (ds.items||[]).length + ' items')
      ));
      row.appendChild($('div', null,
        $('span', {style:'font-size:12px;color:var(--text-dim);font-family:var(--font-mono)'}, (ds.judge_specs||[]).length + ' specs')
      ));
      row.addEventListener('click', () => navigate(`#/features/${feature}/datasets/${ds.name}`));
      dsCard.appendChild(row);
    });
  }
  wrap.appendChild(dsCard);

  // Runs
  const runCard = $('div', {className: 'card'});
  runCard.appendChild($('h2', null, 'Runs'));

  if (data.runs.length === 0) {
    runCard.appendChild($('p', {style:'color:var(--text-dim)'}, 'No runs yet.'));
  } else {
    const tbl = $('table');
    tbl.appendChild($('thead', null, $('tr', null,
      $('th', null, 'Run ID'), $('th', null, 'Tests'), $('th', null, 'Pass Rate'), $('th', null, 'Duration')
    )));
    const tbody = $('tbody');
    data.runs.slice().reverse().forEach(r => {
      const bs = r.binary_stats || {};
      const pr = bs.pass_rate != null ? (bs.pass_rate * 100).toFixed(0) + '%' : '-';
      const prColor = bs.pass_rate >= 1 ? 'var(--green)' : bs.pass_rate >= 0.8 ? 'var(--yellow)' : bs.pass_rate != null ? 'var(--red)' : '';
      const row = $('tr', {className:'clickable', onClick: () => navigate(`#/features/${feature}/runs/${r.run_id}`)},
        $('td', {style:'font-family:var(--font-mono);font-weight:500'}, r.run_id || '-'),
        $('td', null, String(r.total || '-')),
        $('td', null, $('span', {style:'color:'+prColor+';font-weight:600'}, pr)),
        $('td', {style:'color:var(--text-dim)'}, r.duration ? formatDuration(r.duration) : '-')
      );
      tbody.appendChild(row);
    });
    tbl.appendChild(tbody);
    runCard.appendChild(tbl);
  }
  wrap.appendChild(runCard);

  return wrap;
}

/* ================================================================
   Page: Dataset Detail
   ================================================================ */
async function renderDatasetDetail(params) {
  const { feature, dataset } = params;
  updateSidebar(feature);
  const ds = await api('GET', `/features/${feature}/datasets/${dataset}`);
  const wrap = $('div', {className: 'stagger'});
  wrap.appendChild(breadcrumb({href:'#/', text:'Features'}, {href:`#/features/${feature}`, text:feature}, {text:dataset}));

  const header = $('div', {style:'display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px'});
  header.appendChild($('div', null,
    $('div', {className:'page-title', style:'margin-bottom:4px'}, ds.name),
    ds.description ? $('p', {style:'color:var(--text-secondary);font-size:15px'}, ds.description) : null
  ));
  const actions = $('div', {style:'display:flex;gap:8px'});
  actions.appendChild($('button', {className:'btn btn-sm', onClick: () => showEditDatasetModal(feature, ds)}, 'Edit'));
  actions.appendChild($('button', {className:'btn btn-danger btn-sm', onClick: () => {
    confirmDialog('Delete Dataset', `Delete "${ds.name}" and all its items? This cannot be undone.`, async () => {
      await api('DELETE', `/features/${feature}/datasets/${dataset}`);
      navigate(`#/features/${feature}`);
    });
  }}, 'Delete'));
  header.appendChild(actions);
  wrap.appendChild(header);

  if (ds.judge_specs && ds.judge_specs.length > 0) {
    const specCard = $('div', {className:'card'});
    specCard.appendChild($('h2', null, 'Default Judge Specs'));
    ds.judge_specs.forEach(spec => specCard.appendChild(renderSpec(spec)));
    wrap.appendChild(specCard);
  }

  const itemCard = $('div', {className:'card'});
  const itemHeader = $('div', {style:'display:flex;justify-content:space-between;align-items:center'});
  itemHeader.appendChild($('h2', null, `Items (${(ds.items||[]).length})`));
  itemHeader.appendChild($('button', {className:'btn btn-primary btn-sm', onClick: () => showCreateItemModal(feature, dataset)}, '+ New'));
  itemCard.appendChild(itemHeader);

  (ds.items || []).forEach(item => {
    const hasOverride = item.judge_specs && item.judge_specs.length > 0;
    const title = $('div', {style:'display:flex;justify-content:space-between;align-items:center;width:100%'},
      $('span', null,
        item.id,
        item.tags && item.tags.length > 0 ? $('span', {style:'margin-left:8px'}, ...item.tags.map(t => badge(t, 'badge-rule'))) : null,
        hasOverride ? $('span', {style:'margin-left:8px'}, badge('custom specs', 'badge-gate')) : null
      ),
      $('span', {style:'display:flex;gap:4px'},
        $('button', {className:'btn btn-sm', onClick: (e) => { e.stopPropagation(); showEditItemModal(feature, dataset, item); }}, 'Edit'),
        $('button', {className:'btn btn-danger btn-sm', onClick: (e) => {
          e.stopPropagation();
          confirmDialog('Delete Item', `Delete item "${item.id}"?`, async () => {
            await api('DELETE', `/features/${feature}/datasets/${dataset}/items/${item.id}`);
            handleRoute();
          });
        }}, 'Del')
      )
    );
    itemCard.appendChild(collapsible(title, () => {
      const w = $('div');
      w.appendChild(jsonPre(item.data));
      if (hasOverride) {
        w.appendChild($('h4', {style:'margin-top:12px;font-family:var(--font-display);font-size:14px;color:var(--text-secondary)'}, 'Item Judge Specs'));
        item.judge_specs.forEach(spec => w.appendChild(renderSpec(spec)));
      }
      return w;
    }));
  });
  wrap.appendChild(itemCard);

  return wrap;
}

function renderSpec(spec) {
  const detail = $('div', {className: 'spec-detail'});
  const header = $('div', {style:'display:flex;gap:8px;align-items:center;margin-bottom:8px'});
  header.appendChild(badge(spec.method, spec.method === 'rule' ? 'badge-rule' : 'badge-llm'));
  if (spec.method === 'rule') header.appendChild($('strong', {style:'color:var(--text)'}, spec.rule));
  if (spec.weight === 'gate') header.appendChild(badge('GATE', 'badge-gate'));
  detail.appendChild(header);

  if (spec.method === 'rule' && spec.args) {
    const dl = $('dl');
    Object.entries(spec.args).forEach(([k,v]) => {
      dl.appendChild($('dt', null, k));
      dl.appendChild($('dd', null, typeof v === 'object' ? JSON.stringify(v) : String(v)));
    });
    detail.appendChild(dl);
  }

  if (spec.method === 'llm') {
    const dl = $('dl');
    if (spec.scoring) { dl.appendChild($('dt', null, 'Scoring')); dl.appendChild($('dd', null, spec.scoring)); }
    if (spec.criteria) { dl.appendChild($('dt', null, 'Criteria')); dl.appendChild($('dd', null, spec.criteria)); }
    if (spec.test_intent) { dl.appendChild($('dt', null, 'Test Intent')); dl.appendChild($('dd', null, spec.test_intent)); }
    if (spec.trap_design) { dl.appendChild($('dt', null, 'Trap Design')); dl.appendChild($('dd', null, spec.trap_design)); }
    if (spec.target && spec.target !== 'output') { dl.appendChild($('dt', null, 'Target')); dl.appendChild($('dd', null, JSON.stringify(spec.target))); }
    if (spec.anchors) {
      dl.appendChild($('dt', null, 'Anchors'));
      const anchorList = $('div');
      Object.entries(spec.anchors).forEach(([score, desc]) => {
        anchorList.appendChild($('div', {style:'margin:4px 0'}, $('strong', {style:'color:var(--accent)'}, score + ': '), desc));
      });
      dl.appendChild($('dd', null, anchorList));
    }
    if (spec.calibrations && spec.calibrations.length > 0) {
      dl.appendChild($('dt', null, 'Calibrations (' + spec.calibrations.length + ')'));
      spec.calibrations.forEach((cal, i) => {
        dl.appendChild($('dd', null, collapsible('Example ' + (i+1) + ' (score: ' + cal.score + ')', () => jsonPre(cal))));
      });
    }
    detail.appendChild(dl);
  }
  return detail;
}

/* ================================================================
   Page: Run Detail
   ================================================================ */
async function renderRunDetail(params) {
  const { feature, run_id } = params;
  updateSidebar(feature);
  const data = await api('GET', `/features/${feature}/runs/${run_id}`);
  const wrap = $('div', {className: 'stagger'});
  wrap.appendChild(breadcrumb({href:'#/', text:'Features'}, {href:`#/features/${feature}`, text:feature}, {text: run_id}));

  const s = data.summary;
  const bs = s.binary_stats || {};
  const fs = s.five_point_stats || {};

  wrap.appendChild($('div', {className: 'page-title'}, run_id));

  const stats = $('div', {className: 'stats'});
  const passRate = bs.total > 0 ? (bs.pass_rate * 100).toFixed(0) + '%' : '-';
  stats.appendChild(statBox(passRate, 'Pass Rate', bs.pass_rate >= 1 ? 'var(--green)' : bs.pass_rate >= 0.8 ? 'var(--yellow)' : 'var(--red)'));
  stats.appendChild(statBox(s.total, 'Test Cases', 'var(--text)'));
  stats.appendChild(statBox((bs.passed||0) + '/' + (bs.total||0), 'Passed', 'var(--text)'));
  stats.appendChild(statBox(formatDuration(s.duration), 'Duration', 'var(--text)'));
  wrap.appendChild(stats);

  if (bs.total > 0) {
    const card = $('div', {className: 'card'});
    card.appendChild($('h3', null, 'Binary Pass Rate'));
    const bar = $('div', {className: 'bar-container'});
    bar.appendChild($('div', {className: 'bar-pass', style: 'width:' + (bs.pass_rate*100) + '%'}));
    bar.appendChild($('div', {className: 'bar-fail', style: 'width:' + ((1-bs.pass_rate)*100) + '%'}));
    card.appendChild(bar);
    card.appendChild($('div', {className: 'bar-label'}, bs.passed + ' passed, ' + bs.failed + ' failed'));
    wrap.appendChild(card);
  }

  const criteria = Object.keys(fs);
  if (criteria.length > 0) {
    const card = $('div', {className: 'card'});
    card.appendChild($('h3', null, 'Five-Point Scores'));
    criteria.forEach(c => {
      const d = fs[c];
      const total = [1,2,3,4,5].reduce((a,i) => a + (d[i]||0), 0);
      const row = $('div', {className: 'dist-row'});
      row.appendChild($('div', {className: 'dist-label', title: c}, c));
      const bar = $('div', {className: 'dist-bar'});
      [1,2,3,4,5].forEach(i => {
        const pct = total > 0 ? (d[i]||0)/total*100 : 0;
        if (pct > 0) bar.appendChild($('div', {className: 'dist-'+i, style: 'width:'+pct+'%', title: i+': '+(d[i]||0)}));
      });
      row.appendChild(bar);
      row.appendChild($('div', {className: 'dist-avg'}, (d.avg||0).toFixed(1)));
      card.appendChild(row);
    });
    wrap.appendChild(card);
  }

  // Results table
  const resCard = $('div', {className: 'card'});
  resCard.appendChild($('h2', null, 'Test Results'));
  const tbl = $('table');
  tbl.appendChild($('thead', null, $('tr', null,
    $('th', null, 'Test'), $('th', null, 'Dataset'), $('th', null, 'Item'),
    $('th', null, 'Judges'), $('th', null, 'Status'), $('th', null, 'Duration')
  )));
  const tbody = $('tbody');
  data.results.forEach((r, idx) => {
    const jrs = r.judge_results || [];
    const hasFailure = jrs.some(j => { const sp = j.spec || {}; return (sp.method === 'rule' || sp.scoring === 'binary') && j.score === 0; });
    const allPass = jrs.length > 0 && jrs.every(j => { const sp = j.spec || {}; if (sp.method === 'rule' || sp.scoring === 'binary') return j.score === 1; return j.score >= 4; });
    const status = jrs.length === 0 ? badge('N/A', '') : hasFailure ? badge('FAIL', 'badge-fail') : allPass ? badge('PASS', 'badge-pass') : badge('MIXED', 'badge-gate');
    const row = $('tr', {className:'clickable', onClick: () => { document.getElementById('result-'+idx)?.scrollIntoView({behavior:'smooth'}); }},
      $('td', {style:'font-weight:500'}, r.test_name), $('td', null, r.dataset), $('td', null, r.item_id),
      $('td', null, jrs.length + ''), $('td', null, status), $('td', {style:'color:var(--text-dim);font-family:var(--font-mono);font-size:12px'}, formatDuration(r.duration || 0))
    );
    tbody.appendChild(row);
  });
  tbl.appendChild(tbody);
  resCard.appendChild(tbl);
  wrap.appendChild(resCard);

  // Detailed results
  data.results.forEach((r, idx) => {
    const jrs = r.judge_results || [];
    const hasFailure = jrs.some(j => { const sp = j.spec || {}; return (sp.method === 'rule' || sp.scoring === 'binary') && j.score === 0; });

    const card = $('div', {className: 'card result-card' + (hasFailure ? ' has-failure' : ''), id: 'result-' + idx});
    const hdr = $('div', {style:'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px'});
    hdr.appendChild($('div', null,
      $('strong', {style:'font-size:15px;font-family:var(--font-display)'}, r.test_name),
      $('span', {style:'color:var(--text-dim);margin-left:10px;font-size:13px;font-family:var(--font-mono)'}, r.dataset + ' / ' + r.item_id)
    ));
    hdr.appendChild($('div', {style:'font-size:12px;color:var(--text-dim);font-family:var(--font-mono)'}, formatDuration(r.duration || 0)));
    card.appendChild(hdr);

    if (jrs.length > 0) {
      card.appendChild(collapsible('Judge Results (' + jrs.length + ')', () => {
        const t = $('table');
        t.appendChild($('thead', null, $('tr', null, $('th', null, 'Method'), $('th', null, 'Rule / Criteria'), $('th', null, 'Score'), $('th', null, 'Reason'))));
        const tb = $('tbody');
        jrs.forEach(jr => {
          const sp = jr.spec || {};
          const methodBadge = badge(sp.method, sp.method === 'rule' ? 'badge-rule' : 'badge-llm');
          const gateBadge = sp.weight === 'gate' ? badge('GATE', 'badge-gate') : null;
          const name = sp.method === 'rule' ? sp.rule : (sp.criteria || '').substring(0, 60) + ((sp.criteria||'').length > 60 ? '...' : '');
          tb.appendChild($('tr', null,
            $('td', null, methodBadge, gateBadge ? $('span', null, ' ', gateBadge) : ''),
            $('td', null, name),
            $('td', null, scoreBadge(jr.score, sp.method, sp.scoring)),
            $('td', {style:'font-size:13px;max-width:400px;color:var(--text-secondary)'}, jr.reason || '')
          ));
        });
        t.appendChild(tb);
        return t;
      }, true));
    }

    if (r.trace && r.trace.turns && r.trace.turns.length > 0) {
      card.appendChild(collapsible('Trace (' + r.trace.turns.length + ' turn' + (r.trace.turns.length > 1 ? 's' : '') + ')', () => {
        const w = $('div');
        r.trace.turns.forEach(turn => {
          const t = $('div', {className: 'turn'});
          t.appendChild($('div', {className: 'turn-header'}, 'Turn ' + turn.turn));
          if (turn.input) t.appendChild(collapsible('Input', () => jsonPre(turn.input)));
          if (turn.steps && turn.steps.length > 0) {
            const timeline = $('div', {className: 'timeline'});
            turn.steps.forEach(step => {
              const s = $('div', {className: 'step ' + (step.type || '')});
              s.appendChild($('div', {className: 'step-dot'}));
              const body = $('div', {className: 'step-body'});
              const h = $('div', {style:'display:flex;align-items:center;gap:8px'});
              h.appendChild($('span', {className: 'step-type'}, step.type));
              if (step.type === 'tool_call' && step.data?.name) h.appendChild($('span', {className: 'step-header'}, step.data.name));
              else if (step.type === 'tool_result' && step.data?.name) h.appendChild($('span', {className: 'step-header'}, step.data.name));
              else if (step.type === 'llm_call' && step.data?.system) h.appendChild($('span', {className: 'step-header'}, step.data.system.substring(0, 60)));
              body.appendChild(h);
              if (step.data) body.appendChild(collapsible('Details', () => jsonPre(step.data)));
              s.appendChild(body);
              timeline.appendChild(s);
            });
            t.appendChild(timeline);
          }
          if (turn.output) t.appendChild(collapsible('Output', () => jsonPre(turn.output)));
          w.appendChild(t);
        });
        return w;
      }));
    }

    if (r.inputs) card.appendChild(collapsible('Inputs', () => jsonPre(r.inputs)));
    if (r.outputs) card.appendChild(collapsible('Outputs', () => jsonPre(r.outputs)));
    wrap.appendChild(card);
  });

  return wrap;
}

/* ================================================================
   Page: Analysis
   ================================================================ */
async function renderAnalysis(params) {
  const { feature } = params;
  updateSidebar(feature);
  const data = await api('GET', `/features/${feature}/analysis`);
  const wrap = $('div', {className: 'stagger'});
  wrap.appendChild(breadcrumb({href:'#/', text:'Features'}, {href:`#/features/${feature}`, text:feature}, {text:'Analysis'}));
  wrap.appendChild($('div', {className: 'page-title'}, 'Analysis'));

  if (!data || Object.keys(data).length === 0) {
    wrap.appendChild($('div', {className:'card'}, $('p', {style:'color:var(--text-dim)'}, 'No analysis data found. Run /vibeval to generate.')));
    return wrap;
  }

  const analysis = data.analysis || data[Object.keys(data)[0]] || data;

  if (analysis.project) {
    const card = $('div', {className:'card'});
    card.appendChild($('h2', null, 'Project'));
    const p = analysis.project;
    const dl = $('dl', {className:'spec-detail'});
    if (p.name) { dl.appendChild($('dt', null, 'Name')); dl.appendChild($('dd', null, p.name)); }
    if (p.language) { dl.appendChild($('dt', null, 'Language')); dl.appendChild($('dd', null, p.language)); }
    if (p.test_framework) { dl.appendChild($('dt', null, 'Test Framework')); dl.appendChild($('dd', null, p.test_framework)); }
    if (p.ai_frameworks) { dl.appendChild($('dt', null, 'AI Frameworks')); dl.appendChild($('dd', null, p.ai_frameworks.join(', '))); }
    card.appendChild(dl);
    wrap.appendChild(card);
  }

  if (analysis.pipelines && analysis.pipelines.length > 0) {
    const card = $('div', {className:'card'});
    card.appendChild($('h2', null, 'Pipelines'));
    analysis.pipelines.forEach(pipe => {
      const pipeWrap = $('div', {style:'margin-bottom:24px'});
      pipeWrap.appendChild($('h3', {style:'margin-bottom:8px;color:var(--text)'}, pipe.name));
      if (pipe.description) pipeWrap.appendChild($('p', {style:'color:var(--text-secondary);margin-bottom:12px;font-size:14px;line-height:1.6'}, pipe.description.trim()));

      const meta = $('div', {style:'display:flex;gap:12px;margin-bottom:12px;font-size:13px'});
      if (pipe.entry_point) meta.appendChild($('span', null, badge('entry', 'badge-rule'), ' ', $('span', {style:'font-family:var(--font-mono)'}, pipe.entry_point)));
      if (pipe.type) meta.appendChild(badge(pipe.type, 'badge-llm'));
      pipeWrap.appendChild(meta);

      if (pipe.ai_calls && pipe.ai_calls.length > 0) {
        pipeWrap.appendChild(collapsible(`AI Calls (${pipe.ai_calls.length})`, () => {
          const w = $('div');
          pipe.ai_calls.forEach(call => {
            const callDiv = $('div', {className:'spec-detail', style:'margin-bottom:8px'});
            callDiv.appendChild($('div', {style:'display:flex;gap:8px;align-items:center;margin-bottom:6px'},
              $('strong', {style:'color:var(--text)'}, call.id || call.function),
              call.file ? $('span', {style:'color:var(--text-dim);font-size:12px;font-family:var(--font-mono)'}, call.file + ':' + (call.function || '')) : null
            ));
            if (call.purpose) callDiv.appendChild($('p', {style:'font-size:13px;margin-bottom:4px;color:var(--text-secondary)'}, call.purpose));
            if (call.mock_target) callDiv.appendChild($('div', {style:'font-size:11px;color:var(--text-dim);font-family:var(--font-mono)'}, 'mock: ' + call.mock_target));
            if (call.input_description) callDiv.appendChild(collapsible('Input', () => $('p', {style:'font-size:13px;color:var(--text-secondary)'}, call.input_description.trim())));
            if (call.output_description) callDiv.appendChild(collapsible('Output', () => $('p', {style:'font-size:13px;color:var(--text-secondary)'}, call.output_description.trim())));
            w.appendChild(callDiv);
          });
          return w;
        }, true));
      }

      if (pipe.external_deps && pipe.external_deps.length > 0) {
        pipeWrap.appendChild(collapsible(`External Dependencies (${pipe.external_deps.length})`, () => {
          const w = $('div');
          pipe.external_deps.forEach(dep => {
            const d = $('div', {className:'spec-detail', style:'margin-bottom:8px'});
            d.appendChild($('strong', {style:'color:var(--text)'}, dep.id || dep.function));
            if (dep.purpose) d.appendChild($('p', {style:'font-size:13px;color:var(--text-secondary)'}, dep.purpose));
            if (dep.mock_target) d.appendChild($('div', {style:'font-size:11px;color:var(--text-dim);font-family:var(--font-mono)'}, 'mock: ' + dep.mock_target));
            w.appendChild(d);
          });
          return w;
        }));
      }

      if (pipe.data_flow && pipe.data_flow.length > 0) {
        pipeWrap.appendChild(collapsible('Data Flow', () => {
          const timeline = $('div', {className:'timeline'});
          pipe.data_flow.forEach(stage => {
            const s = $('div', {className:'step'});
            s.appendChild($('div', {className:'step-dot'}));
            const body = $('div', {className:'step-body'});
            const hdr = $('div', {style:'display:flex;align-items:center;gap:8px'});
            hdr.appendChild($('span', {className:'step-header'}, stage.stage));
            if (stage.call_id) hdr.appendChild(badge(stage.call_id, 'badge-llm'));
            if (stage.condition) hdr.appendChild($('span', {style:'font-size:11px;color:var(--text-dim);font-family:var(--font-mono)'}, 'if: ' + stage.condition));
            body.appendChild(hdr);
            if (stage.source) body.appendChild($('div', {style:'font-size:12px;color:var(--text-dim);font-family:var(--font-mono)'}, stage.source));
            if (stage.description) body.appendChild($('div', {style:'font-size:13px;margin-top:4px;color:var(--text-secondary)'}, stage.description));
            if (stage.notes) body.appendChild($('div', {style:'font-size:13px;margin-top:4px;color:var(--text-dim)'}, stage.notes.trim()));
            if (stage.key_fields) body.appendChild($('div', {style:'font-size:12px;margin-top:4px'}, stage.key_fields.map(f => badge(f, 'badge-rule')).reduce((acc, b) => { acc.appendChild($('span', null, ' ')); acc.appendChild(b); return acc; }, $('span'))));
            s.appendChild(body);
            timeline.appendChild(s);
          });
          return timeline;
        }, true));
      }

      card.appendChild(pipeWrap);
    });
    wrap.appendChild(card);
  }

  if (analysis.excluded_pipelines && analysis.excluded_pipelines.length > 0) {
    const card = $('div', {className:'card'});
    card.appendChild($('h2', null, 'Excluded Pipelines'));
    analysis.excluded_pipelines.forEach(ep => {
      const d = $('div', {style:'padding:12px 0;border-bottom:1px solid var(--border)'});
      d.appendChild($('div', null, $('strong', {style:'color:var(--text)'}, ep.name), ep.location ? $('span', {style:'margin-left:10px;font-size:11px;color:var(--text-dim);font-family:var(--font-mono)'}, ep.location) : null));
      if (ep.reason) d.appendChild($('p', {style:'font-size:13px;color:var(--text-dim);margin-top:6px;line-height:1.5'}, ep.reason.trim()));
      card.appendChild(d);
    });
    wrap.appendChild(card);
  }

  if (analysis.suggestions && analysis.suggestions.length > 0) {
    const card = $('div', {className:'card'});
    card.appendChild($('h2', null, 'Suggestions'));
    analysis.suggestions.forEach(sug => {
      const d = $('div', {style:'padding:14px 0;border-bottom:1px solid var(--border)'});
      d.appendChild($('div', {style:'display:flex;gap:8px;align-items:center;margin-bottom:8px'},
        badge(sug.severity, sug.severity === 'high' ? 'badge-fail' : sug.severity === 'medium' ? 'badge-gate' : 'badge-rule'),
        sug.category ? badge(sug.category, 'badge-llm') : null,
        sug.location ? $('span', {style:'font-size:11px;color:var(--text-dim);font-family:var(--font-mono)'}, sug.location) : null
      ));
      if (sug.issue) d.appendChild($('p', {style:'font-size:14px;margin-bottom:6px;color:var(--text-secondary);line-height:1.5'}, sug.issue.trim()));
      if (sug.suggestion) d.appendChild($('p', {style:'font-size:13px;color:var(--accent);line-height:1.5'}, sug.suggestion.trim()));
      card.appendChild(d);
    });
    wrap.appendChild(card);
  }

  return wrap;
}

/* ================================================================
   Page: Design
   ================================================================ */
async function renderDesignPage(params) {
  const { feature } = params;
  updateSidebar(feature);
  const data = await api('GET', `/features/${feature}/design`);
  const wrap = $('div', {className: 'stagger'});
  wrap.appendChild(breadcrumb({href:'#/', text:'Features'}, {href:`#/features/${feature}`, text:feature}, {text:'Design'}));
  wrap.appendChild($('div', {className: 'page-title'}, 'Test Design'));

  if (!data || Object.keys(data).length === 0) {
    wrap.appendChild($('div', {className:'card'}, $('p', {style:'color:var(--text-dim)'}, 'No design data found. Run /vibeval to generate.')));
    return wrap;
  }

  const design = data.design || data[Object.keys(data)[0]] || data;

  if (design.source_analysis) {
    wrap.appendChild($('div', {style:'font-size:12px;color:var(--text-dim);margin-bottom:16px;font-family:var(--font-mono)'}, 'source: ' + design.source_analysis));
  }

  if (design.datasets && design.datasets.length > 0) {
    design.datasets.forEach(ds => {
      const card = $('div', {className:'card'});
      card.appendChild($('h2', null, ds.name));
      if (ds.description) card.appendChild($('p', {style:'color:var(--text-secondary);margin-bottom:14px;font-size:14px;line-height:1.6'}, ds.description.trim()));

      const meta = $('div', {style:'display:flex;gap:12px;margin-bottom:16px'});
      if (ds.target_pipeline) meta.appendChild($('span', {style:'font-size:13px'}, badge('pipeline', 'badge-rule'), ' ', $('span', {style:'font-family:var(--font-mono)'}, ds.target_pipeline)));
      if (ds.type) meta.appendChild(badge(ds.type, 'badge-llm'));
      card.appendChild(meta);

      if (ds.items && ds.items.length > 0) {
        card.appendChild($('h3', null, `Test Items (${ds.items.length})`));
        ds.items.forEach(item => {
          const titleParts = [item.id || item.name];
          if (item._tags && item._tags.length > 0) titleParts.push('[' + item._tags.join(', ') + ']');
          card.appendChild(collapsible(titleParts.join(' '), () => {
            const w = $('div', {style:'padding-left:12px'});
            if (item.description) w.appendChild($('p', {style:'font-size:14px;margin-bottom:10px;color:var(--text-secondary);line-height:1.6'}, item.description.trim()));
            if (item.data) {
              const dl = $('dl', {className:'spec-detail'});
              if (item.data.system_prompt) { dl.appendChild($('dt', null, 'System Prompt')); dl.appendChild($('dd', null, item.data.system_prompt.trim())); }
              if (item.data.opening_message) { dl.appendChild($('dt', null, 'Opening Message')); dl.appendChild($('dd', null, item.data.opening_message)); }
              if (item.data.behavior_rules) {
                dl.appendChild($('dt', null, 'Behavior Rules'));
                const ul = $('ul', {style:'margin:4px 0 0 20px;font-size:13px;color:var(--text-secondary)'});
                item.data.behavior_rules.forEach(r => ul.appendChild($('li', {style:'margin:4px 0'}, r)));
                dl.appendChild($('dd', null, ul));
              }
              if (item.data.rounds) { dl.appendChild($('dt', null, 'Rounds')); dl.appendChild($('dd', null, String(item.data.rounds))); }
              w.appendChild(dl);
            }
            return w;
          }));
        });
      }

      if (ds.judge_specs && ds.judge_specs.length > 0) {
        card.appendChild($('h3', {style:'margin-top:24px'}, `Judge Specs (${ds.judge_specs.length})`));
        ds.judge_specs.forEach(spec => card.appendChild(renderSpec(spec)));
      }
      wrap.appendChild(card);
    });
  }

  if (design.test_code) {
    const card = $('div', {className:'card'});
    card.appendChild($('h2', null, 'Test Code Plan'));
    if (design.test_code.framework) {
      card.appendChild($('p', {style:'margin-bottom:12px;font-size:12px;color:var(--text-dim);font-family:var(--font-mono)'}, 'framework: ' + design.test_code.framework));
    }
    if (design.test_code.tests && design.test_code.tests.length > 0) {
      const tbl = $('table');
      tbl.appendChild($('thead', null, $('tr', null, $('th', null, 'Test'), $('th', null, 'Type'), $('th', null, 'Dataset'), $('th', null, 'Pipeline Entry'))));
      const tbody = $('tbody');
      design.test_code.tests.forEach(t => {
        tbody.appendChild($('tr', null,
          $('td', null, $('strong', {style:'color:var(--text)'}, t.name)),
          $('td', null, t.type ? badge(t.type, 'badge-llm') : '-'),
          $('td', null, t.dataset || '-'),
          $('td', {style:'font-family:var(--font-mono);font-size:12px;color:var(--text-dim)'}, t.pipeline_entry || '-')
        ));
      });
      tbl.appendChild(tbody);
      card.appendChild(tbl);
      design.test_code.tests.forEach(t => {
        if (t.notes) card.appendChild(collapsible(t.name + ' — notes', () => $('p', {style:'font-size:13px;padding:8px;color:var(--text-secondary);line-height:1.5'}, t.notes.trim())));
      });
    }
    wrap.appendChild(card);
  }

  return wrap;
}

/* ================================================================
   Page: Trends (Chart.js)
   ================================================================ */
async function renderTrends(params) {
  const { feature } = params;
  updateSidebar(feature);
  const points = await api('GET', `/features/${feature}/trends`);
  const wrap = $('div', {className: 'stagger'});
  wrap.appendChild(breadcrumb({href:'#/', text:'Features'}, {href:`#/features/${feature}`, text:feature}, {text:'Trends'}));
  wrap.appendChild($('div', {className: 'page-title'}, 'Trends'));

  if (points.length === 0) {
    wrap.appendChild($('div', {className:'card'}, $('p', {style:'color:var(--text-dim)'}, 'No run data available for trends.')));
    return wrap;
  }

  const prPoints = points.filter(p => p.pass_rate != null);
  if (prPoints.length > 0) {
    wrap.appendChild(makeChart('Binary Pass Rate', prPoints.map(p => p.run_id), prPoints.map(p => p.pass_rate * 100), {suffix:'%', min:0, max:100, color:'#34d399'}));
  }

  wrap.appendChild(makeChart('Test Count', points.map(p => p.run_id), points.map(p => p.total), {min:0, color:'#e8943a'}));

  const allCriteria = new Set();
  points.forEach(p => { if (p.five_point) Object.keys(p.five_point).forEach(k => allCriteria.add(k)); });
  const criteriaColors = ['#a78bfa','#22d3ee','#f87171','#fbbf24','#34d399','#818cf8'];
  let ci = 0;
  allCriteria.forEach(c => {
    const fp = points.filter(p => p.five_point && p.five_point[c] != null);
    if (fp.length > 0) {
      wrap.appendChild(makeChart(c + ' (avg)', fp.map(p => p.run_id), fp.map(p => p.five_point[c]), {min:1, max:5, color:criteriaColors[ci++ % criteriaColors.length]}));
    }
  });

  return wrap;
}

function makeChart(title, labels, values, opts = {}) {
  const container = $('div', {className: 'chart-container'});
  container.appendChild($('h3', null, title));
  const canvas = $('canvas');
  canvas.style.maxHeight = '240px';
  container.appendChild(canvas);

  const color = opts.color || '#e8943a';
  const gradId = 'grad_' + Math.random().toString(36).slice(2,8);

  requestAnimationFrame(() => {
    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 240);
    grad.addColorStop(0, color + '30');
    grad.addColorStop(1, color + '00');

    new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: color,
          backgroundColor: grad,
          borderWidth: 2.5,
          pointRadius: 4,
          pointBackgroundColor: color,
          pointBorderColor: '#13131b',
          pointBorderWidth: 2,
          pointHoverRadius: 6,
          fill: true,
          tension: 0.3,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1a1a24',
            titleColor: '#e4e4ec',
            bodyColor: '#e4e4ec',
            borderColor: 'rgba(255,255,255,.1)',
            borderWidth: 1,
            cornerRadius: 8,
            padding: 12,
            titleFont: { family: 'JetBrains Mono', size: 11 },
            bodyFont: { family: 'DM Sans', size: 13 },
            callbacks: {
              label: (ctx) => ctx.parsed.y.toFixed(1) + (opts.suffix || '')
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,.04)', drawBorder: false },
            ticks: { color: '#44445a', font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 45 },
          },
          y: {
            min: opts.min,
            max: opts.max,
            grid: { color: 'rgba(255,255,255,.04)', drawBorder: false },
            ticks: {
              color: '#44445a',
              font: { family: 'JetBrains Mono', size: 11 },
              callback: (v) => v + (opts.suffix || '')
            },
          }
        },
        interaction: { mode: 'index', intersect: false },
        animation: { duration: 800, easing: 'easeOutQuart' }
      }
    });
  });

  return container;
}

/* ================================================================
   Page: Comparisons
   ================================================================ */
async function renderComparisons(params) {
  const { feature } = params;
  updateSidebar(feature);
  const comparisons = await api('GET', `/features/${feature}/comparisons`);
  const wrap = $('div', {className: 'stagger'});
  wrap.appendChild(breadcrumb({href:'#/', text:'Features'}, {href:`#/features/${feature}`, text:feature}, {text:'Comparisons'}));
  wrap.appendChild($('div', {className: 'page-title'}, 'Comparisons'));

  if (!comparisons || comparisons.length === 0) {
    wrap.appendChild($('div', {className:'card'}, $('p', {style:'color:var(--text-dim)'}, 'No comparisons found. Run "vibeval compare" to create one.')));
    return wrap;
  }

  comparisons.forEach(comp => {
    const card = $('div', {className: 'card'});
    card.appendChild($('h3', {style:'color:var(--text);font-family:var(--font-display);font-size:18px;font-weight:700;letter-spacing:-0.3px'}, (comp.run_a || '?') + ' vs ' + (comp.run_b || '?')));

    const s = comp.summary || {};
    const summary = $('div', {className: 'comp-summary'});
    summary.appendChild(compBox(s.a_wins || 0, comp.run_a || 'A', 'var(--green)'));
    summary.appendChild(compBox(s.ties || 0, 'Ties', 'var(--text-dim)'));
    summary.appendChild(compBox(s.b_wins || 0, comp.run_b || 'B', 'var(--accent)'));
    if (s.inconclusive) summary.appendChild(compBox(s.inconclusive, 'Inconclusive', 'var(--orange)'));
    card.appendChild(summary);

    if (comp.pairs && comp.pairs.length > 0) {
      const tbl = $('table');
      tbl.appendChild($('thead', null, $('tr', null, $('th', null, 'Test / Item'), $('th', null, 'Criteria'), $('th', null, 'Winner'), $('th', null, 'Confidence'), $('th', null, 'Reason'))));
      const tbody = $('tbody');
      comp.pairs.forEach(p => {
        const winLabel = p.winner === 'a' ? comp.run_a : p.winner === 'b' ? comp.run_b : p.winner;
        tbody.appendChild($('tr', null,
          $('td', {style:'font-weight:500'}, (p.test_name || '') + ' / ' + (p.item_id || '')),
          $('td', {style:'max-width:200px;font-size:13px;color:var(--text-secondary)'}, (p.criteria || '').substring(0, 80)),
          $('td', null, $('strong', {style:'color:var(--accent)'}, winLabel || '-')),
          $('td', null, p.confidence || '-'),
          $('td', {style:'font-size:13px;color:var(--text-dim)'}, (p.reason || '').substring(0, 120))
        ));
      });
      tbl.appendChild(tbody);
      card.appendChild(tbl);
    }
    wrap.appendChild(card);
  });

  return wrap;
}

function compBox(value, label, color) {
  const box = $('div', {className: 'comp-box'});
  box.appendChild($('div', {className: 'value', style: 'color:'+color}, String(value)));
  box.appendChild($('div', {className: 'label'}, label));
  return box;
}

/* ================================================================
   Form Components
   ================================================================ */

// Simple text field
function formField(field, label, value, placeholder) {
  const g = $('div', {className: 'form-group'});
  g.appendChild($('label', null, label));
  g.appendChild($('input', {type:'text', 'data-field':field, placeholder: placeholder||'', value: value||''}));
  return g;
}

// Tag chip input
function tagInput(label, initialTags) {
  const g = $('div', {className: 'form-group'});
  g.appendChild($('label', null, label));
  const wrap = $('div', {className: 'tag-input'});
  const tags = [...(initialTags || [])];

  function render() {
    wrap.querySelectorAll('.tag-chip').forEach(c => c.remove());
    const inp = wrap.querySelector('input');
    tags.forEach((t, i) => {
      const chip = $('span', {className: 'tag-chip'}, t,
        $('span', {className: 'tag-remove', onClick: () => { tags.splice(i, 1); render(); }}, '\u00d7'));
      wrap.insertBefore(chip, inp);
    });
  }

  const inp = $('input', {type:'text', placeholder:'Type and press Enter...'});
  inp.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ',') && inp.value.trim()) {
      e.preventDefault();
      const v = inp.value.trim().replace(/,$/,'');
      if (v && !tags.includes(v)) { tags.push(v); inp.value = ''; render(); }
    }
    if (e.key === 'Backspace' && !inp.value && tags.length) { tags.pop(); render(); }
  });
  wrap.appendChild(inp);
  wrap.addEventListener('click', () => inp.focus());
  g.appendChild(wrap);
  render();

  g._getTags = () => [...tags];
  return g;
}

// Key-Value data editor
function kvEditor(label, initialData) {
  const g = $('div', {className: 'form-group'});
  g.appendChild($('label', null, label));
  const editor = $('div', {className: 'kv-editor'});
  const rows = [];

  function addRow(key, val) {
    const row = $('div', {className: 'kv-row'});
    const kInput = $('input', {type:'text', placeholder:'key', value: key||''});
    kInput.style.flex = '1';
    // Determine if value needs textarea (multiline or long)
    const valStr = typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val ?? '');
    const isComplex = typeof val === 'object' || valStr.length > 80 || valStr.includes('\n');
    let vInput;
    if (isComplex) {
      vInput = $('textarea', {placeholder:'value (JSON)'});
      vInput.value = valStr;
      vInput.style.flex = '2';
    } else {
      vInput = $('input', {type:'text', placeholder:'value', value: valStr});
      vInput.style.flex = '2';
    }
    const removeBtn = $('button', {className:'kv-remove', onClick: () => {
      const idx = rows.indexOf(entry);
      if (idx >= 0) { rows.splice(idx, 1); row.remove(); }
    }}, '\u00d7');
    row.appendChild(kInput);
    row.appendChild(vInput);
    row.appendChild(removeBtn);
    editor.insertBefore(row, editor.querySelector('.kv-add'));
    const entry = { row, kInput, vInput, isComplex };
    rows.push(entry);
  }

  const addBtn = $('button', {className:'kv-add', type:'button', onClick: () => addRow('', '')}, '+ Add field');
  editor.appendChild(addBtn);
  g.appendChild(editor);

  // Populate
  if (initialData && typeof initialData === 'object') {
    Object.entries(initialData).forEach(([k, v]) => addRow(k, v));
  }

  // JSON toggle for advanced editing
  const jsonArea = $('textarea', {style:'display:none;width:100%;min-height:150px;padding:10px 14px;border:1px solid var(--border-strong);border-radius:8px;font-size:13px;font-family:var(--font-mono);background:var(--bg);color:var(--text);margin-top:8px;resize:vertical'});
  let jsonMode = false;
  const toggle = $('div', {className:'json-toggle', onClick: () => {
    jsonMode = !jsonMode;
    if (jsonMode) {
      jsonArea.value = JSON.stringify(g._getData(), null, 2);
      editor.style.display = 'none';
      jsonArea.style.display = 'block';
      toggle.textContent = '\u25c0 Visual editor';
    } else {
      try {
        const parsed = JSON.parse(jsonArea.value);
        rows.length = 0;
        editor.querySelectorAll('.kv-row').forEach(r => r.remove());
        Object.entries(parsed).forEach(([k,v]) => addRow(k, v));
      } catch(e) { /* keep JSON if invalid */ }
      editor.style.display = 'flex';
      jsonArea.style.display = 'none';
      toggle.textContent = 'Edit as JSON \u25b6';
    }
  }}, 'Edit as JSON \u25b6');
  g.appendChild(toggle);
  g.appendChild(jsonArea);

  g._getData = () => {
    if (jsonMode) {
      try { return JSON.parse(jsonArea.value); } catch(e) { return {}; }
    }
    const data = {};
    rows.forEach(({kInput, vInput, isComplex}) => {
      const k = kInput.value.trim();
      if (!k) return;
      const raw = vInput.value;
      if (isComplex || (raw.startsWith('{') || raw.startsWith('[') || raw.startsWith('"'))) {
        try { data[k] = JSON.parse(raw); return; } catch(e) {}
      }
      // Auto-detect numbers
      if (raw !== '' && !isNaN(raw) && raw.trim() !== '') { data[k] = Number(raw); return; }
      data[k] = raw;
    });
    return data;
  };
  return g;
}

// Judge spec list builder — rule definitions with expected args
const RULE_DEFS = {
  contains:            { desc: 'Field contains a substring',           args: [{key:'field',hint:'e.g. outputs.summary'},{key:'value',hint:'text to find'}] },
  contains_all:        { desc: 'Field contains all values',            args: [{key:'field',hint:'e.g. outputs.summary'},{key:'values',hint:'["val1","val2"]',json:true}] },
  contains_any:        { desc: 'Field contains at least one value',    args: [{key:'field',hint:'e.g. outputs.summary'},{key:'values',hint:'["val1","val2"]',json:true}] },
  not_contains:        { desc: 'Field does not contain a substring',   args: [{key:'field',hint:'e.g. outputs.content'},{key:'value',hint:'text that should NOT appear'}] },
  equals:              { desc: 'Field exactly equals expected value',   args: [{key:'field',hint:'e.g. outputs.status'},{key:'expected',hint:'expected value'}] },
  matches:             { desc: 'Field matches a regex pattern',        args: [{key:'field',hint:'e.g. outputs.content'},{key:'pattern',hint:'regex, e.g. ^\\d{4}-\\d{2}'}] },
  is_json:             { desc: 'Field is valid JSON',                   args: [{key:'field',hint:'e.g. outputs.response'}] },
  length_between:      { desc: 'Field length within range',            args: [{key:'field',hint:'e.g. outputs.content'},{key:'min',hint:'minimum length',num:true},{key:'max',hint:'maximum length',num:true}] },
  tool_sequence:       { desc: 'Tools called in exact order',          args: [{key:'tools',hint:'["search","summarize"]',json:true}] },
  tool_called:         { desc: 'A specific tool was called',           args: [{key:'tool_name',hint:'e.g. generate_image'}] },
  tool_not_called:     { desc: 'A specific tool was NOT called',       args: [{key:'tool_name',hint:'e.g. generate_image'}] },
  max_turns:           { desc: 'Conversation within turn limit',       args: [{key:'max',hint:'e.g. 5',num:true}] },
  max_steps:           { desc: 'Steps within limit',                   args: [{key:'max',hint:'e.g. 10',num:true}] },
  conversation_turns:  { desc: 'Minimum conversation turns',           args: [{key:'min',hint:'e.g. 3',num:true}] },
  all_turns_responded: { desc: 'Every turn has a response',            args: [] },
  no_role_violation:   { desc: 'No role violations in conversation',   args: [] },
};
const RULE_NAMES = Object.keys(RULE_DEFS);

function specListEditor(label, initialSpecs) {
  const g = $('div', {className: 'form-group'});
  g.appendChild($('label', null, label));
  const list = $('div', {className: 'spec-builder'});
  const specs = [];

  function addSpec(spec) {
    spec = spec || { method: 'rule', rule: 'contains' };
    const entry = $('div', {className: 'spec-entry'});
    const state = { ...spec };
    const idx = specs.length;
    specs.push({ el: entry, state });

    function renderEntry() {
      entry.innerHTML = '';
      // Header
      const header = $('div', {className: 'spec-entry-header'});
      const methodSel = $('select');
      ['rule','llm'].forEach(m => {
        const o = $('option', {value:m}, m);
        if (m === state.method) o.selected = true;
        methodSel.appendChild(o);
      });
      methodSel.addEventListener('change', () => { state.method = methodSel.value; renderEntry(); });
      header.appendChild(methodSel);
      if (state.method === 'rule') {
        const ruleSel = $('select');
        RULE_NAMES.forEach(r => {
          const def = RULE_DEFS[r];
          const o = $('option', {value:r}, r + (def.desc ? '  \u2014 ' + def.desc : ''));
          if (r === state.rule) o.selected = true;
          ruleSel.appendChild(o);
        });
        ruleSel.addEventListener('change', () => { state.rule = ruleSel.value; renderEntry(); });
        header.appendChild(ruleSel);
      }
      // Weight
      const weightSel = $('select');
      [['default','1.0'],['gate','gate']].forEach(([label,val]) => {
        const o = $('option', {value:val}, label);
        if (String(state.weight) === val) o.selected = true;
        weightSel.appendChild(o);
      });
      weightSel.addEventListener('change', () => { state.weight = weightSel.value === 'gate' ? 'gate' : undefined; });
      header.appendChild(weightSel);

      entry.appendChild(header);

      // Remove button
      entry.appendChild($('button', {className:'spec-remove', onClick: () => {
        const i = specs.findIndex(s => s.el === entry);
        if (i >= 0) { specs.splice(i, 1); entry.remove(); }
      }}, '\u00d7'));

      const fields = $('div', {className: 'spec-fields'});

      if (state.method === 'rule') {
        // Auto-populated args based on selected rule
        const ruleName = state.rule || 'contains';
        const def = RULE_DEFS[ruleName] || { args: [] };
        const argInputs = [];

        if (def.args.length > 0) {
          const argsWrap = $('div', {className:'spec-fields'});
          def.args.forEach(argDef => {
            const f = $('div', {className:'spec-field'});
            f.appendChild($('label', null, argDef.key));
            const existingVal = state.args && state.args[argDef.key];
            const displayVal = existingVal != null
              ? (typeof existingVal === 'object' ? JSON.stringify(existingVal) : String(existingVal))
              : '';
            const inp = $('input', {
              type: argDef.num ? 'number' : 'text',
              value: displayVal,
              placeholder: argDef.hint || '',
            });
            f.appendChild(inp);
            argsWrap.appendChild(f);
            argInputs.push({ key: argDef.key, inp, json: argDef.json, num: argDef.num });
          });
          fields.appendChild(argsWrap);
        } else {
          fields.appendChild($('div', {style:'font-size:12px;color:var(--text-dim);padding:4px 0'}, 'This rule has no arguments.'));
        }

        state._getArgs = () => {
          const a = {};
          argInputs.forEach(({key, inp, json, num}) => {
            const raw = inp.value.trim();
            if (!raw) return;
            if (json) { try { a[key] = JSON.parse(raw); return; } catch(e) {} }
            if (num && !isNaN(raw)) { a[key] = Number(raw); return; }
            a[key] = raw;
          });
          return a;
        };
      } else {
        // LLM spec fields
        const inline = $('div', {className:'spec-inline'});
        const scoringSel = specField('select', 'Scoring', null, null, ['binary','five-point']);
        scoringSel.querySelector('select').value = state.scoring || 'binary';
        inline.appendChild(scoringSel);
        inline.appendChild(specField('input', 'Target', state.target && state.target !== 'output' ? JSON.stringify(state.target) : '', 'output, or {"turns":[1,3]}'));
        fields.appendChild(inline);

        fields.appendChild(specField('textarea', 'Criteria', state.criteria || '', 'The evaluation criteria. e.g. "AI correctly identifies all action items without fabrication"'));
        fields.appendChild(specField('textarea', 'Test Intent', state.test_intent || '', 'What this test checks (insider knowledge the judge has). e.g. "Verify the AI doesn\'t merge disputed items into consensus"'));
        fields.appendChild(specField('textarea', 'Trap Design', state.trap_design || '', 'How the trap works (what pitfalls to watch for). e.g. "Item 3 has conflicting opinions — AI may incorrectly present them as agreement"'));

        // Anchors
        const anchorsField = $('div', {className:'spec-field'});
        anchorsField.appendChild($('label', null, 'Anchors'));
        const anchorsDiv = $('div', {style:'display:flex;flex-direction:column;gap:4px'});
        const anchorScores = state.scoring === 'five-point' ? ['1','2','3','4','5'] : ['0','1'];
        anchorScores.forEach(sc => {
          const row = $('div', {style:'display:flex;gap:8px;align-items:center'});
          row.appendChild($('span', {style:'font-family:var(--font-mono);font-size:12px;font-weight:600;width:20px;color:var(--accent)'}, sc));
          row.appendChild($('input', {type:'text', 'data-anchor':sc, style:'flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:6px;font-size:12px;background:var(--bg);color:var(--text)', value: (state.anchors && state.anchors[sc]) || '', placeholder:'Anchor description for score '+sc}));
          anchorsDiv.appendChild(row);
        });
        anchorsField.appendChild(anchorsDiv);
        fields.appendChild(anchorsField);
      }

      entry.appendChild(fields);
    }

    renderEntry();
    list.insertBefore(entry, list.querySelector('.kv-add'));
  }

  const addBtn = $('button', {className:'kv-add', type:'button', onClick: () => addSpec()}, '+ Add judge spec');
  list.appendChild(addBtn);
  g.appendChild(list);

  if (initialSpecs && initialSpecs.length > 0) {
    initialSpecs.forEach(s => addSpec({...s}));
  }

  // JSON toggle
  const jsonArea = $('textarea', {style:'display:none;width:100%;min-height:150px;padding:10px 14px;border:1px solid var(--border-strong);border-radius:8px;font-size:13px;font-family:var(--font-mono);background:var(--bg);color:var(--text);margin-top:8px;resize:vertical'});
  let jsonMode = false;
  const toggle = $('div', {className:'json-toggle', onClick: () => {
    jsonMode = !jsonMode;
    if (jsonMode) {
      jsonArea.value = JSON.stringify(g._getSpecs(), null, 2);
      list.style.display = 'none';
      jsonArea.style.display = 'block';
      toggle.textContent = '\u25c0 Visual editor';
    } else {
      try {
        const parsed = JSON.parse(jsonArea.value);
        specs.length = 0;
        list.querySelectorAll('.spec-entry').forEach(e => e.remove());
        parsed.forEach(s => addSpec(s));
      } catch(e) {}
      list.style.display = 'flex';
      jsonArea.style.display = 'none';
      toggle.textContent = 'Edit as JSON \u25b6';
    }
  }}, 'Edit as JSON \u25b6');
  g.appendChild(toggle);
  g.appendChild(jsonArea);

  g._getSpecs = () => {
    if (jsonMode) { try { return JSON.parse(jsonArea.value); } catch(e) { return []; } }
    return specs.map(({el, state}) => {
      const s = { method: state.method };
      if (state.method === 'rule') {
        s.rule = state.rule || el.querySelectorAll('select')[1]?.value || 'contains';
        if (state._getArgs) s.args = state._getArgs();
        const w = el.querySelectorAll('select')[2]?.value;
        if (w === 'gate') s.weight = 'gate';
      } else {
        const inputs = el.querySelectorAll('.spec-field input, .spec-field textarea, .spec-field select');
        s.scoring = el.querySelector('.spec-fields select')?.value || 'binary';
        const targetVal = el.querySelectorAll('.spec-inline input')?.[0]?.value?.trim();
        if (targetVal) { try { s.target = JSON.parse(targetVal); } catch(e) { s.target = targetVal; } }
        const textareas = el.querySelectorAll('.spec-fields > .spec-field > textarea');
        if (textareas[0]?.value) s.criteria = textareas[0].value;
        if (textareas[1]?.value) s.test_intent = textareas[1].value;
        if (textareas[2]?.value) s.trap_design = textareas[2].value;
        const anchors = {};
        el.querySelectorAll('[data-anchor]').forEach(inp => {
          if (inp.value.trim()) anchors[inp.getAttribute('data-anchor')] = inp.value.trim();
        });
        if (Object.keys(anchors).length) s.anchors = anchors;
        const w = el.querySelectorAll('.spec-entry-header select')[1]?.value;
        if (w === 'gate') s.weight = 'gate';
      }
      return s;
    });
  };
  return g;
}

function specField(type, label, value, placeholder, options) {
  const f = $('div', {className:'spec-field'});
  f.appendChild($('label', null, label));
  if (type === 'select') {
    const sel = $('select');
    (options||[]).forEach(o => sel.appendChild($('option', {value:o}, o)));
    if (value) sel.value = value;
    f.appendChild(sel);
  } else if (type === 'textarea') {
    const ta = $('textarea', {placeholder: placeholder||''});
    ta.value = value || '';
    f.appendChild(ta);
  } else {
    f.appendChild($('input', {type:'text', value: value||'', placeholder: placeholder||''}));
  }
  return f;
}

/* ================================================================
   CRUD Modals
   ================================================================ */
function showCreateDatasetModal(feature) {
  showModal('New Dataset', () => {
    const form = $('div');
    form.appendChild(formField('name', 'Name', '', 'my_dataset'));
    form.appendChild(formField('description', 'Description', '', 'Optional description'));
    const tags = tagInput('Tags', []);
    form.appendChild(tags);
    const specsEditor = specListEditor('Judge Specs', []);
    form.appendChild(specsEditor);
    form._tags = tags;
    form._specs = specsEditor;
    return form;
  }, [{ text: 'Create', cls: 'btn-primary', action: async (form) => {
    const name = form.querySelector('[data-field="name"]').value.trim();
    if (!name) throw new Error('Name is required');
    await api('POST', `/features/${feature}/datasets`, {
      name,
      description: form.querySelector('[data-field="description"]').value.trim(),
      tags: form._tags._getTags(),
      judge_specs: form._specs._getSpecs(),
    });
    handleRoute();
  }}]);
}

function showEditDatasetModal(feature, ds) {
  showModal('Edit Dataset', () => {
    const form = $('div');
    form.appendChild(formField('description', 'Description', ds.description || '', ''));
    const tags = tagInput('Tags', ds.tags || []);
    form.appendChild(tags);
    const specsEditor = specListEditor('Judge Specs', ds.judge_specs || []);
    form.appendChild(specsEditor);
    form._tags = tags;
    form._specs = specsEditor;
    return form;
  }, [{ text: 'Save', cls: 'btn-primary', action: async (form) => {
    await api('PUT', `/features/${feature}/datasets/${ds.name}`, {
      description: form.querySelector('[data-field="description"]').value.trim(),
      tags: form._tags._getTags(),
      judge_specs: form._specs._getSpecs(),
    });
    handleRoute();
  }}]);
}

async function showCreateItemModal(feature, dataset) {
  // Fetch sibling items to infer key structure
  let templateKeys = {};
  try {
    const ds = await api('GET', `/features/${feature}/datasets/${dataset}`);
    if (ds.items && ds.items.length > 0) {
      // Use the first item's data keys as template (empty values)
      const firstData = ds.items[0].data || {};
      Object.keys(firstData).forEach(k => { templateKeys[k] = ''; });
    }
  } catch(e) {}

  showModal('New Item', () => {
    const form = $('div');
    form.appendChild(formField('id', 'Item ID', '', 'my_item'));
    const tags = tagInput('Tags', []);
    form.appendChild(tags);
    const dataEditor = kvEditor('Data', templateKeys);
    form.appendChild(dataEditor);
    const specsEditor = specListEditor('Judge Specs Override', []);
    form.appendChild(specsEditor);
    form._tags = tags;
    form._data = dataEditor;
    form._specs = specsEditor;
    return form;
  }, [{ text: 'Create', cls: 'btn-primary', action: async (form) => {
    const id = form.querySelector('[data-field="id"]').value.trim();
    if (!id) throw new Error('ID is required');
    await api('POST', `/features/${feature}/datasets/${dataset}/items`, {
      id,
      tags: form._tags._getTags(),
      data: form._data._getData(),
      judge_specs: form._specs._getSpecs(),
    });
    handleRoute();
  }}]);
}

function showEditItemModal(feature, dataset, item) {
  showModal('Edit Item: ' + item.id, () => {
    const form = $('div');
    const tags = tagInput('Tags', item.tags || []);
    form.appendChild(tags);
    const dataEditor = kvEditor('Data', item.data || {});
    form.appendChild(dataEditor);
    const specsEditor = specListEditor('Judge Specs Override', item.judge_specs || []);
    form.appendChild(specsEditor);
    form._tags = tags;
    form._data = dataEditor;
    form._specs = specsEditor;
    return form;
  }, [{ text: 'Save', cls: 'btn-primary', action: async (form) => {
    await api('PUT', `/features/${feature}/datasets/${dataset}/items/${item.id}`, {
      tags: form._tags._getTags(),
      data: form._data._getData(),
      judge_specs: form._specs._getSpecs(),
    });
    handleRoute();
  }}]);
}

/* ================================================================
   Theme toggle
   ================================================================ */
function initTheme() {
  const saved = localStorage.getItem('vibeval-theme');
  if (saved === 'light') setTheme('light');
  else setTheme('dark');
}

function setTheme(mode) {
  document.documentElement.setAttribute('data-theme', mode);
  const label = document.getElementById('theme-label');
  const icon = document.getElementById('theme-icon');
  if (mode === 'light') {
    if (label) label.textContent = 'Dark mode';
    if (icon) icon.innerHTML = '<path d="M8 1a7 7 0 104.5 12.4A5.5 5.5 0 013.6 6.5 7 7 0 018 1z"/>';
  } else {
    if (label) label.textContent = 'Light mode';
    if (icon) icon.innerHTML = '<circle cx="8" cy="8" r="3.5"/><path d="M8 1.5v1M8 13.5v1M1.5 8h1M13.5 8h1M3.4 3.4l.7.7M11.9 11.9l.7.7M3.4 12.6l.7-.7M11.9 4.1l.7-.7"/>';
  }
  localStorage.setItem('vibeval-theme', mode);
}

document.getElementById('theme-toggle').addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme');
  setTheme(current === 'light' ? 'dark' : 'light');
});

initTheme();

/* ================================================================
   Route registration & init
   ================================================================ */
addRoute('', renderFeaturesList);
addRoute('features/:feature', renderFeatureDetail);
addRoute('features/:feature/analysis', renderAnalysis);
addRoute('features/:feature/design', renderDesignPage);
addRoute('features/:feature/datasets/:dataset', renderDatasetDetail);
addRoute('features/:feature/runs/:run_id', renderRunDetail);
addRoute('features/:feature/trends', renderTrends);
addRoute('features/:feature/comparisons', renderComparisons);

window.addEventListener('hashchange', handleRoute);
handleRoute();
