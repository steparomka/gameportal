/* Файл: static/js/main.js */

/* ── Тема: применяем до рендера, чтобы не было мигания ── */
(function () {
  var saved = localStorage.getItem('gp-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
})();


/* ── Всё остальное — после загрузки DOM ── */
window.addEventListener('DOMContentLoaded', function () {

  /* ── Переключатель тем ── */
  var themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var cur  = document.documentElement.getAttribute('data-theme');
      var next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('gp-theme', next);
      window.showToast(next === 'light' ? '☀️ Сила Света!' : '🔴 Сила Тьмы!');
    });
  }

  /* ── Бургер-меню ── */
  var burger     = document.getElementById('burger');
  var burgerMenu = document.getElementById('burgerMenu');

  if (burger && burgerMenu) {
    burger.addEventListener('click', function (e) {
      e.stopPropagation();
      burger.classList.toggle('open');
      burgerMenu.classList.toggle('open');
    });

    /* Закрыть при клике вне */
    document.addEventListener('click', function (e) {
      if (!burger.contains(e.target) && !burgerMenu.contains(e.target)) {
        burger.classList.remove('open');
        burgerMenu.classList.remove('open');
      }
    });

    /* Закрыть при нажатии Escape */
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        burger.classList.remove('open');
        burgerMenu.classList.remove('open');
      }
    });
  }

  /* ── Активная ссылка в navbar и burger-dropdown ── */
  var path  = window.location.pathname;
  var links = document.querySelectorAll('.navbar-nav a, .burger-dropdown a');
  links.forEach(function (a) {
    if (a.getAttribute('href') === path) a.classList.add('active');
  });

  /* ── Счётчик онлайн (обновляем каждые 30 сек) ── */
  function updateOnline() {
    fetch('/api/online')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var el = document.getElementById('online-count');
        if (el) el.textContent = d.online;
      })
      .catch(function () {});
  }
  updateOnline();
  setInterval(updateOnline, 30000);

});


/* ── Toast-уведомления ── */
window.showToast = function (message, duration) {
  var container = document.getElementById('toast-container');
  if (!container) return;

  var toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = message;
  container.appendChild(toast);

  setTimeout(function () {
    toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    toast.style.opacity    = '0';
    toast.style.transform  = 'translateX(20px)';
    setTimeout(function () { toast.remove(); }, 320);
  }, duration || 3000);
};