(function() {
  var saved = localStorage.getItem('gp-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
})();

window.showToast = function(message) {
  var container = document.getElementById('toast-container');
  if (!container) return;
  var toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = message;
  container.appendChild(toast);
  setTimeout(function() { toast.remove(); }, 3000);
};

window.onload = function() {
  var btn = document.querySelector('.theme-toggle');
  if (btn) {
    btn.onclick = function() {
      var c = document.documentElement.getAttribute('data-theme');
      var n = c === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', n);
      localStorage.setItem('gp-theme', n);
      window.showToast(n === 'light' ? '☀️ Сила Света!' : '🔴 Сила Тьмы!');
    };
  }

  var burger = document.querySelector('.burger');
  var nav = document.querySelector('.navbar-nav');
  if (burger && nav) {
    burger.onclick = function() { nav.classList.toggle('open'); };
  }

  var path = window.location.pathname;
  var links = document.querySelectorAll('.navbar-nav a');
  for (var i = 0; i < links.length; i++) {
    if (links[i].getAttribute('href') === path) {
      links[i].classList.add('active');
    }
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
};
