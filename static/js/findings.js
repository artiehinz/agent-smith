(function(){
  window.pollFindings = window.pollFindings || async function() {
    if (typeof window._safeRender === 'function') {
      window._safeRender('findings', window.renderFindings || function() {
        var wrap = document.getElementById('findings');
        if (wrap) {
          wrap.innerHTML = '<div class="empty-placeholder">No findings available yet.</div>';
        }
      });
    }
  };
  window.renderFindings = window.renderFindings || function() {
    var wrap = document.getElementById('findings');
    if (wrap && !wrap.querySelector('.empty-placeholder')) {
      wrap.innerHTML = '<div class="empty-placeholder">No findings available yet.</div>';
    }
  };
})();
