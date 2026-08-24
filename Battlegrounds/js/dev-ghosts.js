/**
 * Dev Ghosts - Ghost Analysis Dashboard
 * Uses the same minion card structure as the main game (desktop.css .minion-card)
 */

const API_BASE = '/api/dev-ghosts';

// ── State ──

let currentTab = 'overview';
let ghostListPage = 1;
let ghostListFilters = {};

// ── Roman numerals for tier display ──
function toRomanNumeral(num) {
    const map = { 1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI' };
    return map[num] || String(num);
}

// ── Keyword color mapping (matches the main game's effect tag styling) ──
const KEYWORD_COLORS = {
    'guard': '#4a90d9',
    'assault': '#e74c3c',
    'poke': '#f39c12',
    'cast': '#9b59b6',
    'death_toll': '#2c3e50',
    'rich': '#f1c40f',
    'fast': '#1abc9c',
    'leech': '#8e44ad',
    'stun': '#e67e22',
    'blitz': '#e74c3c',
    'poison': '#27ae60',
    'rally': '#3498db',
    'scavenge': '#95a5a6',
    'grow': '#2ecc71',
    'bond': '#e91e63',
    'resurrect': '#7f8c8d',
    'summon': '#00bcd4',
    'on_any_death': '#555',
    'on_any_summon': '#00838f',
    'start_of_combat': '#ff9800',
};

// ── Render a proper minion card using the same HTML structure as the game ──
function renderMinionCard(minion) {
    const golden = minion.golden ? 'golden' : '';
    const imageStyle = minion.image
        ? `background-image: url('images/original/${minion.image}'); background-size: 100% 100%; background-repeat: no-repeat; background-position: center;`
        : '';

    // Keyword tags
    let tagsHtml = '';
    if (minion.keywords && minion.keywords.length > 0) {
        tagsHtml = '<div class="minion-tags">';
        for (const kw of minion.keywords) {
            const color = KEYWORD_COLORS[kw] || '#666';
            tagsHtml += `<div class="effect-tag" style="background:${color}" title="${kw}">${kw.replace(/_/g, ' ')}</div>`;
        }
        tagsHtml += '</div>';
    }

    // Tribe display
    let tribesHtml = '';
    if (minion.type) {
        const tribes = typeof minion.type === 'string' && minion.type.includes(',')
            ? minion.type.split(',').map(t => t.trim())
            : [minion.type];
        if (tribes[0]) {
            tribesHtml = `<div class="minion-tribes">${tribes.map(t => `<div class="minion-tribe">${t}</div>`).join('')}</div>`;
        }
    }

    // Tier display
    const tierHtml = minion.tier ? `<div class="minion-tier">${toRomanNumeral(minion.tier)}</div>` : '';

    return `
        <div class="minion-card ${golden}" style="${imageStyle}">
            <div class="minion-name">${minion.name}</div>
            ${tierHtml}
            ${tagsHtml}
            <div class="minion-stats-box">
                <div class="minion-stats">
                    <span class="stat attack">${minion.attack}</span>
                    <span class="stat health">${Math.max(0, minion.health)}</span>
                </div>
            </div>
            ${tribesHtml}
        </div>
    `;
}

// ── Render a band as a grid of minion cards ──
function renderBandGrid(band) {
    if (!band || band.length === 0) return '<div class="muted">Empty band</div>';
    return `<div class="band-grid">${band.map(m => renderMinionCard(m)).join('')}</div>`;
}

// ── Init ──

document.addEventListener('DOMContentLoaded', () => {
    loadOverview();
    setupTabs();
});

function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTab = btn.dataset.tab;
            showTab(currentTab);
        });
    });
}

function showTab(tab) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById('tab-' + tab);
    if (panel) panel.classList.add('active');

    if (tab === 'overview') loadOverview();
    else if (tab === 'analysis') loadAnalysis();
    else if (tab === 'journeys') loadJourneys();
    else if (tab === 'ghosts') loadGhostList();
    else if (tab === 'populate') setupPopulate();
}

// ── Overview Tab ──

