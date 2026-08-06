(function(){
  window.renderComponentMap = window.renderComponentMap || function() {
    var wrap = document.getElementById('components');
    if (wrap && !wrap.querySelector('.empty-placeholder')) {
      wrap.innerHTML = '<div class="empty-placeholder">Component map is unavailable in this bootstrap.</div>';
    }
  };
})();
