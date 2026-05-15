// Файл: static/js/main.js
// Общий JS: тосты, навбар, онлайн-счётчик, переключатель тем

// ── Тосты ───────────────────────────────────────────────
window.showToast = function(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  toast.innerHTML = `${icons[type] || ''} ${message}`;
  toast.style.borderColor = {
    success: 'rgba(16,185,129,0.3)',
    error:   'rgba(239,68,68,0.3)',
    info:    'rgba(0,212,255,0.2)',
  }[type] || '';
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
};

// ── Переключатель тем Свет/Тьма ─────────────────────────
(function() {
  // Загружаем сохранённую тему из localStorage
  const saved = localStorage.getItem('gp-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;

    btn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';

      // Плавный переход
      document.documentElement.style.transition = 'background-color 0.4s ease, color 0.4s ease';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('gp-theme', next);

      // Тост с названием темы
      if (next === 'light') {
        showToast('☀️ Сила Света активирована!', 'info');
      } else {
        showToast('🔴 Сила Тьмы активирована!', 'info');
      }
    });
  });
})();

// ── Мобильное меню ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const burger = document.querySelector('.burger');
  const nav    = document.querySelector('.navbar-nav');
  if (burger && nav) {
    burger.addEventListener('click', () => nav.classList.toggle('open'));
    nav.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => nav.classList.remove('open'));
    });
  }

  // Активный пункт меню
  const path = window.location.pathname;
  document.querySelectorAll('.navbar-nav a').forEach(a => {
    if (a.getAttribute('href') === path ||
        (path.startsWith(a.getAttribute('href')) && a.getAttribute('href') !== '/')) {
      a.classList.add('active');
    }
  });

  // Обновляем онлайн каждые 30 сек
  async function updateOnline() {
    try {
      const r = await fetch('/api/online');
      const d = await r.json();
      const el = document.getElementById('online-count');
      if (el) el.textContent = d.online;
    } catch (_) {}
  }
  updateOnline();
  setInterval(updateOnline, 30000);
});
