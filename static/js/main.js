// Файл: static/js/main.js
// Общий JS для всего сайта: тосты, навбар, онлайн-счётчик

// ── Тост-уведомления ────────────────────────────
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
  // Автоудаление через 3 секунды
  setTimeout(() => {
    toast.style.animation = 'none';
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
};

// ── Мобильное меню (бургер) ─────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const burger = document.querySelector('.burger');
  const nav    = document.querySelector('.navbar-nav');
  if (burger && nav) {
    burger.addEventListener('click', () => nav.classList.toggle('open'));
    // Закрываем при клике на ссылку
    nav.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => nav.classList.remove('open'));
    });
  }

  // ── Подсвечиваем активный пункт меню ──────────
  const path = window.location.pathname;
  document.querySelectorAll('.navbar-nav a').forEach(a => {
    if (a.getAttribute('href') === path ||
        (path.startsWith(a.getAttribute('href')) && a.getAttribute('href') !== '/')) {
      a.classList.add('active');
    }
  });

  // ── Обновляем онлайн-счётчик каждые 30 сек ────
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
