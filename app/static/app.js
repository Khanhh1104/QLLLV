"use strict";
const $ = (id) => document.getElementById(id);
// Bảng màu chỉ lưu trên thiết bị, không thay đổi dữ liệu lịch làm việc.
const THEMES = {
  pixel: { name: "Pixel mặc định", colors: ["#6750a4", "#eaddff", "#fffbfe"] },
  forest: { name: "Pixel xanh lá", colors: ["#386a20", "#b8f397", "#f8fbf4"] },
  ocean: { name: "Pixel xanh dương", colors: ["#415f91", "#d6e3ff", "#f8f9ff"] },
  lavender: { name: "Pixel lavender", colors: ["#76558f", "#f1daff", "#fdf7ff"] },
  rose: { name: "Pixel hồng", colors: ["#984061", "#ffd9e4", "#fff8f8"] },
  sand: { name: "Pixel màu cát", colors: ["#825500", "#ffddb0", "#fff8f3"] },
};
function applyTheme(id, persist = false) {
  if (!Object.hasOwn(THEMES, id)) id = "pixel";
  document.documentElement.dataset.theme = id;
  let saved = true;
  if (persist) {
    try { localStorage.setItem("sm_theme", id); } catch { saved = false; }
  }
  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.themeChoice === id));
  });
  $("themeStatus").textContent = `Đang dùng: ${THEMES[id].name}.` +
    (saved ? "" : " Trình duyệt không cho phép lưu lựa chọn.");
}
$("themeChoices").innerHTML = Object.entries(THEMES).map(([id, theme]) =>
  `<button type="button" class="theme-choice" data-theme-choice="${id}" aria-pressed="false"><span class="theme-swatches" aria-hidden="true">${theme.colors.map(color => `<i style="background:${color}"></i>`).join("")}</span><span>${theme.name}</span><span class="theme-check" aria-hidden="true">✓</span></button>`
).join("");
$("themeChoices").addEventListener("click", (event) => {
  const button = event.target.closest("[data-theme-choice]");
  if (button) applyTheme(button.dataset.themeChoice, true);
});
$("resetTheme").addEventListener("click", () => applyTheme("pixel", true));
let initialTheme = "pixel";
try { initialTheme = localStorage.getItem("sm_theme") || "pixel"; } catch {}
applyTheme(initialTheme);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const STATUS = {
  todo: "Chưa làm",
  in_progress: "Đang làm",
  done: "Hoàn thành",
};
const PRIORITY = { high: "Cao", medium: "Trung bình", low: "Thấp" };
const TITLES = {
  today: ["Hôm nay", "Một kế hoạch rõ ràng cho một ngày nhẹ nhàng."],
  calendar: [
    "Lịch của tôi",
    "Nhìn toàn cảnh, dành chỗ cho những điều quan trọng.",
  ],
  tasks: ["Công việc", "Sắp xếp từng việc, tiến gần hơn đến mục tiêu."],
  stats: ["Thống kê", "Nhìn lại tiến độ để lên kế hoạch tốt hơn."],
  activities: ["Hoạt động", "Nhìn lại những thay đổi trong lịch làm việc."],
  notifications: ["Thông báo", "Không bỏ lỡ lịch hẹn và việc cần làm."],
  categories: ["Danh mục", "Một chút ngăn nắp cho những kế hoạch của bạn."],
  transfer: ["Nhập / xuất", "Mang công việc và lịch trình đến nơi bạn cần."],
  trash: ["Thùng rác", "Bạn luôn có thể thay đổi quyết định."],
  account: ["Tài khoản", "Điều chỉnh trải nghiệm theo cách của bạn."],
};
let token = localStorage.getItem("sm_token"),
  user = null,
  categories = [],
  currentView = "today",
  listPage = 1,
  trashPage = 1,
  noticePage = 1,
  calMode = "month",
  calDate = "",
  editing = null,
  toastTimer = null,
  pollTimer = null,
  resetToken = "",
  renderVersion = 0;
let browserNotified = new Set(),
  emailConfigured = false,
  templates = [],
  savedFilters = [],
  activityPage = 1,
  activeFocus = null,
  focusInterval = null,
  focusStopping = false,
  calendarSuppressClick = false;
