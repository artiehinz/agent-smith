(function(){
  window.pollSetupGates = window.pollSetupGates || async function() {
    var wrap = document.getElementById('setup-gates');
    if (wrap && !wrap.querySelector('.empty-placeholder')) {
      wrap.innerHTML = '<div class="empty-placeholder">Setup gates are unavailable in this bootstrap.</div>';
    }
  };
})();
