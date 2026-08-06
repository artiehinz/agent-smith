let _policy = null;
let _policyTasks = null;
let _policyPreflight = null;
let _policyBackendDecisions = null;
let _policyPreflightState = null;
let _policyTaskDetail = null;

function _taskQueryString() {
  const params = new URLSearchParams();
  const status = (document.getElementById('policy-task-status')?.value || '').trim();
  const owner = (document.getElementById('policy-task-owner')?.value || '').trim();
  const route = (document.getElementById('policy-task-route')?.value || '').trim();
  const since = (document.getElementById('policy-task-since')?.value || '').trim();
  const until = (document.getElementById('policy-task-until')?.value || '').trim();
  const limit = parseInt((document.getElementById('policy-task-limit')?.value || '12').trim(), 10);
  const offset = parseInt((document.getElementById('policy-task-offset')?.value || '0').trim(), 10);

  if (status) params.set('status', status);
  if (owner) params.set('owner_role', owner);
  if (route) params.set('route', route);
  if (since) params.set('since', since);
  if (until) params.set('until', until);
  if (Number.isFinite(limit) && limit > 0) params.set('limit', String(limit));
  if (Number.isFinite(offset) && offset >= 0) params.set('offset', String(offset));
  return params.toString() ? `?${params.toString()}` : '';
}

async function pollPolicy() {
  try {
    const [policyRes, tasksRes, preflightRes] = await Promise.all([
      fetch('/api/policy'),
      fetch(`/api/policy/tasks${_taskQueryString()}`),
      fetch('/api/policy/preflight'),
    ]);

    _policy = policyRes.ok ? await policyRes.json() : null;
    const taskPayload = tasksRes.ok ? await tasksRes.json() : null;
    _policyTasks = taskPayload && taskPayload.ok ? (taskPayload.tasks || []) : [];

    const preflightPayload = preflightRes.ok ? await preflightRes.json() : {};
    _policyPreflight = preflightPayload && preflightPayload.ok ? (preflightPayload.preflight || {}) : {};
    _policyBackendDecisions = preflightPayload && preflightPayload.ok ? (preflightPayload.backend_decisions || {}) : {};
    _policyPreflightState = preflightPayload && preflightPayload.ok ? (preflightPayload.policy_preflight_state || null) : null;

    const taskId = (_policy && typeof _policy === 'object' && _policy.ledger_id) ? String(_policy.ledger_id) : '';
    _policyTaskDetail = null;
    if (taskId) {
      const taskRes = await fetch(`/api/policy/tasks/${taskId}`);
      const taskPayload = taskRes.ok ? await taskRes.json() : null;
      if (taskPayload && taskPayload.ok) {
        _policyTaskDetail = taskPayload;
      }
    }

    _renderPolicyTab();
  } catch (err) {
    // Keep policy tab resilient while no scan is active yet.
    console.warn('[policy] refresh failed', err?.message || err);
  }
}

function _policyStatusIcon(status) {
  if (status === 'complete') return '[done]';
  if (status === 'in_progress' || status === 'running') return '[active]';
  if (status === 'incomplete_with_unresolved_blockers' || status === 'limit_reached') return '[warn]';
  return '[idle]';
}

