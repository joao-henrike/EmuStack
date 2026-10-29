'use strict';

const state = {
  health: null,
  installReport: null,
  installReportError: '',
  emulators: [],
  environments: [],
  consoleSystems: [],
  consoleSystemsError: '',
  games: [],
  sessions: [],
  sources: { categories: [], sources: [] },
  docs: [],
  currentView: 'overview',
  selectedSourceCategory: 'all',
  selectedSourcePlatform: 'all',
  selectedDoc: 'readme',
  launchTarget: null,
  launchEnvironmentId: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = (value = '') => String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: 'no-store',
    ...options,
    headers: { ...(options.headers || {}), ...(options.method === 'POST' ? {'Content-Type':'application/json','X-EmuStack-Request':'1'} : {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Erro HTTP ${response.status}`);
  return data;
}

function toast(message, type = '') {
  const node = document.createElement('div');
  node.className = `toast ${type}`;
  node.textContent = message;
  $('#toast-region').append(node);
  window.setTimeout(() => node.remove(), 4800);
}

function platformFamily(platform = '') {
  if (/playstation/i.test(platform)) return 'ps';
  if (/xbox/i.test(platform)) return 'xb';
  if (/nintendo|game boy|super nintendo|nes/i.test(platform)) return 'nin';
  return 'generic';
}
function platformGlyph(platform = '') {
  const family = platformFamily(platform);
  return family === 'ps' ? 'PS' : family === 'xb' ? 'XB' : family === 'nin' ? 'N' : 'PC';
}
function statusClass(item) {
  const st = (item.runtime_status || '').toUpperCase();
  if (st === 'AVAILABLE' || st === 'AVAILABLE VIA WINE') return item.status === 'mature' ? 'mature' : 'ready';
  if (st.includes('NO LINUX') || st.includes('NO STANDALONE') || st.includes('UNVERIFIED')) return 'blocked';
  if (item.status === 'experimental' || /experimental|research/i.test(item.runtime || '')) return 'experimental';
  return 'missing';
}
function statusLabel(item) {
  const st = (item.runtime_status || '').toUpperCase();
  if (st === 'AVAILABLE') return 'Launcher encontrado';
  if (st === 'AVAILABLE VIA WINE') return 'Disponível via Wine';
  if (st === 'NEEDS WINE') return 'Requer Wine';
  if (st === 'NEEDS BINARY') return 'Binário ausente';
  if (st === 'NO LINUX EMULATOR BIN') return 'Sem binário Linux';
  if (st === 'NO STANDALONE RUNNER') return 'Projeto de pesquisa';
  if (st === 'UNVERIFIED VARIANT') return 'Variante não verificada';
  return 'Não instalado';
}
function shortStatus(item) {
  if (item.runtime_status === 'AVAILABLE' || item.runtime_status === 'AVAILABLE VIA WINE') return 'Disponível';
  if (item.runtime_status === 'NO LINUX EMULATOR BIN' || item.runtime_status === 'NO STANDALONE RUNNER' || item.runtime_status === 'UNVERIFIED VARIANT') return 'Sem launcher genérico';
  return 'Verificar instalação';
}
function iconClass(ext = '') {
  const e = ext.toLowerCase().replace('.', '');
  if (['gba','gb','gbc','nes','sfc','smc','n64','z64','v64'].includes(e)) return e;
  return 'disc';
}
function formatDate(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.valueOf())) return '—';
  return new Intl.DateTimeFormat('pt-BR', {day:'2-digit',month:'short',year:'numeric'}).format(date);
}
function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB','MB','GB','TB'];
  let value = bytes / 1024, idx = 0;
  while (value >= 1024 && idx < units.length - 1) { value /= 1024; idx++; }
  return `${value.toFixed(1)} ${units[idx]}`;
}
function setView(view) {
  const ids = ['overview','environments','consoles','emulators','library','sources','docs'];
  if (!ids.includes(view)) view = 'overview';
  state.currentView = view;
  $$('.view').forEach(el => el.classList.toggle('active', el.id === `view-${view}`));
  $$('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  const labels = {overview:'Visão geral',environments:'Ambientes isolados',consoles:'Sistemas originais',emulators:'Emuladores',library:'Biblioteca',sources:'Fontes de jogos',docs:'Documentação'};
  $('#crumb-current').textContent = labels[view];
  $('#sidebar').classList.remove('open');
  if (view === 'environments') renderEnvironments();
  if (view === 'consoles') renderConsoleSystems();
  if (view === 'emulators') renderEmulators();
  if (view === 'library') renderLibrary();
  if (view === 'sources') renderSources();
  if (view === 'docs') renderDocs();
  window.scrollTo({top:0,behavior:'smooth'});
}

function emulatorCard(item, featured = false) {
  const family = platformFamily(item.platform);
  const status = statusClass(item);
  const canLaunch = item.launchable;
  const notes = item.notes || 'Confira a documentação oficial para requisitos e compatibilidade.';
  return `<article class="emulator-card ${featured ? 'featured-card' : ''}">
    <div class="emu-card-top"><div class="console-icon ${family}">${escapeHtml(platformGlyph(item.platform))}</div><div class="emu-card-heading"><h3>${escapeHtml(item.name)}</h3><div class="console-name">${escapeHtml(item.platform)}</div></div></div>
    <div><span class="status-badge ${status}">${escapeHtml(statusLabel(item))}</span></div>
    <p class="emu-note">${escapeHtml(notes)}</p>
    <div class="emu-card-bottom"><a class="source-link" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">Fonte oficial ↗</a><button class="launch-mini" data-launch="${escapeHtml(item.id)}" ${canLaunch ? '' : 'disabled'} title="${canLaunch ? 'Abrir emulador' : escapeHtml(item.launch_reason || statusLabel(item))}">${canLaunch ? 'Abrir →' : 'Indisponível'}</button></div>
  </article>`;
}

function renderOverview() {
  if (!state.health) return;
  $('#metric-emulators').textContent = state.health.emulator_count ?? state.emulators.length;
  $('#metric-ready').textContent = state.health.launchers_ready ?? '—';
  $('#metric-games').textContent = state.health.game_count ?? state.games.length;
  $('#metric-storage').textContent = `${state.health.game_bytes_label || '0 B'} catalogados`;
  $('#metric-runtime').textContent = 'Docker';
  $('#metric-report').textContent = state.health.install_report_present ? 'Relatório de instalação encontrado' : 'Relatório ainda não detectado';
  if ($('#nav-environment-count')) $('#nav-environment-count').textContent = state.environments.length || state.health.environment_count || '—';
  $('#nav-emulator-count').textContent = state.emulators.length;
  $('#nav-game-count').textContent = state.games.length;
  $('#side-health').textContent = `${state.health.launchers_ready} launchers encontrados`;
  const priority = ['rpcs3','pcsx2','dolphin'];
  let featured = priority.map(id => state.emulators.find(item => item.id === id)).filter(Boolean);
  if (featured.length < 3) featured = state.emulators.slice(0,3);
  $('#featured-grid').innerHTML = featured.map(item => emulatorCard(item, true)).join('');
  if (!state.games.length) {
    $('#overview-library').innerHTML = `<div class="empty-state">Nenhum arquivo compatível detectado. Adicione jogos autorizados a <code>data/environments/&lt;id&gt;/games/</code> no ambiente correto.</div>`;
  } else {
    $('#overview-library').innerHTML = state.games.slice(0,4).map(game => `<div class="mini-game-row"><div class="file-icon ${iconClass(game.extension)}">${escapeHtml(game.extension.replace('.','').slice(0,4) || 'FILE')}</div><div class="mini-game-main"><b>${escapeHtml(game.name)}</b><small>${escapeHtml(game.environment_id ? `${game.environment_id} / ` : '')}${escapeHtml(game.path)}</small></div><span class="file-size">${escapeHtml(game.size_label)}</span></div>`).join('');
  }
  const experimentCount = state.emulators.filter(i => ['NO LINUX EMULATOR BIN','NO STANDALONE RUNNER','UNVERIFIED VARIANT'].includes(i.runtime_status)).length;
  const lines = [
    ['Núcleo', `${state.environments.length || 20} ambientes isolados`, 'good'],
    ['Rede', 'Agentes sem comunicação entre si', 'good'],
    ['Catálogo', `${state.emulators.length} projetos registrados`, 'good'],
    ['Launchers', `${state.health.launchers_ready} detectados`, state.health.launchers_ready ? 'good' : 'warn'],
    ['Biblioteca', `${state.games.length} arquivos catalogados`, 'good'],
    ['Projetos sem runner genérico', `${experimentCount} entradas`, experimentCount ? 'warn' : 'good'],
    ['Exposição web', 'Somente loopback (127.0.0.1)', 'good'],
  ];
  $('#system-lines').innerHTML = lines.map(([label,value,tone]) => `<div class="system-line"><span>${escapeHtml(label)}</span><b class="${tone}">${escapeHtml(value)}</b></div>`).join('');
}

function installStatusLabel(status) {
  const labels = {
    installed: 'Instalado',
    failed: 'Falhou',
    'not-available': 'Indisponível',
    'skipped-by-lock': 'Ignorado pelo lock',
    'unsupported-no-runner': 'Sem runner suportado',
  };
  return labels[status] || status || 'Desconhecido';
}

function installStatusTone(status) {
  if (status === 'installed') return 'good';
  if (status === 'failed') return 'bad';
  if (status === 'skipped-by-lock' || status === 'unsupported-no-runner') return 'warn';
  return 'muted';
}

function renderInstallReport() {
  const host = $('#install-report-list');
  if (!host) return;
  if (state.installReportError) {
    host.innerHTML = `<div class="empty-state">Não foi possível ler o relatório: ${escapeHtml(state.installReportError)}</div>`;
    return;
  }
  const report = state.installReport;
  const itemsObject = report && report.items && typeof report.items === 'object' && !Array.isArray(report.items) ? report.items : {};
  const items = Object.entries(itemsObject).sort(([a], [b]) => a.localeCompare(b));
  if (!report || !items.length) {
    host.innerHTML = '<div class="empty-state">Relatório ainda não disponível. Faça o build da imagem para criar o relatório de instalação por perfil.</div>';
    return;
  }
  const installed = items.filter(([, item]) => item && item.status === 'installed').length;
  const failed = items.filter(([, item]) => item && item.status === 'failed').length;
  const pending = items.length - installed - failed;
  const summary = `<div class="install-report-summary"><span><b>${items.length}</b> perfis</span><span class="good"><b>${installed}</b> instalados</span><span class="bad"><b>${failed}</b> falhas</span><span class="muted"><b>${pending}</b> ignorados/indisponíveis</span></div>`;
  const rows = items.map(([id, rawItem]) => {
    const item = rawItem && typeof rawItem === 'object' ? rawItem : {};
    const evidence = item.evidence && typeof item.evidence === 'object' ? item.evidence : {};
    const execution = item.execution_test && typeof item.execution_test === 'object' ? item.execution_test : {status:'not-run',reason:'Teste não registrado no relatório legado.'};
    const runtime = item.runtime_test && typeof item.runtime_test === 'object' ? item.runtime_test : {status:'not-run',reason:'Teste não registrado no relatório legado.'};
    const version = item.version || evidence.version || '—';
    const artifact = item.asset || evidence.artifact || item.binary || evidence.binary_path || '—';
    const source = item.url || evidence.source_url || item.repo || evidence.source_repository || item.source || evidence.install_source || '—';
    const sha = item.sha256 || evidence.sha256_actual || '—';
    const expectedSha = evidence.sha256_expected || '—';
    return `<details class="install-report-row">
      <summary><span class="status-chip ${installStatusTone(item.status)}">${escapeHtml(installStatusLabel(item.status))}</span><b>${escapeHtml(id)}</b><span class="install-report-version">${escapeHtml(String(version))}</span><span class="install-report-test">Execução: ${escapeHtml(execution.status || 'not-run')}</span></summary>
      <div class="install-report-evidence">
        <dl>
          <dt>Versão</dt><dd>${escapeHtml(String(version))}</dd>
          <dt>Arquitetura do host</dt><dd>${escapeHtml(String(evidence.host_architecture || 'não registrada'))}</dd>
          <dt>Origem</dt><dd>${escapeHtml(String(source))}</dd>
          <dt>Ativo</dt><dd>${escapeHtml(String(artifact))}</dd>
          <dt>SHA-256 esperado</dt><dd><code>${escapeHtml(String(expectedSha))}</code></dd>
          <dt>SHA-256 calculado</dt><dd><code>${escapeHtml(String(sha))}</code></dd>
          <dt>Executável</dt><dd><code>${escapeHtml(String(item.binary || evidence.binary_path || '—'))}</code></dd>
          <dt>Teste de execução</dt><dd>${escapeHtml(installStatusLabel(execution.status))}: ${escapeHtml(execution.reason || 'sem detalhe')}</dd>
          <dt>Teste de runtime</dt><dd>${escapeHtml(installStatusLabel(runtime.status))}: ${escapeHtml(runtime.reason || 'sem detalhe')}</dd>
        </dl>
        ${item.reason ? `<p class="install-report-reason"><b>Motivo/erro:</b> ${escapeHtml(String(item.reason))}</p>` : ''}
        ${item.details ? `<p class="install-report-reason">${escapeHtml(String(item.details))}</p>` : ''}
        ${evidence.size_bytes != null ? `<p class="install-report-reason">Tamanho do ativo: ${escapeHtml(formatBytes(Number(evidence.size_bytes)))}</p>` : ''}
      </div>
    </details>`;
  }).join('');
  host.innerHTML = summary + rows;
}

function renderSessions() {
  const host = $('#process-list');
  if (!host) return;
  const sessions = state.sessions || [];
  if (!sessions.length) {
    host.innerHTML = '<div class="empty-state">Nenhuma sessão iniciada. Os processos e logs são mantidos pelo agente do ambiente correspondente.</div>';
    return;
  }
  host.innerHTML = sessions.map(session => {
    const running = session.status === 'running';
    const statusTone = running ? 'good' : session.status === 'failed' ? 'bad' : 'muted';
    const key = session.session_key || String(session.pid);
    return `<article class="session-row"><div class="session-main"><div class="session-mark ${running ? 'running' : ''}">${running ? '▶' : session.status === 'failed' ? '!' : '✓'}</div><div class="session-copy"><b>${escapeHtml(session.emulator_name || session.emulator)}</b><small>Ambiente ${escapeHtml(session.environment_id || 'local')} · PID ${escapeHtml(session.pid)} · ${escapeHtml(session.game || 'sem arquivo associado')} · ${escapeHtml(formatDate(session.started_at))}</small></div></div><div class="session-actions"><span class="session-status ${statusTone}">${escapeHtml(running ? 'Em execução' : session.status === 'failed' ? `Falhou (${session.exit_code ?? '?'})` : `${session.status === 'stopped' ? 'Encerrado pelo usuário' : `Finalizado (${session.exit_code ?? '?'})`}`)}</span><button class="row-action" data-process-log="${escapeHtml(key)}">Logs</button>${running ? `<button class="row-action danger-action" data-stop-process="${escapeHtml(key)}">Encerrar</button>` : ''}</div></article>`;
  }).join('');
}

function findSessionByKey(key) {
  return (state.sessions || []).find(s => (s.session_key || String(s.pid)) === String(key));
}

async function stopSession(sessionKey) {
  const session = findSessionByKey(sessionKey);
  if (!session) { toast('Sessão não encontrada; atualize a lista.', 'warning'); return; }
  const button = $(`[data-stop-process="${CSS.escape(String(sessionKey))}"]`);
  if (button) { button.disabled = true; button.textContent = 'Encerrando…'; }
  try {
    const payload = session.local_session_id
      ? {environment_id: session.environment_id, session_id: session.local_session_id}
      : {pid:Number(session.pid)};
    const result = await api('/api/processes/stop', {method:'POST', body:JSON.stringify(payload)});
    toast(result.stopped ? `Sessão ${sessionKey} encerrada.` : `Pedido de encerramento enviado para ${sessionKey}.`, result.stopped ? '' : 'warning');
    await refreshAll();
  } catch (error) {
    toast(error.message || 'Não foi possível encerrar a sessão.', 'error');
    if (button) { button.disabled = false; button.textContent = 'Encerrar'; }
    await refreshSessionsOnly();
  }
}

async function showSessionLog(sessionKey) {
  const session = findSessionByKey(sessionKey);
  if (!session) { toast('Sessão não encontrada; atualize a lista.', 'warning'); return; }
  try {
    const logPath = session.local_session_id
      ? `/api/processes/${encodeURIComponent(session.environment_id)}/${encodeURIComponent(session.local_session_id)}/log`
      : `/api/processes/${encodeURIComponent(session.pid)}/log`;
    const data = await api(logPath);
    $('#process-log-title').textContent = `Logs: ${session.environment_id || 'local'} · PID ${session.pid} · ${data.status}`;
    $('#process-log-content').textContent = `${data.truncated ? '[Trecho inicial do log omitido — exibindo o final.]\n' : ''}${data.log || '(sem saída registrada)'}`;
    $('#process-log-dialog').showModal();
  } catch (error) {
    toast(error.message || 'Não foi possível ler o log.', 'error');
  }
}

async function refreshSessionsOnly() {
  try {
    const data = await api('/api/processes');
    state.sessions = data.processes || [];
    renderSessions();
  } catch (_) { /* Preserve the last known snapshot if an agent is unavailable. */ }
}

function renderPlatformOptions() {
  const select = $('#platform-filter');
  const platforms = [...new Set(state.emulators.map(i => i.platform))].sort((a,b)=>a.localeCompare(b));
  select.innerHTML = '<option value="all">Todas as plataformas</option>' + platforms.map(p => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join('');
  const families = [
    ['all','Tudo'], ['ps','PlayStation'], ['xb','Xbox'], ['nin','Nintendo']
  ];
  $('#platform-strip').innerHTML = families.map(([key,label],i) => `<button class="platform-pill ${i===0?'active':''}" data-family="${key}">${label}</button>`).join('');
  $$('#platform-strip [data-family]').forEach(button => button.addEventListener('click', () => {
    $$('#platform-strip .platform-pill').forEach(p => p.classList.toggle('active', p === button));
    $('#platform-filter').value = 'all';
    $('#platform-filter').dataset.family = button.dataset.family;
    renderEmulators();
  }));
}
function renderEmulators() {
  const query = ($('#emulator-search')?.value || $('#global-search')?.value || '').trim().toLowerCase();
  const platform = $('#platform-filter')?.value || 'all';
  const family = $('#platform-filter')?.dataset.family || 'all';
  const filterStatus = $('#status-filter')?.value || 'all';
  const filtered = state.emulators.filter(item => {
    const haystack = `${item.name} ${item.platform} ${item.notes} ${item.runtime}`.toLowerCase();
    if (query && !haystack.includes(query)) return false;
    if (platform !== 'all' && item.platform !== platform) return false;
    if (family !== 'all' && platformFamily(item.platform) !== family) return false;
    if (filterStatus === 'ready' && !['AVAILABLE','AVAILABLE VIA WINE'].includes(item.runtime_status)) return false;
    if (filterStatus === 'missing' && !['NOT INSTALLED','NEEDS BINARY','NEEDS WINE'].includes(item.runtime_status)) return false;
    if (filterStatus === 'experimental' && !['NO LINUX EMULATOR BIN','NO STANDALONE RUNNER','UNVERIFIED VARIANT'].includes(item.runtime_status) && item.status !== 'experimental') return false;
    return true;
  });
  $('#emulator-results-count').textContent = `${filtered.length} de ${state.emulators.length} projetos`;
  $('#emulator-grid').innerHTML = filtered.length ? filtered.map(item => emulatorCard(item)).join('') : `<div class="empty-state empty-state-wide">Nenhum projeto corresponde a esses filtros.</div>`;
}

function environmentTone(environment) {
  if (!environment.online) return 'blocked';
  if (environment.launch_available) return 'good';
  return 'warn';
}
function environmentCapabilityLabel(environment) {
  const labels = {
    SYSTEM_MENU_BOOT: 'Boot do menu do sistema (condicionado a firmware)',
    FIRMWARE_BOOT: 'Boot da BIOS/firmware',
    CONDITIONAL_SYSTEM_BOOT: 'Boot do sistema; dashboard depende dos arquivos',
    CONDITIONAL_MENU_BOOT: 'Menu de sistema condicionado a dados oficiais',
    MANUAL_SYSTEM_BOOT: 'Menu/sistema exige ação manual',
    BOOT_SEQUENCE_ONLY: 'Sequência de boot; sem dashboard dedicado',
    GAME_ONLY_EXPERIMENTAL: 'Jogos / suporte experimental; sem boot completo verificado',
    GAME_ONLY: 'Executar jogos; boot completo não integrado',
    UNAVAILABLE: 'Runner não disponível/verificado',
  };
  return labels[environment.capability_level] || environment.capability_note || 'Capacidade não classificada';
}
function renderEnvironments() {
  const host = $('#environment-grid');
  if (!host) return;
  const environments = state.environments || [];
  const online = environments.filter(e => e.online).length;
  const active = new Set((state.sessions || []).filter(s => s.status === 'running').map(s => s.environment_id).filter(Boolean)).size;
  $('#environment-stats').innerHTML = `<div class="summary-chip"><span>Ambientes definidos</span><b>${environments.length}</b></div><div class="summary-chip"><span>Agentes online</span><b>${online}/${environments.length}</b></div><div class="summary-chip"><span>Ambientes ativos / limite</span><b>${active}/${state.health?.max_active_environments || 2}</b></div>`;
  const query = ($('#environment-search')?.value || '').trim().toLowerCase();
  const filter = $('#environment-filter')?.value || 'all';
  const items = environments.filter(env => {
    const text = `${env.name} ${env.platform} ${env.emulator_name} ${env.id} ${env.capability_note}`.toLowerCase();
    if (query && !text.includes(query)) return false;
    if (filter === 'online' && !env.online) return false;
    if (filter === 'offline' && env.online) return false;
    if (filter === 'launchable' && !env.launch_available) return false;
    if (filter === 'system-boot' && !['SYSTEM_MENU_BOOT','FIRMWARE_BOOT','CONDITIONAL_SYSTEM_BOOT','CONDITIONAL_MENU_BOOT','MANUAL_SYSTEM_BOOT'].includes(env.capability_level)) return false;
    return true;
  });
  host.innerHTML = items.length ? items.map(env => {
    const tone = environmentTone(env);
    const dataRoot = env.directories?.root || `data/environments/${env.id}`;
    const systems = (env.system_profile_ids || []).map(id => {
      const match = (state.consoleSystems || []).find(system => system.id === id);
      return match ? `${match.name}: ${systemStateLabel(match)}` : id;
    }).join(' · ');
    const launch = env.launch_available
      ? `<button class="button primary" data-environment-launch="${escapeHtml(env.id)}">Abrir emulador <span>→</span></button>`
      : `<button class="button secondary" disabled title="${escapeHtml(env.launch_reason || env.capability_note || 'Launcher indisponível')}">Launcher indisponível</button>`;
    const systemProfile = (env.system_profile_ids || []).map(id => (state.consoleSystems || []).find(system => system.id === id)).find(Boolean);
    const consoleButton = systemProfile
      ? `<button class="button secondary" data-environment-system="${escapeHtml(systemProfile.id)}">${escapeHtml(systemProfile.can_attempt_boot ? 'Ver estado de boot' : systemProfile.can_open_emulator ? 'Ver limites / configuração' : 'Ver indisponibilidade')}</button>`
      : '';
    return `<article class="environment-card ${tone}"><div class="environment-card-top"><div><div class="console-family">${escapeHtml(env.platform)}</div><h3>${escapeHtml(env.emulator_name)}</h3><p>${escapeHtml(env.name)}</p></div><span class="system-state-pill ${tone}"><i></i>${escapeHtml(env.online ? 'Agente online' : 'Agente offline')}</span></div><div class="environment-capability"><b>${escapeHtml(environmentCapabilityLabel(env))}</b><p>${escapeHtml(env.capability_note || '')}</p></div><div class="environment-detail-grid"><div><small>Ambiente</small><code>${escapeHtml(env.id)}</code></div><div><small>Runtime</small><b>${escapeHtml(env.runtime_status || '—')}</b></div><div><small>Jogos</small><code>${escapeHtml(dataRoot)}/games</code></div><div><small>BIOS / firmware</small><code>${escapeHtml(dataRoot)}/bios</code></div><div><small>Saves</small><code>${escapeHtml(dataRoot)}/saves</code></div><div><small>Configurações</small><code>${escapeHtml(dataRoot)}/home</code></div></div>${systems ? `<p class="environment-system-profiles"><b>Perfis de sistema:</b> ${escapeHtml(systems)}</p>` : ''}<div class="environment-actions">${launch}${consoleButton}<a class="source-link" href="${escapeHtml(env.url || env.emulator_url || '#')}" target="_blank" rel="noopener noreferrer">Projeto oficial ↗</a></div></article>`;
  }).join('') : `<div class="empty-state empty-state-wide">Nenhum ambiente corresponde ao filtro atual.</div>`;
}

function systemStateTone(system) {
  if (system.state === 'ready') return 'good';
  if (system.state === 'needs-setup' || system.state === 'manual' || system.state === 'needs-verification') return 'warn';
  if (system.state === 'unsupported' || system.state === 'no-dashboard' || system.state === 'launcher-missing' || system.state === 'environment-offline') return 'blocked';
  return 'muted';
}
function systemStateLabel(system) {
  return system.state_label || 'Estado não determinado';
}
function systemBootLabel(system) {
  if (system.id === 'xbox-original-dashboard') return 'Tentar iniciar Xbox virtual (dashboard do HDD)';
  if (system.id === 'ps3-xmb') return 'Tentar iniciar VSH / XMB';
  if (system.id === 'ps2-bios-menu') return 'Tentar iniciar BIOS / Browser';
  if (system.id === 'wiiu-menu') return 'Tentar iniciar Wii U Menu';
  if (system.id === 'wii-menu') return 'Tentar iniciar Wii Menu';
  return 'Tentar iniciar sistema';
}
function consoleSystemCard(system) {
  const family = platformFamily(system.family || system.name);
  const tone = systemStateTone(system);
  const checks = (system.checks || []).map(check => {
    const checkClass = check.ok === true ? 'check-good' : check.ok === false ? 'check-bad' : 'check-unknown';
    const symbol = check.ok === true ? '✓' : check.ok === false ? '!' : '·';
    return `<li class="system-check ${checkClass}"><span>${symbol}</span><div><b>${escapeHtml(check.label || 'Verificação')}</b><small>${escapeHtml(check.detail || '')}</small></div></li>`;
  }).join('');
  const bootButton = system.can_attempt_boot
    ? `<button class="button primary system-action" data-system-action="boot" data-system-id="${escapeHtml(system.id)}">${escapeHtml(systemBootLabel(system))} <span>→</span></button>`
    : '';
  const bootEvidenceNote = system.can_attempt_boot && !system.boot_observed
    ? '<p class="console-system-details"><strong>Validação pendente:</strong> os pré-requisitos foram detectados, mas este host ainda não comprovou um boot real do sistema.</p>'
    : system.boot_observed && !system.smoke_test_passed
      ? '<p class="console-system-details"><strong>Validação parcial:</strong> há evidência de boot, mas o teste mínimo de runtime ainda não passou.</p>'
      : '';
  const openButton = system.can_open_emulator
    ? `<button class="button secondary system-action" data-system-action="open" data-system-id="${escapeHtml(system.id)}">Abrir emulador</button>`
    : `<button class="button secondary system-action" data-system-action="open" data-system-id="${escapeHtml(system.id)}" disabled>Emulador indisponível</button>`;
  const requirements = (system.requirements || []).slice(0, 2).map(req => `<li>${escapeHtml(req)}</li>`).join('');
  return `<article class="console-system-card ${tone}">
    <div class="console-card-top"><div class="console-system-icon ${family}">${escapeHtml(platformGlyph(system.family || system.name))}</div><div class="console-system-heading"><div class="console-family">${escapeHtml(system.family || 'Console')}</div><h3>${escapeHtml(system.name)}</h3><p>${escapeHtml(system.interface_name || 'Interface do sistema')}</p></div></div>
    <div class="system-state-row"><span class="system-state-pill ${tone}"><i></i>${escapeHtml(systemStateLabel(system))}</span><span class="system-capability">${escapeHtml(String(system.capability || '').replaceAll('-', ' '))}</span></div><div class="environment-boundary-note">Ambiente isolado: <code>${escapeHtml(system.environment_id || system.emulator_ids?.[0] || 'sem runner')}</code> · ${escapeHtml(system.environment_online === false && system.environment_id ? 'offline ou não associado' : 'sem compartilhamento de dados de console')}</div>
    <p class="console-system-details">${escapeHtml(system.details || '')}</p>
    ${bootEvidenceNote}
    ${requirements ? `<div class="system-requirements"><b>Necessário</b><ul>${requirements}</ul></div>` : ''}
    ${checks ? `<ul class="system-checks">${checks}</ul>` : ''}
    <div class="console-system-actions">${bootButton}${openButton}<button class="text-button system-info-action" data-system-setup="${escapeHtml(system.id)}">Passos e fontes ↗</button></div>
  </article>`;
}
function renderConsoleSystems() {
  const host = $('#console-system-grid');
  if (!host) return;
  const systems = state.consoleSystems || [];
  const ready = systems.filter(s => s.can_attempt_boot).length;
  const needs = systems.filter(s => ['needs-setup','needs-verification','manual'].includes(s.state)).length;
  const unavailable = systems.filter(s => ['unsupported','no-dashboard','launcher-missing','environment-offline'].includes(s.state)).length;
  $('#console-system-stats').innerHTML = `<div class="summary-chip"><span>Pronto para tentativa (boot não garantido)</span><b>${ready}</b></div><div class="summary-chip"><span>Precisa configurar</span><b>${needs}</b></div><div class="summary-chip"><span>Sem boot completo</span><b>${unavailable}</b></div>`;
  $('#nav-console-count').textContent = systems.length || '—';
  const query = ($('#console-system-search')?.value || '').trim().toLowerCase();
  const filter = $('#console-system-filter')?.value || 'all';
  const filtered = systems.filter(system => {
    const haystack = `${system.name} ${system.interface_name} ${system.family} ${system.details} ${(system.emulator_ids || []).join(' ')}`.toLowerCase();
    return (!query || haystack.includes(query)) && (filter === 'all' || system.state === filter);
  });
  if (state.consoleSystemsError && !systems.length) {
    host.innerHTML = `<div class="empty-state empty-state-wide">Não foi possível carregar os perfis de sistema: ${escapeHtml(state.consoleSystemsError)}. Confira console-systems.json e os logs do dashboard.</div>`;
    return;
  }
  host.innerHTML = filtered.length ? filtered.map(consoleSystemCard).join('') : '<div class="empty-state empty-state-wide">Nenhum sistema corresponde a esses filtros.</div>';
}
function showSystemSetup(systemId) {
  const system = state.consoleSystems.find(item => item.id === systemId);
  if (!system) return;
  $('#system-setup-title').textContent = `${system.name} — ${system.interface_name}`;
  $('#system-setup-summary').textContent = `${systemStateLabel(system)}. ${system.details || ''}`;
  const checks = (system.checks || []).map(check => {
    const status = check.ok === true ? 'Detectado' : check.ok === false ? 'Ausente' : 'Verificação manual';
    const cls = check.ok === true ? 'check-good' : check.ok === false ? 'check-bad' : 'check-unknown';
    return `<div class="system-setup-check ${cls}"><b>${escapeHtml(status)} · ${escapeHtml(check.label || '')}</b><p>${escapeHtml(check.detail || '')}</p></div>`;
  }).join('');
  $('#system-setup-checks').innerHTML = checks || '<p>Nenhuma verificação automática disponível para este sistema.</p>';
  const steps = (system.setup_steps || []).length ? system.setup_steps : ['No momento não há inicialização automática do sistema completo neste projeto. Consulte a documentação oficial e não interprete um launcher de jogos como emulação do sistema operacional do console.'];
  $('#system-setup-steps').innerHTML = steps.map(step => `<li>${escapeHtml(step)}</li>`).join('');
  const links = (system.official_docs || []).filter(url => /^https:\/\//i.test(url));
  $('#system-setup-links').innerHTML = links.length ? links.map((url, index) => `<a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Documentação oficial ${index + 1} ↗</a>`).join('') : '<span>Sem link oficial cadastrado.</span>';
  $('#system-setup-dialog').showModal();
}
async function launchConsoleSystem(systemId, action) {
  const system = state.consoleSystems.find(item => item.id === systemId);
  if (!system) return;
  try {
    const result = await api('/api/console-systems/launch', {method:'POST', body:JSON.stringify({system:systemId, action})});
    if (!result.started) throw new Error(result.error || 'O sistema não iniciou.');
    const actionName = action === 'boot' ? 'Inicialização solicitada' : 'Emulador aberto para configuração';
    toast(`${actionName}: ${system.name}${result.pid ? ` (PID ${result.pid})` : ''}.`, '');
    if (action === 'open') showSystemSetup(systemId);
    await refreshSessionsOnly();
  } catch (error) {
    const message = error.message || 'Não foi possível iniciar o sistema.';
    toast(message, 'error');
    showSystemSetup(systemId);
  }
}

function renderLibrary() {
  const extSelect = $('#extension-filter');
  const extensions = [...new Set(state.games.map(g=>g.extension))].sort();
  const current = extSelect.value;
  extSelect.innerHTML = '<option value="all">Todos os formatos</option>' + extensions.map(ext=>`<option value="${escapeHtml(ext)}">${escapeHtml(ext.toUpperCase())}</option>`).join('');
  if (extensions.includes(current)) extSelect.value = current;
  const totalBytes = state.games.reduce((sum,g)=>sum+g.size_bytes,0);
  $('#library-summary').innerHTML = `<div class="summary-chip"><span>Itens detectados</span><b>${state.games.length}</b></div><div class="summary-chip"><span>Espaço catalogado</span><b>${escapeHtml(formatBytes(totalBytes))}</b></div><div class="summary-chip"><span>Diretório do host</span><b><code>data/environments/&lt;id&gt;/games/</code></b></div>`;
  const query = ($('#library-search').value || '').toLowerCase().trim();
  const ext = extSelect.value;
  const sort = $('#library-sort').value;
  const items = state.games.filter(g => (!query || `${g.name} ${g.path}`.toLowerCase().includes(query)) && (ext === 'all' || g.extension === ext));
  if (sort === 'size') items.sort((a,b)=>b.size_bytes-a.size_bytes);
  if (sort === 'recent') items.sort((a,b)=>new Date(b.modified)-new Date(a.modified));
  if (sort === 'name') items.sort((a,b)=>a.path.localeCompare(b.path));
  $('#library-table-body').innerHTML = items.length ? items.map(game => `<tr><td><div class="library-file-cell"><div class="file-icon ${iconClass(game.extension)}">${escapeHtml(game.extension.replace('.','').slice(0,4)||'FILE')}</div><div><b>${escapeHtml(game.name)}</b><small>${escapeHtml(game.environment_id ? `${game.environment_id} / ` : '')}${escapeHtml(game.path)}</small></div></div></td><td><span class="file-tag">${escapeHtml(game.extension.toUpperCase())}</span></td><td>${escapeHtml(game.size_label)}</td><td>${escapeHtml(game.environment_name || game.environment_id || 'legado')}</td><td>${escapeHtml(formatDate(game.modified))}</td><td><button class="row-action" data-launch-game="${escapeHtml(game.path)}" data-launch-environment="${escapeHtml(game.environment_id || '')}">Abrir…</button></td></tr>`).join('') : `<tr><td colspan="6" class="empty-state">${state.games.length ? 'Nenhum arquivo corresponde à busca.' : 'Nenhum arquivo encontrado nos diretórios de jogos dos ambientes.'}</td></tr>`;
  $('#library-empty-hint').classList.toggle('hidden', state.games.length !== 0);
  if (!state.games.length) $('#library-table-body').innerHTML = '';
  $('#nav-game-count').textContent = state.games.length;
  if (state.health?.games_limit_reached) toast('O catálogo atingiu o limite de 3.000 arquivos; nem todos podem aparecer.', 'warning');
}

function renderSources() {
  const categories = state.sources.categories || [];
  const platformGuidance = state.sources.platform_guidance || [];
  const categoryTabs = [{id:'all',title:'Todas as fontes'},...categories.map(c=>({id:c.id,title:c.title}))];
  $('#source-tabs').innerHTML = categoryTabs.map(t=>`<button class="source-tab ${t.id===state.selectedSourceCategory?'active':''}" data-source-category="${escapeHtml(t.id)}">${escapeHtml(t.title)}</button>`).join('');
  $$('#source-tabs [data-source-category]').forEach(button=>button.addEventListener('click',()=>{state.selectedSourceCategory=button.dataset.sourceCategory;renderSources();}));

  const platformTabs = [{id:'all',title:'Todos os consoles'},...platformGuidance.map(p=>({id:p.environment_id,title:p.platform}))];
  $('#source-platform-tabs').innerHTML = platformTabs.map(t=>`<button class="source-tab ${t.id===state.selectedSourcePlatform?'active':''}" data-source-platform="${escapeHtml(t.id)}">${escapeHtml(t.title)}</button>`).join('');
  $$('#source-platform-tabs [data-source-platform]').forEach(button=>button.addEventListener('click',()=>{state.selectedSourcePlatform=button.dataset.sourcePlatform;renderSources();}));

  const selectedPlatform = platformGuidance.find(p=>p.environment_id===state.selectedSourcePlatform);
  const platformNote = $('#source-platform-note');
  platformNote.textContent = selectedPlatform
    ? selectedPlatform.guidance
    : 'Importante: repositórios de emuladores normalmente publicam código e binários do emulador, não jogos. As fontes desta página são lojas oficiais, homebrew/demos publicadas por seus autores e documentação. A compatibilidade e a licença devem ser verificadas item por item.';
  const allowedIds = selectedPlatform ? new Set(selectedPlatform.source_ids || []) : null;
  let sources = (state.sources.sources||[]).filter(s =>
    (state.selectedSourceCategory==='all' || s.category===state.selectedSourceCategory) &&
    (!allowedIds || allowedIds.has(s.id))
  );
  let cards = sources.map(source=>sourceCard(source)).join('');
  if (state.selectedSourceCategory === 'all' || state.selectedSourceCategory === 'personal-library') {
    if (!selectedPlatform || selectedPlatform.include_personal_library) cards += personalLibraryCard();
  }
  if (!cards) cards = `<div class="empty-state empty-state-wide">Nenhuma fonte de download autorizada foi verificada para este filtro. Consulte a documentação do emulador e os canais oficiais dos autores; não trate uma loja digital como se fornecesse um ROM/ISO.</div>`;
  $('#source-grid').innerHTML = cards;
}
function sourceCard(source) {
  const initials = source.name.split(/\s+/).filter(Boolean).slice(0,2).map(s=>s[0]).join('').toUpperCase();
  return `<article class="source-card"><div class="source-top"><div class="source-logo">${escapeHtml(initials)}</div><div class="source-title"><h3>${escapeHtml(source.name)}</h3><small>${escapeHtml(source.type)}</small></div></div><p>${escapeHtml(source.description)}</p><div class="source-caveat">${escapeHtml(source.caveat || 'Confira os termos e a licença do item.')}</div><div class="source-card-foot"><small>${escapeHtml(source.platforms.join(' · '))}</small><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">Visitar ↗</a></div></article>`;
}
function personalLibraryCard() {
 return `<article class="source-card"><div class="source-top"><div class="source-logo">LIB</div><div class="source-title"><h3>Sua própria biblioteca</h3><small>Arquivos locais autorizados</small></div></div><p>Adicione demos, homebrew e arquivos que você está autorizado a usar. O EmuStack organiza o que já está no seu computador sem buscar arquivos na internet.</p><div class="source-caveat">A possibilidade de copiar ou usar firmware/BIOS depende da legislação aplicável e dos termos de cada plataforma.</div><div class="source-card-foot"><small>Local · read-only no container</small><a href="#docs" data-goto="docs">Guia de uso ↗</a></div></article>`;
}

function mdInline(source) {
  let text = escapeHtml(source);
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  return text;
}
function markdownToHtml(markdown) {
  const lines = markdown.replace(/\r/g,'').split('\n');
  const output = [];
  let paragraph = [], list = null, code = false, codeLines = [], tableLines = [];
  const flushParagraph = () => { if (paragraph.length) { output.push(`<p>${paragraph.map(mdInline).join('<br>')}</p>`); paragraph=[]; } };
  const flushList = () => { if (list) { output.push(`</${list}>`); list=null; } };
  const flushCode = () => { if (codeLines.length || code) { output.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`); codeLines=[]; } };
  const flushTable = () => {
    if (!tableLines.length) return;
    const rows = tableLines.filter(line => !/^\s*\|?\s*:?-{2,}/.test(line));
    if (rows.length) {
      const parsed = rows.map(line => line.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(c=>c.trim()));
      const head = parsed[0] || [];
      const body = parsed.slice(1);
      output.push(`<table><thead><tr>${head.map(c=>`<th>${mdInline(c)}</th>`).join('')}</tr></thead><tbody>${body.map(row=>`<tr>${row.map(c=>`<td>${mdInline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`);
    }
    tableLines=[];
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line.startsWith('```')) {
      flushParagraph(); flushList(); flushTable();
      if (code) { flushCode(); code=false; } else { code=true; codeLines=[]; }
      continue;
    }
    if (code) { codeLines.push(raw); continue; }
    if (/^\|.*\|$/.test(line.trim())) { flushParagraph(); flushList(); tableLines.push(line.trim()); continue; }
    flushTable();
    if (!line.trim()) { flushParagraph(); flushList(); continue; }
    if (/^---+$/.test(line.trim())) { flushParagraph(); flushList(); output.push('<hr>'); continue; }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) { flushParagraph(); flushList(); const level=heading[1].length; output.push(`<h${level}>${mdInline(heading[2])}</h${level}>`); continue; }
    if (/^>\s?/.test(line)) { flushParagraph(); flushList(); output.push(`<blockquote>${mdInline(line.replace(/^>\s?/,''))}</blockquote>`); continue; }
    const bullet = line.match(/^[-*]\s+(.+)$/);
    const ordered = line.match(/^\d+\.\s+(.+)$/);
    if (bullet || ordered) {
      flushParagraph();
      const nextList = bullet ? 'ul' : 'ol';
      if (list !== nextList) { flushList(); output.push(`<${nextList}>`); list=nextList; }
      output.push(`<li>${mdInline((bullet || ordered)[1])}</li>`); continue;
    }
    flushList(); paragraph.push(line.trim());
  }
  flushParagraph(); flushList(); flushTable(); if (code) flushCode();
  return output.join('\n');
}
function renderDocs() {
  if (!state.docs.length) return;
  if (!state.docs.some(d=>d.id===state.selectedDoc)) state.selectedDoc=state.docs[0].id;
  $('#docs-nav').innerHTML = state.docs.map(doc=>`<button class="doc-nav-item ${doc.id===state.selectedDoc?'active':''}" data-doc="${escapeHtml(doc.id)}">${escapeHtml(doc.title)}</button>`).join('');
  $$('#docs-nav [data-doc]').forEach(button=>button.addEventListener('click',()=>{state.selectedDoc=button.dataset.doc;renderDocs();}));
  const doc=state.docs.find(d=>d.id===state.selectedDoc);
  $('#docs-content').innerHTML = doc ? markdownToHtml(doc.content) : '<p>Documento não encontrado.</p>';
}

function openLaunchDialog(emulatorId = null, gamePath = '') {
  const launchable = state.emulators.filter(e => e.launchable);
  if (!launchable.length) { toast('Nenhum launcher está disponível. Confira os ambientes isolados e o relatório de instalação.', 'warning'); return; }
  const recommendedId = emulatorId || window.EmuStackLaunch.recommendEmulatorForGame(gamePath);
  const recommendedItem = recommendedId ? state.emulators.find(e => e.id === recommendedId && e.launchable) : null;
  const first = recommendedItem || (!gamePath ? launchable[0] : null);
  state.launchTarget = first;
  state.launchEnvironmentId = first?.id || null;
  $('#launch-title').textContent = emulatorId && first ? `Abrir ${first.name}` : 'Abrir ambiente de console';
  $('#launch-description').textContent = gamePath
    ? `O arquivo será buscado somente em data/environments/${first?.id || '<id>'}/games/. Outro ambiente não terá acesso a esse arquivo.`
    : 'Escolha um ambiente de execução. Cada ambiente vê apenas sua própria biblioteca, BIOS/firmware, saves e configurações.';
  const emuSelect = $('#launch-emulator-select');
  emuSelect.innerHTML = (first ? '' : '<option value="">Selecione um launcher disponível…</option>') + launchable.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} — ${escapeHtml(item.platform)} · ${escapeHtml(shortStatus(item))}</option>`).join('');
  emuSelect.value = first ? first.id : '';
  const gameSelect = $('#launch-game-select');
  const games = state.games.filter(g => first && g.environment_id === first.id);
  const emptyGameLabel = first?.game_arg === 'ui-only' ? 'Escolher conteúdo na interface do emulador' : (first ? 'Abrir interface do emulador sem jogo' : 'Selecione um emulador primeiro');
  gameSelect.innerHTML = `<option value="">${emptyGameLabel}</option>` + games.map(g=>`<option value="${escapeHtml(g.path)}">${escapeHtml(g.path)} · ${escapeHtml(g.size_label)}</option>`).join('');
  if (gamePath && games.some(g=>g.path===gamePath)) gameSelect.value = gamePath;
  updateLaunchDialogForSelection();
  $('#confirm-launch').disabled = !state.launchTarget;
  $('#confirm-launch').innerHTML = 'Abrir ambiente <span>→</span>';
  $('#launch-dialog').showModal();
}
function updateLaunchDialogForSelection() {
  const item=state.emulators.find(e => e.id === $('#launch-emulator-select').value);
  state.launchTarget=item || null;
  $('#confirm-launch').disabled = !item || !item.launchable;
  const gameSelect=$('#launch-game-select');
  const previousEnvironment=state.launchEnvironmentId;
  const previousGame=gameSelect.value;
  const selectedPath = previousEnvironment === item?.id ? previousGame : '';
  const availableGames = state.games.filter(g => item && g.environment_id === item.id);
  const uiOnly=item?.game_arg === 'ui-only';
  const emptyGameLabel = uiOnly ? 'Escolher conteúdo na interface do emulador' : (item ? 'Abrir interface do emulador sem jogo' : 'Selecione um emulador primeiro');
  gameSelect.innerHTML = `<option value="">${emptyGameLabel}</option>` + availableGames.map(g=>`<option value="${escapeHtml(g.path)}">${escapeHtml(g.path)} · ${escapeHtml(g.size_label)}</option>`).join('');
  if (selectedPath && availableGames.some(g=>g.path===selectedPath)) gameSelect.value = selectedPath;
  gameSelect.disabled=uiOnly || !item;
  if (uiOnly) gameSelect.value='';
  state.launchEnvironmentId = item?.id || null;
  const selectedGame = gameSelect.value;
  const extension = selectedGame.includes('.') ? selectedGame.slice(selectedGame.lastIndexOf('.')).toLowerCase() : '';
  const unsupportedLicense = item?.id === 'rpcs3' && ['.rap', '.edat'].includes(extension);
  $('#confirm-launch').disabled = !item || !item.launchable || unsupportedLicense;
  const note = $('#launch-status-note');
  if (!item) note.textContent = 'Selecione um ambiente online com launcher disponível.';
  else if (!item.environment_online && item.environment_online !== null) note.textContent = 'O agente deste ambiente está offline. Atualize os serviços Docker.';
  else if (uiOnly) note.textContent = 'Este emulador escolhe o conteúdo pela própria interface; nenhum arquivo será montado de outro ambiente.';
  else if (item.id === 'rpcs3' && extension === '.pkg') note.textContent = 'O RPCS3 abrirá o fluxo de instalação do pacote PKG dentro do ambiente PS3.';
  else if (unsupportedLicense) note.textContent = 'RAP/EDAT é dado de licença/suporte, não um jogo inicializável.';
  else note.textContent = `O processo será iniciado pelo agente ${item.id}; somente ${item.id}/games é visível como biblioteca.`;
}

async function confirmLaunch() {
  const item=state.launchTarget;
  if (!item) return;
  const game = item.game_arg === 'ui-only' ? '' : $('#launch-game-select').value;
  const button=$('#confirm-launch'); button.disabled=true; button.textContent='Iniciando…';
  try {
    const result=await api('/api/launch',{method:'POST',body:JSON.stringify({emulator:item.id,game})});
    $('#launch-dialog').close();
    toast(`${item.name} iniciado no ambiente ${item.id}${result.pid ? ` (PID ${result.pid})` : ''}.`);
  } catch(error) {
    toast(error.message || 'Não foi possível iniciar o emulador. Consulte as sessões e seus logs.', 'error');
    await refreshAll();
  } finally {
    button.disabled=false; button.innerHTML='Abrir emulador <span>→</span>';
  }
}

async function refreshAll() {
  $('#refresh-button').classList.add('refreshing');
  try {
    const [health, catalog, games, sources, docs, processes, consoleSystems, environments, reportResult] = await Promise.all([
      api('/api/health'), api('/api/catalog'), api('/api/games'), api('/api/sources'), api('/api/docs'), api('/api/processes'), api('/api/console-systems').catch(error => ({systems:[], error:error.message})), api('/api/environments').catch(error => ({environments:[], error:error.message})), api('/api/report').catch(error => ({available:false, message:error.message}))
    ]);
    state.health=health; state.emulators=catalog.emulators||[]; state.games=games.games||[]; state.sources=sources; state.docs=docs.documents||[]; state.sessions=processes.processes||[]; state.consoleSystems=consoleSystems.systems||[]; state.consoleSystemsError=consoleSystems.error||''; state.environments=environments.environments||[];
    state.installReport = reportResult.available ? reportResult.report : null;
    state.installReportError = reportResult.available ? '' : (reportResult.message || '');
    renderOverview(); renderInstallReport(); renderPlatformOptions(); renderEmulators(); renderEnvironments(); renderConsoleSystems(); renderLibrary(); renderSources(); renderDocs(); renderSessions();
  } catch(error) {
    $('#side-health').textContent='API indisponível';
    toast(`Não foi possível ler o container: ${error.message}`, 'error');
  } finally {
    $('#refresh-button').classList.remove('refreshing');
  }
}

document.addEventListener('click', event => {
  const nav = event.target.closest('[data-view]');
  if (nav) { setView(nav.dataset.view); return; }
  const goto = event.target.closest('[data-goto]');
  if (goto) { event.preventDefault(); setView(goto.dataset.goto); return; }
  const environmentLaunch = event.target.closest('[data-environment-launch]');
  if (environmentLaunch) { openLaunchDialog(environmentLaunch.dataset.environmentLaunch); return; }
  const environmentSystem = event.target.closest('[data-environment-system]');
  if (environmentSystem) { setView('consoles'); showSystemSetup(environmentSystem.dataset.environmentSystem); return; }
  const systemAction = event.target.closest('[data-system-action]');
  if (systemAction) { launchConsoleSystem(systemAction.dataset.systemId, systemAction.dataset.systemAction); return; }
  const systemSetup = event.target.closest('[data-system-setup]');
  if (systemSetup) { showSystemSetup(systemSetup.dataset.systemSetup); return; }
  const stop = event.target.closest('[data-stop-process]');
  if (stop) { stopSession(stop.dataset.stopProcess); return; }
  const log = event.target.closest('[data-process-log]');
  if (log) { showSessionLog(log.dataset.processLog); return; }
  const launch = event.target.closest('[data-launch]');
  if (launch) { openLaunchDialog(launch.dataset.launch); return; }
  const launchGame = event.target.closest('[data-launch-game]');
  if (launchGame) {
    openLaunchDialog(launchGame.dataset.launchEnvironment || null, launchGame.dataset.launchGame); return;
  }
});
$('#confirm-launch').addEventListener('click', confirmLaunch);
if ($('#console-system-search')) $('#console-system-search').addEventListener('input', renderConsoleSystems);
if ($('#console-system-filter')) $('#console-system-filter').addEventListener('change', renderConsoleSystems);
if ($('#environment-search')) $('#environment-search').addEventListener('input', renderEnvironments);
if ($('#environment-filter')) $('#environment-filter').addEventListener('change', renderEnvironments);
if ($('#close-system-setup')) $('#close-system-setup').addEventListener('click', () => $('#system-setup-dialog').close());
$('#launch-emulator-select').addEventListener('change', updateLaunchDialogForSelection);
$('#launch-game-select').addEventListener('change', updateLaunchDialogForSelection);
$('#refresh-button').addEventListener('click', refreshAll);
$('#refresh-library').addEventListener('click', refreshAll);
if ($('#refresh-install-report')) $('#refresh-install-report').addEventListener('click', refreshAll);
if ($('#refresh-sessions')) $('#refresh-sessions').addEventListener('click', refreshSessionsOnly);
if ($('#close-process-log')) $('#close-process-log').addEventListener('click', () => $('#process-log-dialog').close());
$('#emulator-search').addEventListener('input', () => { $('#global-search').value=$('#emulator-search').value; renderEmulators(); });
$('#platform-filter').addEventListener('change', () => { $('#platform-filter').dataset.family='all'; $$('#platform-strip .platform-pill').forEach(p=>p.classList.toggle('active',p.dataset.family==='all')); renderEmulators(); });
$('#status-filter').addEventListener('change', renderEmulators);
$('#library-search').addEventListener('input', renderLibrary);
$('#extension-filter').addEventListener('change', renderLibrary);
$('#library-sort').addEventListener('change', renderLibrary);
$('#global-search').addEventListener('input', () => {
  const query=$('#global-search').value;
  $('#emulator-search').value=query;
  if (query) setView('emulators');
  renderEmulators();
});
$('#global-search').addEventListener('keydown', event => {if(event.key==='Enter'){setView('emulators');renderEmulators();}});
document.addEventListener('keydown', event => {
  if (event.key === '/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName) && !event.ctrlKey && !event.metaKey) {event.preventDefault();$('#global-search').focus();}
  if (event.key === 'Escape') $('#sidebar').classList.remove('open');
});
$('#mobile-menu').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));

refreshAll();
