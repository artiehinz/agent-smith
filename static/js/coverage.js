(function(){
  window.pollCoverage = window.pollCoverage || async function() {
    var wrap = document.getElementById('coverage');
    if (wrap && !wrap.querySelector('.empty-placeholder')) {
      wrap.innerHTML = '<div class="empty-placeholder">Coverage data is unavailable in this bootstrap.</div>';
    }
  };
})();