function toast(message, bad = false) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").className = "toast" + (bad ? " bad" : "");
  toastTimer = setTimeout(() => $("toast").classList.add("hidden"), 5000);
}
function detailText(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((x) => `${(x.loc || []).slice(1).join(".")}: ${x.msg}`)
      .join("\n");
  return detail?.message || "Có lỗi xảy ra. Vui lòng thử lại.";
}
async function api(
  path,
  { method = "GET", body, raw = false, auth = true } = {},
) {
  const headers = {};
  if (auth && token) headers.Authorization = "Bearer " + token;
  if (
    body &&
    !(body instanceof FormData) &&
    !(body instanceof URLSearchParams)
  ) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, { method, headers, body });
  } catch {
    throw new Error("Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 && auth) {
      localLogout();
    }
    const error = new Error(detailText(data.detail));
    error.status = response.status;
    error.detail = data.detail;
    throw error;
  }
  return response.status === 204 ? null : raw ? response : response.json();
}
async function busy(form, fn) {
  const buttons = [
    ...form.querySelectorAll("[type=submit],button:not([type])"),
  ];
  buttons.forEach((b) => (b.disabled = true));
  try {
    return await fn();
  } finally {
    buttons.forEach((b) => (b.disabled = false));
  }
}
function localLogout() {
  token = null;
  user = null;
  localStorage.removeItem("sm_token");
  clearInterval(pollTimer);
  clearInterval(focusInterval);
  activeFocus = null;
  $("focusDock").classList.add("hidden");
  renderVersion++;
  if ($("taskModal").open) $("taskModal").close();
  $("appView").classList.add("hidden");
  $("authView").classList.remove("hidden");
  $("loginPassword").value = "";
  showAuth("login");
}
function showAuth(mode) {
  ["login", "register", "forgot", "reset"].forEach((x) =>
    $(x + "Form").classList.toggle("hidden", x !== mode),
  );
  $("authTabs").classList.toggle("hidden", ["forgot", "reset"].includes(mode));
  document
    .querySelectorAll("[data-auth]")
    .forEach((b) => b.classList.toggle("active", b.dataset.auth === mode));
  $("authTitle").textContent = {
    login: "Chào mừng trở lại",
    register: "Bắt đầu kế hoạch mới",
    forgot: "Khôi phục tài khoản",
    reset: "Đặt mật khẩu mới",
  }[mode];
  $("authMessage").textContent = "";
}
function zone() {
  return user?.timezone || "Asia/Ho_Chi_Minh";
}
function parts(value, tz = zone()) {
  const d = new Date(value);
  const p = {};
  new Intl.DateTimeFormat("sv-SE", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  })
    .formatToParts(d)
    .forEach((x) => {
      p[x.type] = x.value;
    });
  return p;
}
function dayKey(value = new Date()) {
  const p = parts(value);
  return `${p.year}-${p.month}-${p.day}`;
}
function localInput(value, tz = zone()) {
  if (!value) return "";
  const p = parts(value, tz);
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
function zonedISO(value, tz = zone()) {
  if (!value) return null;
  const wall = value.length === 10 ? value + "T00:00" : value;
  const target = Date.parse(wall + "Z");
  if (!Number.isFinite(target)) throw new Error("Ngày giờ không hợp lệ");
  let guess = target;
  for (let i = 0; i < 4; i++) {
    const p = parts(guess, tz);
    const shown = Date.parse(
      `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}Z`,
    );
    const next = guess + target - shown;
    if (next === guess) break;
    guess = next;
  }
  if (localInput(guess, tz) !== wall.slice(0, 16))
    throw new Error(
      "Giờ này không tồn tại do đổi giờ mùa hè. Hãy chọn giờ khác.",
    );
  return new Date(guess).toISOString();
}
function addDays(key, n) {
  const d = new Date(key + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
function weekStart(key) {
  const n = new Date(key + "T12:00:00Z").getUTCDay();
  return addDays(key, -((n + 6) % 7));
}
function dateLabel(key, opts = { day: "2-digit", month: "2-digit" }) {
  return new Date(key + "T12:00:00Z").toLocaleDateString("vi-VN", {
    timeZone: "UTC",
    ...opts,
  });
}
function fmt(value, withDate = true) {
  if (!value) return "";
  return new Date(value).toLocaleString("vi-VN", {
    timeZone: zone(),
    ...(withDate ? { day: "2-digit", month: "2-digit" } : {}),
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
}
function due(task) {
  return task.deadline || task.end_time;
}
function overdue(task) {
  return (
    task.status !== "done" && due(task) && new Date(due(task)) < new Date()
  );
}
function colorFor(name) {
  return categories.find((c) => c.name === name)?.color || "#9aa88e";
}
function categoryTag(name) {
  return name
    ? `<span class="tag" style="background:${colorFor(name)}18;color:${colorFor(name)}">${esc(name)}</span>`
    : "";
}
function taskHTML(task, { trash = false, compact = false } = {}) {
  const checklist = task.checklist || [],
    doneCount = checklist.filter((x) => x.done).length;
  const details = [
    task.location
      ? `<span title="Địa điểm">⌖ ${esc(task.location)}</span>`
      : "",
    task.meeting_url
      ? `<a href="${esc(task.meeting_url)}" target="_blank" rel="noopener noreferrer">Mở liên kết ↗</a>`
      : "",
    task.actual_minutes
      ? `<span>Đã tập trung ${task.actual_minutes} phút</span>`
      : "",
  ].join("");
  const actions = trash
    ? `<button data-action="restore" data-id="${task.id}">Khôi phục</button><button data-action="purge" data-id="${task.id}">Xóa hẳn</button>`
    : `<button data-action="focus" data-id="${task.id}">${task.timer_started_at ? "Dừng giờ" : "Tập trung 25'"}</button><button data-action="duplicate" data-id="${task.id}">Nhân bản</button>${overdue(task) ? `<button data-action="tomorrow" data-id="${task.id}">Dời ngày mai</button>` : ""}<button data-action="edit" data-id="${task.id}" aria-label="Sửa ${esc(task.title)}">Sửa</button><button data-action="delete" data-id="${task.id}" aria-label="Xóa ${esc(task.title)}">×</button>`;
  return `<article class="task-card ${task.timer_started_at ? "timer-active" : ""}"><button class="task-check ${task.status === "done" ? "done" : ""}" data-action="${trash ? "restore" : "done"}" data-id="${task.id}" aria-label="${trash ? "Khôi phục" : task.status === "done" ? "Đánh dấu chưa làm" : "Đánh dấu hoàn thành"}">${trash ? "↶" : task.status === "done" ? "✓" : ""}</button><div class="task-body"><button class="task-title ${task.status === "done" ? "done" : ""}" data-action="${trash ? "restore" : "edit"}" data-id="${task.id}">${esc(task.title)}</button><div class="task-meta"><span class="time">${fmt(task.start_time)}${task.end_time ? " – " + fmt(task.end_time, false) : ""}</span>${categoryTag(task.category)}<span class="tag ${task.status}">${STATUS[task.status]}</span>${overdue(task) ? '<span class="tag overdue">Quá hạn</span>' : ""}${task.series_id ? '<span title="Công việc thuộc chuỗi lặp">↻ Lặp</span>' : ""}${task.reminder_minutes !== null ? '<span title="Đã bật nhắc việc">♧</span>' : ""}</div>${!compact ? `<div class="task-meta"><span class="${task.priority}"><i class="priority-dot"></i>Ưu tiên ${PRIORITY[task.priority].toLowerCase()}</span>${task.deadline ? `<span>Hạn chót: ${fmt(task.deadline)}</span>` : ""}${checklist.length ? `<span>${doneCount}/${checklist.length} bước</span>` : ""}${details}</div>` : ""}${checklist.length ? `<div class="progress-track" aria-label="Đã hoàn thành ${doneCount} trên ${checklist.length} bước"><i style="width:${(100 * doneCount) / checklist.length}%"></i></div>` : ""}</div><div class="task-actions">${actions}</div></article>`;
}
function taskListHTML(tasks, opts = {}) {
  return tasks.length
    ? tasks.map((t) => taskHTML(t, opts)).join("")
    : '<div class="empty">Chưa có công việc trong mục này.</div>';
}
function paginate(id, total, page, size, kind) {
  const pages = Math.ceil(total / size);
  const unit =
    kind === "activities"
      ? "hoạt động"
      : kind === "notifications"
        ? "thông báo"
        : "công việc";
  $(id).innerHTML =
    pages > 1
      ? `<button class="secondary" data-page="${page - 1}" data-kind="${kind}" ${page <= 1 ? "disabled" : ""}>← Trước</button><span>Trang ${page}/${pages} · ${total} ${unit}</span><button class="secondary" data-page="${page + 1}" data-kind="${kind}" ${page >= pages ? "disabled" : ""}>Sau →</button>`
      : `<span>${total} ${unit}</span>`;
}
async function allTasks(params) {
  const query = new URLSearchParams(params);
  query.set("page_size", "500");
  let result = [],
    page = 1,
    total = 0;
  do {
    query.set("page", page++);
    const data = await api("/tasks?" + query);
    result.push(...data.items);
    total = data.total;
    if (!data.items.length) break;
  } while (result.length < total);
  return result;
}
function categoryOptions() {
  for (const id of ["filterCategory", "taskCategory"]) {
    const previous = $(id).value;
    $(id).innerHTML =
      `<option value="">${id === "filterCategory" ? "Mọi danh mục" : "Chưa phân loại"}</option>` +
      categories
        .map((c) => `<option value="${esc(c.name)}">${esc(c.name)}</option>`)
        .join("");
    $(id).value = previous;
  }
}
async function loadCategories() {
  categories = await api("/categories");
  categoryOptions();
}
async function loadTemplates() {
  templates = await api("/templates");
  const current = $("taskTemplate")?.value || "";
  if ($("taskTemplate")) {
    $("taskTemplate").innerHTML =
      '<option value="">Chọn mẫu công việc…</option>' +
      templates
        .map((item) => `<option value="${item.id}">${esc(item.name)}</option>`)
        .join("");
    $("taskTemplate").value = current;
  }
}
async function loadSavedFilters() {
  savedFilters = await api("/saved-filters");
  const current = $("savedFilterSelect")?.value || "";
  $("savedFilterSelect").innerHTML =
    '<option value="">Bộ lọc đã lưu…</option>' +
    savedFilters
      .map((item) => `<option value="${item.id}">${esc(item.name)}</option>`)
      .join("");
  $("savedFilterSelect").value = current;
}
async function summary() {
  const data = await api("/stats");
  const labels = {
    total: "Tổng công việc",
    todo: "Chưa làm",
    in_progress: "Đang làm",
    done: "Hoàn thành",
    overdue: "Quá hạn",
  };
  $("summary").innerHTML = Object.entries(labels)
    .map(
      ([key, label]) =>
        `<button class="summary-card ${key === "overdue" ? "warn" : ""}" data-summary="${key}"><span>${label}</span><strong>${data[key]}</strong><small>công việc</small></button>`,
    )
    .join("");
}
async function enterApp() {
  user = await api("/auth/me");
  emailConfigured = (await api("/config", { auth: false })).email_configured;
  await Promise.all([loadCategories(), loadTemplates(), loadSavedFilters()]);
  $("authView").classList.add("hidden");
  $("appView").classList.remove("hidden");
  $("whoami").textContent = user.display_name || user.username;
  $("avatar").textContent = (user.display_name || user.username)
    .slice(0, 1)
    .toUpperCase();
  $("zoneLabel").textContent = user.timezone;
  $("todayLabel").textContent = new Date().toLocaleDateString("vi-VN", {
    timeZone: zone(),
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  calDate = dayKey();
  $("statsFrom").value = addDays(dayKey(), -6);
  $("statsTo").value = dayKey();
  const running = await api("/timers/active");
  if (running) startFocusDisplay(running);
  await showView(
    TITLES[location.hash.slice(1)] ? location.hash.slice(1) : "today",
  );
  clearInterval(pollTimer);
  await pollNotices();
  pollTimer = setInterval(pollNotices, 30000);
}
async function showView(view) {
  if (!user) return;
  currentView = view;
  history.replaceState(null, "", "#" + view);
  document
    .querySelectorAll(".view")
    .forEach((el) => el.classList.toggle("hidden", el.id !== view + "View"));
  document
    .querySelectorAll("[data-view]")
    .forEach((el) => el.classList.toggle("active", el.dataset.view === view));
  $("pageTitle").textContent = TITLES[view][0];
  $("pageSubtitle").textContent = TITLES[view][1];
  $("summary").classList.toggle(
    "hidden",
    !["today", "tasks", "calendar"].includes(view),
  );
  await refresh();
}
async function refresh() {
  const version = ++renderVersion;
  $("pageError").textContent = "";
  try {
    await Promise.all([
      ["today", "tasks", "calendar"].includes(currentView) ? summary() : null,
      {
        today: loadToday,
        tasks: loadTasks,
        calendar: loadCalendar,
        stats: loadStats,
        activities: loadActivities,
        notifications: loadNotifications,
        categories: renderCategories,
        transfer: async () => {},
        trash: loadTrash,
        account: renderAccount,
      }[currentView](),
    ]);
  } catch (err) {
    if (version === renderVersion) $("pageError").textContent = err.message;
  }
}
async function loadToday() {
  const today = dayKey();
  const [scheduled, late, future] = await Promise.all([
    allTasks({
      date_from: zonedISO(today),
      date_to: zonedISO(addDays(today, 1)),
    }),
    api("/tasks?overdue=true&page_size=5&sort=deadline"),
    api(
      "/tasks?" +
        new URLSearchParams({
          unfinished: true,
          due_from: new Date().toISOString(),
          due_to: new Date(Date.now() + 7 * 86400000).toISOString(),
          sort: "deadline",
          page_size: 4,
        }),
    ),
  ]);
  $("todayTasks").innerHTML = taskListHTML(scheduled);
  $("todayCount").textContent = scheduled.length + " công việc";
  $("overdueTasks").innerHTML = taskListHTML(late.items);
  const soon = future.items;
  $("upcomingTasks").innerHTML = taskListHTML(soon, { compact: true });
}
function filters() {
  const query = new URLSearchParams({
    page: listPage,
    page_size: 15,
    sort: $("filterSort").value,
  });
  for (const [id, key] of [
    ["filterKeyword", "keyword"],
    ["filterStatus", "status"],
    ["filterPriority", "priority"],
    ["filterCategory", "category"],
  ])
    if ($(id).value) query.set(key, $(id).value);
  if ($("filterFrom").value)
    query.set("date_from", zonedISO($("filterFrom").value));
  if ($("filterTo").value)
    query.set("date_to", zonedISO(addDays($("filterTo").value, 1)));
  if ($("filterOverdue").checked) query.set("overdue", "true");
  return query;
}
function currentFilterState() {
  return {
    keyword: $("filterKeyword").value.trim(),
    status: $("filterStatus").value,
    priority: $("filterPriority").value,
    category: $("filterCategory").value,
    date_from: $("filterFrom").value,
    date_to: $("filterTo").value,
    overdue: $("filterOverdue").checked,
    sort: $("filterSort").value,
  };
}
function applyFilterState(state) {
  resetFilters();
  $("filterKeyword").value = state.keyword || "";
  $("filterStatus").value = state.status || "";
  $("filterPriority").value = state.priority || "";
  $("filterCategory").value = state.category || "";
  $("filterFrom").value = state.date_from || "";
  $("filterTo").value = state.date_to || "";
  $("filterOverdue").checked = Boolean(state.overdue);
  $("filterSort").value = state.sort || "start";
}
async function loadTasks() {
  const data = await api("/tasks?" + filters());
  if (listPage > 1 && !data.items.length) {
    listPage--;
    return loadTasks();
  }
  $("taskList").innerHTML = taskListHTML(data.items);
  paginate("taskPagination", data.total, listPage, 15, "tasks");
}
async function loadTrash() {
  const data = await api(`/tasks?trash=true&page=${trashPage}&page_size=15`);
  if (trashPage > 1 && !data.items.length) {
    trashPage--;
    return loadTrash();
  }
  $("trashList").innerHTML = taskListHTML(data.items, { trash: true });
  paginate("trashPagination", data.total, trashPage, 15, "trash");
}
function calendarRange() {
  if (calMode === "day") return [calDate, addDays(calDate, 1)];
  if (calMode === "week") {
    const start = weekStart(calDate);
    return [start, addDays(start, 7)];
  }
  const first = calDate.slice(0, 7) + "-01";
  const start = weekStart(first);
  return [start, addDays(start, 42)];
}
function intersects(task, key) {
  const start = Date.parse(zonedISO(key)),
    end = Date.parse(zonedISO(addDays(key, 1)));
  return (
    Date.parse(task.start_time) < end &&
    (task.end_time
      ? Date.parse(task.end_time) > start
      : Date.parse(task.start_time) >= start)
  );
}
async function loadCalendar() {
  const [start, end] = calendarRange();
  const tasks = await allTasks({
    date_from: zonedISO(start),
    date_to: zonedISO(end),
  });
  $("calTitle").textContent =
    calMode === "month"
      ? dateLabel(calDate, { month: "long", year: "numeric" })
      : calMode === "week"
        ? `${dateLabel(start)} – ${dateLabel(addDays(end, -1), { day: "2-digit", month: "2-digit", year: "numeric" })}`
        : dateLabel(calDate, {
            weekday: "long",
            day: "numeric",
            month: "long",
          });
  $("calendarLegend").innerHTML = categories
    .map(
      (c) => `<span><i style="background:${c.color}"></i>${esc(c.name)}</span>`,
    )
    .join("");
  if (calMode === "month") {
    let html =
      '<div class="month-grid">' +
      ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
        .map((x) => `<div class="weekday">${x}</div>`)
        .join("");
    for (let i = 0; i < 42; i++) {
      const key = addDays(start, i),
        dayTasks = tasks.filter((t) => intersects(t, key));
      html += `<div class="month-cell ${key.slice(0, 7) !== calDate.slice(0, 7) ? "outside" : ""}" data-date-cell="${key}"><button class="month-day ${key === dayKey() ? "today" : ""}" data-new-date="${key}T09:00" aria-label="Thêm công việc ngày ${dateLabel(key)}">${Number(key.slice(-2))}</button>${dayTasks
        .slice(0, 3)
        .map(
          (t) =>
            `<button class="cal-event ${t.status}" draggable="true" style="--event-color:${colorFor(t.category)}" data-action="edit" data-calendar-task="${t.id}" data-id="${t.id}" title="${esc(t.title)} · ${fmt(t.start_time)}">${fmt(t.start_time, false)} ${esc(t.title)}</button>`,
        )
        .join(
          "",
        )}${dayTasks.length > 3 ? `<button class="cal-more" data-cal-day="${key}">+${dayTasks.length - 3} công việc</button>` : ""}</div>`;
    }
    html += "</div>";
    $("calendar").innerHTML = html;
    return;
  }
  const days = calMode === "day" ? 1 : 7;
  let html = `<div class="week-grid ${days === 1 ? "single" : ""}" style="--days:${days}"><div class="time-header"><div>Giờ</div>`;
  for (let i = 0; i < days; i++) {
    const key = addDays(start, i);
    html += `<div class="${key === dayKey() ? "current-day" : ""}">${dateLabel(key, { weekday: "short", day: "2-digit", month: "2-digit" })}</div>`;
  }
  html +=
    '</div><div class="time-body"><div class="hours">' +
    Array.from(
      { length: 24 },
      (_, h) => `<div>${String(h).padStart(2, "0")}:00</div>`,
    ).join("") +
    "</div>";
  for (let i = 0; i < days; i++) {
    const key = addDays(start, i),
      dayStart = Date.parse(zonedISO(key)),
      dayEnd = Date.parse(zonedISO(addDays(key, 1)));
    html +=
      '<div class="day-column">' +
      Array.from(
        { length: 24 },
        (_, h) =>
          `<button class="time-slot" style="top:${h * 52}px" data-new-date="${key}T${String(h).padStart(2, "0")}:00" aria-label="Thêm công việc ${dateLabel(key)} lúc ${h} giờ"></button>`,
      ).join("");
    const events = tasks
      .filter((t) => intersects(t, key))
      .map((t) => {
        const p = parts(t.start_time),
          q = t.end_time ? parts(t.end_time) : null;
        let top =
          Date.parse(t.start_time) < dayStart
            ? 0
            : Number(p.hour) * 60 + Number(p.minute);
        let bottom = t.end_time
          ? Date.parse(t.end_time) >= dayEnd
            ? 1440
            : Number(q.hour) * 60 + Number(q.minute)
          : top + 30;
        return {
          task: t,
          top,
          bottom: Math.min(1440, Math.max(top + 24, bottom)),
          column: 0,
          total: 1,
        };
      })
      .sort((a, b) => a.top - b.top || b.bottom - a.bottom);
    // Chia cột các sự kiện giao nhau để mọi công việc đều có thể bấm.
    let group = [],
      groupEnd = -1;
    const finish = () => {
      const columns = [];
      for (const event of group) {
        let column = columns.findIndex((end) => end <= event.top);
        if (column < 0) column = columns.length;
        columns[column] = event.bottom;
        event.column = column;
      }
      group.forEach((e) => (e.total = columns.length));
    };
    for (const event of events) {
      if (event.top >= groupEnd) {
        finish();
        group = [];
        groupEnd = -1;
      }
      group.push(event);
      groupEnd = Math.max(groupEnd, event.bottom);
    }
    finish();
    for (const e of events) {
      const t = e.task;
      html += `<button class="cal-event time-event ${t.status}" draggable="true" style="--event-color:${colorFor(t.category)};top:${(e.top / 60) * 52}px;height:${((e.bottom - e.top) / 60) * 52}px;left:calc(${(e.column / e.total) * 100}% + 2px);width:calc(${100 / e.total}% - 4px)" data-action="edit" data-calendar-task="${t.id}" data-id="${t.id}" title="${esc(t.title)} · ${fmt(t.start_time)}"><strong>${esc(t.title)}</strong>${fmt(t.start_time, false)}${t.end_time ? " – " + fmt(t.end_time, false) : ""}<span class="event-resize" title="Kéo để đổi thời lượng"></span></button>`;
    }
    html += "</div>";
  }
  html += "</div></div>";
  $("calendar").innerHTML = html;
  const body = $("calendar").querySelector(".time-body");
  body.scrollTop = 7 * 52;
}
async function loadStats() {
  const data = await api(
    "/stats?" +
      new URLSearchParams({
        date_from: $("statsFrom").value,
        date_to: $("statsTo").value,
      }),
  );
  const period = data.period;
  $("periodStats").innerHTML = [
    ["Có lịch trong kỳ", period.scheduled],
    ["Đã hoàn thành trong kỳ", period.completed],
    ["Tỷ lệ hoàn thành lịch trong kỳ", period.completion_rate + "%"],
    ["Hoàn thành đúng hạn", period.on_time],
  ]
    .map(
      ([label, value]) =>
        `<div class="summary-card"><span>${label}</span><strong>${value}</strong></div>`,
    )
    .join("");
  const max = Math.max(
    1,
    ...data.daily.flatMap((d) => [d.scheduled, d.completed]),
  );
  $("dailyChart").innerHTML = data.daily
    .map(
      (d) =>
        `<div class="bar-group" title="${dateLabel(d.date)}: có lịch ${d.scheduled}, hoàn thành ${d.completed}"><div class="bar-pair"><div class="bar" style="height:${(d.scheduled / max) * 90}%"><span class="bar-number">${d.scheduled || ""}</span></div><div class="bar completed" style="height:${(d.completed / max) * 90}%"><span class="bar-number">${d.completed || ""}</span></div></div><small>${dateLabel(d.date)}</small></div>`,
    )
    .join("");
  const total = period.scheduled || 1;
  $("categoryChart").innerHTML = data.categories.length
    ? data.categories
        .map(
          (c) =>
            `<div class="category-bar"><div><span>${esc(c.name)}</span><strong>${c.count}</strong></div><div class="category-bar-track"><i style="width:${(c.count / total) * 100}%;background:${colorFor(c.name)}"></i></div></div>`,
        )
        .join("")
    : '<div class="empty">Chưa có dữ liệu trong khoảng này.</div>';
  $("legacyStats").textContent = data.legacy_completed_without_date
    ? `${data.legacy_completed_without_date} công việc đã hoàn thành (dữ liệu cũ hoặc nhập từ tệp) chưa có thời điểm hoàn thành; không tính vào biểu đồ hoàn thành theo ngày.`
    : "";
}
const ACTIVITY_LABEL = {
  created: "Đã tạo",
  updated: "Đã cập nhật",
  deleted: "Đã chuyển vào thùng rác",
  restored: "Đã khôi phục",
  purged: "Đã xóa vĩnh viễn",
  duplicated: "Đã nhân bản",
  rescheduled: "Đã dời lịch",
  timer_started: "Bắt đầu tập trung",
  timer_stopped: "Kết thúc tập trung",
};
async function loadActivities() {
  const data = await api(`/activities?page=${activityPage}&page_size=30`);
  $("activityList").innerHTML = data.items.length
    ? `<div class="activity-timeline">${data.items
        .map(
          (item) =>
            `<article class="activity-item"><i></i><div><strong>${esc(ACTIVITY_LABEL[item.action] || item.action)}</strong><span>${esc(item.task_title)}</span><small>${fmt(item.created_at)}${item.details?.minutes ? ` · ${item.details.minutes} phút` : ""}</small></div>${item.task_id ? `<button class="link" data-activity-task="${item.task_id}">Xem</button>` : ""}</article>`,
        )
        .join("")}</div>`
    : '<div class="empty">Chưa có hoạt động nào được ghi lại.</div>';
  paginate("activityPagination", data.total, activityPage, 30, "activities");
}
async function pollNotices() {
  if (!user) return;
  try {
    const data = await api("/notifications");
    $("unreadBadge").textContent = data.unread;
    $("unreadBadge").classList.toggle("hidden", !data.unread);
    if ("Notification" in window && Notification.permission === "granted") {
      for (const n of data.items.filter(
        (n) =>
          !n.read_at &&
          (!n.snoozed_until || Date.parse(n.snoozed_until) <= Date.now()),
      )) {
        if (browserNotified.has(n.id)) continue;
        browserNotified.add(n.id);
        const message = new Notification("Lịch Làm Việc", {
          body: n.title,
          tag: "task-" + n.id,
        });
        message.onclick = () => {
          window.focus();
          openTaskById(n.task_id).catch((e) => toast(e.message, true));
          message.close();
        };
      }
    }
    $("connectionLabel").textContent = "Không gian của bạn";
  } catch (err) {
    $("connectionLabel").textContent = "Chưa kết nối";
  }
}
async function loadNotifications() {
  const data = await api("/notifications?page=" + noticePage);
  $("notificationList").innerHTML = data.items.length
    ? data.items
        .map(
          (n) =>
            `<article class="notice ${n.read_at ? "" : "unread"}"><span>♧</span><div class="notice-body"><strong>${esc(n.title)}</strong><small>${n.snoozed_until && Date.parse(n.snoozed_until) > Date.now() ? `Đã hoãn đến ${fmt(n.snoozed_until)}` : `${fmt(n.created_at)} · ${n.read_at ? "Đã đọc" : "Chưa đọc"}`}</small></div><button class="link" data-notice-open="${n.task_id}" data-notice="${n.id}">Xem việc</button>${!n.read_at ? `<button class="link" data-notice-snooze="${n.id}">Hoãn 10'</button><button class="link" data-notice-read="${n.id}">Đã đọc</button>` : ""}</article>`,
        )
        .join("")
    : '<div class="empty">Bạn chưa có thông báo mới.</div>';
  paginate(
    "notificationPagination",
    data.total,
    noticePage,
    30,
    "notifications",
  );
  await pollNotices();
}
async function renderCategories() {
  await loadCategories();
  $("categoryList").innerHTML =
    categories
      .map(
        (c) =>
          `<div class="category-row"><i style="background:${c.color}"></i><strong>${esc(c.name)}</strong><button class="link" data-category-edit="${c.id}">Sửa</button><button class="link danger-text" data-category-delete="${c.id}">Xóa</button></div>`,
      )
      .join("") || '<div class="empty">Chưa có danh mục.</div>';
}
async function renderAccount() {
  $("profileName").value = user.display_name || "";
  $("profileEmail").value = user.email;
  if (![...$("profileZone").options].some((o) => o.value === user.timezone))
    $("profileZone").add(new Option(user.timezone, user.timezone));
  $("profileZone").value = user.timezone;
  $("profileReminders").checked = user.email_reminders;
  $("emailStatus").textContent = emailConfigured
    ? "Dịch vụ email đã được cấu hình. Hãy chọn giờ nhắc khi tạo công việc."
    : "Máy chủ chưa cấu hình SMTP. Bạn vẫn có thể nhận thông báo trong ứng dụng; xem README để bật email.";
}
function checklistRow(item = { text: "", done: false }) {
  const row = document.createElement("div");
  row.className = "checklist-row";
  row.innerHTML = `<input type="checkbox" ${item.done ? "checked" : ""} aria-label="Hoàn thành bước"><input type="text" maxlength="200" required value="${esc(item.text)}" placeholder="Một bước nhỏ để hoàn thành…" aria-label="Nội dung bước"><button type="button" aria-label="Xóa bước">×</button>`;
  row.querySelector("button").addEventListener("click", () => row.remove());
  $("checklistEditor").appendChild(row);
}
function openTask(task = null, start = null) {
  editing = task;
  $("taskForm").reset();
  $("taskFormError").textContent = "";
  $("taskId").value = task?.id || "";
  $("modalTitle").textContent = task ? "Chi tiết công việc" : "Công việc mới";
  $("taskTitle").value = task?.title || "";
  $("taskDescription").value = task?.description || "";
  $("taskLocation").value = task?.location || "";
  $("taskMeetingUrl").value = task?.meeting_url || "";
  $("taskCategory").value = task?.category || "";
  $("taskPriority").value = task?.priority || "medium";
  $("taskStatus").value = task?.status || "todo";
  const tz = task?.timezone || zone();
  $("taskZone").textContent = "Thời gian theo múi giờ " + tz;
  $("taskStart").value = task
    ? localInput(task.start_time, tz)
    : start || localInput(new Date(), tz);
  $("taskEnd").value = task ? localInput(task.end_time, tz) : "";
  $("taskDeadline").value = task ? localInput(task.deadline, tz) : "";
  if (
    task?.reminder_minutes != null &&
    ![...$("taskReminder").options].some(
      (x) => x.value === String(task.reminder_minutes),
    )
  )
    $("taskReminder").add(
      new Option(task.reminder_minutes + " phút", task.reminder_minutes),
    );
  $("taskReminder").value = task?.reminder_minutes ?? "";
  $("taskRecurrence").value = task?.recurrence || "none";
  $("recurrenceLabel").classList.toggle("hidden", !!task);
  $("recurrenceUntilLabel").classList.add("hidden");
  $("taskRecurrenceUntil").required = false;
  $("scopeLabel").classList.toggle("hidden", !task?.series_id);
  $("taskScope").value = "one";
  $("checklistEditor").innerHTML = "";
  (task?.checklist || []).forEach(checklistRow);
  $("deleteFromModal").classList.toggle("hidden", !task);
  $("duplicateFromModal").classList.toggle("hidden", !task);
  $("taskModal").showModal();
  $("taskTitle").focus();
}
async function openTaskById(id) {
  const task = await api("/tasks/" + id);
  openTask(task);
}
async function withConflict(fn) {
  try {
    return await fn(false);
  } catch (err) {
    if (err.status === 409 && err.detail?.conflicts) {
      const text = err.detail.conflicts
        .map((t) => `• ${t.title} (${fmt(t.start_time)})`)
        .join("\n");
      if (confirm("Lịch bị trùng:\n" + text + "\n\nBạn vẫn muốn lưu?"))
        return fn(true);
      return null;
    }
    throw err;
  }
}
async function deleteTask(task, scope = "one") {
  if (
    !confirm(
      scope === "series"
        ? "Chuyển tất cả công việc trong chuỗi vào thùng rác?"
        : `Chuyển “${task.title}” vào thùng rác?`,
    )
  )
    return;
  await api(`/tasks/${task.id}?scope=${scope}`, { method: "DELETE" });
  if ($("taskModal").open) $("taskModal").close();
  toast("Đã chuyển vào thùng rác");
  await refresh();
  await pollNotices();
}
async function taskAction(action, id) {
  if (action === "edit") return openTaskById(id);
  if (action === "delete") return deleteTask(await api("/tasks/" + id));
  if (action === "duplicate") {
    const result = await withConflict((allow) =>
      api(`/tasks/${id}/duplicate`, {
        method: "POST",
        body: { offset_days: 1, allow_overlap: allow },
      }),
    );
    if (result) {
      toast("Đã nhân bản công việc sang ngày kế tiếp");
      await refresh();
    }
  }
  if (action === "tomorrow") {
    const result = await withConflict((allow) =>
      api(`/tasks/${id}/reschedule`, {
        method: "POST",
        body: { target_date: addDays(dayKey(), 1), allow_overlap: allow },
      }),
    );
    if (result) {
      toast("Đã dời công việc sang ngày mai");
      await refresh();
    }
  }
  if (action === "focus") {
    if (activeFocus?.id === id) await stopFocusTimer();
    else {
      const task = await api(`/tasks/${id}/timer/start`, { method: "POST" });
      startFocusDisplay(task);
      toast("Đã bắt đầu phiên tập trung 25 phút");
      await refresh();
    }
  }
  if (action === "done") {
    const task = await api("/tasks/" + id);
    const result = await withConflict((allow) =>
      api("/tasks/" + id, {
        method: "PUT",
        body: {
          status: task.status === "done" ? "todo" : "done",
          allow_overlap: allow,
        },
      }),
    );
    if (result) {
      toast(
        result.status === "done"
          ? "Đã hoàn thành. Thêm một bước tiến!"
          : "Đã chuyển về chưa làm",
      );
      await refresh();
    }
  }
  if (action === "restore") {
    const result = await withConflict((allow) =>
      api(`/tasks/${id}/restore?allow_overlap=${allow}`, { method: "POST" }),
    );
    if (result) {
      toast("Đã khôi phục công việc");
      await refresh();
    }
  }
  if (
    action === "purge" &&
    confirm(
      "Xóa vĩnh viễn công việc này? Không thể khôi phục sau thao tác này.",
    )
  ) {
    await api(`/tasks/${id}/permanent`, { method: "DELETE" });
    toast("Đã xóa vĩnh viễn");
    await refresh();
  }
}
function localPlusMinutes(value, minutes) {
  const date = new Date(value + (value.endsWith("Z") ? "" : "Z"));
  date.setUTCMinutes(date.getUTCMinutes() + minutes);
  return date.toISOString().slice(0, 16);
}
function startFocusDisplay(task) {
  activeFocus = task;
  clearInterval(focusInterval);
  $("focusDock").classList.remove("hidden");
  $("focusTitle").textContent = task.title;
  const tick = () => {
    if (!activeFocus?.timer_started_at || focusStopping) return;
    const remaining =
      25 * 60 -
      Math.floor(
        (Date.now() - Date.parse(activeFocus.timer_started_at)) / 1000,
      );
    if (remaining <= 0) {
      $("focusClock").textContent = "00:00";
      stopFocusTimer(true).catch((err) => toast(err.message, true));
      return;
    }
    $("focusClock").textContent =
      String(Math.floor(remaining / 60)).padStart(2, "0") +
      ":" +
      String(remaining % 60).padStart(2, "0");
  };
  tick();
  focusInterval = setInterval(tick, 1000);
}
async function stopFocusTimer(completed = false) {
  if (!activeFocus || focusStopping) return;
  focusStopping = true;
  try {
    const task = await api(`/tasks/${activeFocus.id}/timer/stop`, {
      method: "POST",
    });
    activeFocus = null;
    clearInterval(focusInterval);
    $("focusDock").classList.add("hidden");
    toast(
      completed
        ? "Hoàn thành phiên tập trung 25 phút"
        : "Đã dừng và lưu thời gian",
    );
    if (
      completed &&
      "Notification" in window &&
      Notification.permission === "granted"
    )
      new Notification("Phiên tập trung đã hoàn thành", { body: task.title });
    await refresh();
  } finally {
    focusStopping = false;
  }
}
function templatePayload(name) {
  const start = $("taskStart").value;
  const end = $("taskEnd").value;
  let duration = 60;
  if (start && end)
    duration = Math.max(
      15,
      Math.round((Date.parse(end + "Z") - Date.parse(start + "Z")) / 60000),
    );
  return {
    name,
    title: $("taskTitle").value.trim(),
    description: $("taskDescription").value.trim() || null,
    category: $("taskCategory").value || null,
    priority: $("taskPriority").value,
    duration_minutes: duration,
    reminder_minutes:
      $("taskReminder").value === "" ? null : Number($("taskReminder").value),
    checklist: [...$("checklistEditor").children].map((row) => ({
      text: row.querySelector("[type=text]").value.trim(),
      done: false,
    })),
    location: $("taskLocation").value.trim() || null,
    meeting_url: $("taskMeetingUrl").value.trim() || null,
  };
}
function applyTemplate(item) {
  $("taskTitle").value = item.title;
  $("taskDescription").value = item.description || "";
  $("taskCategory").value = item.category || "";
  $("taskPriority").value = item.priority;
  $("taskReminder").value = item.reminder_minutes ?? "";
  $("taskLocation").value = item.location || "";
  $("taskMeetingUrl").value = item.meeting_url || "";
  if (!$("taskStart").value) $("taskStart").value = localInput(new Date());
  $("taskEnd").value = localPlusMinutes(
    $("taskStart").value,
    item.duration_minutes,
  );
  $("checklistEditor").innerHTML = "";
  (item.checklist || []).forEach((step) =>
    checklistRow({ text: step.text, done: false }),
  );
}
async function moveTaskTo(id, targetWall) {
  const task = await api("/tasks/" + id);
  const sourceWall = localInput(task.start_time, task.timezone);
  if (targetWall.length === 10) targetWall += "T" + sourceWall.slice(11, 16);
  const start = zonedISO(targetWall, task.timezone);
  const shift = Date.parse(start) - Date.parse(task.start_time);
  const shifted = (value) =>
    value ? new Date(Date.parse(value) + shift).toISOString() : null;
  const saved = await withConflict((allow) =>
    api("/tasks/" + id, {
      method: "PUT",
      body: {
        start_time: start,
        end_time: shifted(task.end_time),
        deadline: shifted(task.deadline),
        allow_overlap: allow,
      },
    }),
  );
  if (saved) {
    toast("Đã dời công việc trên lịch");
    await refresh();
  }
}
async function resizeCalendarTask(event, handle) {
  event.preventDefault();
  event.stopPropagation();
  calendarSuppressClick = true;
  const card = handle.closest("[data-calendar-task]");
  const task = await api("/tasks/" + card.dataset.calendarTask);
  const initialY = event.clientY;
  const baseEnd =
    Date.parse(task.end_time || task.start_time) +
    (task.end_time ? 0 : 30 * 60000);
  let delta = 0;
  card.draggable = false;
  card.classList.add("resizing");
  const move = (pointer) => {
    delta = Math.round(((pointer.clientY - initialY) / 52) * 4) * 15;
    const duration = Math.max(
      15,
      Math.round((baseEnd - Date.parse(task.start_time)) / 60000) + delta,
    );
    card.style.height = `${Math.max(20, (duration / 60) * 52)}px`;
  };
  const finish = async () => {
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", finish);
    card.classList.remove("resizing");
    try {
      const minutes = Math.max(
        15,
        Math.round((baseEnd - Date.parse(task.start_time)) / 60000) + delta,
      );
      if (delta) {
        const saved = await withConflict((allow) =>
          api("/tasks/" + task.id, {
            method: "PUT",
            body: {
              end_time: new Date(
                Date.parse(task.start_time) + minutes * 60000,
              ).toISOString(),
              allow_overlap: allow,
            },
          }),
        );
        if (saved) toast("Đã cập nhật thời lượng công việc");
      }
      await refresh();
    } catch (err) {
      toast(err.message, true);
      await refresh();
    } finally {
      card.draggable = true;
      setTimeout(() => (calendarSuppressClick = false), 100);
    }
  };
  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", finish, { once: true });
}
function resetFilters() {
  $("filterForm").reset();
  listPage = 1;
}
function quickFilter(kind) {
  resetFilters();
  if (kind === "overdue") $("filterOverdue").checked = true;
  else {
    const today = dayKey();
    $("filterFrom").value = kind === "week" ? weekStart(today) : today;
    $("filterTo").value =
      kind === "week" ? addDays(weekStart(today), 6) : today;
  }
  showView("tasks");
}
// Các hành động động được bắt tập trung, không chèn JavaScript vào nội dung người dùng.
document.addEventListener("click", async (event) => {
  const b = event.target.closest("button");
  if (!b) return;
  if (calendarSuppressClick && b.closest("#calendar")) return;
  try {
    if (b.dataset.auth) showAuth(b.dataset.auth);
    if (b.dataset.view) await showView(b.dataset.view);
    if (b.dataset.action) {
      b.disabled = true;
      try {
        await taskAction(b.dataset.action, Number(b.dataset.id));
      } finally {
        b.disabled = false;
      }
    }
    if (b.dataset.summary) {
      resetFilters();
      if (b.dataset.summary === "overdue") $("filterOverdue").checked = true;
      else if (b.dataset.summary !== "total")
        $("filterStatus").value = b.dataset.summary;
      await showView("tasks");
    }
    if (b.dataset.page) {
      if (b.disabled) return;
      const page = Number(b.dataset.page);
      if (b.dataset.kind === "tasks") listPage = page;
      else if (b.dataset.kind === "trash") trashPage = page;
      else if (b.dataset.kind === "activities") activityPage = page;
      else noticePage = page;
      await refresh();
    }
    if (b.dataset.quick) quickFilter(b.dataset.quick);
    if (b.dataset.cal) {
      calMode = b.dataset.cal;
      document
        .querySelectorAll("[data-cal]")
        .forEach((x) => x.classList.toggle("active", x === b));
      await refresh();
    }
    if (b.dataset.newDate) openTask(null, b.dataset.newDate);
    if (b.dataset.calDay) {
      calDate = b.dataset.calDay;
      calMode = "day";
      document
        .querySelectorAll("[data-cal]")
        .forEach((x) => x.classList.toggle("active", x.dataset.cal === "day"));
      await refresh();
    }
    if (b.dataset.period) {
      $("statsFrom").value =
        b.dataset.period === "week"
          ? addDays(dayKey(), -6)
          : dayKey().slice(0, 7) + "-01";
      $("statsTo").value = dayKey();
      await refresh();
    }
    if (b.dataset.noticeRead) {
      await api("/notifications/" + b.dataset.noticeRead + "/read", {
        method: "POST",
      });
      await loadNotifications();
    }
    if (b.dataset.noticeSnooze) {
      await api(`/notifications/${b.dataset.noticeSnooze}/snooze`, {
        method: "POST",
        body: { minutes: 10 },
      });
      browserNotified.delete(Number(b.dataset.noticeSnooze));
      toast("Đã hoãn thông báo 10 phút");
      await loadNotifications();
    }
    if (b.dataset.noticeOpen) {
      await api("/notifications/" + b.dataset.notice + "/read", {
        method: "POST",
      });
      await loadNotifications();
      await openTaskById(b.dataset.noticeOpen);
    }
    if (b.dataset.activityTask) await openTaskById(b.dataset.activityTask);
    if (b.dataset.categoryEdit) {
      const c = categories.find((x) => x.id === Number(b.dataset.categoryEdit));
      $("categoryId").value = c.id;
      $("categoryName").value = c.name;
      $("categoryColor").value = c.color;
      $("categoryName").focus();
    }
    if (b.dataset.categoryDelete) {
      const c = categories.find(
        (x) => x.id === Number(b.dataset.categoryDelete),
      );
      if (
        confirm(
          `Xóa danh mục “${c.name}”? Các công việc vẫn giữ lại và chuyển thành chưa phân loại.`,
        )
      ) {
        await api("/categories/" + c.id, { method: "DELETE" });
        await renderCategories();
        toast("Đã xóa danh mục");
      }
    }
    if (b.dataset.export) {
      const res = await api("/transfer/export?format=" + b.dataset.export, {
        raw: true,
      });
      const blob = await res.blob(),
        url = URL.createObjectURL(blob),
        a = document.createElement("a");
      a.href = url;
      a.download = "lich-lam-viec." + b.dataset.export;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  } catch (err) {
    toast(err.message, true);
  }
});
$("calendar").addEventListener("click", (e) => {
  if (calendarSuppressClick) return;
  if (e.target.matches("[data-date-cell]"))
    openTask(null, e.target.dataset.dateCell + "T09:00");
});
$("calendar").addEventListener("dragstart", (event) => {
  const card = event.target.closest("[data-calendar-task]");
  if (!card || event.target.closest(".event-resize")) return;
  calendarSuppressClick = true;
  card.classList.add("dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", card.dataset.calendarTask);
});
$("calendar").addEventListener("dragend", (event) => {
  event.target.closest("[data-calendar-task]")?.classList.remove("dragging");
  document
    .querySelectorAll(".calendar-drop-target")
    .forEach((element) => element.classList.remove("calendar-drop-target"));
  setTimeout(() => (calendarSuppressClick = false), 100);
});
$("calendar").addEventListener("dragover", (event) => {
  const target =
    event.target.closest("[data-date-cell]") ||
    event.target.closest("[data-new-date]");
  if (!target) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  document
    .querySelectorAll(".calendar-drop-target")
    .forEach((element) => element.classList.remove("calendar-drop-target"));
  target.classList.add("calendar-drop-target");
});
$("calendar").addEventListener("drop", async (event) => {
  const target =
    event.target.closest("[data-date-cell]") ||
    event.target.closest("[data-new-date]");
  if (!target) return;
  event.preventDefault();
  const id = Number(event.dataTransfer.getData("text/plain"));
  const wall = target.dataset.dateCell || target.dataset.newDate;
  try {
    if (id && wall) await moveTaskTo(id, wall);
  } catch (err) {
    toast(err.message, true);
    await refresh();
  }
});
$("calendar").addEventListener("pointerdown", (event) => {
  const handle = event.target.closest(".event-resize");
  if (!handle) return;
  resizeCalendarTask(event, handle).catch((err) => toast(err.message, true));
});
$("loginForm").addEventListener("submit", (e) => {
  e.preventDefault();
  busy(e.currentTarget, async () => {
    try {
      const data = await api("/auth/login", {
        method: "POST",
        body: new URLSearchParams({
          username: $("loginUsername").value.trim(),
          password: $("loginPassword").value,
        }),
        auth: false,
      });
      token = data.access_token;
      localStorage.setItem("sm_token", token);
      await enterApp();
    } catch (err) {
      $("authMessage").textContent = err.message;
    }
  });
});
$("registerForm").addEventListener("submit", (e) => {
  e.preventDefault();
  busy(e.currentTarget, async () => {
    try {
      await api("/auth/register", {
        method: "POST",
        body: {
          username: $("registerUsername").value.trim(),
          email: $("registerEmail").value.trim(),
          password: $("registerPassword").value,
        },
        auth: false,
      });
      $("loginUsername").value = $("registerUsername").value.trim();
      $("registerForm").reset();
      showAuth("login");
      $("authMessage").textContent =
        "Tạo tài khoản thành công. Hãy đăng nhập để bắt đầu.";
    } catch (err) {
      $("authMessage").textContent = err.message;
    }
  });
});
$("forgotLink").addEventListener("click", () => showAuth("forgot"));
$("forgotForm").addEventListener("submit", (e) => {
  e.preventDefault();
  busy(e.currentTarget, async () => {
    try {
      const data = await api("/auth/forgot-password", {
        method: "POST",
        body: { email: $("forgotEmail").value },
        auth: false,
      });
      $("authMessage").textContent = data.message;
    } catch (err) {
      $("authMessage").textContent = err.message;
    }
  });
});
$("resetForm").addEventListener("submit", (e) => {
  e.preventDefault();
  busy(e.currentTarget, async () => {
    try {
      const data = await api("/auth/reset-password", {
        method: "POST",
        body: { token: resetToken, new_password: $("resetPassword").value },
        auth: false,
      });
      resetToken = "";
      history.replaceState(null, "", location.pathname);
      $("resetForm").reset();
      showAuth("login");
      $("authMessage").textContent = data.message;
    } catch (err) {
      $("authMessage").textContent = err.message;
    }
  });
});
$("logoutBtn").addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
    localLogout();
  } catch (err) {
    toast(err.message, true);
  }
});
$("refreshBtn").addEventListener("click", refresh);
$("newTaskBtn").addEventListener("click", () => openTask());
$("todayCreate").addEventListener("click", () => openTask());
$("viewOverdue").addEventListener("click", () => quickFilter("overdue"));
$("filterForm").addEventListener("submit", (e) => {
  e.preventDefault();
  listPage = 1;
  refresh();
});
$("clearFilter").addEventListener("click", () => {
  resetFilters();
  refresh();
});
$("applySavedFilter").addEventListener("click", async () => {
  const item = savedFilters.find(
    (filter) => filter.id === Number($("savedFilterSelect").value),
  );
  if (!item) return toast("Hãy chọn một bộ lọc", true);
  applyFilterState(item.query);
  await refresh();
  toast(`Đã áp dụng “${item.name}”`);
});
$("saveCurrentFilter").addEventListener("click", async () => {
  const name = prompt("Tên bộ lọc:");
  if (!name?.trim()) return;
  try {
    const item = await api("/saved-filters", {
      method: "POST",
      body: { name: name.trim(), query: currentFilterState() },
    });
    await loadSavedFilters();
    $("savedFilterSelect").value = item.id;
    toast("Đã lưu bộ lọc");
  } catch (err) {
    toast(err.message, true);
  }
});
$("deleteSavedFilter").addEventListener("click", async () => {
  const id = Number($("savedFilterSelect").value);
  const item = savedFilters.find((filter) => filter.id === id);
  if (!item || !confirm(`Xóa bộ lọc “${item.name}”?`)) return;
  try {
    await api("/saved-filters/" + id, { method: "DELETE" });
    await loadSavedFilters();
    toast("Đã xóa bộ lọc");
  } catch (err) {
    toast(err.message, true);
  }
});
$("calToday").addEventListener("click", () => {
  calDate = dayKey();
  refresh();
});
function shiftCalendar(n) {
  if (calMode === "month") {
    const d = new Date(calDate.slice(0, 7) + "-01T12:00:00Z");
    d.setUTCMonth(d.getUTCMonth() + n);
    calDate = d.toISOString().slice(0, 10);
  } else calDate = addDays(calDate, n * (calMode === "week" ? 7 : 1));
  refresh();
}
$("calPrev").addEventListener("click", () => shiftCalendar(-1));
$("calNext").addEventListener("click", () => shiftCalendar(1));
$("statsForm").addEventListener("submit", (e) => {
  e.preventDefault();
  refresh();
});
$("exportPdf").addEventListener("click", async () => {
  try {
    const params = new URLSearchParams({
      date_from: $("statsFrom").value,
      date_to: $("statsTo").value,
    });
    const response = await api("/reports/tasks.pdf?" + params, { raw: true });
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = `bao-cao-lich-${$("statsFrom").value}-${$("statsTo").value}.pdf`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (err) {
    toast(err.message, true);
  }
});
$("closeTask").addEventListener("click", () => $("taskModal").close());
$("cancelTask").addEventListener("click", () => $("taskModal").close());
$("addChecklist").addEventListener("click", () => {
  if ($("checklistEditor").children.length >= 100)
    return toast("Tối đa 100 bước", true);
  checklistRow();
  $("checklistEditor").lastElementChild.querySelector("[type=text]").focus();
});
$("loadTemplate").addEventListener("click", () => {
  const item = templates.find(
    (template) => template.id === Number($("taskTemplate").value),
  );
  if (!item) return toast("Hãy chọn một mẫu công việc", true);
  applyTemplate(item);
  toast("Đã điền nội dung từ mẫu");
});
$("saveTemplate").addEventListener("click", async () => {
  const name = prompt("Tên mẫu công việc:");
  if (!name?.trim()) return;
  try {
    const payload = templatePayload(name.trim());
    if (!payload.title) throw new Error("Hãy nhập tiêu đề trước khi lưu mẫu");
    const item = await api("/templates", { method: "POST", body: payload });
    await loadTemplates();
    $("taskTemplate").value = item.id;
    toast("Đã lưu mẫu công việc");
  } catch (err) {
    $("taskFormError").textContent = err.message;
  }
});
$("deleteTemplate").addEventListener("click", async () => {
  const id = Number($("taskTemplate").value);
  const item = templates.find((template) => template.id === id);
  if (!item || !confirm(`Xóa mẫu “${item.name}”?`)) return;
  try {
    await api("/templates/" + id, { method: "DELETE" });
    await loadTemplates();
    toast("Đã xóa mẫu công việc");
  } catch (err) {
    $("taskFormError").textContent = err.message;
  }
});
$("taskRecurrence").addEventListener("change", () => {
  const enabled = $("taskRecurrence").value !== "none";
  $("recurrenceUntilLabel").classList.toggle("hidden", !enabled);
  $("taskRecurrenceUntil").required = enabled;
  if (enabled && !$("taskRecurrenceUntil").value)
    $("taskRecurrenceUntil").value = addDays(
      $("taskStart").value.slice(0, 10),
      30,
    );
});
$("deleteFromModal").addEventListener("click", async () => {
  try {
    if (editing) await deleteTask(editing, $("taskScope").value);
  } catch (err) {
    $("taskFormError").textContent = err.message;
  }
});
$("duplicateFromModal").addEventListener("click", async () => {
  if (!editing) return;
  try {
    const result = await withConflict((allow) =>
      api(`/tasks/${editing.id}/duplicate`, {
        method: "POST",
        body: { offset_days: 1, allow_overlap: allow },
      }),
    );
    if (result) {
      $("taskModal").close();
      toast("Đã nhân bản công việc sang ngày kế tiếp");
      await refresh();
    }
  } catch (err) {
    $("taskFormError").textContent = err.message;
  }
});
$("stopFocus").addEventListener("click", () =>
  stopFocusTimer().catch((err) => toast(err.message, true)),
);
$("taskForm").addEventListener("submit", (e) => {
  e.preventDefault();
  busy(e.currentTarget, async () => {
    try {
      $("taskFormError").textContent = "";
      const tz = editing?.timezone || zone();
      const body = {
        title: $("taskTitle").value.trim(),
        description: $("taskDescription").value.trim() || null,
        location: $("taskLocation").value.trim() || null,
        meeting_url: $("taskMeetingUrl").value.trim() || null,
        category: $("taskCategory").value || null,
        priority: $("taskPriority").value,
        status: $("taskStatus").value,
        start_time: zonedISO($("taskStart").value, tz),
        end_time: zonedISO($("taskEnd").value, tz),
        deadline: zonedISO($("taskDeadline").value, tz),
        timezone: tz,
        reminder_minutes:
          $("taskReminder").value === ""
            ? null
            : Number($("taskReminder").value),
        checklist: [...$("checklistEditor").children].map((row) => ({
          text: row.querySelector("[type=text]").value.trim(),
          done: row.querySelector("[type=checkbox]").checked,
        })),
      };
      if (!body.title) throw new Error("Vui lòng nhập tiêu đề");
      if (
        body.end_time &&
        Date.parse(body.end_time) <= Date.parse(body.start_time)
      )
        throw new Error("Giờ kết thúc phải sau giờ bắt đầu");
      if (
        body.deadline &&
        Date.parse(body.deadline) < Date.parse(body.start_time)
      )
        throw new Error("Hạn chót phải từ giờ bắt đầu trở đi");
      if (editing) body.scope = $("taskScope").value;
      else {
        body.recurrence = $("taskRecurrence").value;
        body.recurrence_until =
          body.recurrence === "none" ? null : $("taskRecurrenceUntil").value;
      }
      const saved = await withConflict((allow) =>
        api("/tasks" + (editing ? "/" + editing.id : ""), {
          method: editing ? "PUT" : "POST",
          body: { ...body, allow_overlap: allow },
        }),
      );
      if (saved) {
        $("taskModal").close();
        toast(
          "Đã lưu công việc" +
            (!editing && body.recurrence !== "none" ? " và các lần lặp" : ""),
        );
        await refresh();
        await pollNotices();
      }
    } catch (err) {
      $("taskFormError").textContent = err.message;
    }
  });
});
$("categoryForm").addEventListener("submit", (e) => {
  e.preventDefault();
  busy(e.currentTarget, async () => {
    try {
      const id = $("categoryId").value;
      await api("/categories" + (id ? "/" + id : ""), {
        method: id ? "PUT" : "POST",
        body: {
          name: $("categoryName").value.trim(),
          color: $("categoryColor").value,
        },
      });
      $("categoryForm").reset();
      $("categoryId").value = "";
      await renderCategories();
      toast("Đã lưu danh mục");
    } catch (err) {
      toast(err.message, true);
    }
  });
});
$("cancelCategory").addEventListener("click", () => {
  $("categoryForm").reset();
  $("categoryId").value = "";
});
$("readAll").addEventListener("click", async () => {
  try {
    await api("/notifications/read-all", { method: "POST" });
    await loadNotifications();
  } catch (err) {
    toast(err.message, true);
  }
});
$("enableNotifications").addEventListener("click", async () => {
  try {
    if (!("Notification" in window))
      return toast("Trình duyệt này chưa hỗ trợ thông báo hệ thống.", true);
    const permission = await Notification.requestPermission();
    toast(
      permission === "granted"
        ? "Đã bật thông báo khi trang đang mở."
        : "Bạn có thể cấp quyền trong cài đặt trình duyệt.",
    );
    await pollNotices();
  } catch (err) {
    toast(err.message, true);
  }
});
$("profileForm").addEventListener("submit", (e) => {
  e.preventDefault();
  busy(e.currentTarget, async () => {
    try {
      user = await api("/auth/me", {
        method: "PUT",
        body: {
          display_name: $("profileName").value.trim(),
          email: $("profileEmail").value.trim(),
          timezone: $("profileZone").value,
          email_reminders: $("profileReminders").checked,
        },
      });
      await enterApp();
      toast("Đã cập nhật thông tin");
    } catch (err) {
      toast(err.message, true);
    }
  });
});
$("passwordForm").addEventListener("submit", (e) => {
  e.preventDefault();
  busy(e.currentTarget, async () => {
    try {
      if ($("newPassword").value !== $("confirmPassword").value)
        throw new Error("Hai mật khẩu mới chưa khớp");
      const data = await api("/auth/change-password", {
        method: "POST",
        body: {
          current_password: $("oldPassword").value,
          new_password: $("newPassword").value,
        },
      });
      $("passwordForm").reset();
      localLogout();
      $("authMessage").textContent = data.message;
    } catch (err) {
      toast(err.message, true);
    }
  });
});
$("importForm").addEventListener("submit", (e) => {
  e.preventDefault();
  busy(e.currentTarget, async () => {
    try {
      const file = $("importFile").files[0];
      if (file.size > 2 * 1024 * 1024) throw new Error("Tệp tối đa 2 MB");
      const result = await withConflict((allow) => {
        const body = new FormData();
        body.append("file", file);
        return api("/transfer/import?allow_overlap=" + allow, {
          method: "POST",
          body,
        });
      });
      if (result) {
        $("importResult").textContent =
          `Đã nhập ${result.imported} công việc, bỏ qua ${result.skipped} sự kiện đã có.`;
        await loadCategories();
        toast("Nhập dữ liệu thành công");
      }
    } catch (err) {
      $("importResult").textContent = err.message;
      toast(err.message, true);
    }
  });
});
(async function init() {
  if (location.hash.startsWith("#reset=")) {
    resetToken = location.hash.slice(7);
    showAuth("reset");
    return;
  }
  if (token) {
    try {
      await enterApp();
    } catch (err) {
      $("authMessage").textContent = err.message;
    }
  }
})();

$("accountLogout").addEventListener("click", () => $("logoutBtn").click());
window.addEventListener("hashchange", () => {
  const view = location.hash.slice(1);
  if (user && TITLES[view] && view !== currentView) showView(view);
});
