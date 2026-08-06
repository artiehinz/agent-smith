(function(){
  window.pollQA = window.pollQA || async function() {
    window._safeRender = window._safeRender || function(id, renderFn) {
      var el = document.getElementById(id);
      if (!el || typeof renderFn !== 'function') return;
      try { renderFn(); } catch (e) { el.innerHTML = '<div class="empty-placeholder">Unable to render activity right now.</div>'; }
    };
    window.renderQA = window.renderQA || function() {
      var el = document.getElementById('qa');
      if (el) el.innerHTML = '<div class="empty-placeholder">QA feed unavailable.</div>';
    };
    window.renderSteering = window.renderSteering || function() {
      var el = document.getElementById('steering');
      if (el) el.innerHTML = '<div class="empty-placeholder">Steering feed unavailable.</div>';
    };
    window.renderQuickLog = window.renderQuickLog || function() {
      var el = document.getElementById('quick-log');
      if (el) el.innerHTML = '<div class="empty-placeholder">Quick log unavailable.</div>';
    };
    window.renderCycleHistory = window.renderCycleHistory || function() {
      var el = document.getElementById('cycle-history');
      if (el) el.innerHTML = '<div class="empty-placeholder">Cycle history unavailable.</div>';
    };
    window.renderAdjudicationLog = window.renderAdjudicationLog || function() {
      var el = document.getElementById('adjudication-log');
      if (el) el.innerHTML = '<div class="empty-placeholder">Adjudication log unavailable.</div>';
    };
  };
})();
