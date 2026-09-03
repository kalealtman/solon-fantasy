(function () {
  const DATA = JSON.parse(document.getElementById('league-data').textContent);
  const { standings, draft, transactions, owner_career, head_to_head, trophy_case } = DATA;

  const fmt = (n, d = 0) => Number(n).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (n) => (n * 100).toFixed(1) + '%';
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

  function statTile(value, label, sub, accent) {
    return `<div class="card stat-tile"><div class="value${accent ? ' accent' : ''}">${value}</div><div class="label">${label}</div>${sub ? `<div class="sub">${sub}</div>` : ''}</div>`;
  }

  function factCard(f) {
    const parts = f.value.split(' -- ');
    return `<div class="card fact-card"><div class="fact-label">${f.fact}</div><div class="fact-value">${parts[0]}</div>${parts[1] ? `<div class="fact-detail">${parts[1]}</div>` : ''}</div>`;
  }

  function renderOverview() {
    const champRow = standings.find((s) => s.season === latestSeason && s.rank === 1);
    const mostChamps = [...owner_career].sort((a, b) => b.championships - a.championships)[0];
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
        ${statTile(mostChamps.championships, 'Most Championships', mostChamps.owner, true)}
        ${statTile(transactions.length.toLocaleString(), 'Career Transactions')}
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
    { key: 'best_finish', label: 'Best', num: true },
    { key: 'worst_finish', label: 'Worst', num: true },
  ];

  function renderStandings() {
    document.getElementById('view-standings').innerHTML = `
      <h2 class="section-title">Championships by Owner</h2>
      <div class="chart-wrap" style="margin-bottom:28px" id="champ-chart"></div>
      <h2 class="section-title">All-Time Owner Records</h2>
      <div class="section-sub">Click a column header to sort.</div>
      <div class="table-wrap"><table id="career-table"></table></div>
    `;
    renderChampChart();
    renderCareerTable();
  }

  function renderChampChart() {
    const rows = [...owner_career].filter((o) => o.championships > 0).sort((a, b) => b.championships - a.championships);
    const max = Math.max(...rows.map((r) => r.championships));
    document.getElementById('champ-chart').innerHTML = rows
      .map(
        (r) => `
      <div class="bar-row">
        <div class="bar-label">${r.owner}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${(r.championships / max) * 100}%"><span class="bar-value">${r.championships}</span></div></div>
      </div>`
      )
      .join('');
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
              return `<td>${r.championships > 0 ? `<span class="rank-badge accent" style="margin-right:8px">${r.championships}</span>` : ''}${r.owner}</td>`;
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
            (r) => `<tr><td class="num"><span class="rank-badge${r.rank === 1 ? ' accent' : ''}">${r.rank}</span></td><td>${r.team_name}</td><td class="num">${r.wins}</td><td class="num">${r.losses}</td><td class="num">${r.ties}</td><td class="num">${fmt(r.points_for, 1)}</td><td class="num">${fmt(r.points_against, 1)}</td></tr>`
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
