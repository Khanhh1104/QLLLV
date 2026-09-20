const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const BASE = process.env.TEST_BASE_URL || "http://127.0.0.1:8000";
const artifacts = path.resolve("test-results");
fs.mkdirSync(artifacts, { recursive: true });
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH }
      : {}),
    args: [
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--single-process",
      "--no-zygote",
    ],
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
    timezoneId: "Asia/Ho_Chi_Minh",
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(BASE);
  await page.screenshot({
    path: path.join(artifacts, "login.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Đăng ký", exact: true }).click();
  await page.locator("#registerUsername").fill("khanh_" + Date.now());
  await page
    .locator("#registerEmail")
    .fill("demo" + Date.now() + "@example.com");
  await page.locator("#registerPassword").fill("DemoPassword123");
  await page
    .getByRole("button", { name: "Tạo tài khoản", exact: true })
    .click();
  await page.locator("#loginForm").waitFor({ state: "visible" });
  await page.locator("#loginPassword").fill("DemoPassword123");
  await page.locator("#loginForm button[type=submit]").click();
  await page.locator("#appView").waitFor({ state: "visible" });
  await page.locator("#summary .summary-card").first().waitFor();
  await page.locator("#newTaskBtn").click();
  await page.locator("#taskTitle").fill("Hoàn thiện báo cáo dự án");
  await page
    .locator("#taskDescription")
    .fill("Rà soát nội dung và chuẩn bị tài liệu trình bày.");
  await page.locator("#taskCategory").selectOption("Công việc");
  await page.locator("#taskPriority").selectOption("high");
  const today = await page.evaluate(() =>
    new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" }).format(
      new Date(),
    ),
  );
  await page.locator("#taskStart").fill(today + "T09:00");
  await page.locator("#taskEnd").fill(today + "T10:30");
  await page.locator("#taskReminder").selectOption("15");
  await page.locator("#addChecklist").click();
  await page.locator("#checklistEditor [type=text]").fill("Kiểm tra nội dung");
  await page
    .getByRole("button", { name: "Lưu công việc", exact: true })
    .click();
  await page.locator("#taskModal").waitFor({ state: "hidden" });
  await page.locator("#todayTasks .task-title").first().waitFor();
  const token = await page.evaluate(() => localStorage.getItem("sm_token"));
  for (const t of [
    {
      title: "Học tiếng Anh · 30 phút",
      category: "Học tập",
      start_time: today + "T11:00:00+07:00",
      end_time: today + "T11:30:00+07:00",
      status: "done",
      priority: "low",
    },
    {
      title: "Họp nhóm lên kế hoạch tuần mới",
      category: "Công việc",
      start_time: today + "T14:00:00+07:00",
      end_time: today + "T15:00:00+07:00",
      status: "in_progress",
      priority: "medium",
    },
    {
      title: "Đọc sách và ghi chú",
      category: "Cá nhân",
      start_time: today + "T20:00:00+07:00",
      end_time: today + "T21:00:00+07:00",
      priority: "low",
    },
  ]) {
    const r = await page.request.post(BASE + "/tasks", {
      headers: { Authorization: "Bearer " + token },
      data: t,
    });
    if (r.status() !== 201) throw new Error(await r.text());
  }
  await page.locator("#refreshBtn").click();
  await page.waitForTimeout(400);
  await page.screenshot({
    path: path.join(artifacts, "today.png"),
    fullPage: true,
  });
  for (const view of [
    "calendar",
    "tasks",
    "stats",
    "notifications",
    "categories",
    "transfer",
    "trash",
    "account",
  ]) {
    await page.locator(`[data-view="${view}"]`).click();
    await page.waitForTimeout(250);
    const error = await page.locator("#pageError").textContent();
    if (error) throw new Error(view + ": " + error);
  }
  await page.locator('[data-view="calendar"]').click();
  await page.locator(".month-cell").first().waitFor();
  await page.screenshot({
    path: path.join(artifacts, "month.png"),
    fullPage: true,
  });
  await page.locator('[data-cal="week"]').click();
  await page.locator(".time-event").first().waitFor();
  await page.screenshot({
    path: path.join(artifacts, "week.png"),
    fullPage: true,
  });
  await page.locator('[data-cal="day"]').click();
  await page.locator(".time-slot").first().waitFor();
  await page.locator('[data-view="tasks"]').click();
  await page.locator("#filterKeyword").fill("báo cáo");
  await page
    .locator("#filterForm")
    .getByRole("button", { name: "Lọc", exact: true })
    .click();
  await page.waitForTimeout(200);
  if ((await page.locator("#taskList .task-card").count()) !== 1)
    throw new Error("Filter failed");
  await page.locator('#taskList [data-action="edit"]').first().click();
  await page.locator("#taskModal").waitFor({ state: "visible" });
  await page.locator("#checklistEditor [type=checkbox]").check();
  await page
    .getByRole("button", { name: "Lưu công việc", exact: true })
    .click();
  await page.locator("#taskModal").waitFor({ state: "hidden" });
  page.on("dialog", (d) => d.accept());
  await page.locator('#taskList [data-action="delete"]').first().click();
  await page.waitForTimeout(300);
  await page.locator('[data-view="trash"]').click();
  await page.locator('#trashList [data-action="restore"]').first().click();
  await page.waitForTimeout(300);
  if ((await page.locator("#trashList .task-card").count()) !== 0)
    throw new Error("Restore failed");

  await page.locator('[data-view="categories"]').click();
  await page.locator("#categoryName").fill("Đồ án");
  await page.locator("#categoryColor").fill("#4369b2");
  await page.locator("#categoryForm .primary").click();
  await page.waitForTimeout(200);
  await page.locator("#newTaskBtn").click();
  await page.locator("#taskTitle").fill("Lịch họp lặp");
  await page.locator("#taskCategory").selectOption("Đồ án");
  const dayPlus = (n) => {
    const d = new Date(today + "T12:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  await page.locator("#taskStart").fill(dayPlus(1) + "T09:00");
  await page.locator("#taskEnd").fill(dayPlus(1) + "T10:00");
  await page.locator("#taskRecurrence").selectOption("daily");
  await page.locator("#taskRecurrenceUntil").fill(dayPlus(3));
  await page
    .getByRole("button", { name: "Lưu công việc", exact: true })
    .click();
  await page.locator("#taskModal").waitFor({ state: "hidden" });
  let repeated = await (
    await page.request.get(
      BASE + "/tasks?keyword=" + encodeURIComponent("Lịch họp lặp"),
      { headers: { Authorization: "Bearer " + token } },
    )
  ).json();
  if (repeated.total !== 3) throw new Error("Recurring UI failed");
  await page.locator('[data-view="tasks"]').click();
  await page.locator("#clearFilter").click();
  await page.locator("#filterKeyword").fill("Lịch họp lặp");
  await page
    .locator("#filterForm")
    .getByRole("button", { name: "Lọc", exact: true })
    .click();
  await page.waitForTimeout(200);
  await page.locator('#taskList [data-action="edit"]').first().click();
  await page.locator("#taskScope").selectOption("series");
  await page.locator("#taskTitle").fill("Lịch họp cập nhật");
  await page
    .getByRole("button", { name: "Lưu công việc", exact: true })
    .click();
  await page.locator("#taskModal").waitFor({ state: "hidden" });
  repeated = await (
    await page.request.get(
      BASE + "/tasks?keyword=" + encodeURIComponent("Lịch họp cập nhật"),
      { headers: { Authorization: "Bearer " + token } },
    )
  ).json();
  if (repeated.total !== 3) throw new Error("Series update UI failed");
  await page.locator('[data-view="account"]').click();
  await page.locator("#profileName").fill("Khánh");
  await page.locator("#profileForm .primary").click();
  await page.waitForTimeout(300);
  await page.locator("#whoami").filter({ hasText: "Khánh" }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('[data-view="today"]').click();
  await page.waitForTimeout(250);
  await page.screenshot({
    path: path.join(artifacts, "mobile.png"),
    fullPage: true,
  });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > innerWidth,
  );
  if (overflow) throw new Error("Mobile horizontal overflow");
  await page.locator('[data-view="account"]').click();
  await page.locator("#accountLogout").click();
  await page.locator("#authView").waitFor({ state: "visible" });
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    JSON.stringify({
      result: "passed",
      javascriptErrors: errors,
      views: 9,
      mobileOverflow: overflow,
    }),
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
