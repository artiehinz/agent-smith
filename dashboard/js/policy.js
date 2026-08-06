let _policy = null;
let _policyTasks = null;
let _policyPreflight = null;
let _policyBackendDecisions = null;

async function pollPolicy() {
  try {
    const [policyRes, tasksRes, preflightRes] = await Promise.all([
      fetch('/api/policy'),
      fetch('/api/policy/tasks'),
      fetch('/api/policy/preflight'),
    ]);

    _policy = policyRes.ok ? await policyRes.json() : null;
    const taskPayload = tasksRes.ok ? await tasksRes.json() : null;
    _policyTasks = taskPayload && taskPayload.ok ? (taskPayload.tasks || []) : [];

    const preflightPayload = preflightRes.ok ? await preflightRes.json() : {};
    _policyPreflight = preflightPayload && preflightPayload.ok ? (preflightPayload.preflight || {}) : {};
    _policyBackendDecisions = preflightPayload && preflightPayload.ok ? (preflightPayload.backend_decisions || {}) : {};

    _renderPolicyTab();
  } catch (err) {
    // Keep policy tab resilient while no scan is active yet.
    console.warn('[policy] refresh failed', err?.message || err);
  }
}

function _policyStatusIcon(status) {
  if (status === 'complete') return '[done]';
  if (status === 'in_progress' || status === 'running') return '[active]';
  if (status === 'incomplete_with_unresolved_blockers') return '[warn]';
  return '[idle]';
}

function _safeRenderPolicySummary(sessionPolicy) {
  const el = document.getElementById('policy-summary');
  if (!el) return;
  if (!sessionPolicy || !Object.keys(sessionPolicy).length) {
    el.textContent = 'No policy blob on this session yet.';
    return;
  }

  const route = sessionPolicy.route || 'n/a';
  const score = sessionPolicy.score == null ? 'n/a' : sessionPolicy.score;
  const routeHint = sessionPolicy.route_hint || 'n/a';
  const override = sessionPolicy.override_applied ? 'yes' : 'no';
  const engine = sessionPolicy.policy_engine || 'n/a';

  el.innerHTML = `
    <div><strong>Route:</strong> ${route}</div>
    <div><strong>Route hint:</strong> ${routeHint}</div>
    <div><strong>Score:</strong> ${score}</div>
    <div><strong>Override applied:</strong> ${override}</div>
    <div><strong>Engine:</strong> ${engine}</div>
    <div><strong>Rationale:</strong> ${(sessionPolicy.rationale || []).join(', ') || 'n/a'}</div>
  `;

  const current = document.getElementById('policy-route-current');
  if (current) current.textContent = `Current route: ${route}`;

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
  const body = policyTasks.slice(0, 12).map((task) => {
    const status = task.status || 'unknown';
    const route = task.route || 'unknown';
    const owner = task.owner_role || 'unknown';
    return `<div><strong>${_policyStatusIcon(status)} ${task.task_id}</strong> - route=${route} owner=${owner} status=${status}</div>`;
  }).join('');
  el.innerHTML = body;
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
    const intended = result.intended || {};
    const actual = result.actual || {};
    const mismatch = status !== 'match';
    return `<div>
      <div><strong>${role}</strong> - status: ${status} ${mismatch ? '(warning)' : ''}</div>
      <div>Intended: ${intended.model || 'n/a'} / ${intended.effort || 'n/a'} (${intended.sandbox || 'read_only'})</div>
      <div>Actual: ${actual.model || 'n/a'} / ${actual.effort || 'n/a'} (${actual.sandbox || 'n/a'})</div>
      ${result.parse_error ? `<div>Parse error: ${result.parse_error}</div>` : ''}
    </div>`;
  }).join('<hr/>');
  el.innerHTML = `<strong>Model attestation:</strong><div style=\"margin-top:8px;\">${rows}</div>`;
  if (msgEl) msgEl.textContent = `Loaded ${Object.keys(summary).length} preflight role(s).`;
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
    return `<div><strong>${role}</strong>: ${backend} (fail_closed=${failClosed})</div>`;
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
  if (!el || !out) return;
  const role = el.value || 'executor';
  out.textContent = `Running preflight for role=${role}. Paste probe output into the box.`;
}

function _renderPolicyTab() {
  _safeRenderPolicySummary(_policy);
  _safeRenderPolicyBudget(_policy ? _policy.token_budget : null);
  _safeRenderPolicyTasks(_policyTasks);
  _renderPolicyPreflight(_policyPreflight);
  _renderPolicyBackendDecisions(_policyBackendDecisions);
  _populatePreflightDefaults();
  _fillPreflightHintFromRole();
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

  if (!roleEl || !modelEl || !effortEl || !outputEl) return;
  const role = (roleEl.value || '').trim();
  const model = (modelEl.value || '').trim();
  const effort = (effortEl.value || '').trim();
  const sandbox = (sandboxEl?.value || '').trim() || 'read_only';
  const output = (outputEl.value || '').trim();
  if (!role || !model || !effort) {
    if (msgEl) msgEl.textContent = 'role/model/effort are required';
    return;
  }
  if (!output) {
    if (msgEl) msgEl.textContent = 'Paste probe output to run preflight.';
    return;
  }

  if (msgEl) msgEl.textContent = 'Submitting...';
  try {
    const r = await fetch('/api/policy/preflight', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        role,
        model,
        effort,
        sandbox,
        raw_output: output,
      }),
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

function policyPrefRoleChanged() {
  _fillPreflightHintFromRole();
}

window.applyPolicyRoute = applyPolicyRoute;
window.runPolicyPreflight = runPolicyPreflight;
window.policyPrefRoleChanged = policyPrefRoleChanged;
window._policy = _policy;
