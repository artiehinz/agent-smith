// policy/policy.js
// Dedicated policy-page script scaffold.
// The dashboard currently exposes the route-policy data through /api/policy.
(() => {
  window.policyApi = {
    async get() {
      const r = await fetch('/api/policy');
      if (!r.ok) {
        throw new Error('policy endpoint unavailable');
      }
      return r.json();
    },
    async tasks() {
      const r = await fetch('/api/policy/tasks');
      if (!r.ok) {
        throw new Error('policy tasks endpoint unavailable');
      }
      return r.json();
    },
  };
})();