function _safeRenderPolicySummary(sessionPolicy) {
  const el = document.getElementById('policy-summary');
  const routeEl = document.getElementById('policy-route-current');
  const summaryRouteEl = document.getElementById('policy-route-summary');
  if (!el) return;

  if (!sessionPolicy || !Object.keys(sessionPolicy).length) {
    el.textContent = 'No policy blob on this session yet.';
    if (routeEl) routeEl.textContent = '';
    if (summaryRouteEl) summaryRouteEl.textContent = '';
    return;
  }

  const route = sessionPolicy.route || 'n/a';
  const score = sessionPolicy.score == null ? 'n/a' : sessionPolicy.score;
  const routeHint = sessionPolicy.route_hint || 'n/a';
  const override = sessionPolicy.override_applied ? 'yes' : 'no';
  const engine = sessionPolicy.policy_engine || 'n/a';
  const resetApplied = sessionPolicy.route_reset_applied ? 'yes' : 'no';
  const resetSource = sessionPolicy.route_reset_source || 'n/a';
  const resetAfter = sessionPolicy.route_after_reset || 'n/a';
  const tokenBudget = sessionPolicy.token_budget || {};

  el.innerHTML = `
    <div><strong>Route:</strong> ${route}</div>
    <div><strong>Route hint:</strong> ${routeHint}</div>
    <div><strong>Score:</strong> ${score}</div>
    <div><strong>Override applied:</strong> ${override}</div>
    <div><strong>Engine:</strong> ${engine}</div>
    <div><strong>Rationale:</strong> ${(sessionPolicy.rationale || []).join(', ') || 'n/a'}</div>
    <div><strong>Token budget:</strong> task hard=${tokenBudget.task_hard || 'n/a'}, worker hard=${tokenBudget.worker_hard || 'n/a'}</div>
    <div><strong>Route reset last attempt:</strong> ${resetApplied}</div>
    <div><strong>Route reset source:</strong> ${resetSource}</div>
    <div><strong>Route after reset:</strong> ${resetAfter}</div>
  `;

  const routeText = `Current route: ${route}` + (routeHint !== 'n/a' ? ` (hint: ${routeHint})` : '');
  if (routeEl) routeEl.textContent = `Current: ${route}`;
  if (summaryRouteEl) summaryRouteEl.textContent = routeText;

  const select = document.getElementById('policy-route-select');
  if (select && [...select.options].every(o => o.value !== route)) return;
  if (select) select.value = route;
}

function _safeRenderPolicyBudget(policyBudget) {
  const el = document.getElementById('policy-budget');
  if (!el) return;
  if (!policyBudget || typeof policyBudget !== 'object') {
    el.textContent = 'No budget information on this session yet.';
    return;
  }
  el.innerHTML = `
    <div><strong>Token budget (task):</strong> hard=${policyBudget.task_hard}, soft=${policyBudget.task_soft}</div>
    <div><strong>Token budget (worker):</strong> hard=${policyBudget.worker_hard}, soft=${policyBudget.worker_soft}</div>
  `;
}

function _safeRenderPolicyTasks(policyTasks) {
  const el = document.getElementById('policy-tasks');
  if (!el) return;
  if (!policyTasks || !policyTasks.length) {
    el.textContent = 'No tasks recorded yet.';
    return;
  }

  const maxRows = 12;
  const body = policyTasks.slice(0, maxRows).map((task) => {
    const status = task.status || 'unknown';
    const route = task.route || 'unknown';
    const owner = task.owner_role || 'unknown';
    const hint = task.route_hint || 'n/a';
    return `<div><strong>${_policyStatusIcon(status)} ${task.task_id}</strong> - route=${route} owner=${owner} status=${status} hint=${hint}</div>`;
  }).join('');
  el.innerHTML = body;
}

