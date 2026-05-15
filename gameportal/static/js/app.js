/* Файл: static/js/app.js */
/* Общие JS-утилиты и функционал для всего сайта */

// ════════════════════════════════════════════
//  TOAST-уведомления
// ════════════════════════════════════════════
function showToast(msg, duration = 3000) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), duration);
}

// ════════════════════════════════════════════
//  Обновление счётчика онлайна
// ════════════════════════════════════════════
async function updateOnline() {
  try {
    const res = await fetch('/api/online');
    const data = await res.json();
    const el = document.getElementById('online-count');
    if (el) el.textContent = data.online;
  } catch (e) { /* тихо пропускаем */ }
}

// Обновляем счётчик каждые 30 секунд
document.addEventListener('DOMContentLoaded', () => {
  updateOnline();
  setInterval(updateOnline, 30000);
});

// ════════════════════════════════════════════
//  ЛАЙК реплея
// ════════════════════════════════════════════
async function likeReplay(replayId) {
  const btn = document.getElementById('like-btn');
  if (btn && btn.classList.contains('liked')) return; // уже лайкнули

  try {
    const res = await fetch(`/replays/${replayId}/like`, { method: 'POST' });
    if (!res.ok) throw new Error('Error');
    const data = await res.json();
    const countEl = document.getElementById('like-count');
    if (countEl) countEl.textContent = data.likes;
    if (btn) btn.classList.add('liked');
    showToast('❤️ Лайк поставлен!');
  } catch (e) {
    showToast('Ошибка при лайке');
  }
}

// ════════════════════════════════════════════
//  ЗАГРУЗКА РЕПЛЕЯ (форма с прогресс-баром)
// ════════════════════════════════════════════
function initUploadForm() {
  const form = document.getElementById('upload-form');
  const zone = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input');
  const fileNameEl = document.getElementById('file-name');
  const progressBar = document.getElementById('progress-bar');
  const progressFill = document.getElementById('progress-fill');
  const submitBtn = document.getElementById('submit-btn');

  if (!form) return;

  // Клик по зоне = открыть диалог выбора файла
  zone && zone.addEventListener('click', () => fileInput && fileInput.click());

  // Drag and Drop
  zone && zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('dragover');
  });
  zone && zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone && zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file && fileInput) {
      // Устанавливаем файл через DataTransfer
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;
      if (fileNameEl) fileNameEl.textContent = file.name;
    }
  });

  // Показываем имя выбранного файла
  fileInput && fileInput.addEventListener('change', () => {
    if (fileInput.files[0] && fileNameEl) {
      fileNameEl.textContent = fileInput.files[0].name;
    }
  });

  // Отправка формы с XMLHttpRequest для прогресс-бара
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const title = document.getElementById('replay-title').value.trim();
    if (!title) { showToast('Введите название!'); return; }
    if (!fileInput || !fileInput.files[0]) { showToast('Выберите файл!'); return; }

    const formData = new FormData();
    formData.append('title', title);
    formData.append('file', fileInput.files[0]);

    if (submitBtn) submitBtn.disabled = true;
    if (progressBar) progressBar.style.display = 'block';

    const xhr = new XMLHttpRequest();

    // Прогресс загрузки
    xhr.upload.addEventListener('progress', e => {
      if (e.lengthComputable && progressFill) {
        const pct = Math.round((e.loaded / e.total) * 100);
        progressFill.style.width = pct + '%';
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        showToast('✅ Реплей загружен!');
        setTimeout(() => window.location.href = '/replays', 1000);
      } else {
        const err = JSON.parse(xhr.responseText);
        showToast('Ошибка: ' + (err.detail || 'неизвестно'));
        if (submitBtn) submitBtn.disabled = false;
        if (progressBar) progressBar.style.display = 'none';
      }
    });

    xhr.addEventListener('error', () => {
      showToast('Ошибка сети при загрузке');
      if (submitBtn) submitBtn.disabled = false;
      if (progressBar) progressBar.style.display = 'none';
    });

    xhr.open('POST', '/upload-replay');
    xhr.send(formData);
  });
}