async function loadOverview() {
    const panel = document.getElementById('tab-overview');
    panel.innerHTML = '<div class="loading">Loading stats...</div>';

    try {
        const res = await fetch(`${API_BASE}/stats`);
        const data = await res.json();

        if (!data.success) throw new Error(data.error);
        if (data.empty) {
            panel.innerHTML = `
                <div class="empty-state">
                    <h3>No Ghosts Yet</h3>
                    <p>Use the Populate tab to generate ghost data from headless games.</p>
                </div>`;
            return;
        }

        let html = '';

        // Summary cards
        html += '<div class="stat-cards">';
        html += statCard('Total Ghosts', data.total);
        html += statCard('Avg Power', data.power.avg);
        html += statCard('Power Range', `${data.power.min} - ${data.power.max}`);
        html += statCard('Total Battles', data.battles.total);
        html += '</div>';

        // Source breakdown + Battle results row
        html += '<div class="section-row">';
        html += '<div class="section-card">';
        html += '<h3>By Source</h3>';
        html += '<div class="source-tags">';
        for (const [src, count] of Object.entries(data.sources)) {
            html += `<div class="source-tag tag-${src}"><span class="tag-label">${src}</span><span class="tag-count">${count}</span></div>`;
        }
        html += '</div></div>';

        html += '<div class="section-card">';
        html += '<h3>Battle Results</h3>';
        const b = data.battles;
        if (b.total > 0) {
            const pWinPct = Math.round(b.player_wins / b.total * 100);
            const gWinPct = Math.round(b.ghost_wins / b.total * 100);
            html += `<div class="battle-bar">`;
            html += `<div class="bar-fill player-fill" style="width:${pWinPct}%">${b.player_wins} Player</div>`;
            html += `<div class="bar-fill ghost-fill" style="width:${gWinPct}%">${b.ghost_wins} Ghost</div>`;
            if (b.draws > 0) html += `<div class="bar-fill draw-fill" style="width:${100-pWinPct-gWinPct}%">${b.draws} Draw</div>`;
            html += `</div>`;
        } else {
            html += '<p class="muted">No battles recorded</p>';
        }
        html += '</div></div>';

        // Milestones chart
        html += '<div class="section-card full-width">';
        html += '<h3>Ghosts by Milestone</h3>';
        html += '<div class="bar-chart">';
        const maxCount = Math.max(...data.milestones.map(m => m.count));
        for (const ms of data.milestones) {
            const pct = Math.round(ms.count / maxCount * 100);
            html += `<div class="chart-bar">
                <div class="chart-bar-fill" style="height:${pct}%"></div>
                <div class="chart-bar-label">${ms.milestone}s</div>
                <div class="chart-bar-value">${ms.count}</div>
            </div>`;
        }
        html += '</div></div>';

        // Heroes
        html += '<div class="section-card full-width">';
        html += '<h3>By Hero</h3>';
        html += '<div class="hero-grid">';
        for (const [hero, count] of Object.entries(data.heroes)) {
            html += `<div class="hero-card">
                <div class="hero-name">${hero}</div>
                <div class="hero-count">${count} ghosts</div>
            </div>`;
        }
        html += '</div></div>';

        panel.innerHTML = html;
    } catch (e) {
        panel.innerHTML = `<div class="error">Error: ${e.message}</div>`;
    }
}

function statCard(label, value) {
    return `<div class="stat-card">
        <div class="stat-value">${value}</div>
        <div class="stat-label">${label}</div>
    </div>`;
}

// ── Analysis Tab ──

async function loadAnalysis() {
    const panel = document.getElementById('tab-analysis');
    panel.innerHTML = '<div class="loading">Analyzing ghost data...</div>';

    try {
        const res = await fetch(`${API_BASE}/analysis`);
        const data = await res.json();

        if (!data.success) throw new Error(data.error);
        if (data.empty) {
            panel.innerHTML = '<div class="empty-state"><h3>No data to analyze</h3></div>';
            return;
        }

        let html = '';

        // Top Minions
        html += '<div class="section-card full-width">';
        html += '<h3>Most Common Minions</h3>';
        html += '<div class="minion-bars">';
        const maxMinion = data.minions.length > 0 ? data.minions[0].count : 1;
        for (const m of data.minions) {
            const pct = Math.round(m.count / maxMinion * 100);
            html += `<div class="minion-bar-row">
                <span class="bar-name">${m.name}</span>
                <div class="minion-bar-track"><div class="minion-bar-fill" style="width:${pct}%"></div></div>
                <span class="bar-count">${m.count} (${m.pct}%)</span>
            </div>`;
        }
        html += '</div></div>';

        // Combos
        if (data.combos.length > 0) {
            html += '<div class="section-card full-width">';
            html += '<h3>Best Minion Combos</h3>';
            html += '<table class="data-table"><thead><tr><th>Minion A</th><th>Minion B</th><th>Seen Together</th></tr></thead><tbody>';
            for (const c of data.combos) {
                html += `<tr><td>${c.minion_a}</td><td>${c.minion_b}</td><td>${c.count}x</td></tr>`;
            }
            html += '</tbody></table></div>';
        }

        // Keywords + Tribes side by side
        html += '<div class="section-row">';
        html += '<div class="section-card">';
        html += '<h3>Keywords</h3>';
        html += '<table class="data-table"><thead><tr><th>Keyword</th><th>Count</th></tr></thead><tbody>';
        for (const kw of data.keywords) {
            html += `<tr><td>${kw.name}</td><td>${kw.count}</td></tr>`;
        }
        html += '</tbody></table></div>';

        html += '<div class="section-card">';
        html += '<h3>Tribes</h3>';
        html += '<table class="data-table"><thead><tr><th>Tribe</th><th>Count</th></tr></thead><tbody>';
        for (const t of data.tribes) {
            html += `<tr><td>${t.name}</td><td>${t.count}</td></tr>`;
        }
        html += '</tbody></table></div>';
        html += '</div>';

        // Band Sizes
        html += '<div class="section-card full-width">';
        html += '<h3>Band Sizes</h3>';
        html += '<div class="size-chips">';
        for (const s of data.band_sizes) {
            html += `<div class="size-chip"><span class="size-num">${s.size}</span> minions <span class="size-count">${s.count}x</span></div>`;
        }
        html += '</div></div>';

        // Milestone Progression
        html += '<div class="section-card full-width">';
        html += '<h3>Milestone Progression</h3>';
        html += '<div class="milestone-grid">';
        for (const ms of data.milestone_progression) {
            html += `<div class="milestone-col">
                <div class="ms-header">${ms.milestone}s <span class="muted">(${ms.ghost_count})</span></div>`;
            for (const m of ms.top_minions) {
                html += `<div class="ms-minion">${m.name} <span class="muted">${m.pct}%</span></div>`;
            }
            html += '</div>';
        }
        html += '</div></div>';

        // Strongest Ghosts - with proper minion cards
        html += '<div class="section-card full-width">';
        html += '<h3>Strongest Ghosts (Top 10)</h3>';
        for (const g of data.strongest) {
            html += renderGhostCard(g);
        }
        html += '</div>';

        // Hero Comparison
        html += '<div class="section-card full-width">';
        html += '<h3>Hero Comparison</h3>';
        html += '<table class="data-table"><thead><tr><th>Hero</th><th>Ghosts</th><th>Avg Power</th><th>Max</th><th>Min</th></tr></thead><tbody>';
        for (const h of data.hero_comparison) {
            html += `<tr><td>${h.hero}</td><td>${h.count}</td><td>${h.avg_power}</td><td>${h.max_power}</td><td>${h.min_power}</td></tr>`;
        }
        html += '</tbody></table></div>';

        // Battle Results
        if (data.battle_results.length > 0) {
            html += '<div class="section-card full-width">';
            html += '<h3>Battle Win Rate by Milestone</h3>';
            html += '<div class="battle-chart">';
            for (const br of data.battle_results) {
                html += `<div class="battle-ms-row">
                    <span class="battle-ms-label">${br.milestone}s</span>
                    <div class="battle-ms-bar">
                        <div class="battle-ms-fill" style="width:${br.win_rate}%"></div>
                    </div>
                    <span class="battle-ms-stat">${br.player_wins}/${br.total} (${br.win_rate}%)</span>
                </div>`;
            }
            html += '</div></div>';
        }

        panel.innerHTML = html;
    } catch (e) {
        panel.innerHTML = `<div class="error">Error: ${e.message}</div>`;
    }
}