function _safeRenderPolicyTaskDetail(taskDetail) {
  const el = document.getElementById('policy-task-detail');
  if (!el) return;
  if (!taskDetail || !taskDetail.ok) {
    el.textContent = 'Task telemetry not yet available.';
    return;
  }

  const events = Array.isArray(taskDetail.events) ? taskDetail.events : [];
  const completion = events.slice().reverse().find((event) => event.kind === 'completed');
  const routeReset = events.slice().reverse().find((event) => event.kind === 'route_reset');
  const launchEvents = events.filter((event) => event.kind && event.kind.startsWith('delegation_'));

  const rows = [];
  if (completion) {
    const payload = completion.payload || {};
    rows.push(`<div><strong>completion:</strong> status=${payload.status || completion.status || 'n/a'} route=${payload.route || 'n/a'} hint=${payload.route_hint || 'n/a'} route_reset_applied=${payload.route_reset_applied ? 'yes' : 'no'} route_reset_source=${payload.route_reset_source || 'n/a'} route_after_reset=${payload.route_after_reset || 'n/a'}</div>`);
  }
  if (routeReset) {
    const resetPayload = routeReset.payload || {};
    rows.push(`<div><strong>route_reset:</strong> from ${resetPayload.previous_route || 'n/a'} -> ${resetPayload.route || 'n/a'} (${resetPayload.source || 'n/a'})</div>`);
  }
  if (launchEvents.length) {
    const lastLaunch = launchEvents[launchEvents.length - 1];
    const launchPayload = lastLaunch.payload || {};
    const selectedBackend = launchPayload.selected_backend || 'n/a';
    const requiresApproval = launchPayload.requires_approval ? 'yes' : 'no';
    const blocked = launchPayload.block_delegation ? 'yes' : 'no';
    rows.push(`<div><strong>latest launch:</strong> backend=${selectedBackend}, requires_approval=${requiresApproval}, blocked=${blocked}, status=${launchPayload.status || launchPayload.action || 'n/a'}</div>`);
  }

  if (!rows.length) {
    el.textContent = 'Task telemetry not yet recorded.';
    return;
  }
  el.innerHTML = `<strong>Task telemetry:</strong><div style="margin-top:8px;">${rows.join('<br/>')}</div>`;
}

function _renderPolicyPreflight(summary) {
  const el = document.getElementById('policy-preflight');
  const msgEl = document.getElementById('policy-preflight-message');
  if (!el) return;
  if (!summary || typeof summary !== 'object' || !Object.keys(summary).length) {
    el.innerHTML = '<strong>Model attestation:</strong> none yet';
    if (msgEl) msgEl.textContent = 'No preflight evidence has been recorded.';
    return;
  }

  const rows = Object.entries(summary).map(([role, result]) => {
    const status = result.status || 'unknown';
    const mode = result.mode || 'auto';
    const intended = result.intent || {};
    const actual = result.actual || {};
    const mismatch = status !== 'match';
    const parseError = result.parse_error || '';
    return `<div>
      <div><strong>${role}</strong> - mode: ${mode}, status: ${status} ${mismatch ? '(warning)' : ''}</div>
      <div>Intended: ${intended.model || 'n/a'} / ${intended.effort || 'n/a'} (${intended.sandbox || 'read_only'})</div>
      <div>Actual: ${actual.model || 'n/a'} / ${actual.effort || 'n/a'} (${actual.sandbox || 'n/a'})</div>
      ${parseError ? `<div>Parse error: ${parseError}</div>` : ''}
      <div>Marker expected: ${result.marker_expected || 'n/a'} received: ${result.marker || 'n/a'}</div>
    </div>`;
  }).join('<hr/>');
  el.innerHTML = `<strong>Model attestation:</strong><div style=\"margin-top:8px;\">${rows}</div>`;
  if (msgEl) msgEl.textContent = `Loaded ${Object.keys(summary).length} preflight role(s).`;
}

function _renderPolicyPreflightState(state) {
  const stateEl = document.getElementById('policy-preflight-state');
  if (!stateEl) return;
  if (!state || typeof state !== 'object' || !Object.keys(state).length) {
    stateEl.textContent = 'Preflight state not yet initialized.';
    return;
  }
  const mode = state.mode || 'n/a';
  const status = state.status || 'unknown';
  const roles = Array.isArray(state.roles) ? state.roles.join(', ') : 'n/a';
  const updatedAt = state.updated_at || 'n/a';
  stateEl.textContent = `Preflight state: mode=${mode}, status=${status}, roles=[${roles}], updated=${updatedAt}`;
}

