(function(){
  window.pollThreatModel = window.pollThreatModel || async function() {
    var wrap = document.getElementById('threat-model');
    if (wrap && !wrap.querySelector('.empty-placeholder')) {
      wrap.innerHTML = '<div class="empty-placeholder">Threat model is unavailable in this bootstrap.</div>';
    }
  };
})();
