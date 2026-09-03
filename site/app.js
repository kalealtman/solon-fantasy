(function () {
  const DATA = JSON.parse(document.getElementById('league-data').textContent);
  const { standings, draft, transactions, owner_career, head_to_head, trophy_case } = DATA;

  const fmt = (n, d = 0) => Number(n).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (n) => (n * 100).toFixed(1) + '%';
  // 'A' / 'A & B' / 'A, B & C' -- never silently pick a winner out of a tie.
  const joinNames = (names) => (names.length <= 1 ? names.join('') : names.slice(0, -1).join(', ') + ' & ' + names[names.length - 1]);
  const seasons = [...new Set(standings.map((s) => s.season))].sort((a, b) => b - a);
  const latestSeason = seasons[0];

  const TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'standings', label: 'All-Time' },
    { id: 'trophies', label: 'Trophy Case' },
    { id: 'h2h', label: 'Head-to-Head' },
    { id: 'seasons', label: 'Seasons' },
    { id: 'transactions', label: 'Transactions' },
  ];

  const tabsEl = document.getElementById('tabs');
  const mainEl = document.getElementById('main');

  TABS.forEach((t) => {
    const btn = document.createElement('button');
    btn.className = 'tab';
    btn.textContent = t.label;
    btn.dataset.tab = t.id;
    btn.addEventListener('click', () => showTab(t.id));
    tabsEl.appendChild(btn);

    const view = document.createElement('div');
    view.className = 'view';
    view.id = 'view-' + t.id;
    mainEl.appendChild(view);
  });

  function showTab(id) {
    document.querySelectorAll('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === id));
    document.querySelectorAll('.view').forEach((v) => v.classList.toggle('active', v.id === 'view-' + id));
    const view = document.getElementById('view-' + id);
    if (!view.dataset.rendered) {
      RENDERERS[id]();
      view.dataset.rendered = '1';
    }
    history.replaceState(null, '', '#' + id);
  }

  document.getElementById('ticker').innerHTML = `
    <span><b>${seasons.length}</b> seasons</span>
    <span><b>${owner_career.length}</b> owners</span>
    <span><b>${transactions.length.toLocaleString()}</b> transactions</span>
  `;

  // ---------- owner hover tooltip (used on the career table and chart) ----------
  const tooltipEl = document.getElementById('owner-tooltip');
  const ownerByName = Object.fromEntries(owner_career.map((o) => [o.owner, o]));

  function ownerTooltipHTML(owner) {
    const o = ownerByName[owner];
    if (!o) return '';
    const stat = (label, val) => `<div class="ot-stat"><span class="ot-label">${label}</span><span class="ot-val">${val}</span></div>`;
    return `
      <div class="ot-name">${o.owner}</div>
      <div class="ot-grid">
        ${stat('Seasons', o.seasons_played)}
        ${stat('Win%', pct(o.win_pct))}
        ${stat('🥇 1st', o.championships)}
        ${stat('🥈 2nd', o.second_places)}
        ${stat('🥉 3rd', o.third_places)}
        ${stat('Podiums', o.podiums)}
        ${stat('Avg Finish', o.avg_finish.toFixed(2))}
        ${stat('Best / Worst', `${o.best_finish} / ${o.worst_finish}`)}
      </div>
    `;
  }

  function positionTooltip(evt) {
    const pad = 16;
    const w = tooltipEl.offsetWidth || 210;
    const h = tooltipEl.offsetHeight || 170;
    let x = evt.clientX + pad;
    let y = evt.clientY + pad;
    if (x + w > window.innerWidth) x = evt.clientX - w - pad;
    if (y + h > window.innerHeight) y = evt.clientY - h - pad;
    tooltipEl.style.left = x + 'px';
    tooltipEl.style.top = y + 'px';
  }

  function attachOwnerHover(el, owner) {
    el.addEventListener('mouseenter', (e) => {
      tooltipEl.innerHTML = ownerTooltipHTML(owner);
      tooltipEl.classList.add('visible');
      positionTooltip(e);
    });
    el.addEventListener('mousemove', positionTooltip);
    el.addEventListener('mouseleave', () => tooltipEl.classList.remove('visible'));
  }

  function statTile(value, label, sub, accent) {
    return `<div class="card stat-tile"><div class="value${accent ? ' accent' : ''}">${value}</div><div class="label">${label}</div>${sub ? `<div class="sub">${sub}</div>` : ''}</div>`;
  }

  function factCard(f) {
    const parts = f.value.split(' -- ');
    return `<div class="card fact-card"><div class="fact-label">${f.fact}</div><div class="fact-value">${parts[0]}</div>${parts[1] ? `<div class="fact-detail">${parts[1]}</div>` : ''}</div>`;
  }

  function renderOverview() {
    const champRow = standings.find((s) => s.season === latestSeason && s.rank === 1);
    const topChampCount = Math.max(...owner_career.map((o) => o.championships));
    const champNames = owner_career
      .filter((o) => o.championships === topChampCount)
      .map((o) => o.owner)
      .sort();
    const champLeaders = joinNames(champNames);
    document.getElementById('view-overview').innerHTML = `
      <div class="card champ-callout" style="margin-bottom:24px">
        <div class="trophy">🏆</div>
        <div>
          <div class="fact-label">Reigning Champion &mdash; ${latestSeason}</div>
          <div class="name">${champRow.team_name}</div>
          <div class="record">${champRow.wins}-${champRow.losses}${champRow.ties ? '-' + champRow.ties : ''} &middot; ${fmt(champRow.points_for, 1)} PF</div>
        </div>
      </div>
      <h2 class="section-title">League at a Glance</h2>
      <div class="grid cols-4" style="margin-bottom:8px">
        ${statTile(seasons.length, 'Seasons Played', `${Math.min(...seasons)}&ndash;${Math.max(...seasons)}`)}
        ${statTile(owner_career.length, 'All-Time Owners')}
        ${statTile(topChampCount, 'Most Championships', champLeaders, true)}
        ${statTile(fmt(standings.reduce((sum, s) => sum + s.points_for, 0), 0), 'Points Scored, All-Time')}
      </div>
      <h2 class="section-title">Trophy Case Preview</h2>
      <div class="grid cols-3">${trophy_case.slice(0, 3).map(factCard).join('')}</div>
    `;
  }

  let sortState = { key: 'championships', dir: -1 };
  const CAREER_COLS = [
    { key: 'owner', label: 'Owner' },
    { key: 'seasons_played', label: 'Seasons', num: true },
    { key: 'career_wins', label: 'W', num: true },
    { key: 'career_losses', label: 'L', num: true },
    { key: 'win_pct', label: 'Win%', num: true, fmt: pct },
    { key: 'career_points_for', label: 'PF', num: true, fmt: (v) => fmt(v, 0) },
    { key: 'career_points_against', label: 'PA', num: true, fmt: (v) => fmt(v, 0) },
    { key: 'championships', label: 'Titles', num: true },
    { key: 'podiums', label: 'Podiums', num: true },
    { key: 'avg_finish', label: 'Avg Finish', num: true, fmt: (v) => v.toFixed(2) },
    { key: 'best_finish', label: 'Best', num: true },
    { key: 'worst_finish', label: 'Worst', num: true },
  ];

  const CHART_METRICS = [
    { key: 'championships', label: 'Championships' },
    { key: 'podiums', label: 'Podiums (top 3 finishes)' },
    { key: 'career_wins', label: 'Career Wins' },
    { key: 'career_losses', label: 'Career Losses', invert: true },
    { key: 'win_pct', label: 'Win %', fmt: pct },
    { key: 'career_points_for', label: 'Points For', fmt: (v) => fmt(v, 0) },
    { key: 'career_points_against', label: 'Points Against', invert: true, fmt: (v) => fmt(v, 0) },
    { key: 'avg_finish', label: 'Avg Finish (lower is better)', invert: true, fmt: (v) => v.toFixed(2) },
    { key: 'seasons_played', label: 'Seasons Played' },
  ];
  let chartMetric = 'championships';

  function renderStandings() {
    document.getElementById('view-standings').innerHTML = `
      <h2 class="section-title">Owner Comparison</h2>
      <div class="controls">
        <label class="field-label" for="chart-metric">Metric</label>
        <select id="chart-metric">${CHART_METRICS.map((m) => `<option value="${m.key}">${m.label}</option>`).join('')}</select>
      </div>
      <div class="chart-wrap" style="margin-bottom:28px" id="career-chart"></div>
      <h2 class="section-title">All-Time Owner Records</h2>
      <div class="section-sub">Click a column header to sort. Hover a name for a quick stat card.</div>
      <div class="table-wrap"><table id="career-table"></table></div>
    `;
    const metricSel = document.getElementById('chart-metric');
    metricSel.value = chartMetric;
    metricSel.addEventListener('change', () => {
      chartMetric = metricSel.value;
      renderCareerChart();
    });
    renderCareerChart();
    renderCareerTable();
  }

  function renderCareerChart() {
    const metric = CHART_METRICS.find((m) => m.key === chartMetric);
    const rows = [...owner_career].sort((a, b) => (metric.invert ? a[metric.key] - b[metric.key] : b[metric.key] - a[metric.key]));
    const values = rows.map((r) => r[metric.key]);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    document.getElementById('career-chart').innerHTML = rows
      .map((r) => {
        const v = r[metric.key];
        const pctWidth = Math.max(((metric.invert ? max - v : v - min) / range) * 100, 3);
        const shown = metric.fmt ? metric.fmt(v) : v;
        const outside = pctWidth < 20;
        return `
      <div class="bar-row">
        <div class="bar-label owner-hover" data-owner="${r.owner}">${r.owner}</div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${pctWidth}%">${outside ? '' : `<span class="bar-value">${shown}</span>`}</div>
          ${outside ? `<span class="bar-value outside" style="position:absolute;left:${pctWidth}%;top:0;line-height:20px">${shown}</span>` : ''}
        </div>
      </div>`;
      })
      .join('');
    document.querySelectorAll('#career-chart .owner-hover').forEach((el) => attachOwnerHover(el, el.dataset.owner));
  }

  function renderCareerTable() {
    const rows = [...owner_career].sort((a, b) => (a[sortState.key] > b[sortState.key] ? 1 : a[sortState.key] < b[sortState.key] ? -1 : 0) * sortState.dir);
    const table = document.getElementById('career-table');
    table.innerHTML = `
      <thead><tr>${CAREER_COLS.map((c) => `<th class="${c.num ? 'num' : ''}" data-key="${c.key}">${c.label}${sortState.key === c.key ? `<span class="arrow">${sortState.dir === 1 ? '▲' : '▼'}</span>` : ''}</th>`).join('')}</tr></thead>
      <tbody>${rows
        .map(
          (r) => `<tr>${CAREER_COLS.map((c) => {
            if (c.key === 'owner') {
              return `<td>${r.championships > 0 ? `<span class="rank-badge medal" style="margin-right:8px">${r.championships}</span>` : ''}<span class="owner-hover" data-owner="${r.owner}">${r.owner}</span></td>`;
            }
            const v = c.fmt ? c.fmt(r[c.key]) : r[c.key];
            return `<td class="${c.num ? 'num' : ''}">${v}</td>`;
          }).join('')}</tr>`
        )
        .join('')}</tbody>
    `;
    table.querySelectorAll('thead th').forEach((th) => {
      th.addEventListener('click', () => {
        const key = th.dataset.key;
        sortState.dir = sortState.key === key ? -sortState.dir : -1;
        sortState.key = key;
        renderCareerTable();
      });
    });
    table.querySelectorAll('.owner-hover').forEach((el) => attachOwnerHover(el, el.dataset.owner));
  }

  function renderTrophies() {
    document.getElementById('view-trophies').innerHTML = `
      <h2 class="section-title">Trophy Case</h2>
      <div class="section-sub">The records, the blowouts, the shame.</div>
      <div class="grid cols-3">${trophy_case.map(factCard).join('')}</div>
    `;
  }

  function renderH2H() {
    const owners = owner_career.map((o) => o.owner).sort();
    document.getElementById('view-h2h').innerHTML = `
      <h2 class="section-title">Head-to-Head</h2>
      <div class="h2h-picker">
        <select id="h2h-a">${owners.map((o) => `<option>${o}</option>`).join('')}</select>
        <span class="h2h-vs">VS</span>
        <select id="h2h-b">${owners.map((o, i) => `<option ${i === 1 ? 'selected' : ''}>${o}</option>`).join('')}</select>
      </div>
      <div id="h2h-result" class="card"></div>
    `;
    const aSel = document.getElementById('h2h-a');
    const bSel = document.getElementById('h2h-b');
    aSel.addEventListener('change', updateH2H);
    bSel.addEventListener('change', updateH2H);
    updateH2H();

    function updateH2H() {
      const a = aSel.value;
      const b = bSel.value;
      const resEl = document.getElementById('h2h-result');
      if (a === b) {
        resEl.innerHTML = `<p style="color:var(--ink-muted);margin:0">Pick two different owners.</p>`;
        return;
      }
      const rec = head_to_head.find((r) => (r.owner_a === a && r.owner_b === b) || (r.owner_a === b && r.owner_b === a));
      if (!rec) {
        resEl.innerHTML = `<p style="color:var(--ink-muted);margin:0">${a} and ${b} have never played each other.</p>`;
        return;
      }
      const aWins = rec[a + '_wins'] || 0;
      const bWins = rec[b + '_wins'] || 0;
      resEl.innerHTML = `
        <div class="h2h-result">
          <div><div class="h2h-score" style="color:${aWins >= bWins ? 'var(--green)' : 'var(--ink)'}">${aWins}</div><div class="h2h-name">${a}</div></div>
          <div class="h2h-vs">&ndash;</div>
          <div><div class="h2h-score" style="color:${bWins > aWins ? 'var(--green)' : 'var(--ink)'}">${bWins}</div><div class="h2h-name">${b}</div></div>
          ${rec.ties ? `<div style="color:var(--ink-muted);font-family:var(--font-mono)">${rec.ties} tie${rec.ties > 1 ? 's' : ''}</div>` : ''}
          <div style="color:var(--ink-faint);font-size:12px;margin-left:auto">${rec.games} game${rec.games > 1 ? 's' : ''} all-time</div>
        </div>
      `;
    }
  }

  function renderSeasons() {
    document.getElementById('view-seasons').innerHTML = `
      <h2 class="section-title">Season Browser</h2>
      <div class="controls">
        <label class="field-label">Season</label>
        <select id="season-picker">${seasons.map((s) => `<option value="${s}">${s}</option>`).join('')}</select>
      </div>
      <div id="season-content"></div>
    `;
    const picker = document.getElementById('season-picker');
    picker.addEventListener('change', () => renderSeasonContent(Number(picker.value)));
    renderSeasonContent(latestSeason);
  }

  function renderSeasonContent(season) {
    const rows = standings.filter((s) => s.season === season).sort((a, b) => a.rank - b.rank);
    const picks = draft.filter((d) => d.season === season && d.round === 1).sort((a, b) => a.pick - b.pick);
    document.getElementById('season-content').innerHTML = `
      <h3 style="font-family:var(--font-display);font-size:18px;margin:20px 0 10px">Final Standings</h3>
      <div class="table-wrap"><table>
        <thead><tr><th class="num">#</th><th>Team</th><th class="num">W</th><th class="num">L</th><th class="num">T</th><th class="num">PF</th><th class="num">PA</th></tr></thead>
        <tbody>${rows
          .map(
            (r) => `<tr><td class="num"><span class="rank-badge${r.rank === 1 ? ' medal' : ''}">${r.rank}</span></td><td>${r.team_name}</td><td class="num">${r.wins}</td><td class="num">${r.losses}</td><td class="num">${r.ties}</td><td class="num">${fmt(r.points_for, 1)}</td><td class="num">${fmt(r.points_against, 1)}</td></tr>`
          )
          .join('')}</tbody>
      </table></div>
      <h3 style="font-family:var(--font-display);font-size:18px;margin:24px 0 10px">Round 1 Draft</h3>
      <div class="draft-pick-list">${picks.map((p) => `<div class="draft-pick"><span class="pn">${p.pick}. ${p.player_name}</span><span class="pt">${p.team_name}</span></div>`).join('')}</div>
    `;
  }

  let txnSeason = 'all';
  function renderTransactions() {
    document.getElementById('view-transactions').innerHTML = `
      <h2 class="section-title">Transaction Feed</h2>
      <div class="controls">
        <label class="field-label">Season</label>
        <select id="txn-season"><option value="all">All seasons</option>${seasons.map((s) => `<option value="${s}">${s}</option>`).join('')}</select>
      </div>
      <div class="card" id="txn-list" style="max-height:640px;overflow-y:auto"></div>
    `;
    const sel = document.getElementById('txn-season');
    sel.value = txnSeason;
    sel.addEventListener('change', () => {
      txnSeason = sel.value;
      renderTxnList();
    });
    renderTxnList();
  }

  function renderTxnList() {
    let rows = transactions;
    if (txnSeason !== 'all') {
      rows = rows.filter((t) => String(t.season) === txnSeason);
    } else {
      rows = [...rows].sort((a, b) => b.season - a.season);
    }
    const shown = rows.slice(0, 300);
    document.getElementById('txn-list').innerHTML =
      shown
        .map(
          (t) => `
      <div class="txn-row">
        <span class="txn-icon ${t.action}">${t.action === 'add' ? '+' : '−'}</span>
        <span class="txn-player">${t.player_name}</span>
        <span style="color:var(--ink-faint)">${t.note || ''}</span>
        <span style="color:var(--ink-muted)">${t.team_name}</span>
        <span class="txn-meta">${t.timestamp || ''} &middot; ${t.season}</span>
      </div>`
        )
        .join('') +
      (rows.length > 300 ? `<p style="color:var(--ink-faint);font-size:12px;margin-top:10px">Showing 300 of ${rows.length.toLocaleString()} &mdash; filter by season to narrow it down.</p>` : '');
  }

  const RENDERERS = {
    overview: renderOverview,
    standings: renderStandings,
    trophies: renderTrophies,
    h2h: renderH2H,
    seasons: renderSeasons,
    transactions: renderTransactions,
  };

  const initial = (location.hash || '#overview').slice(1);
  showTab(TABS.some((t) => t.id === initial) ? initial : 'overview');
})();