function _renderPolicyBackendDecisions(decisions) {
  const el = document.getElementById('policy-backend');
  if (!el) return;
  if (!decisions || typeof decisions !== 'object' || !Object.keys(decisions).length) {
    el.textContent = 'No backend decisions recorded yet.';
    return;
  }
  const rows = Object.entries(decisions).map(([role, d]) => {
    const backend = d.selected_backend || 'n/a';
    const failClosed = d.fail_closed ? 'yes' : 'no';
    const requiresApproval = d.requires_approval ? 'yes' : 'no';
    const fallback = d.fallback_backend || 'none';
    const mode = d.mode || 'n/a';
    const status = d.status || 'n/a';
    const command = Array.isArray(d.command) ? d.command.join(' ') : 'n/a';
    return `<div><strong>${role}</strong>: ${backend} (mode=${mode}, status=${status}, fallback=${fallback}, fail_closed=${failClosed}, requires_approval=${requiresApproval}, command=${command})</div>`;
  }).join('');
  el.innerHTML = `<strong>Backend decisions:</strong><div style=\"margin-top:8px;\">${rows}</div>`;
}

function _populatePreflightDefaults() {
  const roleEl = document.getElementById('policy-pref-role');
  const modelEl = document.getElementById('policy-pref-model');
  const effortEl = document.getElementById('policy-pref-effort');
  if (!roleEl || !modelEl || !effortEl) return;
  if (!modelEl.value) modelEl.value = 'gpt-5.6-luna';
  if (!effortEl.value) effortEl.value = 'medium';
  if (!roleEl.value) roleEl.value = 'executor';
}

function _fillPreflightHintFromRole() {
  const el = document.getElementById('policy-pref-role');
  const out = document.getElementById('policy-pref-hint');
  const auto = document.getElementById('policy-pref-auto');
  if (!el || !out) return;
  const role = el.value || 'executor';
  const autoText = auto?.checked ? 'auto-run will execute probe if output is blank' : 'paste raw output below';
  out.textContent = `Running preflight for role=${role}. ${autoText}.`;
}

function _renderPolicyRepairLoop(policy) {
  const statusEl = document.getElementById('policy-repair-status');
  const cycleEl = document.getElementById('policy-repair-cycle');
  const maxEl = document.getElementById('policy-repair-max-cycles');
  if (!statusEl || !cycleEl || !maxEl) return;
  const repair = policy && typeof policy.repair_loop === 'object' && policy.repair_loop ? policy.repair_loop : {};
  const cycle = repair.cycle == null ? 0 : repair.cycle;
  const maxCycles = repair.max_cycles == null ? 2 : repair.max_cycles;
  statusEl.textContent = `current=${cycle} / max=${maxCycles}`;
  if (cycleEl.value === '') cycleEl.value = String(cycle);
  if (maxEl.value === '') maxEl.value = String(maxCycles);
  cycleEl.value = String(cycle);
  maxEl.value = String(maxCycles);
}

function _renderPolicyTab() {
  _safeRenderPolicySummary(_policy);
  _safeRenderPolicyBudget(_policy ? _policy.token_budget : null);
  _safeRenderPolicyTasks(_policyTasks);
  _safeRenderPolicyTaskDetail(_policyTaskDetail);
  _renderPolicyPreflight(_policyPreflight);
  _renderPolicyBackendDecisions(_policyBackendDecisions);
  _renderPolicyPreflightState(_policyPreflightState);
  _populatePreflightDefaults();
  _fillPreflightHintFromRole();
  _renderPolicyRepairLoop(_policy || {});
}

async function applyPolicyRoute() {
  const select = document.getElementById('policy-route-select');
  const msg = document.getElementById('policy-route-message');
  if (!select) return;
  const route = select.value;
  if (!route) return;
  if (msg) msg.textContent = 'Applying...';
  try {
    const r = await fetch('/api/policy/route', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ route }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok || !body.ok) {
      if (msg) msg.textContent = `Failed: ${body.error || 'request failed'}`;
      return;
    }
    if (msg) msg.textContent = `Applied route: ${route}`;
    await pollPolicy();
  } catch (err) {
    if (msg) msg.textContent = `Failed: ${err.message || 'request failed'}`;
  } finally {
    setTimeout(() => {
      if (msg) msg.textContent = '';
    }, 2500);
  }
}