// ── Journeys Tab ──

async function loadJourneys() {
    const panel = document.getElementById('tab-journeys');
    panel.innerHTML = '<div class="loading">Analyzing game journeys...</div>';

    try {
        const res = await fetch(`${API_BASE}/journeys`);
        const data = await res.json();

        if (!data.success) throw new Error(data.error);
        if (data.empty) {
            panel.innerHTML = '<div class="empty-state"><h3>No journey data yet</h3><p>Populate ghosts first, then journeys will be analyzed from action logs.</p></div>';
            return;
        }

        let html = '';

        // Hero Summary Cards
        html += '<div class="section-card full-width"><h3>Hero Performance Summary</h3>';
        for (const hs of data.hero_summary) {
            const winPct = hs.win_rate;
            const lossPct = 100 - winPct;
            html += `<div class="hero-summary-card">
                <div class="hero-summary-header">
                    <span class="hero-summary-name">${hs.hero}</span>
                    <span class="hero-summary-record">${hs.victories}W / ${hs.deaths}L (${hs.games} games)</span>
                    <span class="hero-summary-record">${winPct}% win rate</span>
                </div>
                <div class="hero-bar">
                    <div class="bar-fill player-fill" style="width:${winPct}%">${hs.victories}W</div>
                    <div class="bar-fill ghost-fill" style="width:${lossPct}%">${hs.deaths}L</div>
                </div>
                <div class="journey-stats">
                    <div class="journey-stat"><div class="journey-stat-label">Avg Ghost W/L</div><div class="journey-stat-value">${hs.avg_ghost_wins} / ${hs.avg_ghost_losses}</div></div>
                    <div class="journey-stat"><div class="journey-stat-label">Avg Ghost Dmg</div><div class="journey-stat-value">${hs.avg_ghost_damage}</div></div>
                    <div class="journey-stat"><div class="journey-stat-label">Avg Combat Dmg</div><div class="journey-stat-value">${hs.avg_combat_damage}</div></div>
                    <div class="journey-stat"><div class="journey-stat-label">Avg Win Streak</div><div class="journey-stat-value">${hs.avg_win_streak}</div></div>
                    <div class="journey-stat"><div class="journey-stat-label">Avg Loss Streak</div><div class="journey-stat-value">${hs.avg_loss_streak}</div></div>
                    <div class="journey-stat"><div class="journey-stat-label">Max Milestone</div><div class="journey-stat-value">${hs.max_milestone}s</div></div>
                </div>
            </div>`;
        }
        html += '</div>';

        // Event & Zone Statistics (aggregate)
        html += '<div class="section-row">';

        // Event frequency
        if (data.event_stats && data.event_stats.length > 0) {
            html += '<div class="section-card"><h3>Event Frequency (All Games)</h3>';
            html += '<div class="minion-bars">';
            const maxEvent = data.event_stats[0].count;
            for (const e of data.event_stats) {
                const pct = Math.round(e.count / maxEvent * 100);
                const label = e.event.replace(/_/g, ' ');
                html += `<div class="minion-bar-row">
                    <span class="bar-name">${label}</span>
                    <div class="minion-bar-track"><div class="minion-bar-fill" style="width:${pct}%"></div></div>
                    <span class="bar-count">${e.count}</span>
                </div>`;
            }
            html += '</div></div>';
        }

        // Combat type breakdown
        if (data.combat_type_stats && data.combat_type_stats.length > 0) {
            html += '<div class="section-card"><h3>Combat Types (All Games)</h3>';
            html += '<table class="data-table"><thead><tr><th>Type</th><th>Count</th></tr></thead><tbody>';
            for (const ct of data.combat_type_stats) {
                const label = ct.type.replace(/_/g, ' ');
                html += `<tr><td>${label}</td><td>${ct.count}</td></tr>`;
            }
            html += '</tbody></table>';
            if (data.zone_stats && data.zone_stats.length > 0) {
                html += '<h3 style="margin-top:20px">Zones Visited</h3>';
                html += '<table class="data-table"><thead><tr><th>Zone</th><th>Visits</th></tr></thead><tbody>';
                for (const z of data.zone_stats) {
                    const label = z.zone.replace(/_/g, ' ');
                    html += `<tr><td style="text-transform:capitalize">${label}</td><td>${z.count}</td></tr>`;
                }
                html += '</tbody></table>';
            }
            html += '</div>';
        }
        html += '</div>';

        // Individual Game Journeys
        html += '<div class="section-card full-width"><h3>All Game Journeys (' + data.total_games + ' games)</h3>';

        for (const j of data.journeys) {
            html += `<div class="journey-card ${j.result}">
                <div class="journey-header">
                    <span class="journey-result ${j.result}">${j.result.toUpperCase()}</span>
                    <span class="hero-badge">${j.hero}</span>
                    <span class="ghost-ms">Milestone ${j.milestone}s</span>
                    <span style="color:rgba(255,255,255,0.5)">Ring ${j.max_ring}</span>
                    <span style="color:rgba(255,255,255,0.4)">Power ${j.band_power}</span>
                </div>
                <div class="journey-stats">
                    <div class="journey-stat"><div class="journey-stat-label">Ghost Record</div><div class="journey-stat-value">${j.ghost_wins}W / ${j.ghost_losses}L</div></div>
                    <div class="journey-stat"><div class="journey-stat-label">Combat Record</div><div class="journey-stat-value">${j.combat_wins}W / ${j.combat_losses}L</div></div>
                    <div class="journey-stat"><div class="journey-stat-label">Ghost Damage</div><div class="journey-stat-value">${j.ghost_damage_taken}</div></div>
                    <div class="journey-stat"><div class="journey-stat-label">Combat Damage</div><div class="journey-stat-value">${j.combat_damage_taken}</div></div>
                    <div class="journey-stat"><div class="journey-stat-label">Total Damage</div><div class="journey-stat-value">${j.total_damage_taken}</div></div>
                    <div class="journey-stat"><div class="journey-stat-label">Final HP</div><div class="journey-stat-value">${j.final_health}</div></div>
                </div>`;

            // Combat breakdown by type
            if (j.combat_breakdown && j.combat_breakdown.length > 0) {
                html += '<div class="combat-breakdown">';
                for (const cb of j.combat_breakdown) {
                    const label = cb.type.replace(/_/g, ' ');
                    const winCls = cb.win_rate >= 50 ? 'action-win' : 'action-loss';
                    html += `<span class="combat-type-chip" title="${cb.wins}W/${cb.losses}L, ${cb.total_damage} dmg taken">
                        <span class="combat-type-name">${label}</span>
                        <span class="${winCls}">${cb.wins}W/${cb.losses}L</span>
                        <span class="combat-type-dmg">${cb.total_damage} dmg</span>
                    </span>`;
                }
                html += '</div>';
            }

            // Ghost battle sequence with opponent details
            if (j.ghost_sequence.length > 0) {
                html += '<div class="ghost-battles-detail">';
                html += '<div class="ghost-battles-label">Ghost Battles:</div>';
                html += '<div class="ghost-battle-list">';
                for (let i = 0; i < j.ghost_sequence.length; i++) {
                    const gs = j.ghost_sequence[i];
                    const cls = gs.won ? 'win' : 'loss';
                    const resultText = gs.won ? 'WIN' : 'LOSS';
                    const oppHero = gs.ghost_hero || '?';
                    const oppPower = gs.ghost_power || gs.enemy_power || '?';
                    const oppSource = gs.ghost_source || '?';
                    const oppBand = (gs.ghost_band_names || []).join(', ');

                    html += `<div class="ghost-battle-entry ${cls}">
                        <span class="ghost-battle-num">#${i+1}</span>
                        <span class="ghost-battle-result ${cls}">${resultText}</span>
                        <span class="ghost-battle-power">${gs.player_power} vs ${gs.enemy_power}</span>
                        <span class="ghost-battle-opp" title="Band: ${oppBand}">vs ${oppHero} (${oppSource}, pow ${oppPower})</span>
                        ${gs.damage > 0 ? `<span class="ghost-battle-dmg">-${gs.damage} HP</span>` : ''}
                    </div>`;
                }
                html += '</div></div>';
            }

            // Killing ghost info for deaths
            if (j.result === 'death' && j.killing_ghost) {
                const kg = j.killing_ghost;
                html += `<div class="killing-ghost-info">
                    Died to: <strong>${kg.ghost_hero || '?'}</strong> ghost
                    (power ${kg.enemy_power}, ${kg.ghost_source || '?'} source)
                    at step ${kg.step} | took ${kg.damage} damage
                </div>`;
            }

            // Final band
            html += '<div style="margin-top:8px">';
            html += renderBandGrid(j.final_band);
            html += '</div>';

            html += '</div>'; // close journey-card
        }

        html += '</div>';
        panel.innerHTML = html;
    } catch (e) {
        panel.innerHTML = `<div class="error">Error: ${e.message}</div>`;
    }
}

