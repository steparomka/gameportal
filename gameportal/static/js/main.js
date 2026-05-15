window.showToast = function(message, type) {
  type = type || 'info';
  var container = document.getElementById('toast-container');
  if (!container) return;
  var toast = document.createElement('div');
  toast.className = 'toast';
  var icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  toast.innerHTML = (icons[type] || '') + ' ' + message;
  container.appendChild(toast);
  setTimeout(function() {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(function() { toast.remove(); }, 300);
  }, 3000);
};

(function() {
  var saved = localStorage.getItem('gp-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
})();

document.addEventListener('DOMContentLoaded', function() {
  var btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.onclick = function() {
      var current = document.documentElement.getAttribute('data-theme');
      var next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('gp-theme', next);
      showToast(next === 'light' ? '☀️ Сила Света активирована!' : '🔴 Сила Тьмы активирована!', 'info');
    };
  }

  function updateOnline() {
    fetch('/api/online')
      .then(function(r) { return r.json(); })
      .then(function(d) {
        var el = document.getElementById('online-count');
        if (el) el.textContent = d.online;
      }).catch(function() {});
  }
  updateOnline();
  setInterval(updateOnline, 30000);
});