// ════════════════════════════════════════════
//  РЕГИСТРАЦИЯ В ТУРНИРЕ
// ════════════════════════════════════════════
function initTournamentRegistration() {
  const form = document.getElementById('register-form');
  if (!form) return;
  const msgEl = document.getElementById('reg-message');

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const tournamentId = form.dataset.tournamentId;
    const nickname = document.getElementById('reg-nickname').value.trim();
    if (!nickname) { showToast('Введите никнейм!'); return; }

    try {
      const res = await fetch(`/tournaments/${tournamentId}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nickname }),
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`✅ ${nickname} зарегистрирован!`);
        if (msgEl) { msgEl.className = 'alert alert-success'; msgEl.textContent = `Участник "${nickname}" добавлен!`; }
        document.getElementById('reg-nickname').value = '';
        // Обновляем список участников
        setTimeout(() => location.reload(), 1200);
      } else {
        showToast('Ошибка: ' + (data.detail || 'неизвестно'));
      }
    } catch (err) {
      showToast('Ошибка сети');
    }
  });
}

// ════════════════════════════════════════════
//  СОЗДАНИЕ ТУРНИРА (admin)
// ════════════════════════════════════════════
function initCreateTournament() {
  const form = document.getElementById('create-tournament-form');
  if (!form) return;

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const payload = {
      name:             document.getElementById('t-name').value.trim(),
      game:             document.getElementById('t-game').value.trim(),
      max_participants: parseInt(document.getElementById('t-max').value) || 16,
      admin_token:      document.getElementById('t-token').value.trim(),
    };
    if (!payload.name || !payload.game || !payload.admin_token) {
      showToast('Заполните все поля!'); return;
    }

    try {
      const res = await fetch('/tournaments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok) {
        showToast('✅ Турнир создан!');
        setTimeout(() => window.location.href = `/tournaments/${data.id}`, 1000);
      } else {
        showToast('Ошибка: ' + (data.detail || 'неизвестно'));
      }
    } catch (err) {
      showToast('Ошибка сети');
    }
  });
}

// ════════════════════════════════════════════
//  АНКЕТА ТИММЕЙТА
// ════════════════════════════════════════════
function initTeammateForm() {
  const form = document.getElementById('teammate-form');
  if (!form) return;

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const payload = {
      nickname:    document.getElementById('tm-nick').value.trim(),
      game:        document.getElementById('tm-game').value.trim(),
      rank:        document.getElementById('tm-rank').value.trim(),
      description: document.getElementById('tm-desc').value.trim(),
    };
    if (!payload.nickname || !payload.game) {
      showToast('Никнейм и игра обязательны!'); return;
    }

    try {
      const res = await fetch('/teammates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        showToast('✅ Анкета добавлена!');
        setTimeout(() => location.reload(), 1000);
      } else {
        const data = await res.json();
        showToast('Ошибка: ' + (data.detail || 'неизвестно'));
      }
    } catch (err) {
      showToast('Ошибка сети');
    }
  });
}

// ════════════════════════════════════════════
//  ФИЛЬТР ТИММЕЙТОВ
// ════════════════════════════════════════════
function initTeammateFilter() {
  const filterBtn = document.getElementById('filter-btn');
  const filterInput = document.getElementById('filter-game');
  if (!filterBtn || !filterInput) return;

  filterBtn.addEventListener('click', () => {
    const game = filterInput.value.trim();
    const url = new URL(window.location.href);
    if (game) url.searchParams.set('game', game);
    else url.searchParams.delete('game');
    window.location.href = url.toString();
  });

  filterInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') filterBtn.click();
  });
}

// ════════════════════════════════════════════
//  WebSocket ЧАТ
// ════════════════════════════════════════════
function initChat() {
  const messagesEl = document.getElementById('chat-messages');
  if (!messagesEl) return;

  const nickInput    = document.getElementById('chat-nick');
  const textInput    = document.getElementById('chat-text');
  const sendBtn      = document.getElementById('chat-send');
  const statusEl     = document.getElementById('chat-status-text');

  // Определяем протокол WebSocket (ws или wss)
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${proto}://${location.host}/ws/chat`;

  let ws = null;
  let reconnectTimer = null;

  function setStatus(text, connected) {
    if (statusEl) {
      statusEl.textContent = text;
      statusEl.style.color = connected ? 'var(--success)' : 'var(--text-muted)';
    }
  }

  function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setStatus('● онлайн', true);
      clearTimeout(reconnectTimer);
    };

    ws.onclose = () => {
      setStatus('○ переподключение...', false);
      reconnectTimer = setTimeout(connect, 3000); // авто-реконнект через 3с
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        appendMessage(msg.nickname, msg.text, msg.time);
      } catch (e) { /* ignore */ }
    };
  }

  function appendMessage(nick, text, time) {
    const div = document.createElement('div');
    div.className = 'chat-msg';
    div.innerHTML = `
      <div class="chat-msg-header">
        <span class="chat-msg-nick">${escapeHtml(nick)}</span>
        <span class="chat-msg-time">${escapeHtml(time)}</span>
      </div>
      <div class="chat-msg-text">${escapeHtml(text)}</div>
    `;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight; // скролл вниз
  }

  function sendMessage() {
    const nick = (nickInput && nickInput.value.trim()) || 'Аноним';
    const text = textInput && textInput.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ nickname: nick, text }));
    if (textInput) textInput.value = '';
  }

  sendBtn && sendBtn.addEventListener('click', sendMessage);
  textInput && textInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  // Сохраняем никнейм в localStorage
  if (nickInput) {
    nickInput.value = localStorage.getItem('chat_nick') || '';
    nickInput.addEventListener('input', () => localStorage.setItem('chat_nick', nickInput.value));
  }

  connect();
}

// Экранирование HTML для безопасного вывода
function escapeHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

// ════════════════════════════════════════════
//  ИНИЦИАЛИЗАЦИЯ
// ════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  initUploadForm();
  initTournamentRegistration();
  initCreateTournament();
  initTeammateForm();
  initTeammateFilter();
  initChat();
});