// ── Ghosts List Tab ──

async function loadGhostList() {
    const panel = document.getElementById('tab-ghosts');

    let filterHtml = '<div class="filter-bar">';
    filterHtml += '<select id="filter-source" onchange="applyFilters()"><option value="">All Sources</option><option value="player">Player</option><option value="headless">Headless</option><option value="ai">AI</option></select>';
    filterHtml += '<select id="filter-hero" onchange="applyFilters()"><option value="">All Heroes</option><option value="none">No Hero</option><option value="silas">Silas</option><option value="puck">Puck</option><option value="olimpia">Olimpia</option></select>';
    filterHtml += '<select id="filter-sort" onchange="applyFilters()"><option value="power">Sort: Power</option><option value="milestone">Sort: Milestone</option><option value="recent">Sort: Recent</option></select>';
    filterHtml += '</div>';
    filterHtml += '<div id="ghost-list-content"><div class="loading">Loading ghosts...</div></div>';
    filterHtml += '<div id="ghost-pagination"></div>';

    panel.innerHTML = filterHtml;
    fetchGhostList();
}

function applyFilters() {
    ghostListFilters = {
        source: document.getElementById('filter-source').value,
        hero: document.getElementById('filter-hero').value,
        sort: document.getElementById('filter-sort').value
    };
    ghostListPage = 1;
    fetchGhostList();
}

