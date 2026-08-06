(function(){
  var MAP = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    '/': '&#x2F;'
  };
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"'/]/g, function(ch) {
      return MAP[ch] || ch;
    });
  }
  window.esc = window.esc || esc;
  window.sanitizeHtml = window.sanitizeHtml || esc;
  window.mermaid = window.mermaid || {};
  if (typeof window.mermaid.initialize !== 'function') {
    window.mermaid.initialize = function() {};
  }
  if (typeof window.mermaid.run !== 'function') {
    window.mermaid.run = function() {};
  }
  window.marked = window.marked || {};
  if (typeof window.marked.parse !== 'function') {
    window.marked.parse = function(v) { return String(v || ''); };
  }
  if (typeof window.cytoscape !== 'function') {
    window.cytoscape = function() {
      return {
        layout: function() { return this; },
        run: function() { return this; },
        elements: function() { return []; },
        nodes: function() { return []; },
        edges: function() { return []; }
      };
    };
  }

  window._safeRender = window._safeRender || function(id, renderFn) {
    var element = document.getElementById(id);
    if (!element || typeof renderFn !== 'function') return;
    try {
      renderFn();
    } catch {
      element.innerHTML = '<div class="empty-placeholder">Unable to render this section yet.</div>';
    }
  };
})();
