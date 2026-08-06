(function(){
  window.pollSkills = window.pollSkills || async function() {
    var wrap = document.getElementById('skills');
    if (wrap && !wrap.querySelector('.empty-placeholder')) {
      wrap.innerHTML = '<div class="empty-placeholder">Skills data is unavailable in this bootstrap.</div>';
    }
  };
})();