async function fetchGhostList() {
    const content = document.getElementById('ghost-list-content');
    if (!content) return;
    content.innerHTML = '<div class="loading">Loading...</div>';

    try {
        let url = `${API_BASE}/ghosts?page=${ghostListPage}&per_page=25`;
        if (ghostListFilters.source) url += `&source=${ghostListFilters.source}`;
        if (ghostListFilters.hero) url += `&hero=${ghostListFilters.hero}`;
        if (ghostListFilters.sort) url += `&sort=${ghostListFilters.sort}`;

        const res = await fetch(url);
        const data = await res.json();

        if (!data.success) throw new Error(data.error);

        if (data.ghosts.length === 0) {
            content.innerHTML = '<div class="empty-state"><h3>No ghosts match filters</h3></div>';
            document.getElementById('ghost-pagination').innerHTML = '';
            return;
        }

        let html = '';
        for (const g of data.ghosts) {
            html += renderGhostCard(g);
        }
        content.innerHTML = html;

        // Pagination
        let pagHtml = `<div class="pagination">`;
        pagHtml += `<span class="page-info">${data.total} ghosts | Page ${data.page}/${data.pages}</span>`;
        if (data.page > 1) pagHtml += `<button onclick="ghostListPage=${data.page-1};fetchGhostList()">Prev</button>`;
        if (data.page < data.pages) pagHtml += `<button onclick="ghostListPage=${data.page+1};fetchGhostList()">Next</button>`;
        pagHtml += '</div>';
        document.getElementById('ghost-pagination').innerHTML = pagHtml;
    } catch (e) {
        content.innerHTML = `<div class="error">Error: ${e.message}</div>`;
    }
}

// ── Populate Tab ──

let populatePollTimer = null;

function setupPopulate() {
    const panel = document.getElementById('tab-populate');
    panel.innerHTML = `
        <div class="populate-form">
            <h3>Populate Ghost Database</h3>
            <p class="muted">Run headless AI games (Silas, Puck, Olimpia) to generate ghost opponents.</p>

            <div class="form-row">
                <label>Number of Games (split evenly across 3 heroes)</label>
                <input type="number" id="pop-games" value="21" min="3" max="200" step="3">
            </div>
            <div class="form-row">
                <label><input type="checkbox" id="pop-clear"> Clear Existing Ghosts First</label>
            </div>
            <div class="form-row">
                <label>Starting Seed</label>
                <input type="number" id="pop-seed" value="10000">
            </div>
            <div class="form-row">
                <label>AI Type</label>
                <select id="pop-ai">
                    <option value="full_simulation" selected>Full Simulation (tries every option through real engine)</option>
                    <option value="simulating">Simulating (evaluates hypothetical band states)</option>
                    <option value="smart">Smart (basic heuristics)</option>
                </select>
            </div>

            <div class="form-actions">
                <button class="btn-primary" id="btn-run-populate" onclick="runPopulate()">Run Games</button>
                <button class="btn-danger" id="btn-cancel-populate" onclick="cancelPopulate()" style="display:none">Cancel</button>
                <button class="btn-danger" onclick="clearGhosts()">Clear All Ghosts</button>
            </div>

            <div id="populate-progress"></div>
            <div id="populate-result"></div>
        </div>`;

    // Check if a job is already running (e.g. page was refreshed)
    checkExistingJob();
}

async function checkExistingJob() {
    try {
        const res = await fetch(`${API_BASE}/populate/status`);
        const data = await res.json();
        if (data.running) {
            startPolling();
        } else if (data.final_summary && !data.running) {
            renderFinalSummary(data);
        }
    } catch (e) {
        // Ignore - no job running
    }
}

