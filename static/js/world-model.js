(function(){
  window.pollWorldModel = window.pollWorldModel || async function() {
    var wrap = document.getElementById('world-model');
    if (wrap && !wrap.querySelector('.empty-placeholder')) {
      wrap.innerHTML = '<div class="empty-placeholder">World model data is unavailable in this bootstrap.</div>';
    }
  };
})();
