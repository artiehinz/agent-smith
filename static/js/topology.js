(function(){
  window.renderTopology = window.renderTopology || function() {
    var wrap = document.getElementById('topology');
    if (wrap && !wrap.querySelector('.empty-placeholder')) {
      wrap.innerHTML = '<div class="empty-placeholder">Topology view is unavailable in this bootstrap.</div>';
    }
  };
})();
