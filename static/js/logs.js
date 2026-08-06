(function(){
  window.pollLogs = window.pollLogs || async function() {
    var wrap = document.getElementById('logs');
    if (wrap && !wrap.querySelector('.empty-placeholder')) {
      wrap.innerHTML = '<div class="empty-placeholder">Logs are unavailable in this bootstrap.</div>';
    }
  };
})();
