// Файл: static/js/main.js

window.showToast = function(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  toast.innerHTML = `${icons[type] || ''} ${message}`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
};

// Тема — запускается сразу, до DOMContentLoaded
(function() {
  var saved = localStorage.getItem('gp-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
})();

document.addEventListener('DOMContentLoaded', function() {

  // Переключатель темы
  var btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.onclick = function() {
      var current = document.documentElement.getAttribute('data-theme');
      var next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('gp-theme', next);
      if (next === 'light') {
        showToast('☀️ Сила Света активирована!', 'info');
      } else {
        showToast('🔴 Сила Тьмы активирована!', 'info');
      }
    };
  }

  // Онлайн
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

  // Пользователь
  fetch('/api/me')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.logged_in) {
        var navUser = document.getElementById('navbar-user');
        var navAvatar = document.getElementById('navbar-avatar');
        if (navUser && navAvatar) {
          navAvatar.src = d.avatar;
          navUser.style.display = 'block';
        }
        var profile = document.getElementById('burger-profile');
        if (profile) {
          document.getElementById('burger-avatar').src = d.avatar;
          document.getElementById('burger-username').textContent = d.nickname;
          document.getElementById('burger-steamid').textContent = 'Steam ID: ' + d.steam_id;
          profile.style.display = 'flex';
        }
        document.getElementById('steam-login-btn').style.display = 'none';
        document.getElementById('steam-logout-btn').style.display = 'flex';
      }
    }).catch(function() {});

});