async function runPolicyPreflight() {
  const roleEl = document.getElementById('policy-pref-role');
  const modelEl = document.getElementById('policy-pref-model');
  const effortEl = document.getElementById('policy-pref-effort');
  const sandboxEl = document.getElementById('policy-pref-sandbox');
  const outputEl = document.getElementById('policy-pref-output');
  const msgEl = document.getElementById('policy-pref-status');
  const autoEl = document.getElementById('policy-pref-auto');

  if (!roleEl || !modelEl || !effortEl || !outputEl) return;
  const role = (roleEl.value || '').trim();
  const model = (modelEl.value || '').trim();
  const effort = (effortEl.value || '').trim();
  const sandbox = (sandboxEl?.value || '').trim() || 'read_only';
  const output = (outputEl.value || '').trim();
  const auto = autoEl ? autoEl.checked : true;
  if (!role || !model || !effort) {
    if (msgEl) msgEl.textContent = 'role/model/effort are required';
    return;
  }
  if (!auto && !output) {
    if (msgEl) msgEl.textContent = 'Paste probe output or enable auto-run.';
    return;
  }

  if (msgEl) msgEl.textContent = 'Submitting...';
  const payload = {
    role,
    model,
    effort,
    sandbox,
  };
  if (output) {
    payload.raw_output = output;
  }
  try {
    const r = await fetch('/api/policy/preflight', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok || !body.ok) {
      if (msgEl) msgEl.textContent = `Failed: ${body.error || 'request failed'}`;
      return;
    }
    if (msgEl) {
      msgEl.textContent = `Preflight status for ${role}: ${body.status}`;
    }
    await pollPolicy();
  } catch (err) {
    if (msgEl) msgEl.textContent = `Failed: ${err.message || 'request failed'}`;
  } finally {
    setTimeout(() => {
      if (msgEl) msgEl.textContent = '';
    }, 2500);
  }
}

async function updatePolicyRepairLoop() {
  const cycleEl = document.getElementById('policy-repair-cycle');
  const maxCyclesEl = document.getElementById('policy-repair-max-cycles');
  const msgEl = document.getElementById('policy-repair-message');
  if (!cycleEl || !maxCyclesEl) return;
  const cycle = cycleEl.value.trim();
  const maxCycles = maxCyclesEl.value.trim();
  if (!cycle && !maxCycles) {
    if (msgEl) msgEl.textContent = 'provide cycle and/or max_cycles';
    return;
  }

  const payload = {};
  if (cycle) payload.cycle = parseInt(cycle, 10);
  if (maxCycles) payload.max_cycles = parseInt(maxCycles, 10);

  if (msgEl) msgEl.textContent = 'Updating...';
  try {
    const r = await fetch('/api/policy/repair', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok || !body.ok) {
      if (msgEl) msgEl.textContent = `Failed: ${body.error || 'request failed'}`;
      return;
    }
    if (msgEl) msgEl.textContent = `Repair cycle updated (${body.repair_loop?.cycle ?? 'n/a'} / ${body.repair_loop?.max_cycles ?? 'n/a'})`;
    if (_policy && _policy.repair_loop && body.repair_loop) {
      _policy.repair_loop = body.repair_loop;
    }
    _renderPolicyRepairLoop(_policy || {});
  } catch (err) {
    if (msgEl) msgEl.textContent = `Failed: ${err.message || 'request failed'}`;
  } finally {
    setTimeout(() => {
      if (msgEl) msgEl.textContent = '';
    }, 2500);
  }
}

function policyPrefRoleChanged() {
  _fillPreflightHintFromRole();
}

window.applyPolicyRoute = applyPolicyRoute;
window.runPolicyPreflight = runPolicyPreflight;
window.policyPrefRoleChanged = policyPrefRoleChanged;
window.updatePolicyRepairLoop = updatePolicyRepairLoop;
window._policy = _policy;