async function runPopulate() {
    const resultDiv = document.getElementById('populate-result');
    const progressDiv = document.getElementById('populate-progress');
    resultDiv.innerHTML = '';
    progressDiv.innerHTML = '<div class="loading">Starting games...</div>';

    try {
        const res = await fetch(`${API_BASE}/populate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                games: parseInt(document.getElementById('pop-games').value),
                clear: document.getElementById('pop-clear').checked,
                seed: parseInt(document.getElementById('pop-seed').value),
                ai: document.getElementById('pop-ai').value
            })
        });

        const data = await res.json();
        if (!data.success) {
            if (data.running) {
                progressDiv.innerHTML = '<div class="result-box error"><p>A job is already running. Wait for it to finish or cancel it.</p></div>';
                startPolling();
            } else {
                throw new Error(data.error);
            }
            return;
        }

        startPolling();
    } catch (e) {
        progressDiv.innerHTML = `<div class="result-box error"><h4>Error</h4><p>${e.message}</p></div>`;
    }
}

function startPolling() {
    if (populatePollTimer) clearInterval(populatePollTimer);

    document.getElementById('btn-run-populate').style.display = 'none';
    document.getElementById('btn-cancel-populate').style.display = '';

    populatePollTimer = setInterval(pollProgress, 1500);
    pollProgress(); // immediate first poll
}

function stopPolling() {
    if (populatePollTimer) {
        clearInterval(populatePollTimer);
        populatePollTimer = null;
    }
    const runBtn = document.getElementById('btn-run-populate');
    const cancelBtn = document.getElementById('btn-cancel-populate');
    if (runBtn) runBtn.style.display = '';
    if (cancelBtn) cancelBtn.style.display = 'none';
}

async function pollProgress() {
    try {
        const res = await fetch(`${API_BASE}/populate/status`);
        const data = await res.json();

        renderProgress(data);

        if (!data.running) {
            stopPolling();
            if (data.final_summary) {
                renderFinalSummary(data);
            }
        }
    } catch (e) {
        // Network error - keep polling
    }
}

function renderProgress(data) {
    const progressDiv = document.getElementById('populate-progress');
    if (!progressDiv) return;

    const completed = data.completed_games || 0;
    const total = data.total_games || 1;
    const pct = Math.round(completed / total * 100);
    const elapsed = data.elapsed || 0;

    let html = '<div class="populate-progress-box">';

    // Progress bar
    html += `<div class="progress-header">
        <span>${data.running ? 'Running' : 'Finished'}: ${completed} / ${total} games (${pct}%)</span>
        <span class="muted">${elapsed}s elapsed</span>
    </div>`;
    html += `<div class="progress-bar-track">
        <div class="progress-bar-fill" style="width:${pct}%"></div>
    </div>`;

    if (data.current_game && data.running) {
        html += `<div class="progress-current">Currently running: <strong>${data.current_game}</strong></div>`;
    }
    if (data.cancel_requested) {
        html += `<div class="progress-cancel-notice">Cancel requested - finishing current game...</div>`;
    }

    // Per-game results table
    if (data.results && data.results.length > 0) {
        html += '<div class="progress-results">';
        html += '<table class="data-table"><thead><tr><th>#</th><th>Hero</th><th>Result</th><th>Ghost W</th><th>Events</th><th>HP</th><th>Time</th><th>Info</th></tr></thead><tbody>';
        for (const r of data.results) {
            const cls = r.result === 'victory' ? 'action-win' :
                        r.result === 'error' ? 'action-loss' :
                        r.result === 'timeout' || r.result === 'stuck' ? 'action-loss' : '';
            const hasDiag = r.diagnostic_trail ? true : false;
            const errText = r.error ? `<span class="action-loss" title="${r.error}">${r.error.substring(0, 40)}${r.error.length > 40 ? '...' : ''}</span>` : '';
            const logBtn = r.log_file ? `<button class="btn-trail" onclick="toggleFullLog(${r.game}, '${r.log_file}')">Full Log</button>` : '';
            const diagBtn = hasDiag ? `<button class="btn-trail" onclick="toggleTrail(${r.game})">Diag</button>` : '';
            html += `<tr>
                <td>${r.game}</td>
                <td>${r.hero || '?'}</td>
                <td><span class="${cls}">${r.result}</span></td>
                <td>${r.ghost_wins !== undefined ? r.ghost_wins : '-'}</td>
                <td>${r.events !== undefined ? r.events : '-'}</td>
                <td>${r.health !== undefined ? r.health : '-'}</td>
                <td>${r.elapsed !== undefined ? r.elapsed + 's' : '-'}</td>
                <td>${errText} ${logBtn} ${diagBtn}</td>
            </tr>`;
            // Full log row (loaded on demand)
            html += `<tr id="fulllog-${r.game}" class="trail-row" style="display:none"><td colspan="8"><pre class="full-log-content" id="fulllog-content-${r.game}">Loading...</pre></td></tr>`;
            if (hasDiag) {
                html += `<tr id="trail-${r.game}" class="trail-row" style="display:none"><td colspan="8">${renderDiagnosticTrail(r.diagnostic_trail)}</td></tr>`;
            }
        }
        html += '</tbody></table></div>';
    }

    // Errors
    if (data.errors && data.errors.length > 0) {
        html += '<div class="progress-errors"><h4>Errors</h4>';
        for (const err of data.errors) {
            html += `<div class="error-line">${err}</div>`;
        }
        html += '</div>';
    }

    html += '</div>';
    progressDiv.innerHTML = html;
}

function renderFinalSummary(data) {
    const resultDiv = document.getElementById('populate-result');
    if (!resultDiv) return;
    const s = data.final_summary;
    if (!s) return;

    const statusClass = s.fatal_error ? 'error' : 'success';
    const statusLabel = s.cancelled ? 'Cancelled' : s.fatal_error ? 'Failed' : 'Complete';

    let html = `<div class="result-box ${statusClass}">
        <h4>Population ${statusLabel}</h4>
        <div class="result-stats">
            <div>Games Run: <strong>${s.games_run}</strong></div>
            <div>Victories: <strong>${s.victories || 0}</strong></div>
            <div>Deaths: <strong>${s.deaths || 0}</strong></div>`;
    if (s.timeouts > 0) html += `<div>Timeouts/Stuck: <strong class="action-loss">${s.timeouts}</strong></div>`;
    if (s.errors > 0) html += `<div>Errors: <strong class="action-loss">${s.errors}</strong></div>`;
    html += `<div>New Ghosts: <strong>${s.new_ghosts || 0}</strong></div>
            <div>Total Ghosts: <strong>${s.total_ghosts || 0}</strong></div>
            <div>Time: <strong>${s.elapsed}s</strong>${s.rate ? ` (${s.rate} games/sec)` : ''}</div>`;
    if (s.fatal_error) html += `<div class="action-loss">Fatal: ${s.fatal_error}</div>`;
    if (s.cancelled) html += `<div class="muted">Job was cancelled by user.</div>`;
    if (s.log_dir) html += `<div class="muted" style="margin-top:8px; font-size:0.8rem">Logs: ${s.log_dir}</div>`;
    html += `</div></div>`;

    resultDiv.innerHTML = html;
}

function toggleTrail(gameNum) {
    const row = document.getElementById(`trail-${gameNum}`);
    if (row) {
        row.style.display = row.style.display === 'none' ? '' : 'none';
    }
}

async function toggleFullLog(gameNum, filename) {
    const row = document.getElementById(`fulllog-${gameNum}`);
    if (!row) return;

    if (row.style.display !== 'none') {
        row.style.display = 'none';
        return;
    }

    row.style.display = '';
    const pre = document.getElementById(`fulllog-content-${gameNum}`);
    if (pre.dataset.loaded) return; // Already fetched

    try {
        const res = await fetch(`${API_BASE}/populate/log/${filename}`);
        const data = await res.json();
        if (data.success) {
            pre.textContent = data.content;
            pre.dataset.loaded = '1';
        } else {
            pre.textContent = `Error: ${data.error}`;
        }
    } catch (e) {
        pre.textContent = `Failed to load: ${e.message}`;
    }
}

function renderDiagnosticTrail(trail) {
    if (!trail) return '';
    let html = '<div class="diagnostic-trail">';

    // Game state at time of failure
    if (trail.state) {
        const s = trail.state;
        html += '<div class="trail-section"><strong>State at failure:</strong> ';
        html += `Events: ${s.events_count} | Ring: ${s.ring} | HP: ${s.health} | Gold: ${s.gold} | Band(${s.band_size}): ${(s.band || []).join(', ')}`;
        if (s.in_sub_ring) html += ' | <em>In sub-ring</em>';
        html += `</div>`;
    }

    // What was pending (the thing it was stuck on)
    if (trail.pending) {
        const p = trail.pending;
        html += '<div class="trail-section trail-pending"><strong>Stuck on:</strong> ';
        html += `<span class="action-event">${p.event_type}</span>`;
        if (p.combat_type) html += ` (${p.combat_type})`;
        html += ` | ${p.num_options} options [${(p.option_ids || []).join(', ')}]`;
        html += ` | types: [${(p.option_types || []).join(', ')}]`;
        if (p.disabled_count > 0) html += ` | <span class="action-loss">${p.disabled_count} disabled</span>`;
        if (p.combat_complete) html += ' | combat_complete=true';
        if (p.repeating) html += ' | <em>repeating</em>';
        html += ` | leaveable: ${p.leaveable} | sel: ${p.min_selections}-${p.max_selections}`;
        html += `</div>`;
    } else if (trail.pending === null) {
        html += '<div class="trail-section"><strong>Stuck on:</strong> <em>No pending selection</em></div>';
    }

    html += `<div class="trail-section muted">Iterations: ${trail.iterations} | Stuck for: ${trail.stuck_iterations} | Total actions: ${trail.total_actions}</div>`;

    // Last actions (the action log trail leading up to the failure)
    if (trail.last_actions && trail.last_actions.length > 0) {
        html += '<div class="trail-section"><strong>Last actions:</strong></div>';
        html += '<div class="trail-actions">';
        for (const a of trail.last_actions) {
            let detail = '';
            if (a.action === 'combat') {
                const w = a.winner === 'player' ? 'action-win' : 'action-loss';
                detail = `<span class="${w}">${a.combat_type}: ${a.winner}</span> (${a.player_power} vs ${a.enemy_power}) dmg:${a.damage_taken || 0}`;
            } else if (a.action === 'selection') {
                const added = (a.minions_added || []).join(', ');
                const removed = (a.minions_removed || []).join(', ');
                detail = `<span class="action-event">${a.event_type}</span> [${(a.selected || []).join(', ')}]`;
                if (added) detail += ` <span class="action-add">+${added}</span>`;
                if (removed) detail += ` <span class="action-remove">-${removed}</span>`;
            } else if (a.action === 'ring_upgrade') {
                detail = `Ring ${a.old_ring} -> ${a.new_ring} (cost ${a.cost})`;
            } else if (a.action === 'zone_travel') {
                detail = `Zone: ${a.zone}`;
            } else {
                detail = a.action;
            }
            html += `<div class="trail-action-row">
                <span class="trail-step">E${a.step || 0}</span>
                <span class="trail-detail">${detail}</span>
                <span class="trail-band">Band:${a.band_size} Pow:${a.band_power} HP:${a.health}</span>
            </div>`;
        }
        html += '</div>';
    }

    // Last events (ring movement log)
    if (trail.last_events && trail.last_events.length > 0) {
        html += '<div class="trail-section"><strong>Last ring events:</strong></div>';
        html += '<div class="trail-events">';
        for (const e of trail.last_events.slice(-10)) {
            html += `<span class="trail-event-chip">${e.event} (R${e.ring} P${e.position} E${e.events_count})</span> `;
        }
        html += '</div>';
    }

    html += '</div>';
    return html;
}

async function cancelPopulate() {
    try {
        const res = await fetch(`${API_BASE}/populate/cancel`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            const btn = document.getElementById('btn-cancel-populate');
            if (btn) {
                btn.textContent = 'Cancelling...';
                btn.disabled = true;
            }
        }
    } catch (e) {
        // Ignore
    }
}

async function clearGhosts() {
    if (!confirm('Clear ALL ghost snapshots and battle records?')) return;
    const resultDiv = document.getElementById('populate-result');
    try {
        const res = await fetch(`${API_BASE}/clear`, { method: 'POST' });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        resultDiv.innerHTML = `<div class="result-box success"><p>Cleared ${data.ghosts_deleted} ghosts and ${data.battles_deleted} battles.</p></div>`;
    } catch (e) {
        resultDiv.innerHTML = `<div class="result-box error"><p>${e.message}</p></div>`;
    }
}

// ── Ghost Detail Modal ──

async function showGhostDetail(ghostId) {
    const overlay = document.getElementById('detail-overlay');
    const content = document.getElementById('detail-content');
    overlay.classList.add('active');
    content.innerHTML = '<div class="loading">Loading ghost detail...</div>';

    try {
        const res = await fetch(`${API_BASE}/ghost/${ghostId}`);
        const data = await res.json();
        if (!data.success) throw new Error(data.error);

        const g = data.ghost;
        let html = `<div class="detail-header">
            <h2>Ghost #${g.id} - Power ${g.power}</h2>
            <button class="detail-close" onclick="closeDetail()">&times;</button>
        </div>`;

        html += `<div class="detail-meta">
            <span class="source-tag tag-${g.source}">${g.source}</span>
            <span>Milestone ${g.milestone}s</span>
            <span>Ring ${g.ring}</span>
            <span>HP ${g.health}</span>
            ${g.hero !== 'none' ? `<span class="hero-badge">${g.hero}</span>` : ''}
            <span>W${g.ghost_wins}/L${g.ghost_losses}</span>
        </div>`;

        // Band with full minion cards
        html += '<h3>Band</h3>';
        html += renderBandGrid(g.band);

        // Actions timeline
        if (g.actions && g.actions.length > 0) {
            html += '<h3>Action Timeline</h3>';
            html += '<div class="actions-timeline">';
            for (const action of g.actions) {
                html += renderAction(action);
            }
            html += '</div>';
        }

        content.innerHTML = html;
    } catch (e) {
        content.innerHTML = `<div class="error">Error: ${e.message}</div>`;
    }
}

function closeDetail() {
    document.getElementById('detail-overlay').classList.remove('active');
}

function renderAction(action) {
    const icons = {
        'selection': '&#9881;',
        'combat': '&#9876;',
        'ring_upgrade': '&#9650;',
        'zone_travel': '&#9992;',
    };
    const icon = icons[action.action] || '&#8226;';

    let detail = '';
    if (action.action === 'combat') {
        const winClass = action.winner === 'player' ? 'action-win' : 'action-loss';
        detail = `<span class="${winClass}">${action.combat_type}: ${action.winner}</span> (${action.player_power} vs ${action.enemy_power})`;
    } else if (action.action === 'selection') {
        const added = (action.minions_added || []).join(', ');
        const removed = (action.minions_removed || []).join(', ');
        detail = `<span class="action-event">${action.event_type}</span>`;
        if (added) detail += ` <span class="action-add">+${added}</span>`;
        if (removed) detail += ` <span class="action-remove">-${removed}</span>`;
    } else if (action.action === 'ring_upgrade') {
        detail = `Ring ${action.old_ring} &rarr; ${action.new_ring} (cost ${action.cost})`;
    } else if (action.action === 'zone_travel') {
        detail = `Traveled to ${action.zone}`;
    }

    return `<div class="action-row">
        <span class="action-icon">${icon}</span>
        <span class="action-step">Step ${action.step}</span>
        <span class="action-detail">${detail}</span>
        <span class="action-band" title="${(action.band_names || []).join(', ')}">Band: ${action.band_size} (pow ${action.band_power})</span>
        <span class="action-hp">HP ${action.health}</span>
    </div>`;
}

// ── Shared Renderers ──

function renderGhostCard(g) {
    let html = `<div class="ghost-card" onclick="showGhostDetail(${g.id})" style="cursor:pointer">
        <div class="ghost-header">
            <span class="ghost-power">Power ${g.power}</span>
            <span class="ghost-ms">${g.milestone}s</span>
            <span class="source-tag tag-${g.source}">${g.source}</span>
            ${g.hero !== 'none' ? `<span class="hero-badge">${g.hero}</span>` : ''}
            ${g.player_name ? `<span class="ghost-player">${g.player_name}</span>` : ''}
            ${g.ring ? `<span class="ghost-ring">Ring ${g.ring}</span>` : ''}
            ${g.has_actions ? '<span class="has-actions-badge" title="Has action log">LOG</span>' : ''}
        </div>
        <div class="ghost-band-display">
            ${renderBandGrid(g.band)}
        </div>
    </div>`;
    return html;
}
