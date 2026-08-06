(function(){
  window.pollMetrics = window.pollMetrics || async function() {
    var wrap = document.getElementById('metrics');
    if (wrap && !wrap.querySelector('.empty-placeholder')) {
      wrap.innerHTML = '<div class="empty-placeholder">Metrics are unavailable in this bootstrap.</div>';
    }
  };
})();
