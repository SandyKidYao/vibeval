"""Report generator — self-contained HTML report for a test run."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .dataset import Dataset, load_all_datasets
from .result import load_run, load_summary


def generate_report(
    feature: str,
    run_id: str,
    run_dir: str | Path,
    datasets_dir: str | Path,
    output: str | None = None,
) -> Path:
    """Generate a self-contained HTML report. Returns the output path."""
    run_dir = Path(run_dir)

    summary = load_summary(str(run_dir))
    results = load_run(str(run_dir))
    datasets = load_all_datasets(str(datasets_dir))
    comparisons = _load_comparisons(run_dir.parent.parent)

    context = _build_context(feature, run_id, summary, results, datasets, comparisons)
    html = _render(context)

    out_path = Path(output) if output else run_dir / "report.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _build_context(
    feature: str,
    run_id: str,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    datasets: dict[str, Dataset],
    comparisons: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "feature": feature,
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "results": results,
        "datasets": _serialize_datasets(datasets),
        "comparisons": comparisons,
    }


def _serialize_datasets(datasets: dict[str, Dataset]) -> list[dict[str, Any]]:
    out = []
    for name, ds in datasets.items():
        items = []
        for item in ds.items:
            items.append({
                "id": item.id,
                "tags": item.tags,
                "data": item.data,
                "judge_specs": item.judge_specs,
            })
        out.append({
            "name": ds.name,
            "description": ds.description,
            "version": ds.version,
            "tags": ds.tags,
            "judge_specs": ds.judge_specs,
            "items": items,
        })
    return out


def _load_comparisons(feature_dir: Path) -> list[dict[str, Any]]:
    comp_dir = feature_dir / "comparisons"
    if not comp_dir.exists():
        return []
    result = []
    for f in sorted(comp_dir.iterdir()):
        if f.suffix == ".json":
            result.append(json.loads(f.read_text(encoding="utf-8")))
    return result


def _render(context: dict[str, Any]) -> str:
    data_json = json.dumps(context, indent=None, default=str, ensure_ascii=False)
    # Escape </script> in JSON to prevent premature tag closing
    data_json = data_json.replace("</", "<\\/")
    return _HTML_TEMPLATE.replace("__REPORT_DATA__", data_json)


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>vibeval Report</title>
<style>
:root {
  --bg: #f8f9fa;
  --card-bg: #fff;
  --border: #e0e0e0;
  --text: #1a1a1a;
  --text-secondary: #666;
  --accent: #4a90d9;
  --green: #2ea043;
  --red: #d73a49;
  --orange: #e36209;
  --yellow: #dbab09;
  --sidebar-bg: #1e293b;
  --sidebar-text: #cbd5e1;
  --sidebar-active: #38bdf8;
  --font-mono: 'SF Mono', 'Cascadia Code', 'Fira Code', Consolas, monospace;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); display: flex; min-height: 100vh; }

/* Sidebar */
nav { width: 240px; background: var(--sidebar-bg); color: var(--sidebar-text); padding: 24px 0; position: fixed; top: 0; left: 0; bottom: 0; overflow-y: auto; z-index: 10; }
nav .logo { padding: 0 20px 20px; font-size: 18px; font-weight: 700; color: #fff; border-bottom: 1px solid rgba(255,255,255,.1); margin-bottom: 8px; }
nav .meta { padding: 12px 20px; font-size: 12px; color: rgba(255,255,255,.4); border-bottom: 1px solid rgba(255,255,255,.1); margin-bottom: 8px; }
nav a { display: block; padding: 10px 20px; color: var(--sidebar-text); text-decoration: none; font-size: 14px; transition: background .15s; }
nav a:hover { background: rgba(255,255,255,.08); }
nav a.active { color: var(--sidebar-active); background: rgba(56,189,248,.08); border-right: 3px solid var(--sidebar-active); }

/* Main */
main { margin-left: 240px; flex: 1; padding: 32px; max-width: 1200px; }

/* Cards */
.card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 24px; margin-bottom: 20px; }
.card h2 { font-size: 20px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.card h3 { font-size: 16px; margin: 16px 0 8px; color: var(--text-secondary); }

/* Stats grid */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat-box { background: var(--bg); border-radius: 8px; padding: 16px; text-align: center; }
.stat-box .value { font-size: 32px; font-weight: 700; }
.stat-box .label { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

/* Progress bar */
.bar-container { height: 24px; background: var(--bg); border-radius: 12px; overflow: hidden; display: flex; margin: 8px 0; }
.bar-pass { background: var(--green); transition: width .3s; }
.bar-fail { background: var(--red); transition: width .3s; }
.bar-label { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

/* Five-point distribution */
.dist-row { display: flex; align-items: center; margin: 6px 0; }
.dist-label { width: 200px; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dist-bar { flex: 1; display: flex; height: 20px; border-radius: 4px; overflow: hidden; margin: 0 12px; }
.dist-bar > div { transition: width .3s; min-width: 0; }
.dist-1 { background: var(--red); }
.dist-2 { background: var(--orange); }
.dist-3 { background: var(--yellow); }
.dist-4 { background: #73c23a; }
.dist-5 { background: var(--green); }
.dist-avg { font-size: 14px; font-weight: 600; width: 40px; text-align: right; }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }
th { font-weight: 600; color: var(--text-secondary); font-size: 12px; text-transform: uppercase; letter-spacing: .5px; }
tr:hover { background: rgba(0,0,0,.02); }

/* Badges */
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge-pass { background: #dcfce7; color: #166534; }
.badge-fail { background: #fee2e2; color: #991b1b; }
.badge-gate { background: #fef3c7; color: #92400e; }
.badge-rule { background: #e0e7ff; color: #3730a3; }
.badge-llm { background: #ede9fe; color: #5b21b6; }
.badge-score { padding: 2px 10px; }
.score-1 { background: #fee2e2; color: #991b1b; }
.score-2 { background: #fed7aa; color: #9a3412; }
.score-3 { background: #fef3c7; color: #92400e; }
.score-4 { background: #d9f99d; color: #3f6212; }
.score-5 { background: #dcfce7; color: #166534; }

/* Collapsible */
.collapsible { cursor: pointer; user-select: none; }
.collapsible::before { content: '\25B6'; display: inline-block; margin-right: 8px; font-size: 10px; transition: transform .15s; }
.collapsible.open::before { transform: rotate(90deg); }
.collapse-body { display: none; margin-top: 8px; }
.collapse-body.show { display: block; }

/* JSON */
pre.json { background: #f1f5f9; border-radius: 6px; padding: 12px; font-size: 13px; font-family: var(--font-mono); overflow-x: auto; max-height: 400px; overflow-y: auto; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }

/* Timeline */
.timeline { position: relative; padding-left: 28px; margin: 12px 0; }
.timeline::before { content: ''; position: absolute; left: 8px; top: 0; bottom: 0; width: 2px; background: var(--border); }
.step { position: relative; padding: 8px 0 8px 12px; }
.step::before { content: ''; position: absolute; left: -24px; top: 12px; width: 12px; height: 12px; border-radius: 50%; border: 2px solid var(--border); background: #fff; }
.step.tool_call::before { border-color: #6366f1; background: #e0e7ff; }
.step.tool_result::before { border-color: #06b6d4; background: #cffafe; }
.step.llm_call::before { border-color: #8b5cf6; background: #ede9fe; }
.step.llm_output::before { border-color: #a855f7; background: #f3e8ff; }
.step.handoff::before { border-color: #f59e0b; background: #fef3c7; }
.step.context_update::before { border-color: #64748b; background: #f1f5f9; }
.step.retrieval::before { border-color: #10b981; background: #d1fae5; }
.step-header { font-size: 13px; font-weight: 600; }
.step-type { font-size: 11px; color: var(--text-secondary); font-family: var(--font-mono); }

/* Turn */
.turn { border: 1px solid var(--border); border-radius: 6px; margin: 8px 0; padding: 12px; }
.turn-header { font-weight: 600; font-size: 14px; margin-bottom: 8px; }

/* Result card */
.result-card { border-left: 4px solid var(--green); }
.result-card.has-failure { border-left-color: var(--red); }

/* Section */
section { margin-bottom: 40px; }
section > h2 { font-size: 24px; font-weight: 700; margin-bottom: 20px; }

/* Spec detail */
.spec-detail { background: var(--bg); border-radius: 6px; padding: 12px; margin: 8px 0; font-size: 13px; }
.spec-detail dt { font-weight: 600; color: var(--text-secondary); margin-top: 8px; }
.spec-detail dt:first-child { margin-top: 0; }
.spec-detail dd { margin-left: 0; margin-top: 2px; }

/* Responsive */
@media (max-width: 768px) {
  nav { display: none; }
  main { margin-left: 0; padding: 16px; }
}

/* Comparison */
.comp-summary { display: flex; gap: 16px; margin: 12px 0; }
.comp-box { flex: 1; text-align: center; padding: 12px; border-radius: 8px; background: var(--bg); }
.comp-box .value { font-size: 24px; font-weight: 700; }
</style>
</head>
<body>

<nav id="sidebar">
  <div class="logo">vibeval Report</div>
  <div class="meta" id="nav-meta"></div>
  <a href="#overview" class="active" onclick="scrollTo_(event,'overview')">Overview</a>
  <a href="#design" onclick="scrollTo_(event,'design')">Test Design</a>
  <a href="#data" onclick="scrollTo_(event,'data')">Test Data</a>
  <a href="#results" onclick="scrollTo_(event,'results')">Results</a>
  <a href="#comparisons" onclick="scrollTo_(event,'comparisons')" id="nav-comp" style="display:none">Comparisons</a>
</nav>

<main>
  <div id="app"></div>
</main>

<script>
const DATA = __REPORT_DATA__;

const $ = (tag, attrs, ...children) => {
  const el = document.createElement(tag);
  if (attrs) Object.entries(attrs).forEach(([k,v]) => {
    if (k === 'className') el.className = v;
    else if (k === 'innerHTML') el.innerHTML = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2).toLowerCase(), v);
    else el.setAttribute(k, v);
  });
  children.flat().forEach(c => {
    if (c == null) return;
    el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  });
  return el;
};

function formatDuration(s) {
  if (s < 0.01) return '<0.01s';
  if (s < 60) return s.toFixed(2) + 's';
  return Math.floor(s/60) + 'm ' + (s%60).toFixed(0) + 's';
}

function formatTime(ts) {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString();
}

function jsonPre(obj) {
  const pre = $('pre', {className: 'json'});
  pre.textContent = JSON.stringify(obj, null, 2);
  return pre;
}

function collapsible(title, content, startOpen) {
  const header = $('div', {className: 'collapsible' + (startOpen ? ' open' : '')}, title);
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

function badge(text, cls) {
  return $('span', {className: 'badge ' + cls}, text);
}

function scoreBadge(score, method, scoring) {
  if (method === 'rule' || scoring === 'binary') {
    return badge(score === 1 ? 'PASS' : 'FAIL', score === 1 ? 'badge-pass' : 'badge-fail');
  }
  return badge(score + '/5', 'badge badge-score score-' + score);
}

/* --- Overview --- */
function renderOverview() {
  const s = DATA.summary;
  const bs = s.binary_stats || {};
  const fs = s.five_point_stats || {};
  const sec = $('section', {id: 'overview'});
  sec.appendChild($('h2', null, 'Overview'));

  // Stats
  const stats = $('div', {className: 'stats'});
  const passRate = bs.total > 0 ? (bs.pass_rate * 100).toFixed(0) + '%' : '-';
  stats.appendChild(statBox(passRate, 'Pass Rate', bs.pass_rate >= 1 ? 'var(--green)' : bs.pass_rate >= 0.8 ? 'var(--yellow)' : 'var(--red)'));
  stats.appendChild(statBox(s.total, 'Test Cases'));
  stats.appendChild(statBox(bs.passed + '/' + bs.total, 'Binary Passed'));
  stats.appendChild(statBox(formatDuration(s.duration), 'Duration'));
  sec.appendChild(stats);

  // Binary bar
  if (bs.total > 0) {
    const card = $('div', {className: 'card'});
    card.appendChild($('h3', null, 'Binary Pass Rate'));
    const bar = $('div', {className: 'bar-container'});
    bar.appendChild($('div', {className: 'bar-pass', style: 'width:' + (bs.pass_rate*100) + '%'}));
    bar.appendChild($('div', {className: 'bar-fail', style: 'width:' + ((1-bs.pass_rate)*100) + '%'}));
    card.appendChild(bar);
    card.appendChild($('div', {className: 'bar-label'}, bs.passed + ' passed, ' + bs.failed + ' failed'));
    sec.appendChild(card);
  }

  // Five-point
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
    sec.appendChild(card);
  }

  // Quick results table
  const card = $('div', {className: 'card'});
  card.appendChild($('h3', null, 'All Test Cases'));
  const tbl = $('table');
  tbl.appendChild($('thead', null, $('tr', null,
    $('th', null, 'Test'), $('th', null, 'Dataset'), $('th', null, 'Item'),
    $('th', null, 'Judges'), $('th', null, 'Status'), $('th', null, 'Duration')
  )));
  const tbody = $('tbody');
  DATA.results.forEach((r, idx) => {
    const jrs = r.judge_results || [];
    const allPass = jrs.length > 0 && jrs.every(j => {
      const sp = j.spec || {};
      if (sp.method === 'rule' || sp.scoring === 'binary') return j.score === 1;
      return j.score >= 4;
    });
    const hasFailure = jrs.some(j => {
      const sp = j.spec || {};
      return (sp.method === 'rule' || sp.scoring === 'binary') && j.score === 0;
    });
    const status = jrs.length === 0 ? badge('N/A', '') : hasFailure ? badge('FAIL', 'badge-fail') : allPass ? badge('PASS', 'badge-pass') : badge('MIXED', 'badge-gate');
    const row = $('tr', {style:'cursor:pointer', onClick: () => {
      document.getElementById('result-'+idx)?.scrollIntoView({behavior:'smooth'});
    }},
      $('td', null, r.test_name), $('td', null, r.dataset), $('td', null, r.item_id),
      $('td', null, jrs.length + ''), $('td', null, status), $('td', null, formatDuration(r.duration || 0))
    );
    tbody.appendChild(row);
  });
  tbl.appendChild(tbody);
  card.appendChild(tbl);
  sec.appendChild(card);

  return sec;
}

function statBox(value, label, color) {
  const box = $('div', {className: 'stat-box'});
  box.appendChild($('div', {className: 'value', style: color ? 'color:'+color : ''}, String(value)));
  box.appendChild($('div', {className: 'label'}, label));
  return box;
}

/* --- Test Design --- */
function renderDesign() {
  const sec = $('section', {id: 'design'});
  sec.appendChild($('h2', null, 'Test Design'));

  DATA.datasets.forEach(ds => {
    const card = $('div', {className: 'card'});
    card.appendChild($('h3', null, ds.name));
    if (ds.description) card.appendChild($('p', {style:'color:var(--text-secondary);margin-bottom:12px'}, ds.description));

    // Manifest-level specs
    if (ds.judge_specs && ds.judge_specs.length > 0) {
      card.appendChild($('div', {style:'font-weight:600;margin:12px 0 8px'}, 'Default Judge Specs'));
      ds.judge_specs.forEach(spec => card.appendChild(renderSpec(spec)));
    }

    // Item-level overrides
    const itemsWithSpecs = (ds.items || []).filter(it => it.judge_specs && it.judge_specs.length > 0);
    if (itemsWithSpecs.length > 0) {
      card.appendChild($('div', {style:'font-weight:600;margin:16px 0 8px'}, 'Item-Level Overrides'));
      itemsWithSpecs.forEach(it => {
        card.appendChild(collapsible(it.id, () => {
          const wrap = $('div');
          it.judge_specs.forEach(spec => wrap.appendChild(renderSpec(spec)));
          return wrap;
        }));
      });
    }

    sec.appendChild(card);
  });

  if (DATA.datasets.length === 0) {
    sec.appendChild($('div', {className: 'card'}, $('p', {style:'color:var(--text-secondary)'}, 'No datasets found.')));
  }

  return sec;
}

function renderSpec(spec) {
  const detail = $('div', {className: 'spec-detail'});
  const header = $('div', {style:'display:flex;gap:8px;align-items:center;margin-bottom:8px'});
  header.appendChild(badge(spec.method, spec.method === 'rule' ? 'badge-rule' : 'badge-llm'));
  if (spec.method === 'rule') header.appendChild($('strong', null, spec.rule));
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
        anchorList.appendChild($('div', null, $('strong', null, score + ': '), desc));
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

/* --- Test Data --- */
function renderData() {
  const sec = $('section', {id: 'data'});
  sec.appendChild($('h2', null, 'Test Data'));

  DATA.datasets.forEach(ds => {
    const card = $('div', {className: 'card'});
    const headerParts = [ds.name];
    if (ds.version && ds.version !== '1') headerParts.push('v' + ds.version);
    card.appendChild($('h3', null, headerParts.join(' ')));
    if (ds.description) card.appendChild($('p', {style:'color:var(--text-secondary);margin-bottom:8px'}, ds.description));
    if (ds.tags && ds.tags.length > 0) {
      const tags = $('div', {style:'margin-bottom:12px'});
      ds.tags.forEach(t => tags.appendChild(badge(t, 'badge-rule')));
      card.appendChild(tags);
    }

    card.appendChild($('div', {style:'font-size:13px;color:var(--text-secondary);margin-bottom:8px'}, (ds.items||[]).length + ' items'));

    (ds.items || []).forEach(item => {
      const hasOverride = item.judge_specs && item.judge_specs.length > 0;
      const title = item.id + (item.tags && item.tags.length > 0 ? ' [' + item.tags.join(', ') + ']' : '') + (hasOverride ? ' (custom specs)' : '');
      card.appendChild(collapsible(title, () => jsonPre(item.data)));
    });

    sec.appendChild(card);
  });

  if (DATA.datasets.length === 0) {
    sec.appendChild($('div', {className: 'card'}, $('p', {style:'color:var(--text-secondary)'}, 'No datasets found.')));
  }

  return sec;
}

/* --- Results --- */
function renderResults() {
  const sec = $('section', {id: 'results'});
  sec.appendChild($('h2', null, 'Results'));

  DATA.results.forEach((r, idx) => {
    const jrs = r.judge_results || [];
    const hasFailure = jrs.some(j => {
      const sp = j.spec || {};
      return (sp.method === 'rule' || sp.scoring === 'binary') && j.score === 0;
    });

    const card = $('div', {className: 'card result-card' + (hasFailure ? ' has-failure' : ''), id: 'result-' + idx});

    // Header
    const hdr = $('div', {style:'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px'});
    hdr.appendChild($('div', null,
      $('strong', {style:'font-size:16px'}, r.test_name),
      $('span', {style:'color:var(--text-secondary);margin-left:8px'}, r.dataset + ' / ' + r.item_id)
    ));
    hdr.appendChild($('div', {style:'font-size:13px;color:var(--text-secondary)'}, formatDuration(r.duration || 0)));
    card.appendChild(hdr);

    // Judge results table
    if (jrs.length > 0) {
      card.appendChild(collapsible('Judge Results (' + jrs.length + ')', () => {
        const tbl = $('table');
        tbl.appendChild($('thead', null, $('tr', null,
          $('th', null, 'Method'), $('th', null, 'Rule / Criteria'), $('th', null, 'Score'), $('th', null, 'Reason')
        )));
        const tbody = $('tbody');
        jrs.forEach(jr => {
          const sp = jr.spec || {};
          const methodBadge = badge(sp.method, sp.method === 'rule' ? 'badge-rule' : 'badge-llm');
          const gateBadge = sp.weight === 'gate' ? badge('GATE', 'badge-gate') : null;
          const name = sp.method === 'rule' ? sp.rule : (sp.criteria || '').substring(0, 60) + ((sp.criteria||'').length > 60 ? '...' : '');
          const row = $('tr', null,
            $('td', null, methodBadge, gateBadge ? $('span', null, ' ', gateBadge) : ''),
            $('td', null, name),
            $('td', null, scoreBadge(jr.score, sp.method, sp.scoring)),
            $('td', {style:'font-size:13px;max-width:400px'}, jr.reason || '')
          );
          tbody.appendChild(row);
        });
        tbl.appendChild(tbody);
        return tbl;
      }, true));
    }

    // Trace
    if (r.trace && r.trace.turns && r.trace.turns.length > 0) {
      card.appendChild(collapsible('Trace (' + r.trace.turns.length + ' turn' + (r.trace.turns.length > 1 ? 's' : '') + ')', () => {
        const wrap = $('div');
        r.trace.turns.forEach(turn => {
          const t = $('div', {className: 'turn'});
          t.appendChild($('div', {className: 'turn-header'}, 'Turn ' + turn.turn));

          // Input
          if (turn.input) {
            t.appendChild(collapsible('Input', () => jsonPre(turn.input)));
          }

          // Steps
          if (turn.steps && turn.steps.length > 0) {
            const timeline = $('div', {className: 'timeline'});
            turn.steps.forEach(step => {
              const s = $('div', {className: 'step ' + (step.type || '')});
              const hdr = $('div', {style:'display:flex;align-items:center;gap:8px'});
              hdr.appendChild($('span', {className: 'step-type'}, step.type));
              if (step.type === 'tool_call' && step.data?.name) {
                hdr.appendChild($('span', {className: 'step-header'}, step.data.name));
              } else if (step.type === 'tool_result' && step.data?.name) {
                hdr.appendChild($('span', {className: 'step-header'}, step.data.name));
              } else if (step.type === 'llm_call' && step.data?.system) {
                hdr.appendChild($('span', {className: 'step-header'}, step.data.system.substring(0, 60)));
              }
              s.appendChild(hdr);

              if (step.data) {
                s.appendChild(collapsible('Details', () => jsonPre(step.data)));
              }
              timeline.appendChild(s);
            });
            t.appendChild(timeline);
          }

          // Output
          if (turn.output) {
            t.appendChild(collapsible('Output', () => jsonPre(turn.output)));
          }

          wrap.appendChild(t);
        });
        return wrap;
      }));
    }

    // Inputs / Outputs
    if (r.inputs) {
      card.appendChild(collapsible('Inputs', () => jsonPre(r.inputs)));
    }
    if (r.outputs) {
      card.appendChild(collapsible('Outputs', () => jsonPre(r.outputs)));
    }

    sec.appendChild(card);
  });

  if (DATA.results.length === 0) {
    sec.appendChild($('div', {className: 'card'}, $('p', {style:'color:var(--text-secondary)'}, 'No results found.')));
  }

  return sec;
}

/* --- Comparisons --- */
function renderComparisons() {
  if (!DATA.comparisons || DATA.comparisons.length === 0) return null;
  document.getElementById('nav-comp').style.display = 'block';

  const sec = $('section', {id: 'comparisons'});
  sec.appendChild($('h2', null, 'Comparisons'));

  DATA.comparisons.forEach(comp => {
    const card = $('div', {className: 'card'});
    card.appendChild($('h3', null, (comp.run_a || '?') + ' vs ' + (comp.run_b || '?')));

    const s = comp.summary || {};
    const summary = $('div', {className: 'comp-summary'});
    summary.appendChild(compBox(s.a_wins || 0, comp.run_a || 'A', 'var(--green)'));
    summary.appendChild(compBox(s.ties || 0, 'Ties', 'var(--text-secondary)'));
    summary.appendChild(compBox(s.b_wins || 0, comp.run_b || 'B', 'var(--accent)'));
    if (s.inconclusive) summary.appendChild(compBox(s.inconclusive, 'Inconclusive', 'var(--orange)'));
    card.appendChild(summary);

    if (comp.pairs && comp.pairs.length > 0) {
      const tbl = $('table');
      tbl.appendChild($('thead', null, $('tr', null,
        $('th', null, 'Test / Item'), $('th', null, 'Criteria'), $('th', null, 'Winner'), $('th', null, 'Confidence'), $('th', null, 'Reason')
      )));
      const tbody = $('tbody');
      comp.pairs.forEach(p => {
        const winLabel = p.winner === 'a' ? comp.run_a : p.winner === 'b' ? comp.run_b : p.winner;
        tbody.appendChild($('tr', null,
          $('td', null, (p.test_name || '') + ' / ' + (p.item_id || '')),
          $('td', {style:'max-width:200px;font-size:13px'}, (p.criteria || '').substring(0, 80)),
          $('td', null, $('strong', null, winLabel || '-')),
          $('td', null, p.confidence || '-'),
          $('td', {style:'font-size:13px'}, (p.reason || '').substring(0, 120))
        ));
      });
      tbl.appendChild(tbody);
      card.appendChild(tbl);
    }

    sec.appendChild(card);
  });

  return sec;
}

function compBox(value, label, color) {
  const box = $('div', {className: 'comp-box'});
  box.appendChild($('div', {className: 'value', style: 'color:'+color}, String(value)));
  box.appendChild($('div', {className: 'label'}, label));
  return box;
}

/* --- Navigation --- */
function scrollTo_(e, id) {
  e.preventDefault();
  document.getElementById(id)?.scrollIntoView({behavior: 'smooth'});
  document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
  e.target.classList.add('active');
}

// Highlight active nav on scroll
const sections = ['overview', 'design', 'data', 'results', 'comparisons'];
window.addEventListener('scroll', () => {
  let current = sections[0];
  sections.forEach(id => {
    const el = document.getElementById(id);
    if (el && el.getBoundingClientRect().top <= 80) current = id;
  });
  document.querySelectorAll('nav a').forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === '#' + current);
  });
});

/* --- Init --- */
function init() {
  document.title = 'vibeval Report — ' + DATA.feature + ' / ' + DATA.run_id;
  document.getElementById('nav-meta').innerHTML =
    '<div>' + DATA.feature + '</div>' +
    '<div style="margin-top:4px">' + DATA.run_id + '</div>' +
    '<div style="margin-top:4px">' + DATA.generated_at + '</div>';

  const app = document.getElementById('app');
  app.appendChild(renderOverview());
  app.appendChild(renderDesign());
  app.appendChild(renderData());
  app.appendChild(renderResults());
  const comp = renderComparisons();
  if (comp) app.appendChild(comp);
}

init();
</script>
</body>
</html>"""
