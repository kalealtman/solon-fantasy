(function () {
  const DATA = JSON.parse(document.getElementById('league-data').textContent);
  const { standings, draft, matchups, transactions, trades, owner_career, head_to_head, trophy_case } = DATA;
  const isPostseason = (season, week) => (season <= 2020 ? [14, 15, 16] : [15, 16, 17]).includes(week);
  const SHOTGUN_START_SEASON = 2023;

  // One entry per shotgun: since 2023, whoever has the lowest score in a
  // given regular-season week has to shotgun a beer on video.
  function computeShotgunRecords(minSeason, maxSeason) {
    const byWeek = {};
    matchups
      .filter((m) => m.season >= Math.max(minSeason, SHOTGUN_START_SEASON) && m.season <= maxSeason && !isPostseason(m.season, m.week))
      .forEach((m) => {
        const key = m.season + '-' + m.week;
        (byWeek[key] = byWeek[key] || []).push(m);
      });
    const records = [];
    Object.values(byWeek).forEach((grp) => {
      const minScore = Math.min(...grp.map((m) => m.score));
      grp.filter((m) => m.score === minScore).forEach((m) => records.push({ owner: m.owner, season: m.season }));
    });
    return records;
  }

  const fmt = (n, d = 0) => Number(n).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (n) => (n * 100).toFixed(1) + '%';
  // 'A' / 'A & B' / 'A, B & C' -- never silently pick a winner out of a tie.
  const joinNames = (names) => (names.length <= 1 ? names.join('') : names.slice(0, -1).join(', ') + ' & ' + names[names.length - 1]);
  const seasons = [...new Set(standings.map((s) => s.season))].sort((a, b) => b - a);
  const latestSeason = seasons[0];

  const TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'standings', label: 'All-Time' },
    { id: 'recordbook', label: 'Record Book' },
    { id: 'h2h', label: 'Head-to-Head' },
    { id: 'seasons', label: 'Seasons' },
    { id: 'draft', label: 'Draft' },
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
    <span><b>${owner_career.reduce((sum, o) => sum + (o.career_shotguns || 0), 0)}</b> shotguns since 2023</span>
  `;

  // ---------- owner hover tooltip (used on the career table and chart) ----------
  const tooltipEl = document.getElementById('owner-tooltip');
  const ownerByName = Object.fromEntries(owner_career.map((o) => [o.owner, o]));
  const madePlayoffsByTeam = Object.fromEntries(standings.map((s) => [s.season + '|' + s.team_name, s.made_playoffs]));

  function ownerTooltipHTML(owner) {
    const o = ownerByName[owner];
    if (!o) return '';
    const stat = (label, val) => `<div class="ot-stat"><span class="ot-label">${label}</span><span class="ot-val">${val}</span></div>`;
    return `
      <div class="ot-name">${o.owner}</div>
      <div class="ot-grid">
        ${stat('Seasons', o.seasons_played)}
        ${stat('Playoffs', `${o.playoff_appearances}/${o.seasons_played}`)}
        ${stat('Win%', pct(o.win_pct))}
        ${stat('🥇 1st', o.championships)}
        ${stat('🥈 2nd', o.second_places)}
        ${stat('🥉 3rd', o.third_places)}
        ${stat('Podiums', o.podiums)}
        ${stat('Avg Finish', o.avg_finish.toFixed(2))}
        ${stat('Best / Worst', `${o.best_finish} / ${o.worst_finish}`)}
        ${stat('Postseason', `${o.postseason_wins}-${o.postseason_losses} (${pct(o.postseason_win_pct)})`)}
        ${stat('Trades', o.career_trades)}
        ${stat('🍺 Shotguns', o.career_shotguns === null ? '--' : o.career_shotguns)}
      </div>
      ${
        o.top_drafted_players
          ? `<div class="ot-drafted"><div class="ot-drafted-title">Drafted most</div>${o.top_drafted_players
              .split('; ')
              .map((entry) => `<div>${entry.replace(/\((\d+x)\)/, '<b>$1</b>')}</div>`)
              .join('')}</div>`
          : ''
      }
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
    return `
      <div class="card fact-card">
        <div class="fact-label">${f.fact}</div>
        <div class="fact-number">${f.number}</div>
        <div class="fact-name">${f.name}</div>
        ${f.detail ? `<div class="fact-detail">${f.detail}</div>` : ''}
      </div>`;
  }

  function pickOverviewFacts(n) {
    const shotgunFact = trophy_case.find((f) => f.fact === 'Most Shotguns (Since 2023)');
    const rest = trophy_case.filter((f) => f !== shotgunFact);
    const picked = shotgunFact ? [shotgunFact, ...rest] : rest;
    return picked.slice(0, n);
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
        ${statTile(owner_career.reduce((sum, o) => sum + (o.career_shotguns || 0), 0), 'Total Shotguns', 'Since 2023')}
      </div>
      <h2 class="section-title">Record Book Preview</h2>
      <div class="grid cols-3">${pickOverviewFacts(6).map(factCard).join('')}</div>
    `;
  }

  // Single source of truth for every sortable/chartable owner-level field --
  // used to build both the table columns and the chart's metric picker, and
  // to keep them in sync (sorting the table by a metric re-charts it, and
  // vice versa) instead of tracking two independent, driftable states.
  const METRICS = {
    seasons_played: { label: 'Seasons Played' },
    career_wins: { label: 'Career Wins' },
    career_losses: { label: 'Career Losses', invert: true },
    win_pct: { label: 'Win %', fmt: pct },
    career_points_for: { label: 'Points For', fmt: (v) => fmt(v, 0) },
    career_points_against: { label: 'Points Against', invert: true, fmt: (v) => fmt(v, 0) },
    pf_per_season: { label: 'Points For / Season', fmt: (v) => fmt(v, 1) },
    pa_per_season: { label: 'Points Against / Season', invert: true, fmt: (v) => fmt(v, 1) },
    playoff_appearances: { label: 'Playoff Appearances' },
    career_shotguns: { label: 'Shotguns (Since 2023)', fmt: (v) => (v === null ? '--' : v), chartFilter: (r) => r.career_shotguns !== null },
    shotguns_per_season: { label: 'Shotguns / Season', fmt: (v) => (v === null ? '--' : v.toFixed(2)), chartFilter: (r) => r.shotguns_per_season !== null },
    championships: { label: 'Championships' },
    podiums: { label: 'Podiums (Top 3)' },
    avg_finish: { label: 'Avg Finish', invert: true, fmt: (v) => v.toFixed(2) },
    career_transactions: { label: 'Total Transactions' },
    transactions_per_season: { label: 'Transactions / Season', fmt: (v) => fmt(v, 1) },
    career_adds: { label: 'Waiver/FA Adds' },
    career_drops: { label: 'Drops' },
    career_trades: { label: 'Trades (Completed)' },
    trades_per_season: { label: 'Trades / Season', fmt: (v) => fmt(v, 1) },
    postseason_wins: { label: 'Postseason Wins' },
    postseason_losses: { label: 'Postseason Losses', invert: true },
    postseason_win_pct: { label: 'Postseason Win %', fmt: pct },
    best_finish: { label: 'Best Finish', invert: true, chartable: false },
    worst_finish: { label: 'Worst Finish', invert: true, chartable: false },
  };
  // Curated subset shown as table columns -- the rest are chart-only so the
  // table doesn't get overwhelming. All of them are still one click away
  // via the chart's metric picker.
  const TABLE_COLUMN_KEYS = [
    'seasons_played', 'career_wins', 'career_losses', 'win_pct', 'career_points_for',
    'career_points_against', 'pf_per_season', 'championships', 'podiums', 'avg_finish',
    'postseason_win_pct', 'transactions_per_season', 'career_shotguns', 'shotguns_per_season',
    'best_finish', 'worst_finish',
  ];

  let chartKey = 'championships'; // always a real metric -- drives the chart
  let focusKey = 'championships'; // drives table sort -- can be 'owner', which has no chart form
  let focusDir = -1; // -1 = best/highest first, 1 = worst/lowest first
  let seasonRange = { min: Math.min(...seasons), max: Math.max(...seasons) };

  // Pairs up consecutive rows within each (season, week) group -- parse_matchups()
  // appends both teams of a game back-to-back, and that order survives the
  // JSON round-trip, so row i / row i+1 within a group are always one game.
  function computePostseasonRecords(minSeason, maxSeason) {
    const records = {}; // owner -> { wins, losses, ties }
    const grouped = {};
    matchups
      .filter((m) => m.season >= minSeason && m.season <= maxSeason && isPostseason(m.season, m.week))
      .forEach((m) => {
        const key = m.season + '-' + m.week;
        (grouped[key] = grouped[key] || []).push(m);
      });
    Object.values(grouped).forEach((grp) => {
      for (let i = 0; i < grp.length - 1; i += 2) {
        const a = grp[i];
        const b = grp[i + 1];
        if (a.owner === b.owner) continue;
        const aIn = madePlayoffsByTeam[a.season + '|' + a.team_name];
        const bIn = madePlayoffsByTeam[b.season + '|' + b.team_name];
        if (!aIn || !bIn) continue; // consolation bracket, not the real playoffs
        [
          [a.owner, a.score, b.score],
          [b.owner, b.score, a.score],
        ].forEach(([owner, own, opp]) => {
          records[owner] = records[owner] || { wins: 0, losses: 0, ties: 0 };
          if (own > opp) records[owner].wins++;
          else if (own < opp) records[owner].losses++;
          else records[owner].ties++;
        });
      }
    });
    return records;
  }

  function computeOwnerStats(minSeason, maxSeason) {
    const inRange = (s) => s >= minSeason && s <= maxSeason;
    const rowsByOwner = {};
    standings.filter((s) => inRange(s.season)).forEach((s) => {
      (rowsByOwner[s.owner] = rowsByOwner[s.owner] || []).push(s);
    });
    const txnsInRange = transactions.filter((t) => inRange(t.season));
    const draftInRange = draft.filter((d) => inRange(d.season));
    const tradesInRange = trades.filter((t) => t.completed && inRange(t.season));
    const postseasonByOwner = computePostseasonRecords(minSeason, maxSeason);
    const shotgunRecords = computeShotgunRecords(minSeason, maxSeason);

    return Object.entries(rowsByOwner).map(([owner, rows]) => {
      const seasonsPlayed = new Set(rows.map((r) => r.season)).size;
      const wins = rows.reduce((s, r) => s + r.wins, 0);
      const losses = rows.reduce((s, r) => s + r.losses, 0);
      const ties = rows.reduce((s, r) => s + r.ties, 0);
      const pf = rows.reduce((s, r) => s + r.points_for, 0);
      const pa = rows.reduce((s, r) => s + r.points_against, 0);
      const championships = rows.filter((r) => r.rank === 1).length;
      const seconds = rows.filter((r) => r.rank === 2).length;
      const thirds = rows.filter((r) => r.rank === 3).length;
      const playoffAppearances = rows.filter((r) => r.made_playoffs).length;
      const ownerTxns = txnsInRange.filter((t) => t.owner === owner);
      const adds = ownerTxns.filter((t) => t.action === 'add').length;
      const drops = ownerTxns.filter((t) => t.action === 'drop').length;
      const pickCounts = {};
      draftInRange
        .filter((d) => d.owner === owner)
        .forEach((d) => (pickCounts[d.player_name] = (pickCounts[d.player_name] || 0) + 1));
      const topPlayers = Object.keys(pickCounts)
        .sort((n1, n2) => pickCounts[n2] - pickCounts[n1] || n1.localeCompare(n2))
        .slice(0, 3)
        .map((name) => `${name} (${pickCounts[name]}x)`)
        .join('; ');
      const tradeCount = tradesInRange.filter((t) => t.owner === owner).length;
      const ps = postseasonByOwner[owner] || { wins: 0, losses: 0, ties: 0 };
      const seasonsSinceShotgunRule = rows.filter((r) => r.season >= SHOTGUN_START_SEASON).length;
      const careerShotguns = seasonsSinceShotgunRule > 0 ? shotgunRecords.filter((s) => s.owner === owner).length : null;
      const shotgunsPerSeason = seasonsSinceShotgunRule > 0 ? careerShotguns / seasonsSinceShotgunRule : null;
      return {
        owner,
        seasons_played: seasonsPlayed,
        career_wins: wins,
        career_losses: losses,
        career_ties: ties,
        win_pct: wins / Math.max(wins + losses, 1),
        career_points_for: pf,
        career_points_against: pa,
        pf_per_season: pf / seasonsPlayed,
        pa_per_season: pa / seasonsPlayed,
        playoff_appearances: playoffAppearances,
        championships,
        second_places: seconds,
        third_places: thirds,
        podiums: championships + seconds + thirds,
        avg_finish: rows.reduce((s, r) => s + r.rank, 0) / rows.length,
        best_finish: Math.min(...rows.map((r) => r.rank)),
        worst_finish: Math.max(...rows.map((r) => r.rank)),
        career_adds: adds,
        career_drops: drops,
        career_transactions: adds + drops,
        transactions_per_season: (adds + drops) / seasonsPlayed,
        top_drafted_players: topPlayers,
        career_shotguns: careerShotguns,
        shotguns_per_season: shotgunsPerSeason,
        career_trades: tradeCount,
        trades_per_season: tradeCount / seasonsPlayed,
        postseason_wins: ps.wins,
        postseason_losses: ps.losses,
        postseason_ties: ps.ties,
        postseason_win_pct: ps.wins / Math.max(ps.wins + ps.losses, 1),
      };
    });
  }

  function renderStandings() {
    const chartableKeys = Object.keys(METRICS).filter((k) => METRICS[k].chartable !== false);
    document.getElementById('view-standings').innerHTML = `
      <h2 class="section-title">Owner Comparison</h2>
      <div class="controls">
        <label class="field-label" for="chart-metric">Metric</label>
        <select id="chart-metric">${chartableKeys.map((k) => `<option value="${k}">${METRICS[k].label}</option>`).join('')}</select>
        <label class="field-label" for="range-from" style="margin-left:14px">Seasons</label>
        <select id="range-from">${seasons.map((s) => `<option value="${s}">${s}</option>`).join('')}</select>
        <span style="color:var(--ink-faint)">&ndash;</span>
        <select id="range-to">${seasons.map((s) => `<option value="${s}">${s}</option>`).join('')}</select>
      </div>
      <div class="chart-wrap" style="margin-bottom:28px" id="career-chart"></div>
      <h2 class="section-title">All-Time Owner Records</h2>
      <div class="section-sub">Click a column header to sort (also updates the chart). Hover a name for a quick stat card.</div>
      <div class="table-wrap"><table id="career-table"></table></div>
    `;
    const metricSel = document.getElementById('chart-metric');
    const fromSel = document.getElementById('range-from');
    const toSel = document.getElementById('range-to');
    metricSel.value = chartKey;
    fromSel.value = seasonRange.min;
    toSel.value = seasonRange.max;

    metricSel.addEventListener('change', () => {
      chartKey = metricSel.value;
      focusKey = chartKey;
      focusDir = METRICS[chartKey].invert ? 1 : -1;
      renderAllTimeViews();
    });
    const onRangeChange = () => {
      let min = Number(fromSel.value);
      let max = Number(toSel.value);
      if (min > max) [min, max] = [max, min]; // tolerate the two selects crossing
      seasonRange = { min, max };
      renderAllTimeViews();
    };
    fromSel.addEventListener('change', onRangeChange);
    toSel.addEventListener('change', onRangeChange);

    renderAllTimeViews();
  }

  function renderAllTimeViews() {
    const rows = computeOwnerStats(seasonRange.min, seasonRange.max);
    renderCareerChart(rows);
    renderCareerTable(rows);
  }

  function renderCareerChart(rows) {
    const metric = METRICS[chartKey];
    const chartable = metric.chartFilter ? rows.filter(metric.chartFilter) : rows;
    const sorted = [...chartable].sort((a, b) => (metric.invert ? a[chartKey] - b[chartKey] : b[chartKey] - a[chartKey]));
    const values = sorted.map((r) => r[chartKey]);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    document.getElementById('career-chart').innerHTML = sorted
      .map((r) => {
        const v = r[chartKey];
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

  function renderCareerTable(rows) {
    const sorted = [...rows].sort((a, b) => {
      const key = focusKey === 'owner' ? 'owner' : focusKey;
      const av = a[key];
      const bv = b[key];
      // Nulls (e.g. shotguns for an owner who left before the rule existed)
      // always sort last, regardless of ascending/descending -- otherwise
      // JS's null-as-0 coercion scatters them in with real low values.
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return (av > bv ? 1 : av < bv ? -1 : 0) * focusDir;
    });
    const table = document.getElementById('career-table');
    const cols = [{ key: 'owner', label: 'Owner' }, ...TABLE_COLUMN_KEYS.map((k) => ({ key: k, label: METRICS[k].label, ...METRICS[k] }))];
    table.innerHTML = `
      <thead><tr>${cols.map((c) => `<th class="${c.key === 'owner' ? '' : 'num'}" data-key="${c.key}">${c.key === 'owner' ? c.label : abbreviate(c.label)}${focusKey === c.key ? `<span class="arrow">${focusDir === 1 ? '▲' : '▼'}</span>` : ''}</th>`).join('')}</tr></thead>
      <tbody>${sorted
        .map(
          (r) => `<tr>${cols
            .map((c) => {
              if (c.key === 'owner') {
                return `<td>${r.championships > 0 ? `<span class="rank-badge medal" style="margin-right:8px">${r.championships}</span>` : ''}<span class="owner-hover" data-owner="${r.owner}">${r.owner}</span></td>`;
              }
              const v = c.fmt ? c.fmt(r[c.key]) : r[c.key];
              return `<td class="num">${v}</td>`;
            })
            .join('')}</tr>`
        )
        .join('')}</tbody>
    `;
    table.querySelectorAll('thead th').forEach((th) => {
      th.addEventListener('click', () => {
        const key = th.dataset.key;
        focusDir = focusKey === key ? -focusDir : key === 'owner' ? 1 : METRICS[key].invert ? 1 : -1;
        focusKey = key;
        if (key !== 'owner') {
          chartKey = key;
          document.getElementById('chart-metric').value = key;
        }
        renderAllTimeViews();
      });
    });
    table.querySelectorAll('.owner-hover').forEach((el) => attachOwnerHover(el, el.dataset.owner));
  }

  function abbreviate(label) {
    const short = {
      'Career Wins': 'W',
      'Career Losses': 'L',
      'Win %': 'Win%',
      'Points For': 'PF',
      'Points Against': 'PA',
      'Postseason Win %': 'Post W%',
      'Shotguns (Since 2023)': 'Shotguns',
      'Shotguns / Season': 'SG/Yr',
    };
    return short[label] || label;
  }

  const RECORD_CATEGORIES = [
    { key: 'regular_season', label: 'Regular Season' },
    { key: 'postseason', label: 'Postseason' },
    { key: 'transactions', label: 'Transactions' },
  ];

  function renderRecordBook() {
    const columns = RECORD_CATEGORIES.map(
      (cat) => `
      <div class="record-column">
        <div class="record-column-title">${cat.label}</div>
        ${trophy_case
          .filter((f) => f.category === cat.key)
          .map(factCard)
          .join('')}
      </div>`
    ).join('');
    document.getElementById('view-recordbook').innerHTML = `
      <h2 class="section-title">Record Book</h2>
      <div class="record-columns">${columns}</div>
    `;
  }

  // Same pairing trick as computePostseasonRecords -- parse_matchups() keeps
  // both teams of a game adjacent, and that survives the JSON round-trip.
  function findGamesBetween(a, b) {
    const grouped = {};
    matchups.forEach((m) => {
      const key = m.season + '-' + m.week;
      (grouped[key] = grouped[key] || []).push(m);
    });
    const games = [];
    Object.values(grouped).forEach((grp) => {
      for (let i = 0; i < grp.length - 1; i += 2) {
        const x = grp[i];
        const y = grp[i + 1];
        if ((x.owner === a && y.owner === b) || (x.owner === b && y.owner === a)) {
          const aRow = x.owner === a ? x : y;
          const bRow = x.owner === a ? y : x;
          games.push({ season: aRow.season, week: aRow.week, aScore: aRow.score, bScore: bRow.score });
        }
      }
    });
    return games.sort((g1, g2) => g1.season - g2.season || g1.week - g2.week);
  }

  function renderH2H() {
    const owners = owner_career.map((o) => o.owner).sort();
    document.getElementById('view-h2h').innerHTML = `
      <h2 class="section-title">Head-to-Head</h2>
      <div class="h2h-picker">
        <select id="h2h-a"><option value="">Select team</option>${owners.map((o) => `<option>${o}</option>`).join('')}</select>
        <span class="h2h-vs">VS</span>
        <select id="h2h-b"><option value="">Select team</option>${owners.map((o) => `<option>${o}</option>`).join('')}</select>
      </div>
      <div id="h2h-result" class="card h2h-card"></div>
      <div id="h2h-games"></div>
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
      const gamesEl = document.getElementById('h2h-games');
      if (!a || !b) {
        resEl.innerHTML = `<p style="color:var(--ink-muted);margin:0">Pick two teams to see their head-to-head record.</p>`;
        gamesEl.innerHTML = '';
        return;
      }
      if (a === b) {
        resEl.innerHTML = `<p style="color:var(--ink-muted);margin:0">Pick two different owners.</p>`;
        gamesEl.innerHTML = '';
        return;
      }
      const rec = head_to_head.find((r) => (r.owner_a === a && r.owner_b === b) || (r.owner_a === b && r.owner_b === a));
      if (!rec) {
        resEl.innerHTML = `<p style="color:var(--ink-muted);margin:0">${a} and ${b} have never played each other.</p>`;
        gamesEl.innerHTML = '';
        return;
      }
      const aWins = rec[a + '_wins'] || 0;
      const bWins = rec[b + '_wins'] || 0;
      resEl.innerHTML = `
        <div class="h2h-result">
          <div><div class="h2h-score" style="color:${aWins >= bWins ? 'var(--green)' : 'var(--ink)'}">${aWins}</div><div class="h2h-name">${a}</div></div>
          <div class="h2h-vs">&ndash;</div>
          <div><div class="h2h-score" style="color:${bWins > aWins ? 'var(--green)' : 'var(--ink)'}">${bWins}</div><div class="h2h-name">${b}</div></div>
        </div>
        <div class="h2h-meta">${rec.games} game${rec.games > 1 ? 's' : ''} all-time${rec.ties ? ` &middot; ${rec.ties} tie${rec.ties > 1 ? 's' : ''}` : ''}</div>
      `;

      const games = findGamesBetween(a, b);
      gamesEl.innerHTML = `
        <h3 class="section-title h2h-games-title" style="font-size:18px">Every Matchup</h3>
        <div class="table-wrap"><table>
          <thead><tr><th class="num">Season</th><th class="num">Week</th><th class="num">${a}</th><th class="num">${b}</th><th>Result</th></tr></thead>
          <tbody>${games
            .map((g) => {
              const post = isPostseason(g.season, g.week);
              const winner = g.aScore > g.bScore ? a : g.bScore > g.aScore ? b : 'Tie';
              return `<tr>
                <td class="num">${g.season}</td>
                <td class="num">${g.week}${post ? ' <span class="ot-label" style="font-size:10px">(post)</span>' : ''}</td>
                <td class="num">${fmt(g.aScore, 2)}</td>
                <td class="num">${fmt(g.bScore, 2)}</td>
                <td>${winner}</td>
              </tr>`;
            })
            .join('')}</tbody>
        </table></div>
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

  function medalClass(rank) {
    return rank === 1 ? ' medal' : rank === 2 ? ' silver' : rank === 3 ? ' bronze' : '';
  }

  function renderSeasonContent(season) {
    const rows = standings.filter((s) => s.season === season).sort((a, b) => a.rank - b.rank);
    const picks = draft.filter((d) => d.season === season && d.round === 1).sort((a, b) => a.pick - b.pick);
    const seasonMatchups = matchups.filter((m) => m.season === season);

    let highest = null;
    let lowest = null;
    const byWeek = {};
    seasonMatchups.forEach((m) => {
      (byWeek[m.week] = byWeek[m.week] || []).push(m);
      if (!highest || m.score > highest.score) highest = m;
      if (!lowest || m.score < lowest.score) lowest = m;
    });
    let biggestBlowout = null;
    let closestGame = null;
    Object.values(byWeek).forEach((grp) => {
      for (let i = 0; i < grp.length - 1; i += 2) {
        const a = grp[i];
        const b = grp[i + 1];
        const margin = Math.abs(a.score - b.score);
        const game = { week: a.week, a, b, margin };
        if (!biggestBlowout || margin > biggestBlowout.margin) biggestBlowout = game;
        if (!closestGame || margin < closestGame.margin) closestGame = game;
      }
    });

    const matchupSub = (game) => {
      const winner = game.a.score >= game.b.score ? game.a : game.b;
      const loser = winner === game.a ? game.b : game.a;
      return `<b>${winner.owner}</b> ${fmt(winner.score, 1)} def. ${loser.owner} ${fmt(loser.score, 1)} &middot; week ${game.week}`;
    };

    const highlightCards = [
      highest && statTile(fmt(highest.score, 1), 'Highest Weekly Score', `${highest.owner} &middot; week ${highest.week}`),
      lowest && statTile(fmt(lowest.score, 1), 'Lowest Weekly Score', `${lowest.owner} &middot; week ${lowest.week}`),
      biggestBlowout && statTile(fmt(biggestBlowout.margin, 1), 'Biggest Blowout', matchupSub(biggestBlowout)),
      closestGame && statTile(fmt(closestGame.margin, 1), 'Closest Game', matchupSub(closestGame)),
    ]
      .filter(Boolean)
      .join('');

    document.getElementById('season-content').innerHTML = `
      <div class="grid cols-4" style="margin:20px 0">${highlightCards}</div>
      <h3 style="font-family:var(--font-display);font-size:18px;margin:24px 0 10px">Final Standings</h3>
      <div class="table-wrap"><table>
        <thead><tr><th class="num">#</th><th>Team</th><th class="num">W</th><th class="num">L</th><th class="num">T</th><th class="num">PF</th><th class="num">PA</th></tr></thead>
        <tbody>${rows
          .map(
            (r) => `<tr><td class="num"><span class="rank-badge${medalClass(r.rank)}">${r.rank}</span></td><td>${r.team_name}<div class="team-owner">${r.owner}</div></td><td class="num">${r.wins}</td><td class="num">${r.losses}</td><td class="num">${r.ties}</td><td class="num">${fmt(r.points_for, 1)}</td><td class="num">${fmt(r.points_against, 1)}</td></tr>`
          )
          .join('')}</tbody>
      </table></div>
      <h3 style="font-family:var(--font-display);font-size:18px;margin:24px 0 10px">Round 1 Draft</h3>
      <div class="draft-board" style="--cols:${picks.length}">${picks
        .map(
          (p) => `<div class="draft-board-slot">
            <div class="draft-board-pick">1.${String(p.pick).padStart(2, '0')}</div>
            <div class="draft-board-card">
              <div class="draft-board-name">${p.player_name}</div>
              <div class="draft-board-owner">${p.owner}</div>
            </div>
          </div>`
        )
        .join('')}</div>
    `;
  }

  function renderDraftPage() {
    document.getElementById('view-draft').innerHTML = `
      <h2 class="section-title">Draft Board</h2>
      <div class="controls">
        <label class="field-label">Season</label>
        <select id="draft-season-picker">${seasons.map((s) => `<option value="${s}">${s}</option>`).join('')}</select>
      </div>
      <div id="draft-board-content"></div>
    `;
    const picker = document.getElementById('draft-season-picker');
    picker.addEventListener('change', () => renderDraftBoardForSeason(Number(picker.value)));
    renderDraftBoardForSeason(latestSeason);
  }

  function renderDraftBoardForSeason(season) {
    const picks = draft.filter((d) => d.season === season);
    const rounds = [...new Set(picks.map((p) => p.round))].sort((a, b) => a - b);
    document.getElementById('draft-board-content').innerHTML = rounds
      .map((round) => {
        const roundPicks = picks.filter((p) => p.round === round).sort((a, b) => a.pick - b.pick);
        return `
          <div class="draft-round-label">Round ${round}</div>
          <div class="draft-board" style="--cols:${roundPicks.length}">${roundPicks
            .map(
              (p) => `<div class="draft-board-slot">
                <div class="draft-board-pick">${round}.${String(p.pick).padStart(2, '0')}</div>
                <div class="draft-board-card">
                  <div class="draft-board-name">${p.player_name}</div>
                  <div class="draft-board-owner">${p.owner}</div>
                </div>
              </div>`
            )
            .join('')}</div>
        `;
      })
      .join('');
  }

  // Trades live in a separate dataset with a different shape (two sides,
  // multiple players per side) -- reshape completed trades into the same
  // one-row-per-player-event form as adds/drops so they can share one feed
  // and one set of filters instead of being a second, disconnected view.
  // Trades and regular adds/drops need to stay grouped as single events (a
  // trade has two sides with multiple players each; Yahoo's transactions
  // page also bundles a same-moment add+drop into one visual block) rather
  // than flattened into disconnected one-player-per-row entries -- that
  // loses who the trade partner was and which direction a player moved.
  const unifiedEvents = (() => {
    const tradeGroups = {};
    trades
      .filter((t) => t.completed)
      .forEach((t) => {
        const key = t.season + '-' + t.trade_id;
        (tradeGroups[key] = tradeGroups[key] || []).push(t);
      });
    const tradeEvents = Object.values(tradeGroups)
      .filter((sides) => sides.length === 2)
      .map((sides) => ({ type: 'trade', season: sides[0].season, timestamp: sides[0].timestamp, sides }));

    // Yahoo doesn't give adds/drops a shared transaction id the way trades
    // have trade_id -- (owner, season, timestamp) is the best available
    // proxy for "these happened as one move" (e.g. a waiver claim that
    // both added and dropped a player at the same instant).
    const regularGroups = {};
    transactions.forEach((t) => {
      const key = [t.owner, t.season, t.timestamp].join('|');
      (regularGroups[key] = regularGroups[key] || []).push(t);
    });
    const regularEvents = Object.values(regularGroups).map((items) => ({
      type: 'regular',
      season: items[0].season,
      timestamp: items[0].timestamp,
      owner: items[0].owner,
      team_name: items[0].team_name,
      adds: items.filter((i) => i.action === 'add'),
      drops: items.filter((i) => i.action === 'drop'),
    }));

    return [...tradeEvents, ...regularEvents];
  })();

  let txnFilters = { season: 'all', type: 'all', owner: 'all', player: '' };

  function renderTransactions() {
    const owners = owner_career.map((o) => o.owner).sort();
    document.getElementById('view-transactions').innerHTML = `
      <h2 class="section-title">Transaction Feed</h2>
      <div class="controls">
        <label class="field-label">Season</label>
        <select id="txn-season"><option value="all">All seasons</option>${seasons.map((s) => `<option value="${s}">${s}</option>`).join('')}</select>
        <label class="field-label" style="margin-left:10px">Type</label>
        <select id="txn-type"><option value="all">All types</option><option value="add">Add</option><option value="drop">Drop</option><option value="trade">Trade</option></select>
        <label class="field-label" style="margin-left:10px">Owner</label>
        <select id="txn-owner"><option value="all">All owners</option>${owners.map((o) => `<option>${o}</option>`).join('')}</select>
        <input id="txn-player" class="btn" type="text" placeholder="Search player&hellip;" style="min-width:160px">
      </div>
      <div class="card" id="txn-list" style="max-height:640px;overflow-y:auto"></div>
    `;
    const seasonSel = document.getElementById('txn-season');
    const typeSel = document.getElementById('txn-type');
    const ownerSel = document.getElementById('txn-owner');
    const playerInput = document.getElementById('txn-player');
    seasonSel.value = txnFilters.season;
    typeSel.value = txnFilters.type;
    ownerSel.value = txnFilters.owner;
    playerInput.value = txnFilters.player;

    seasonSel.addEventListener('change', () => {
      txnFilters.season = seasonSel.value;
      renderTxnList();
    });
    typeSel.addEventListener('change', () => {
      txnFilters.type = typeSel.value;
      renderTxnList();
    });
    ownerSel.addEventListener('change', () => {
      txnFilters.owner = ownerSel.value;
      renderTxnList();
    });
    playerInput.addEventListener('input', () => {
      txnFilters.player = playerInput.value;
      renderTxnList();
    });
    renderTxnList();
  }

  function eventMatchesPlayer(e, q) {
    if (e.type === 'trade') return e.sides.some((s) => (s.players_received || '').toLowerCase().includes(q));
    return [...e.adds, ...e.drops].some((i) => i.player_name.toLowerCase().includes(q));
  }

  function renderEventRow(e) {
    if (e.type === 'trade') {
      const [a, b] = e.sides;
      return `
        <div class="txn-row txn-trade-row">
          <span class="txn-icon trade">⇄</span>
          <div class="txn-trade-body">
            <div><b>${a.owner}</b> (${a.team_name}) receives: ${a.players_received || 'nothing'} &mdash; from <b>${b.owner}</b></div>
            <div><b>${b.owner}</b> (${b.team_name}) receives: ${b.players_received || 'nothing'} &mdash; from <b>${a.owner}</b></div>
          </div>
          <span class="txn-meta">${e.timestamp || ''} &middot; ${e.season}</span>
        </div>`;
    }
    const parts = [
      ...e.adds.map((i) => `<span class="txn-icon add">+</span>${i.player_name}`),
      ...e.drops.map((i) => `<span class="txn-icon drop">&minus;</span>${i.player_name}`),
    ];
    return `
      <div class="txn-row">
        <div class="txn-event-players">${parts.join('')}</div>
        <span style="color:var(--ink-muted)">${e.team_name}</span>
        <span class="txn-meta">${e.timestamp || ''} &middot; ${e.season}</span>
      </div>`;
  }

  function renderTxnList() {
    let events = unifiedEvents;
    if (txnFilters.season !== 'all') events = events.filter((e) => String(e.season) === txnFilters.season);
    if (txnFilters.type !== 'all') {
      events = events.filter((e) => {
        if (txnFilters.type === 'trade') return e.type === 'trade';
        if (e.type !== 'regular') return false;
        return txnFilters.type === 'add' ? e.adds.length > 0 : e.drops.length > 0;
      });
    }
    if (txnFilters.owner !== 'all') {
      events = events.filter((e) => (e.type === 'trade' ? e.sides.some((s) => s.owner === txnFilters.owner) : e.owner === txnFilters.owner));
    }
    if (txnFilters.player.trim()) {
      const q = txnFilters.player.trim().toLowerCase();
      events = events.filter((e) => eventMatchesPlayer(e, q));
    }
    events = [...events].sort((a, b) => b.season - a.season);

    const shown = events.slice(0, 300);
    document.getElementById('txn-list').innerHTML =
      shown.map(renderEventRow).join('') +
      (events.length === 0
        ? `<p style="color:var(--ink-muted);margin:0">No transactions match those filters.</p>`
        : events.length > 300
        ? `<p style="color:var(--ink-faint);font-size:12px;margin-top:10px">Showing 300 of ${events.length.toLocaleString()} &mdash; narrow the filters to see more.</p>`
        : '');
  }

  const RENDERERS = {
    overview: renderOverview,
    standings: renderStandings,
    recordbook: renderRecordBook,
    h2h: renderH2H,
    seasons: renderSeasons,
    draft: renderDraftPage,
    transactions: renderTransactions,
  };

  const initial = (location.hash || '#overview').slice(1);
  showTab(TABS.some((t) => t.id === initial) ? initial : 'overview');
})();
