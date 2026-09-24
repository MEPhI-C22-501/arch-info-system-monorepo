/*
 * Task Tracker — live-прототип (документ 115, см. docs/block-e-ui-ux-design/).
 * Чистый JS без сборки/зависимостей: вся логика — имитация поведения, описанного
 * в vision.md / system-requirements.md / docs/block-*, с данными в памяти вкладки.
 *
 * Это макет для проверки UI/UX-гипотез, а не рабочее приложение: нет ни бэкенда,
 * ни настоящего провайдера аутентификации/Excel/брокера сообщений — переключатель роли имитирует то,
 * что в реальной системе определяется токеном и правами на сервере (NFR-003).
 */

(function () {
  "use strict";

  /* ============================== ДАННЫЕ (мок) ============================== */

  const USERS = [
    { id: "u1", name: "Иван Петров", team: "Backend", dept: "Разработка", active: true, initials: "ИП" },
    { id: "u2", name: "Мария Сидорова", team: "Frontend", dept: "Разработка", active: true, initials: "МС" },
    { id: "u3", name: "Алексей Ким", team: "QA", dept: "Качество", active: true, initials: "АК" },
    { id: "u4", name: "Ольга Новак", team: "Backend", dept: "Разработка", active: true, initials: "ОН" },
    { id: "u5", name: "Дмитрий Волков", team: "Управление", dept: "Управление", active: true, initials: "ДВ" },
    { id: "admin1", name: "Администратор", team: "—", dept: "Управление доступом", active: true, initials: "АД" },
  ];

  const PRIORITIES = ["Критический", "Высокий", "Средний", "Низкий"];
  const TYPES = ["Проект", "Эпик", "Задача", "Ошибка", "Подзадача"];

  let STATUSES = [
    { id: "s1", name: "Бэклог", order: 1, active: true, onBoard: true },
    { id: "s2", name: "В работе", order: 2, active: true, onBoard: true },
    { id: "s3", name: "На проверке", order: 3, active: true, onBoard: true },
    { id: "s4", name: "Завершена", order: 4, active: true, onBoard: true },
    { id: "s5", name: "Архивирована", order: 5, active: true, onBoard: false },
  ];

  let ITERATIONS = [
    {
      id: "it1", name: "Спринт 24.09 — Личный кабинет", description: "Активная итерация",
      startDate: "2026-09-15", endDate: "2026-09-28", state: "Активна",
      capacities: [{ userId: "u1", hours: 40 }, { userId: "u2", hours: 40 }, { userId: "u3", hours: 24 }, { userId: "u4", hours: 32 }],
      baseline: null,
    },
    {
      id: "it2", name: "Спринт 24.08 — Инфраструктура", description: "Завершённая итерация",
      startDate: "2026-08-18", endDate: "2026-08-31", state: "Завершена",
      capacities: [{ userId: "u1", hours: 40 }, { userId: "u3", hours: 24 }],
      baseline: { totalPlanned: 10, itemIds: ["TT-10", "TT-12"] },
    },
    {
      id: "it3", name: "Спринт 24.10 — Планируется", description: "Запланированная итерация",
      startDate: "2026-09-29", endDate: "2026-10-12", state: "Запланирована",
      capacities: [{ userId: "u1", hours: 40 }, { userId: "u2", hours: 40 }, { userId: "u4", hours: 32 }],
      baseline: null,
    },
  ];

  let nextCode = 15;

  let WORK_ITEMS = [
    { code: "TT-1", type: "Проект", title: "Личный кабинет клиента", description: "Верхнеуровневая инициатива по личному кабинету.", statusId: "s2", priorityId: "Средний", assigneeId: "u5", startDate: "2026-09-01", dueDate: "2026-11-30", plannedHours: null, parentCode: null, iterationId: null },
    { code: "TT-2", type: "Эпик", title: "Аутентификация и профиль", description: "Вход, восстановление доступа, профиль пользователя.", statusId: "s2", priorityId: "Высокий", assigneeId: "u2", startDate: "2026-09-01", dueDate: "2026-09-30", plannedHours: null, parentCode: "TT-1", iterationId: null },
    { code: "TT-3", type: "Задача", title: "Форма входа по email", description: "Экран входа: email + пароль, обработка ошибок аутентификации.", statusId: "s2", priorityId: "Высокий", assigneeId: "u2", startDate: "2026-09-15", dueDate: "2026-09-22", plannedHours: 8, parentCode: "TT-2", iterationId: "it1" },
    { code: "TT-4", type: "Подзадача", title: "Вёрстка формы", description: "Адаптивная вёрстка формы входа.", statusId: "s4", priorityId: "Средний", assigneeId: "u2", startDate: "2026-09-15", dueDate: "2026-09-17", plannedHours: 3, parentCode: "TT-3", iterationId: "it1" },
    { code: "TT-5", type: "Подзадача", title: "Валидация полей", description: "Клиентская и серверная валидация формы входа.", statusId: "s2", priorityId: "Средний", assigneeId: "u2", startDate: "2026-09-18", dueDate: "2026-09-20", plannedHours: 2, parentCode: "TT-3", iterationId: "it1" },
    { code: "TT-6", type: "Задача", title: "Восстановление пароля", description: "Сценарий восстановления пароля по email-ссылке.", statusId: "s1", priorityId: "Средний", assigneeId: "u1", startDate: "", dueDate: "", plannedHours: 5, parentCode: "TT-2", iterationId: null },
    { code: "TT-7", type: "Ошибка", title: "Сессия сбрасывается при обновлении страницы", description: "Найдено автотестами: после F5 пользователь разлогинивается.", statusId: "s3", priorityId: "Критический", assigneeId: "u1", startDate: "2026-09-16", dueDate: "2026-09-19", plannedHours: 4, parentCode: "TT-2", iterationId: "it1", externalSource: "test-management", externalDefectId: "TM-4821" },
    { code: "TT-8", type: "Эпик", title: "Профиль пользователя", description: "Просмотр и редактирование профиля.", statusId: "s1", priorityId: "Низкий", assigneeId: "u4", startDate: "", dueDate: "", plannedHours: null, parentCode: "TT-1", iterationId: null },
    { code: "TT-9", type: "Задача", title: "Страница профиля", description: "Отображение и редактирование основных полей профиля.", statusId: "s1", priorityId: "Низкий", assigneeId: "u4", startDate: "", dueDate: "", plannedHours: 6, parentCode: "TT-8", iterationId: null },
    { code: "TT-10", type: "Задача", title: "Настроить CI-пайплайн для деплоя", description: "Пайплайн сборки и деплоя Core в стенд.", statusId: "s4", priorityId: "Средний", assigneeId: "u3", startDate: "2026-08-18", dueDate: "2026-08-25", plannedHours: 6, parentCode: null, iterationId: "it2" },
    { code: "TT-11", type: "Ошибка", title: "Экспорт зависает на большом файле", description: "При выгрузке >5000 строк запрос не завершается.", statusId: "s2", priorityId: "Высокий", assigneeId: "u4", startDate: "2026-09-16", dueDate: "2026-09-23", plannedHours: 3, parentCode: null, iterationId: "it1" },
    { code: "TT-12", type: "Задача", title: "Настройка мониторинга", description: "Базовые дашборды и алерты для стенда.", statusId: "s4", priorityId: "Средний", assigneeId: "u1", startDate: "2026-08-19", dueDate: "2026-08-29", plannedHours: 4, parentCode: null, iterationId: "it2" },
    { code: "TT-13", type: "Задача", title: "Подготовить отчёт по итерации", description: "Свод показателей для ретро.", statusId: "s1", priorityId: "Низкий", assigneeId: "u5", startDate: "", dueDate: "", plannedHours: 2, parentCode: null, iterationId: "it1" },
  ];

  let TIMELOGS = [
    { workItemCode: "TT-4", userId: "u2", date: "2026-09-15", hours: 2, comment: "" },
    { workItemCode: "TT-4", userId: "u2", date: "2026-09-16", hours: 1.5, comment: "Доп. правки по адаптиву" },
    { workItemCode: "TT-5", userId: "u2", date: "2026-09-18", hours: 0, comment: "" },
    { workItemCode: "TT-7", userId: "u1", date: "2026-09-16", hours: 2, comment: "" },
    { workItemCode: "TT-7", userId: "u1", date: "2026-09-17", hours: 2.5, comment: "Отладка на стенде" },
    { workItemCode: "TT-10", userId: "u3", date: "2026-08-20", hours: 6, comment: "" },
    { workItemCode: "TT-11", userId: "u4", date: "2026-09-17", hours: 1, comment: "" },
    { workItemCode: "TT-12", userId: "u1", date: "2026-08-21", hours: 3, comment: "" },
    { workItemCode: "TT-12", userId: "u1", date: "2026-08-27", hours: 2, comment: "Донастройка алертов" },
  ];

  let COMMENTS = [
    { id: "c1", workItemCode: "TT-3", authorId: "u2", text: "Макет формы согласован с UI/UX прототипом, приступаю к вёрстке.", createdAt: "2026-09-15T10:12:00" },
    { id: "c2", workItemCode: "TT-7", authorId: "u5", text: "Критично — переносим в начало спринта.", createdAt: "2026-09-16T09:00:00" },
    { id: "c3", workItemCode: "TT-7", authorId: "u1", text: "Воспроизвёл, причина — некорректный refresh токена. Правлю.", createdAt: "2026-09-16T14:20:00" },
  ];

  let ATTACHMENTS = [
    { id: "a1", workItemCode: "TT-3", fileName: "макет-формы-входа.png", size: "412 КБ", uploadedBy: "u2", uploadedAt: "2026-09-15T11:00:00" },
    { id: "a2", workItemCode: "TT-7", fileName: "лог-ошибки.txt", size: "18 КБ", uploadedBy: "u1", uploadedAt: "2026-09-16T14:05:00" },
  ];

  let HISTORY = [
    { id: "h1", workItemCode: "TT-7", actor: "Сервис тестирования (внешний ID: TM-4821)", occurredAt: "2026-09-16T08:00:00", changes: [{ field: "Элемент", from: "—", to: "Создан из внешнего источника" }, { field: "Приоритет", from: "—", to: "Критический (из серьёзности «high»)" }] },
    { id: "h2", workItemCode: "TT-7", actor: "Иван Петров", occurredAt: "2026-09-16T14:20:05", changes: [{ field: "Статус", from: "В работе", to: "На проверке" }] },
    { id: "h3", workItemCode: "TT-3", actor: "Мария Сидорова", occurredAt: "2026-09-15T09:40:00", changes: [{ field: "Статус", from: "Бэклог", to: "В работе" }] },
    { id: "h4", workItemCode: "TT-3", actor: "Дмитрий Волков", occurredAt: "2026-09-14T18:02:00", changes: [{ field: "Плановая трудоёмкость", from: "6 ч", to: "8 ч" }, { field: "Итерация", from: "—", to: "Спринт 24.09 — Личный кабинет" }] },
  ];

  let NOTIFICATIONS = [
    { id: "n1", recipientId: "u2", workItemCode: "TT-3", message: "Вам назначена задача «Форма входа по email»", createdAt: "2026-09-14T18:02:00", readAt: null },
    { id: "n2", recipientId: "u2", workItemCode: "TT-3", message: "Изменена плановая трудоёмкость задачи «Форма входа по email»: 6 ч → 8 ч", createdAt: "2026-09-14T18:02:05", readAt: null },
    { id: "n3", recipientId: "u2", workItemCode: "TT-3", message: "Добавлен комментарий к задаче «Форма входа по email»", createdAt: "2026-09-15T10:12:00", readAt: "2026-09-15T10:30:00" },
    { id: "n4", recipientId: "u1", workItemCode: "TT-7", message: "Статус ошибки «Сессия сбрасывается при обновлении страницы» изменён на «На проверке»", createdAt: "2026-09-16T14:20:05", readAt: null },
    { id: "n5", recipientId: "u5", workItemCode: "TT-13", message: "Вам назначена задача «Подготовить отчёт по итерации»", createdAt: "2026-09-14T12:00:00", readAt: null },
  ];

  let SYNC_LOG = [
    { time: "2026-09-23T09:00:00", ok: false, message: "Сервис справочников недоступен (timeout)" },
    { time: "2026-09-22T09:00:00", ok: true, message: "Синхронизировано: 5 пользователей, 3 команды, 2 подразделения" },
  ];
  let LAST_SYNC_OK_TIME = "2026-09-22T09:00:00";

  /* ============================== СОСТОЯНИЕ ============================== */

  const ROLE_TO_USER = { member: "u2", lead: "u5", admin: "admin1" };
  const ROLE_LABEL = { member: "Участник команды", lead: "Руководитель / планировщик", admin: "Администратор" };

  const state = {
    role: "lead",
    currentUserId: "u5",
    activeScreen: "backlog",
    openItemCode: null,
    activeTab: "attachments",
    descriptionDrafts: {},
    currentIterationId: "it1",
    dragCode: null,
  };

  /* ============================== ХЕЛПЕРЫ ============================== */

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $all = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const byId = (arr, id, key) => arr.find((x) => (x[key || "id"] === id));
  const userName = (id) => (byId(USERS, id) || {}).name || "—";
  const userInitials = (id) => (byId(USERS, id) || {}).initials || "?";
  const statusName = (id) => (byId(STATUSES, id) || {}).name || id;
  const escapeHtml = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDate = (iso) => (iso ? new Date(iso + "T00:00:00").toLocaleDateString("ru-RU") : "—");
  const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
  const fmtHours = (n) => (Math.round(n * 100) / 100).toString().replace(".", ",") + " ч";
  const uid = (p) => p + Math.random().toString(36).slice(2, 8);

  function item(code) { return byId(WORK_ITEMS, code, "code"); }
  function children(code) { return WORK_ITEMS.filter((w) => w.parentCode === code); }
  function isLeaf(code) { return children(code).length === 0; }

  function actualHours(code) {
    if (!isLeaf(code)) return children(code).reduce((s, c) => s + actualHours(c.code), 0);
    return TIMELOGS.filter((t) => t.workItemCode === code).reduce((s, t) => s + Number(t.hours || 0), 0);
  }
  function plannedHours(code) {
    const it = item(code);
    if (!isLeaf(code)) return children(code).reduce((s, c) => s + plannedHours(c.code), 0);
    return Number(it.plannedHours || 0);
  }
  function remainingHours(code) { return plannedHours(code) - actualHours(code); }

  function currentUser() { return byId(USERS, state.currentUserId); }
  function canHardDelete() { return state.role === "admin"; }
  function canExportImport() { return state.role === "lead"; }
  function canCreateItem() { return state.role === "member" || state.role === "lead"; }
  function canEditWorkItem(w) { return state.role === "lead" || (state.role === "member" && w.assigneeId === state.currentUserId); }
  function canCollaborate() { return state.role === "member" || state.role === "lead"; }
  function canManageIterations() { return state.role === "lead"; }

  function toast(message, kind) {
    const el = document.createElement("div");
    el.className = "toast" + (kind ? " " + kind : "");
    el.textContent = message;
    $("#toastContainer").appendChild(el);
    setTimeout(() => el.remove(), 3600);
  }

  function pushHistory(code, actor, changes) {
    HISTORY.unshift({ id: uid("h"), workItemCode: code, actor, occurredAt: new Date().toISOString(), changes });
  }

  function notify(recipientId, workItemCode, message) {
    if (!recipientId) return;
    const workItem = item(workItemCode);
    NOTIFICATIONS.unshift({
      id: uid("n"), recipientId, workItemCode,
      workItemPublicId: workItemCode, workItemTitle: workItem ? workItem.title : "",
      actor: currentUser() ? currentUser().name : ROLE_LABEL[state.role],
      message, createdAt: new Date().toISOString(), readAt: null,
    });
  }

  /* ============================== НАВИГАЦИЯ ============================== */

  function switchScreen(name) {
    state.activeScreen = name;
    $all(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.screen === name));
    $all(".screen").forEach((s) => s.classList.toggle("active", s.id === "screen-" + name));
    if (name === "backlog") renderBacklog();
    if (name === "board") renderBoard();
    if (name === "iteration") renderIteration();
    if (name === "notifications") renderNotifications();
    if (name === "admin") renderAdmin();
  }

  function applyRoleVisibility() {
    const u = currentUser();
    $("#currentUserAvatar").textContent = u ? u.initials : "АД";
    $("#currentUserName").textContent = u ? u.name : "Администратор";
    $("#currentUserRole").textContent = ROLE_LABEL[state.role];
    $("#navAdmin").hidden = state.role !== "admin";
    $("#btnExport").hidden = !canExportImport();
    $("#btnImport").hidden = !canExportImport();
    $("#btnCreateItem").hidden = !canCreateItem();
    if (state.role !== "admin" && state.activeScreen === "admin") switchScreen("backlog");
    if (state.openItemCode) renderItemCard();
  }

  function updateUnreadBadge() {
    const n = NOTIFICATIONS.filter((x) => x.recipientId === state.currentUserId && !x.readAt).length;
    $("#unreadBadge").textContent = n > 0 ? n : "";
  }

  /* ============================== ФИЛЬТРЫ (общие опции) ============================== */

  function fillSelect(sel, options, placeholder) {
    sel.innerHTML = "";
    const ph = document.createElement("option");
    ph.value = ""; ph.textContent = placeholder;
    sel.appendChild(ph);
    options.forEach((o) => {
      const opt = document.createElement("option");
      opt.value = o.value; opt.textContent = o.label;
      sel.appendChild(opt);
    });
  }

  function fillCommonFilterOptions() {
    fillSelect($("#filterType"), TYPES.map((t) => ({ value: t, label: t })), "Тип: все");
    fillSelect($("#filterStatus"), STATUSES.map((s) => ({ value: s.id, label: s.name })), "Статус: все");
    fillSelect($("#filterPriority"), PRIORITIES.map((p) => ({ value: p, label: p })), "Приоритет: все");
    fillSelect($("#filterAssignee"), USERS.map((u) => ({ value: u.id, label: u.name })), "Исполнитель: все");
    fillSelect($("#filterIteration"), ITERATIONS.map((i) => ({ value: i.id, label: i.name })), "Итерация: все");

    fillSelect($("#boardFilterAssignee"), USERS.map((u) => ({ value: u.id, label: u.name })), "Исполнитель: все");
    fillSelect($("#boardFilterPriority"), PRIORITIES.map((p) => ({ value: p, label: p })), "Приоритет: все");
    fillSelect($("#boardFilterIteration"), ITERATIONS.map((i) => ({ value: i.id, label: i.name })), "Итерация: все");
  }

  /* ============================== ЭКРАН: БЭКЛОГ ============================== */

  function renderBacklog() {
    const type = $("#filterType").value, status = $("#filterStatus").value, priority = $("#filterPriority").value;
    const assignee = $("#filterAssignee").value, iteration = $("#filterIteration").value;
    const search = $("#filterSearch").value.trim().toLowerCase();

    const rows = WORK_ITEMS.filter((w) =>
      (!type || w.type === type) &&
      (!status || w.statusId === status) &&
      (!priority || w.priorityId === priority) &&
      (!assignee || w.assigneeId === assignee) &&
      (!iteration || w.iterationId === iteration) &&
      (!search || w.title.toLowerCase().includes(search))
    );

    const body = $("#backlogBody");
    body.innerHTML = "";
    $("#backlogEmpty").hidden = rows.length > 0;

    rows.forEach((w) => {
      const tr = document.createElement("tr");
      const rem = remainingHours(w.code);
      tr.innerHTML = `
        <td class="id-cell">${w.code}</td>
        <td class="title-cell">${escapeHtml(w.title)}</td>
        <td><span class="badge-pill type-${w.type}">${w.type}</span></td>
        <td>${statusChip(w.statusId)}</td>
        <td><span class="badge-pill priority-${w.priorityId}">${w.priorityId}</span></td>
        <td>${w.assigneeId ? userName(w.assigneeId) : "<span style='color:var(--text-muted)'>не назначен</span>"}</td>
        <td>${fmtDate(w.dueDate)}</td>
        <td>${fmtHours(plannedHours(w.code))} / ${fmtHours(actualHours(w.code))} / <span class="${rem < 0 ? "overspend" : ""}">${fmtHours(rem)}</span></td>
        <td>${w.iterationId ? escapeHtml(byId(ITERATIONS, w.iterationId).name) : "—"}</td>
        <td class="row-actions"></td>`;
      tr.addEventListener("click", () => openItemCard(w.code));
      body.appendChild(tr);
    });
  }

  function statusChip(statusId) {
    const s = byId(STATUSES, statusId) || { name: statusId };
    const cls = s.name === "Завершена" ? "done" : s.name === "В работе" ? "progress" : s.name === "На проверке" ? "review" : s.name === "Архивирована" ? "archived" : "";
    return `<span class="status-chip"><span class="status-dot ${cls}"></span>${escapeHtml(s.name)}</span>`;
  }

  /* ============================== ЭКРАН: КАНБАН-ДОСКА ============================== */

  function renderBoard() {
    const assignee = $("#boardFilterAssignee").value, priority = $("#boardFilterPriority").value, iteration = $("#boardFilterIteration").value;
    const columns = STATUSES.filter((s) => s.onBoard).sort((a, b) => a.order - b.order);
    const boardable = WORK_ITEMS.filter((w) => w.type === "Задача" || w.type === "Ошибка" || w.type === "Подзадача");

    const wrap = $("#boardColumns");
    wrap.innerHTML = "";
    columns.forEach((col) => {
      const items = boardable.filter((w) =>
        w.statusId === col.id &&
        (!assignee || w.assigneeId === assignee) &&
        (!priority || w.priorityId === priority) &&
        (!iteration || w.iterationId === iteration)
      );
      const colEl = document.createElement("div");
      colEl.className = "board-column";
      colEl.dataset.statusId = col.id;
      colEl.innerHTML = `<div class="board-column-header"><span>${escapeHtml(col.name)}</span><span class="board-column-count">${items.length}</span></div>`;
      items.forEach((w) => colEl.appendChild(renderBoardCard(w)));
      colEl.addEventListener("dragover", (e) => { e.preventDefault(); colEl.classList.add("drag-over"); });
      colEl.addEventListener("dragleave", () => colEl.classList.remove("drag-over"));
      colEl.addEventListener("drop", (e) => {
        e.preventDefault();
        colEl.classList.remove("drag-over");
        if (state.dragCode) moveItemToStatus(state.dragCode, col.id);
      });
      wrap.appendChild(colEl);
    });
  }

  function renderBoardCard(w) {
    const card = document.createElement("div");
    card.className = "board-card";
    card.dataset.workItemCode = w.code;
    const editable = canEditWorkItem(w);
    card.classList.toggle("readonly", !editable);
    card.draggable = editable;
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", editable
      ? `${w.code}: ${w.title}. Статус: ${statusName(w.statusId)}. Стрелки влево и вправо меняют статус, Enter открывает карточку.`
      : `${w.code}: ${w.title}. Статус: ${statusName(w.statusId)}. Enter открывает карточку только для просмотра.`);
    const rem = remainingHours(w.code);
    card.innerHTML = `
      <div class="bc-id">${w.code} · <span class="badge-pill type-${w.type}" style="padding:1px 6px;">${w.type}</span></div>
      <div class="bc-title">${escapeHtml(w.title)}</div>
      <div class="bc-meta">
        <span class="badge-pill priority-${w.priorityId}">${w.priorityId}</span>
        <span class="bc-hours ${rem < 0 ? "overspend" : ""}">${fmtHours(rem)} ост.</span>
      </div>
      <div class="bc-meta" style="margin-top:6px;">
        <span class="bc-due">${w.assigneeId ? userName(w.assigneeId) : "не назначен"}</span>
        <span class="bc-due">${fmtDate(w.dueDate)}</span>
      </div>`;
    card.addEventListener("dragstart", () => { state.dragCode = w.code; card.classList.add("dragging"); });
    card.addEventListener("dragend", () => { card.classList.remove("dragging"); state.dragCode = null; });
    card.addEventListener("click", () => openItemCard(w.code));
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openItemCard(w.code);
        return;
      }
      if (!editable || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
      const columns = STATUSES.filter((s) => s.onBoard && s.active).sort((a, b) => a.order - b.order);
      const currentIndex = columns.findIndex((s) => s.id === w.statusId);
      const targetIndex = currentIndex + (e.key === "ArrowLeft" ? -1 : 1);
      if (currentIndex < 0 || targetIndex < 0 || targetIndex >= columns.length) return;
      e.preventDefault();
      moveItemToStatus(w.code, columns[targetIndex].id);
      const movedCard = $all(".board-card").find((el) => el.dataset.workItemCode === w.code);
      if (movedCard) movedCard.focus();
    });
    return card;
  }

  function moveItemToStatus(code, statusId) {
    const w = item(code);
    if (!w || w.statusId === statusId) return;
    if (!canEditWorkItem(w)) {
      toast("Недостаточно прав для смены статуса этого элемента.", "error");
      renderBoard();
      return;
    }
    const targetStatus = byId(STATUSES, statusId);
    if (targetStatus.name !== "Бэклог" && !w.assigneeId) {
      toast(`Нельзя перевести «${code}» из бэклога без назначенного исполнителя — карточка возвращена.`, "error");
      renderBoard();
      return;
    }
    const from = statusName(w.statusId);
    w.statusId = statusId;
    pushHistory(code, currentUser() ? currentUser().name : ROLE_LABEL[state.role], [{ field: "Статус", from, to: targetStatus.name }]);
    if (w.assigneeId) notify(w.assigneeId, code, `Статус «${w.title}» изменён на «${targetStatus.name}»`);
    toast(`«${code}» перемещён в статус «${targetStatus.name}»`);
    renderBoard();
    renderBacklog();
    updateUnreadBadge();
    if (state.activeScreen === "iteration") renderIteration();
  }

  /* ============================== КАРТОЧКА РАБОЧЕГО ЭЛЕМЕНТА ============================== */

  function openItemCard(code) {
    state.openItemCode = code;
    state.activeTab = "attachments";
    renderItemCard();
    $("#itemCardOverlay").classList.add("open");
  }
  function closeItemCard() {
    $("#itemCardOverlay").classList.remove("open");
    state.openItemCode = null;
    renderBacklog();
    renderBoard();
    if (state.activeScreen === "iteration") renderIteration();
  }

  function renderItemCard() {
    const w = item(state.openItemCode);
    if (!w) return;
    const parent = w.parentCode ? item(w.parentCode) : null;

    $("#itemBreadcrumb").innerHTML = parent
      ? `<a href="#" data-open="${parent.code}" style="color:var(--brand);text-decoration:none;">${parent.code} · ${escapeHtml(parent.title)}</a> / ${w.code}`
      : w.code;
    $("#itemBadges").innerHTML = `<span class="badge-pill type-${w.type}">${w.type}</span>${statusChip(w.statusId)}<span class="badge-pill priority-${w.priorityId}">${w.priorityId}</span>` +
      (w.externalSource ? `<span class="badge-pill" style="background:#eef0f3;color:#4b5563;">Из ${escapeHtml(w.externalSource)} · ${escapeHtml(w.externalDefectId)}</span>` : "");
    $("#itemTitle").textContent = w.title;
    $("#itemDescription").textContent = Object.hasOwn(state.descriptionDrafts, w.code)
      ? state.descriptionDrafts[w.code]
      : (w.description || "");

    const leaf = isLeaf(w.code);
    $("#itemFields").innerHTML = `
      <div class="field"><label>Статус</label>${fieldSelect("statusId", STATUSES.filter((s) => s.active).map((s) => [s.id, s.name]), w.statusId)}</div>
      <div class="field"><label>Приоритет</label>${fieldSelect("priorityId", PRIORITIES.map((p) => [p, p]), w.priorityId)}</div>
      <div class="field"><label>Исполнитель</label>${fieldSelect("assigneeId", [["", "не назначен"]].concat(USERS.map((u) => [u.id, u.name])), w.assigneeId || "")}</div>
      <div class="field"><label>Дата начала</label><input type="date" id="fieldStart" value="${w.startDate || ""}"></div>
      <div class="field"><label>Срок выполнения</label><input type="date" id="fieldDue" value="${w.dueDate || ""}"></div>
      <div class="field"><label>Итерация</label>${fieldSelect("iterationId", [["", "нет"]].concat(ITERATIONS.map((i) => [i.id, i.name])), w.iterationId || "")}</div>
      <div class="field"><label>Плановая трудоёмкость</label>${leaf ? `<input type="number" min="0" step="0.5" id="fieldPlanned" value="${w.plannedHours || 0}">` : `<div class="value">${fmtHours(plannedHours(w.code))} (сумма дочерних)</div>`}</div>
      <div class="field"><label>Фактическая трудоёмкость</label><div class="value">${fmtHours(actualHours(w.code))}</div></div>
      <div class="field"><label>Оставшееся время</label><div class="value ${remainingHours(w.code) < 0 ? "overspend" : ""}">${fmtHours(remainingHours(w.code))}</div></div>`;

    const kids = children(w.code);
    let hierarchyHtml = "";
    if (kids.length) {
      hierarchyHtml += `<div class="section-title">Дочерние элементы (${kids.length})</div><ul class="subitem-list">` +
        kids.map((c) => `<li data-open="${c.code}"><span>${c.code} · ${escapeHtml(c.title)}</span>${statusChip(c.statusId)}</li>`).join("") + `</ul>`;
    }
    $("#itemHierarchy").innerHTML = hierarchyHtml;

    renderAttachments(w.code);
    renderTimelog(w.code);
    renderComments(w.code);
    renderHistory(w.code);
    setActiveTab(state.activeTab);

    const editAllowed = canEditWorkItem(w);
    $all("input, select", $("#itemFields")).forEach((control) => { control.disabled = !editAllowed; });
    $("#itemDescription").contentEditable = editAllowed ? "true" : "false";
    $("#btnSaveCard").hidden = !editAllowed;
    $("#btnAddAttachment").hidden = !canCollaborate();
    $("#btnAddTimelog").hidden = !canCollaborate();
    $("#btnAddComment").hidden = !canCollaborate();
    $("#btnHardDelete").hidden = !canHardDelete();
  }

  function fieldSelect(id, pairs, value) {
    return `<select id="field_${id}">` + pairs.map(([v, l]) => `<option value="${v}" ${v === value ? "selected" : ""}>${escapeHtml(l)}</option>`).join("") + `</select>`;
  }

  function setActiveTab(tab) {
    state.activeTab = tab;
    $all(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    $all(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + tab));
  }

  function renderAttachments(code) {
    const list = ATTACHMENTS.filter((a) => a.workItemCode === code);
    $("#attachmentList").innerHTML = list.length ? list.map((a) => `
      <li class="attachment-item">
        <span class="file-chip"><span class="file-icon">📎</span><span>${escapeHtml(a.fileName)} <span style="color:var(--text-muted)">· ${a.size}</span></span></span>
        <span style="color:var(--text-muted);font-size:12px;">${userName(a.uploadedBy)}, ${fmtDateTime(a.uploadedAt)}</span>
      </li>`).join("") : `<li style="color:var(--text-muted);border:none;">Вложений пока нет.</li>`;
  }

  const MOCK_FILES = [["скриншот-ошибки.png", "203 КБ"], ["ТЗ-раздел-3.pdf", "1,1 МБ"], ["лог-сервера.txt", "44 КБ"], ["макет-экрана.fig.png", "780 КБ"]];

  function renderTimelog(code) {
    const list = TIMELOGS.filter((t) => t.workItemCode === code);
    $("#timelogList").innerHTML = list.length ? list.map((t) => `
      <li class="timelog-item">
        <span>${fmtDate(t.date)} · ${userName(t.userId)}${t.comment ? " — " + escapeHtml(t.comment) : ""}</span>
        <span>${fmtHours(t.hours)}</span>
      </li>`).join("") : `<li style="color:var(--text-muted);border:none;">Записей ещё нет.</li>`;
    $("#timelogTotal").innerHTML = `<span>Факт: ${fmtHours(actualHours(code))}</span><span>План: ${fmtHours(plannedHours(code))}</span>`;
  }

  function renderComments(code) {
    const list = COMMENTS.filter((c) => c.workItemCode === code);
    $("#commentList").innerHTML = list.length ? list.map((c) => `
      <li class="comment-item">
        <div class="meta-row"><strong>${userName(c.authorId)}</strong> · ${fmtDateTime(c.createdAt)}</div>
        <p class="comment-body">${escapeHtml(c.text)}</p>
      </li>`).join("") : `<li style="color:var(--text-muted);border:none;">Комментариев пока нет.</li>`;
  }

  function renderHistory(code) {
    const list = HISTORY.filter((h) => h.workItemCode === code).sort((a, b) => new Date(b.occurredAt) - new Date(a.occurredAt));
    $("#historyList").innerHTML = list.length ? list.map((h) => `
      <li class="history-item">
        <div class="meta-row" style="cursor:pointer;" data-toggle-diff="${h.id}"><strong>${escapeHtml(h.actor)}</strong> · ${fmtDateTime(h.occurredAt)} · <span style="color:var(--brand)">${h.changes.length} изм. (diff ▾)</span></div>
        <div class="history-diff" id="diff-${h.id}">
          ${h.changes.map((c) => `<div class="diff-field"><span>${escapeHtml(c.field)}</span><span class="diff-old">${escapeHtml(c.from)}</span><span>→</span><span class="diff-new">${escapeHtml(c.to)}</span></div>`).join("")}
        </div>
      </li>`).join("") : `<li style="color:var(--text-muted);border:none;">История пуста.</li>`;
  }

  /* ============================== ЭКРАН: ИТЕРАЦИЯ ============================== */

  function renderIteration() {
    const picker = $("#iterationPicker");
    picker.innerHTML = ITERATIONS.map((i) => `<button class="iteration-pill ${i.id === state.currentIterationId ? "active" : ""}" data-it="${i.id}">${escapeHtml(i.name)}</button>`).join("");

    const it = byId(ITERATIONS, state.currentIterationId);
    if (!it) return;
    const items = WORK_ITEMS.filter((w) => w.iterationId === it.id);

    $("#iterationMeta").innerHTML = `
      <div class="field"><label>Состояние</label><span class="badge-pill" style="background:#eef1fd;color:#3452eb;">${it.state}</span></div>
      <div class="field"><label>Начало</label><div class="value">${fmtDate(it.startDate)}</div></div>
      <div class="field"><label>Окончание</label><div class="value">${fmtDate(it.endDate)}</div></div>
      <div class="field"><label>Описание</label><div class="value">${escapeHtml(it.description || "—")}</div></div>`;

    const actions = $("#iterationActions");
    actions.innerHTML = "";
    if (canManageIterations() && it.state === "Запланирована") {
      actions.innerHTML = `<button class="btn primary" id="btnStartIteration">Запустить итерацию</button>`;
    } else if (canManageIterations() && it.state === "Активна") {
      actions.innerHTML = `<button class="btn primary" id="btnCompleteIteration">Завершить итерацию</button>`;
    }

    const totalPlanned = items.reduce((s, w) => s + (isLeaf(w.code) ? plannedHours(w.code) : 0), 0);
    const totalActual = items.reduce((s, w) => s + (isLeaf(w.code) ? actualHours(w.code) : 0), 0);
    const doneCount = items.filter((w) => statusName(w.statusId) === "Завершена").length;
    const pct = items.length ? Math.round((doneCount / items.length) * 100) : 0;

    $("#iterationMetrics").innerHTML = [
      ["Элементов", items.length],
      ["Плановые часы", fmtHours(totalPlanned)],
      ["Фактические часы", fmtHours(totalActual)],
      ["Остаток", fmtHours(totalPlanned - totalActual)],
      ["Завершено", pct + "%"],
    ].map(([label, val]) => `<div class="metric-card"><div class="metric-value">${val}</div><div class="metric-label">${label}</div></div>`).join("");

    $("#capacityRows").innerHTML = it.capacities.map((cap) => {
      const used = items.filter((w) => w.assigneeId === cap.userId && isLeaf(w.code)).reduce((s, w) => s + plannedHours(w.code), 0);
      const pctUsed = Math.min(100, Math.round((used / cap.hours) * 100));
      const overload = used > cap.hours;
      return `<div class="capacity-row">
        <span>${userName(cap.userId)}</span>
        <div class="capacity-bar"><div class="capacity-bar-fill ${overload ? "overload" : ""}" style="width:${pctUsed}%"></div></div>
        <span class="capacity-value ${overload ? "overspend" : ""}">${fmtHours(used)} / ${fmtHours(cap.hours)}</span>
      </div>`;
    }).join("") || `<div class="empty-state">Ёмкость участников не задана.</div>`;

    const byStatus = {};
    items.forEach((w) => { byStatus[w.statusId] = (byStatus[w.statusId] || 0) + 1; });
    $("#statusDist").innerHTML = STATUSES.filter((s) => byStatus[s.id]).map((s) => {
      const pctS = Math.round((byStatus[s.id] / items.length) * 100);
      return `<div class="status-dist-item">${s.name} (${byStatus[s.id]})<div class="status-dist-bar"><div class="status-dist-fill" style="width:${pctS}%"></div></div></div>`;
    }).join("") || `<div class="empty-state">Нет элементов для распределения.</div>`;

    const baselinePanel = $("#baselinePanel");
    if (it.baseline) {
      baselinePanel.hidden = false;
      const dev = totalActual - it.baseline.totalPlanned;
      $("#baselineBody").innerHTML = `
        <tr><td>Плановые часы (базовый план)</td><td>${fmtHours(it.baseline.totalPlanned)}</td><td>${fmtHours(totalActual)}</td><td class="${dev > 0 ? "overspend" : ""}">${dev > 0 ? "+" : ""}${fmtHours(dev)}</td></tr>
        <tr><td>Состав итерации</td><td>${it.baseline.itemIds.length} элем.</td><td>${items.length} элем.</td><td>${items.length - it.baseline.itemIds.length === 0 ? "без изменений" : (items.length - it.baseline.itemIds.length > 0 ? "+" : "") + (items.length - it.baseline.itemIds.length)}</td></tr>`;
    } else {
      baselinePanel.hidden = true;
    }

    const body = $("#iterationItemsBody");
    body.innerHTML = "";
    $("#iterationItemsEmpty").hidden = items.length > 0;
    items.forEach((w) => {
      const tr = document.createElement("tr");
      const rem = remainingHours(w.code);
      tr.innerHTML = `<td class="id-cell">${w.code}</td><td class="title-cell">${escapeHtml(w.title)}</td><td>${statusChip(w.statusId)}</td><td>${w.assigneeId ? userName(w.assigneeId) : "не назначен"}</td><td class="${rem < 0 ? "overspend" : ""}">${fmtHours(rem)}</td><td></td>`;
      tr.addEventListener("click", () => openItemCard(w.code));
      body.appendChild(tr);
    });
  }

  function startIteration() {
    if (!canManageIterations()) return;
    const it = byId(ITERATIONS, state.currentIterationId);
    const items = WORK_ITEMS.filter((w) => w.iterationId === it.id);
    const overloaded = it.capacities.filter((cap) => {
      const used = items.filter((w) => w.assigneeId === cap.userId && isLeaf(w.code)).reduce((s, w) => s + plannedHours(w.code), 0);
      return used > cap.hours;
    });
    if (overloaded.length) {
      const names = overloaded.map((c) => userName(c.userId)).join(", ");
      openModal(`
        <h3>Обнаружена перегрузка</h3>
        <p>Превышена доступная ёмкость участников: <strong>${escapeHtml(names)}</strong>. Запустить итерацию всё равно?</p>
        <div class="modal-actions"><button class="btn" id="modalCancel">Отмена</button><button class="btn primary" id="modalConfirm">Запустить</button></div>`);
      $("#modalConfirm").onclick = () => { closeModal(); doStartIteration(it, items); };
      $("#modalCancel").onclick = closeModal;
      return;
    }
    doStartIteration(it, items);
  }

  function doStartIteration(it, items) {
    it.state = "Активна";
    it.baseline = { totalPlanned: items.reduce((s, w) => s + (isLeaf(w.code) ? plannedHours(w.code) : 0), 0), itemIds: items.map((w) => w.code) };
    toast(`Итерация «${it.name}» запущена, базовый план зафиксирован.`);
    renderIteration();
  }

  function completeIteration() {
    if (!canManageIterations()) return;
    const it = byId(ITERATIONS, state.currentIterationId);
    const items = WORK_ITEMS.filter((w) => w.iterationId === it.id);
    const unfinished = items.filter((w) => statusName(w.statusId) !== "Завершена");
    it.state = "Завершена";
    unfinished.forEach((w) => { w.iterationId = null; });
    toast(`Итерация «${it.name}» завершена. Незавершённых элементов возвращено в бэклог: ${unfinished.length}.`);
    renderIteration();
    renderBacklog();
  }

  /* ============================== ЭКРАН: УВЕДОМЛЕНИЯ ============================== */

  function renderNotifications() {
    const list = NOTIFICATIONS.filter((n) => n.recipientId === state.currentUserId).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    $("#notifEmpty").hidden = list.length > 0;
    $("#notifList").innerHTML = list.map((n) => `
      <li class="notif-item ${n.readAt ? "read" : "unread"}" data-notif="${n.id}">
        <span class="notif-dot"></span>
        <div class="notif-body">
          <div class="notif-title">${escapeHtml(n.message)}</div>
          <div class="notif-meta">${escapeHtml(n.actor || "Система")} · ${escapeHtml(n.workItemCode || n.workItemPublicId || "удалённый элемент")} · ${fmtDateTime(n.createdAt)}</div>
        </div>
      </li>`).join("");
  }

  /* ============================== ЭКРАН: АДМИН-ПАНЕЛЬ ============================== */

  function renderAdmin() {
    $("#statusList").innerHTML = STATUSES.sort((a, b) => a.order - b.order).map((s, idx) => `
      <div class="status-row" data-status="${s.id}">
        <span style="color:var(--text-muted);font-size:12px;width:16px;">${idx + 1}</span>
        <input type="text" value="${escapeHtml(s.name)}" data-rename="${s.id}">
        <label class="toggle"><input type="checkbox" data-toggle-active="${s.id}" ${s.active ? "checked" : ""}><span class="slider"></span></label>
        <div class="order-btns"><button data-up="${s.id}">▲</button><button data-down="${s.id}">▼</button></div>
      </div>`).join("");

    $("#syncTime").textContent = "Последняя успешная синхронизация: " + fmtDateTime(LAST_SYNC_OK_TIME);
    $("#syncLog").innerHTML = SYNC_LOG.slice(0, 5).map((l) => `<div class="sync-log-item ${l.ok ? "ok" : "error"}">${fmtDateTime(l.time)} — ${escapeHtml(l.message)}</div>`).join("");
  }

  function addStatus() {
    const name = $("#newStatusName").value.trim();
    if (!name) { toast("Введите наименование статуса", "warn"); return; }
    const id = uid("s");
    STATUSES.push({ id, name, order: STATUSES.length + 1, active: true, onBoard: true });
    $("#newStatusName").value = "";
    toast(`Статус «${name}» добавлен, новая колонка появилась на доске.`);
    renderAdmin();
  }

  function syncNow() {
    toast("Запрошена синхронизация со справочником…");
    setTimeout(() => {
      const ok = Math.random() > 0.25;
      const now = new Date().toISOString();
      if (ok) {
        LAST_SYNC_OK_TIME = now;
        SYNC_LOG.unshift({ time: now, ok: true, message: "Синхронизировано: 5 пользователей, 3 команды, 2 подразделения" });
        toast("Синхронизация завершена успешно.");
      } else {
        SYNC_LOG.unshift({ time: now, ok: false, message: "Сервис справочников недоступен (timeout) — используются последние полученные данные" });
        toast("Сервис справочников недоступен. Работаем на последних полученных данных.", "error");
      }
      renderAdmin();
    }, 650);
  }

  /* ============================== МОДАЛЬНЫЕ ОКНА ============================== */

  function openModal(html) {
    $("#modalPanel").innerHTML = html;
    $("#modalOverlay").classList.add("open");
  }
  function closeModal() { $("#modalOverlay").classList.remove("open"); }

  function confirmHardDelete() {
    const w = item(state.openItemCode);
    if (children(w.code).length) {
      openModal(`
        <h3>Удаление заблокировано</h3>
        <p>У элемента «${escapeHtml(w.title)}» есть дочерние элементы. Сначала удалите или перенесите их — это требование BR-010.</p>
        <div class="modal-actions"><button class="btn primary" id="modalOk">Понятно</button></div>`);
      $("#modalOk").onclick = closeModal;
      return;
    }
    openModal(`
      <h3>Жёсткое удаление</h3>
      <p>Элемент «${escapeHtml(w.title)}» и все связанные данные (комментарии, вложения, трудозатраты, история) будут удалены <strong>безвозвратно</strong>. Действие нельзя отменить.</p>
      <div class="modal-actions"><button class="btn" id="modalCancel">Отмена</button><button class="btn danger" id="modalConfirm">Удалить безвозвратно</button></div>`);
    $("#modalCancel").onclick = closeModal;
    $("#modalConfirm").onclick = () => {
      const code = w.code;
      const title = w.title;
      const recipientId = w.assigneeId;
      WORK_ITEMS = WORK_ITEMS.filter((x) => x.code !== code);
      TIMELOGS = TIMELOGS.filter((x) => x.workItemCode !== code);
      COMMENTS = COMMENTS.filter((x) => x.workItemCode !== code);
      ATTACHMENTS = ATTACHMENTS.filter((x) => x.workItemCode !== code);
      HISTORY = HISTORY.filter((x) => x.workItemCode !== code);
      NOTIFICATIONS = NOTIFICATIONS.map((n) => n.workItemCode === code
        ? { ...n, workItemCode: null, workItemPublicId: code, workItemTitle: title }
        : n);
      if (recipientId) {
        NOTIFICATIONS.unshift({
          id: uid("n"), recipientId, workItemCode: null, workItemPublicId: code,
          workItemTitle: title, actor: currentUser() ? currentUser().name : ROLE_LABEL[state.role],
          message: `Рабочий элемент «${title}» удалён безвозвратно`,
          createdAt: new Date().toISOString(), readAt: null,
        });
      }
      delete state.descriptionDrafts[code];
      closeModal();
      closeItemCard();
      toast(`Элемент ${code} удалён безвозвратно.`);
    };
  }

  function openCreateItemModal() {
    openModal(`
      <h3>Создать рабочий элемент</h3>
      <div class="field" style="margin-bottom:10px;"><label>Тип</label>${fieldSelect("newType", TYPES.map((t) => [t, t]), "Задача")}</div>
      <div class="field" style="margin-bottom:10px;"><label>Наименование *</label><input type="text" id="field_newTitle" placeholder="Обязательное поле"></div>
      <div class="field" style="margin-bottom:10px;"><label>Исполнитель</label>${fieldSelect("newAssignee", [["", "не назначен"]].concat(USERS.map((u) => [u.id, u.name])), "")}</div>
      <div class="field" style="margin-bottom:10px;"><label>Приоритет</label>${fieldSelect("newPriority", PRIORITIES.map((p) => [p, p]), "Средний")}</div>
      <div class="field"><label>Плановая трудоёмкость, ч</label><input type="number" id="field_newHours" min="0" step="0.5" value="4"></div>
      <div class="modal-actions"><button class="btn" id="modalCancel">Отмена</button><button class="btn primary" id="modalConfirm">Создать</button></div>`);
    $("#modalCancel").onclick = closeModal;
    $("#modalConfirm").onclick = () => {
      const title = $("#field_newTitle").value.trim();
      if (!title) { toast("Наименование обязательно для заполнения", "warn"); return; }
      const code = "TT-" + nextCode++;
      WORK_ITEMS.push({
        code, type: $("#field_newType").value, title,
        description: "", statusId: "s1", priorityId: $("#field_newPriority").value,
        assigneeId: $("#field_newAssignee").value || null, startDate: "", dueDate: "",
        plannedHours: Number($("#field_newHours").value || 0), parentCode: null, iterationId: null,
      });
      pushHistory(code, currentUser() ? currentUser().name : ROLE_LABEL[state.role], [{ field: "Элемент", from: "—", to: "Создан" }]);
      const created = item(code);
      if (created.assigneeId) notify(created.assigneeId, code, `Вам назначен рабочий элемент «${created.title}»`);
      closeModal();
      toast(`Элемент ${code} создан.`);
      renderBacklog(); updateUnreadBadge();
    };
  }

  function openExportModal() {
    const count = WORK_ITEMS.length;
    const csvRows = [["ID", "Тип", "Наименование", "Статус", "Приоритет", "Исполнитель", "Итерация", "План", "Факт", "Остаток"]]
      .concat(WORK_ITEMS.map((w) => [w.code, w.type, w.title, statusName(w.statusId), w.priorityId, w.assigneeId ? userName(w.assigneeId) : "", w.iterationId ? byId(ITERATIONS, w.iterationId).name : "", plannedHours(w.code), actualHours(w.code), remainingHours(w.code)]));
    const csv = csvRows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(";")).join("\r\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    openModal(`
      <h3>Экспорт в Excel</h3>
      <p>Сформирован файл с ${count} рабочими элементами (идентификаторы и связанные справочные значения включены). В прототипе выгружается как CSV — в реальной системе бэкенд отдаёт настоящий <code>.xlsx</code>.</p>
      <div class="modal-actions">
        <button class="btn" id="modalCancel">Закрыть</button>
        <a class="btn primary" id="modalDownload" href="${url}" download="tasktracker-export.csv">Скачать файл</a>
      </div>`);
    $("#modalCancel").onclick = closeModal;
  }

  function openImportModal() {
    openModal(`
      <h3>Импорт из Excel</h3>
      <p>Выберите ранее экспортированный файл. Для демонстрации обоих сценариев проверки используйте кнопки ниже.</p>
      <div class="modal-actions" style="justify-content:flex-start;flex-wrap:wrap;">
        <button class="btn" id="btnImportOk">Загрузить корректный файл (демо)</button>
        <button class="btn" id="btnImportBad">Загрузить файл с ошибками (демо)</button>
      </div>
      <div id="importReportHolder"></div>
      <div class="modal-actions"><button class="btn" id="modalCancel">Закрыть</button></div>`);
    $("#modalCancel").onclick = closeModal;
    $("#btnImportOk").onclick = () => {
      const code = "TT-" + nextCode++;
      WORK_ITEMS.push({ code, type: "Задача", title: "Загружено из Excel: провести ретро", description: "", statusId: "s1", priorityId: "Средний", assigneeId: null, startDate: "", dueDate: "", plannedHours: 2, parentCode: null, iterationId: null });
      const updated = WORK_ITEMS[0];
      const oldPriority = updated.priorityId;
      updated.priorityId = oldPriority === "Высокий" ? "Средний" : "Высокий";
      pushHistory(updated.code, "Импорт из Excel", [{ field: "Приоритет", from: oldPriority, to: updated.priorityId }]);
      if (updated.assigneeId) notify(updated.assigneeId, updated.code, `Карточка «${updated.title}» обновлена импортом из Excel`);
      $("#importReportHolder").innerHTML = `<div class="import-report">Импорт завершён: создано 1, обновлено 1, отклонено 0.</div>`;
      renderBacklog(); updateUnreadBadge();
    };
    $("#btnImportBad").onclick = () => {
      $("#importReportHolder").innerHTML = `<div class="import-report">
        Импорт отклонён: создано 0, обновлено 0, отклонено 2. Данные не изменены.
        <ul>
          <li>Строка 5: неизвестный статус «В процессе»</li>
          <li>Строка 8: срок выполнения раньше даты начала</li>
        </ul></div>`;
    };
  }

  /* ============================== ИНИЦИАЛИЗАЦИЯ / ОБРАБОТЧИКИ ============================== */

  function wireEvents() {
    $all(".nav-item").forEach((b) => b.addEventListener("click", () => switchScreen(b.dataset.screen)));

    $("#roleSelect").addEventListener("change", (e) => {
      state.role = e.target.value;
      state.currentUserId = ROLE_TO_USER[state.role];
      applyRoleVisibility();
      updateUnreadBadge();
      switchScreen(state.activeScreen);
    });

    ["filterType", "filterStatus", "filterPriority", "filterAssignee", "filterIteration"].forEach((id) => $("#" + id).addEventListener("change", renderBacklog));
    $("#filterSearch").addEventListener("input", renderBacklog);
    ["boardFilterAssignee", "boardFilterPriority", "boardFilterIteration"].forEach((id) => $("#" + id).addEventListener("change", renderBoard));

    $("#btnCreateItem").addEventListener("click", openCreateItemModal);
    $("#btnExport").addEventListener("click", openExportModal);
    $("#btnImport").addEventListener("click", openImportModal);

    $("#btnCloseCard").addEventListener("click", closeItemCard);
    $("#btnCloseCard2").addEventListener("click", closeItemCard);
    $("#btnHardDelete").addEventListener("click", confirmHardDelete);
    $("#btnSaveCard").addEventListener("click", saveItemCard);

    document.addEventListener("click", (e) => {
      const openTarget = e.target.closest("[data-open]");
      if (openTarget) { e.preventDefault(); openItemCard(openTarget.dataset.open); }
      const tabBtn = e.target.closest(".tab-btn");
      if (tabBtn) setActiveTab(tabBtn.dataset.tab);
      const diffToggle = e.target.closest("[data-toggle-diff]");
      if (diffToggle) $("#diff-" + diffToggle.dataset.toggleDiff).classList.toggle("open");
      const itPill = e.target.closest("[data-it]");
      if (itPill) { state.currentIterationId = itPill.dataset.it; renderIteration(); }
      if (e.target.id === "btnStartIteration") startIteration();
      if (e.target.id === "btnCompleteIteration") completeIteration();
      if (e.target.id === "btnAddStatus") addStatus();
      if (e.target.id === "btnSyncNow") syncNow();
      const notifRow = e.target.closest("[data-notif]");
      if (notifRow) {
        const n = byId(NOTIFICATIONS, notifRow.dataset.notif);
        if (n) {
          n.readAt = n.readAt || new Date().toISOString();
          updateUnreadBadge();
          renderNotifications();
          if (n.workItemCode && item(n.workItemCode)) openItemCard(n.workItemCode);
          else toast("Рабочий элемент удалён; уведомление сохранено без ссылки на карточку.", "warn");
        }
      }
      if (e.target.id === "btnAddAttachment") {
        const w = item(state.openItemCode);
        const [fileName, size] = MOCK_FILES[Math.floor(Math.random() * MOCK_FILES.length)];
        ATTACHMENTS.push({ id: uid("a"), workItemCode: w.code, fileName, size, uploadedBy: state.currentUserId || "u5", uploadedAt: new Date().toISOString() });
        pushHistory(w.code, currentUser() ? currentUser().name : ROLE_LABEL[state.role], [{ field: "Вложение", from: "—", to: fileName }]);
        if (w.assigneeId) notify(w.assigneeId, w.code, `Добавлено вложение к «${w.title}»`);
        renderAttachments(w.code); renderHistory(w.code); updateUnreadBadge();
      }
      if (e.target.id === "btnAddTimelog") {
        const w = item(state.openItemCode);
        const hours = Number($("#timelogHours").value);
        if (!hours || hours <= 0) { toast("Укажите часы больше нуля", "warn"); return; }
        TIMELOGS.push({ workItemCode: w.code, userId: state.currentUserId || "u5", date: new Date().toISOString().slice(0, 10), hours, comment: $("#timelogComment").value.trim() });
        pushHistory(w.code, currentUser() ? currentUser().name : ROLE_LABEL[state.role], [{ field: "Трудозатраты", from: "—", to: fmtHours(hours) }]);
        if (w.assigneeId) notify(w.assigneeId, w.code, `Добавлены трудозатраты к «${w.title}»: ${fmtHours(hours)}`);
        $("#timelogHours").value = ""; $("#timelogComment").value = "";
        renderTimelog(w.code); renderHistory(w.code); renderItemFieldsHoursOnly(w.code); updateUnreadBadge();
      }
      if (e.target.id === "btnAddComment") {
        const w = item(state.openItemCode);
        const text = $("#newComment").value.trim();
        if (!text) return;
        COMMENTS.push({ id: uid("c"), workItemCode: w.code, authorId: state.currentUserId || "u5", text, createdAt: new Date().toISOString() });
        $("#newComment").value = "";
        pushHistory(w.code, currentUser() ? currentUser().name : ROLE_LABEL[state.role], [{ field: "Комментарий", from: "—", to: text }]);
        if (w.assigneeId) notify(w.assigneeId, w.code, `Новый комментарий к «${w.title}»`);
        renderComments(w.code); renderHistory(w.code); updateUnreadBadge();
      }
      if (e.target.id === "btnMarkAllRead") {
        NOTIFICATIONS.filter((n) => n.recipientId === state.currentUserId).forEach((n) => { n.readAt = n.readAt || new Date().toISOString(); });
        updateUnreadBadge(); renderNotifications();
      }
    });

    document.addEventListener("change", (e) => {
      if (e.target.matches("[data-toggle-active]")) {
        const s = byId(STATUSES, e.target.dataset.toggleActive);
        s.active = e.target.checked;
        toast(`Статус «${s.name}» ${s.active ? "активирован" : "деактивирован"}.`);
      }
      if (e.target.matches("[data-rename]")) {
        const s = byId(STATUSES, e.target.dataset.rename);
        s.name = e.target.value || s.name;
        renderBacklog(); renderBoard();
      }
    });

    document.addEventListener("click", (e) => {
      if (e.target.matches("[data-up]") || e.target.matches("[data-down]")) {
        const id = e.target.dataset.up || e.target.dataset.down;
        const dir = e.target.dataset.up ? -1 : 1;
        const sorted = STATUSES.slice().sort((a, b) => a.order - b.order);
        const idx = sorted.findIndex((s) => s.id === id);
        const swapIdx = idx + dir;
        if (swapIdx < 0 || swapIdx >= sorted.length) return;
        const tmp = sorted[idx].order; sorted[idx].order = sorted[swapIdx].order; sorted[swapIdx].order = tmp;
        renderAdmin(); renderBoard();
      }
    });

    $("#itemDescription").addEventListener("input", () => {
      const w = item(state.openItemCode);
      if (!w) return;
      state.descriptionDrafts[w.code] = $("#itemDescription").textContent;
      $("#autosaveHint").textContent = "Сохранение…";
      clearTimeout(window.__descTimer);
      window.__descTimer = setTimeout(() => { $("#autosaveHint").textContent = "Черновик сохранён автоматически"; }, 500);
    });
  }

  function renderItemFieldsHoursOnly(code) {
    // частичная перерисовка часов в шапке карточки без полного ре-рендера (чтобы не терять фокус полей)
    if (state.openItemCode === code) renderItemCard();
  }

  function saveItemCard() {
    const w = item(state.openItemCode);
    if (!w) return;
    const changes = [];
    const startEl = $("#fieldStart"), dueEl = $("#fieldDue"), plannedEl = $("#fieldPlanned");
    if (startEl && dueEl && startEl.value && dueEl.value && dueEl.value < startEl.value) {
      toast("Срок выполнения не может быть раньше даты начала", "error");
      return;
    }
    if (plannedEl && Number(plannedEl.value) < 0) {
      toast("Трудоёмкость не может быть отрицательной", "error");
      return;
    }
    const map = { statusId: "Статус", priorityId: "Приоритет", assigneeId: "Исполнитель", iterationId: "Итерация" };
    Object.keys(map).forEach((key) => {
      const el = $("#field_" + key);
      if (!el) return;
      const newVal = el.value || null;
      if (newVal !== (w[key] || null)) {
        const label = (arr, id) => (key === "statusId" ? statusName(id) : key === "assigneeId" ? (id ? userName(id) : "не назначен") : key === "iterationId" ? (id ? byId(ITERATIONS, id).name : "нет") : id);
        changes.push({ field: map[key], from: label(null, w[key]), to: label(null, newVal) });
        w[key] = newVal;
      }
    });
    if (startEl && startEl.value !== w.startDate) { changes.push({ field: "Дата начала", from: fmtDate(w.startDate), to: fmtDate(startEl.value) }); w.startDate = startEl.value; }
    if (dueEl && dueEl.value !== w.dueDate) {
      changes.push({ field: "Срок выполнения", from: fmtDate(w.dueDate), to: fmtDate(dueEl.value) }); w.dueDate = dueEl.value;
    }
    if (plannedEl && Number(plannedEl.value) !== Number(w.plannedHours)) {
      changes.push({ field: "Плановая трудоёмкость", from: fmtHours(w.plannedHours || 0), to: fmtHours(Number(plannedEl.value)) });
      w.plannedHours = Number(plannedEl.value);
    }
    if (Object.hasOwn(state.descriptionDrafts, w.code) && state.descriptionDrafts[w.code] !== w.description) {
      changes.push({ field: "Описание", from: w.description || "—", to: state.descriptionDrafts[w.code] || "—" });
      w.description = state.descriptionDrafts[w.code];
      delete state.descriptionDrafts[w.code];
    }
    if (changes.length) {
      pushHistory(w.code, currentUser() ? currentUser().name : ROLE_LABEL[state.role], changes);
      if (w.assigneeId) notify(w.assigneeId, w.code, `Карточка «${w.title}» изменена (${changes.length} поле(й))`);
      toast("Изменения сохранены.");
      updateUnreadBadge();
    } else {
      toast("Изменений нет.");
    }
    renderItemCard();
  }

  function wireOverlayDismissal() {
    // Клик по подложке или Esc закрывает открытый оверлей — ожидаемое поведение модальных
    // окон и часть accessibility-требований из 110.ui-ux.md (управление с клавиатуры).
    $("#itemCardOverlay").addEventListener("click", (e) => { if (e.target.id === "itemCardOverlay") closeItemCard(); });
    $("#modalOverlay").addEventListener("click", (e) => { if (e.target.id === "modalOverlay") closeModal(); });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if ($("#modalOverlay").classList.contains("open")) closeModal();
      else if ($("#itemCardOverlay").classList.contains("open")) closeItemCard();
    });
  }

  function init() {
    fillCommonFilterOptions();
    applyRoleVisibility();
    updateUnreadBadge();
    wireEvents();
    wireOverlayDismissal();
    switchScreen("backlog");
  }

  document.addEventListener("DOMContentLoaded", init);
})();
