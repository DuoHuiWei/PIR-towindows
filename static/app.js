const state = {
  user: null,
  databases: [],
  activeView: "query-view",
  activeDbTab: "db-overview-tab",
  activeMetricsTab: "metrics-load-tab",
  activePerfGeometryTab: "perf-geometry-4k",
  activeLogTab: "query-log-tab",
  activeDatabase: "",
  activeServerAddr: "",
  overviewSelectedDatabase: "",
  uploadLimits: {
    datasetCapacityBytes: 0,
    showHint: false,
  },
  userManagerLogPage: 1,
  userManagerLogTotalPages: 1,
  userManagerLogPageSize: 10,
  databaseLogPage: 1,
  databaseLogTotalPages: 1,
  databaseLogPageSize: 10,
  queryLogPage: 1,
  queryLogTotalPages: 1,
  queryLogPageSize: 10,
  modalLocked: false,
  activePreprocessSession: null,
};

const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => Array.from(document.querySelectorAll(selector));

function setMessage(elementId, text, isError = false) {
  const el = qs(`#${elementId}`);
  if (!el) return;
  el.textContent = text || "";
  el.style.color = isError ? "#cc3354" : "#4f607d";
}

function setDbInlineStatus(text, mode = "") {
  const el = qs("#create-db-status-inline");
  if (!el) return;
  el.textContent = text || "";
  el.classList.remove("state-error", "state-success");
  if (mode === "error") el.classList.add("state-error");
  if (mode === "success") el.classList.add("state-success");
}

function showModal(title, text) {
  const modal = qs("#app-modal");
  const titleEl = qs("#app-modal-title");
  const textEl = qs("#app-modal-text");
  const bodyEl = qs("#app-modal-body");
  if (!modal || !titleEl || !textEl) {
    window.alert(text || title || "\u63d0\u793a");
    return;
  }
  titleEl.textContent = title || "\u63d0\u793a";
  textEl.textContent = text || "";
  if (bodyEl) {
    bodyEl.innerHTML = "";
  }
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

function hideModal(force = false) {
  if (state.modalLocked && !force) return;
  const modal = qs("#app-modal");
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
}

function setModalBody(html) {
  const bodyEl = qs("#app-modal-body");
  if (!bodyEl) return;
  bodyEl.innerHTML = html || "";
}

function setTmpFileCount(count) {
  const inlineEl = qs("#tmp-file-count-inline");
  if (!inlineEl) return;
  inlineEl.textContent = count > 0 ? `\u5df2\u9009 ${count} \u4e2a\u6587\u4ef6` : "\u672a\u9009\u62e9\u4efb\u4f55\u6587\u4ef6";
}

function formatBytesForHint(bytes) {
  if (!bytes || bytes <= 0) return "\u672a\u914d\u7f6e";
  const mb = bytes / (1024 * 1024);
  return Number.isInteger(mb) ? `${mb} MB` : `${mb.toFixed(2)} MB`;
}

function updateUploadLimitHint() {
  const hint = qs("#upload-limit-hint");
  if (!hint) return;
  if (!state.uploadLimits.showHint) {
    hint.textContent = "";
    hint.style.display = "none";
    return;
  }
  hint.style.display = "";
  hint.textContent = `\u5f53\u524d\u6570\u636e\u5e93\u603b\u6253\u5305\u4e0a\u9650 ${formatBytesForHint(state.uploadLimits.datasetCapacityBytes)}\u3002`;
}

function resetCreateDbInputVisual() {
  const input = qs("#create-db-name");
  if (!input) return;
  input.classList.remove("state-error", "state-success");
}

function setCreateDbInputState(mode) {
  const input = qs("#create-db-name");
  if (!input) return;
  input.classList.remove("state-error", "state-success");
  if (mode === "error") {
    input.classList.add("state-error");
    input.focus();
    input.select();
    return;
  }
  if (mode === "success") {
    input.classList.add("state-success");
  }
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof data === "object" && data?.detail ? data.detail : String(data);
    throw new Error(detail);
  }
  return data;
}

function switchView(viewId) {
  state.activeView = viewId;
  qsa(".side-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewId);
  });
  qsa(".view-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === viewId);
  });
}

function switchDbTab(tabId) {
  state.activeDbTab = tabId;
  qsa("[data-db-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.dbTab === tabId);
  });
  qsa("#database-view .db-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.id === tabId);
  });
}

function switchMetricsTab(tabId) {
  state.activeMetricsTab = tabId;
  qsa("[data-metrics-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.metricsTab === tabId);
  });
  qsa("#metrics-view .metrics-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.id === tabId);
  });
}

function switchPerfGeometryTab(tabId) {
  state.activePerfGeometryTab = tabId;
  qsa("[data-perf-geometry-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.perfGeometryTab === tabId);
  });
  qsa("#metrics-data-tab .perf-geometry-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.id === tabId);
  });
}

function switchLogTab(tabId) {
  state.activeLogTab = tabId;
  qsa("[data-log-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.logTab === tabId);
  });
  qsa("#logs-view .db-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.id === tabId);
  });
}

function renderDatabaseOptions() {
  const selects = ["query-db-select"];
  selects.forEach((id) => {
    const select = qs(`#${id}`);
    if (!select) return;
    const previous = select.value;
    select.innerHTML = "";

    if (state.databases.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "\u6682\u65e0\u6570\u636e\u5e93";
      select.appendChild(option);
      return;
    }

    state.databases.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.db_name;
      option.textContent = item.db_name;
      select.appendChild(option);
    });

    if (state.databases.some((item) => item.db_name === previous)) {
      select.value = previous;
    } else if (state.activeDatabase && state.databases.some((item) => item.db_name === state.activeDatabase)) {
      select.value = state.activeDatabase;
    } else {
      select.value = state.databases[0].db_name;
    }
  });
}

function renderDatabaseListPanel() {
  const panel = qs("#database-list-panel");
  if (!panel) return;

  if (state.databases.length === 0) {
    panel.className = "result-list empty-state scroll-box medium-scroll";
    panel.innerHTML = "<p>\u5f53\u524d\u6ca1\u6709\u6570\u636e\u5e93\uff0c\u8bf7\u5148\u521b\u5efa\u3002</p>";
    return;
  }

  panel.className = "result-list scroll-box medium-scroll";
  panel.innerHTML = state.databases.map((db) => `
    <div class="db-item">
      <div class="db-item-main">
        <strong>${db.db_name}</strong>
      </div>
      <div class="db-item-side">
        <span class="db-file-count">${db.file_count ?? 0} \u4e2a\u6587\u4ef6</span>
        <span class="db-prep-status">${db.prep_status === "\u672a\u5b8c\u6210" ? "\u672a\u5904\u7406" : (db.prep_status || "\u672a\u5904\u7406")}</span>
        <button class="btn btn-ghost btn-small btn-select-db" data-use-db="${db.db_name}">\u67e5\u8be2\u9009\u4e2d</button>
      </div>
    </div>
  `).join("");

  qsa("[data-use-db]").forEach((button) => {
    button.addEventListener("click", () => {
      const dbName = button.dataset.useDb;
      qs("#query-db-select").value = dbName;
      setOverviewSelectedDatabase(dbName);
      switchView("query-view");
      setMessage("query-message", `\u5df2\u9009\u62e9\u6570\u636e\u5e93 ${dbName}\uff0c\u70b9\u51fb\u201c\u786e\u8ba4\u201d\u5207\u6362\u5728\u7ebf\u8bfb\u53d6\u670d\u52a1\u3002`);
    });
  });
}

function renderOverviewDatabaseListPanel() {
  const panel = qs("#overview-database-list-panel");
  if (!panel) return;

  if (state.databases.length === 0) {
    panel.className = "result-list empty-state scroll-box medium-scroll";
    panel.innerHTML = "<p>\u6682\u65e0\u6570\u636e\u5e93\u53ef\u5c55\u793a</p>";
    return;
  }

  panel.className = "result-list scroll-box medium-scroll";
  panel.innerHTML = state.databases.map((db) => `
    <div class="db-item">
      <div class="db-item-main">
        <strong>${db.db_name}</strong>
      </div>
      <div class="db-item-side">
        <span>${db.prep_status === "\u672a\u5b8c\u6210" ? "\u672a\u5904\u7406" : (db.prep_status || "\u672a\u5904\u7406")}</span>
        <button class="btn btn-pirex btn-small" data-preprocess-pirex="${db.db_name}">pirex\u5904\u7406</button>
        <button class="btn btn-primary btn-small" data-preprocess-pirexx="${db.db_name}">pirex+\u5904\u7406</button>
        <button class="btn btn-secondary btn-small btn-delete-db" data-select-overview-db="${db.db_name}">\u9009\u4e2d</button>
      </div>
    </div>
  `).join("");

  qsa("[data-preprocess-pirex]").forEach((button) => {
    button.addEventListener("click", () => startExistingDatabasePreprocess(button.dataset.preprocessPirex, "pirex"));
  });

  qsa("[data-preprocess-pirexx]").forEach((button) => {
    button.addEventListener("click", () => startExistingDatabasePreprocess(button.dataset.preprocessPirexx, "pirexx"));
  });

  qsa("[data-select-overview-db]").forEach((button) => {
    button.addEventListener("click", async () => {
      const dbName = button.dataset.selectOverviewDb;
      setOverviewSelectedDatabase(dbName);
      await fillOverviewFiles();
    });
  });
}

function renderQueryResults(files) {
  const container = qs("#query-results");
  const countPill = qs("#query-count-pill");
  const currentDbName = state.activeDatabase || qs("#query-db-select")?.value || "";
  const currentDbEntry = state.databases.find((item) => item.db_name === currentDbName);
  const prepStatus = currentDbEntry?.prep_status || "\u672a\u5904\u7406";
  const pirexReady = prepStatus === "pirex" || prepStatus === "pirex+pirex";
  const pirexxReady = prepStatus === "pirexx" || prepStatus === "pirex+pirex";

  countPill.textContent = `${files.length} \u9879`;

  if (!files || files.length === 0) {
    container.className = "result-list empty-state scroll-box medium-scroll";
    container.innerHTML = "<p>\u672a\u627e\u5230\u5339\u914d\u6587\u4ef6</p>";
    return;
  }

  container.className = "result-list scroll-box medium-scroll";
  container.innerHTML = files.map((file) => `
    <div class="result-item">
      <div class="result-item-main">
        <strong>${file.file_name}</strong>
      </div>
      <div class="inline-row compact-row">
        <span class="result-item-size">${Math.max(1, Math.round(file.size_bytes / 1024))} KB</span>
        <button class="btn btn-ghost btn-small" data-direct="${file.file_name}">\u76f4\u63a5\u6062\u590d</button>
        <button class="btn btn-primary btn-small ${pirexxReady ? "" : "btn-disabled"}" data-pirexx="${file.file_name}" ${pirexxReady ? "" : "disabled"}>pirex+\u6062\u590d</button>
        <button class="btn btn-pirex btn-small ${pirexReady ? "" : "btn-disabled"}" data-pirex="${file.file_name}" ${pirexReady ? "" : "disabled"}>pirex\u6062\u590d</button>
      </div>
    </div>
  `).join("");

  qsa("[data-direct]").forEach((button) => {
    button.addEventListener("click", () => {
      const dbName = state.activeDatabase || qs("#query-db-select").value;
      restoreFile(dbName, button.dataset.direct, "direct");
    });
  });

  qsa("[data-pirexx]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!pirexxReady) {
        showModal("\u63d0\u793a", "\u8fd8\u672a\u8fdb\u884c pirex+ \u9884\u5904\u7406");
        return;
      }
      restoreFile(state.activeDatabase, button.dataset.pirexx, "pirexx");
    });
  });

  qsa("[data-pirex]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!pirexReady) {
        showModal("\u63d0\u793a", "\u8fd8\u672a\u8fdb\u884c pirex \u9884\u5904\u7406");
        return;
      }
      restoreFile(state.activeDatabase, button.dataset.pirex, "pirex");
    });
  });
}

function renderTmpFiles(files) {
  const container = qs("#tmp-file-list");
  if (!container) return;
  setTmpFileCount((files || []).length);

  if (!files || files.length === 0) {
    container.className = "tmp-upload-list empty-state scroll-box medium-scroll";
    container.innerHTML = "<p>\u5f85\u4e0a\u4f20\u6587\u4ef6\u5217\u8868\u4e3a\u7a7a</p>";
    return;
  }

  container.className = "tmp-upload-list scroll-box medium-scroll";
  container.innerHTML = files.map((file) => `
    <div class="tmp-upload-item">
      <div class="tmp-upload-meta">
        <strong title="${file.file_name}">${file.file_name}</strong>
        <span>${Math.max(1, Math.round(file.size_bytes / 1024))} KB</span>
      </div>
      <button class="tmp-delete-button" data-delete-tmp="${file.file_name}">\u5220\u9664</button>
    </div>
  `).join("");

  qsa("[data-delete-tmp]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await apiJson("/tmp-files/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ file_name: button.dataset.deleteTmp }),
        });
        await loadTmpFiles();
      } catch (error) {
        setMessage("create-db-message", `\u5220\u9664\u5931\u8d25\uff1a${error.message}`, true);
      }
    });
  });
}

function renderUsers(users) {
  const panel = qs("#user-list-panel");
  if (!panel) return;
  const grid = panel.querySelector(".user-card-grid");
  if (!grid) return;

  if (!users || users.length === 0) {
    grid.innerHTML = "<p>\u6ca1\u6709\u5339\u914d\u7528\u6237\u3002</p>";
    return;
  }

  grid.innerHTML = users.map((user) => `
    <div class="user-card" data-user-keywords="${user.nickname} ${user.username}">
      <strong>${user.nickname}</strong>
      <span>\u8d26\u53f7\uff1a${user.username}</span>
      <span class="user-role-tag">\u89d2\u8272\uff1a${user.role}</span>
      <div class="inline-row">
        <button class="btn btn-danger" data-delete-user="${user.username}">\u5220\u9664</button>
        <button class="btn btn-secondary" data-reset-user="${user.username}">\u91cd\u7f6e\u5bc6\u7801</button>
      </div>
    </div>
  `).join("");

  qsa("[data-delete-user]").forEach((button) => {
    button.addEventListener("click", () => deleteAccount(button.dataset.deleteUser));
  });
  qsa("[data-reset-user]").forEach((button) => {
    button.addEventListener("click", () => resetAccountPassword(button.dataset.resetUser));
  });
}

async function loadUsers(keyword = "") {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  const payload = await apiJson(`/accounts${query}`);
  renderUsers(payload.users || []);
  return payload.users || [];
}


function formatUserManagerLogTime(rawValue) {
  const text = String(rawValue || "").trim();
  if (!text) return "";

  const normalized = text.replace("T", " ");
  const match = normalized.match(/^(\d{4}-\d{2}-\d{2})\s(\d{2}:\d{2}:\d{2})/);
  if (match) {
    return `${match[1]} ${match[2]}`;
  }
  return normalized;
}

function renderUserManagerLogRows(items) {
  const container = qs("#user-manager-log-list");
  if (!container) return;

  if (!items || items.length === 0) {
    container.innerHTML = '<div class="user-log-empty">\u6682\u65e0\u7528\u6237\u7ba1\u7406\u65e5\u5fd7</div>';
    return;
  }

  const rows = items.map((item) => `
    <div class="user-log-row">
      <span>${item.admin_username || ""}</span>
      <span>${item.admin_action || ""}</span>
      <span>${item.target_nickname || ""}</span>
      <span>${item.target_username || ""}</span>
      <span>${formatUserManagerLogTime(item.action_time_utc)}</span>
    </div>
  `);

  while (rows.length < state.userManagerLogPageSize) {
    rows.push(`
      <div class="user-log-row user-log-row-empty">
        <span>&nbsp;</span>
        <span>&nbsp;</span>
        <span>&nbsp;</span>
        <span>&nbsp;</span>
        <span>&nbsp;</span>
      </div>
    `);
  }

  container.innerHTML = rows.join("");
}

function renderUserManagerLogPagination(page, totalPages) {
  const pagesEl = qs("#user-log-pages");
  const prevEl = qs("#user-log-prev");
  const nextEl = qs("#user-log-next");
  if (!pagesEl || !prevEl || !nextEl) return;

  prevEl.disabled = page <= 1;
  nextEl.disabled = page >= totalPages;

  const buttons = [];
  for (let i = 1; i <= totalPages; i += 1) {
    buttons.push(`<button class="log-page-button ${i === page ? "active" : ""}" data-user-log-page="${i}" type="button">${i}</button>`);
  }
  pagesEl.innerHTML = buttons.join("");

  qsa("[data-user-log-page]").forEach((button) => {
    button.addEventListener("click", () => loadUserManagerLogs(Number(button.dataset.userLogPage || "1")));
  });
}

async function loadUserManagerLogs(page = 1) {
  const payload = await apiJson(`/logs/user-manager?page=${page}&page_size=${state.userManagerLogPageSize}`);
  state.userManagerLogPage = Number(payload.page || 1);
  state.userManagerLogTotalPages = Number(payload.total_pages || 1);
  renderUserManagerLogRows(payload.items || []);
  renderUserManagerLogPagination(state.userManagerLogPage, state.userManagerLogTotalPages);
  return payload;
}


function renderDatabaseLogRows(items) {
  const container = qs("#database-log-list");
  if (!container) return;

  if (!items || items.length === 0) {
    container.innerHTML = '<div class="user-log-empty">\u6682\u65e0\u6570\u636e\u5e93\u65e5\u5fd7</div>';
    return;
  }

  const rows = items.map((item) => `
    <div class="user-log-row db-log-row">
      <span>${item.db_name || ""}</span>
      <span>${item.db_action || ""}</span>
      <span>${formatUserManagerLogTime(item.action_time_utc)}</span>
      <span>${item.action_result || ""}</span>
    </div>
  `);

  while (rows.length < state.databaseLogPageSize) {
    rows.push(`
      <div class="user-log-row db-log-row user-log-row-empty">
        <span>&nbsp;</span>
        <span>&nbsp;</span>
        <span>&nbsp;</span>
        <span>&nbsp;</span>
      </div>
    `);
  }

  container.innerHTML = rows.join("");
}

function renderDatabaseLogPagination(page, totalPages) {
  const pagesEl = qs("#db-log-pages");
  const prevEl = qs("#db-log-prev");
  const nextEl = qs("#db-log-next");
  if (!pagesEl || !prevEl || !nextEl) return;

  prevEl.disabled = page <= 1;
  nextEl.disabled = page >= totalPages;

  const buttons = [];
  for (let i = 1; i <= totalPages; i += 1) {
    buttons.push(`<button class="log-page-button ${i === page ? "active" : ""}" data-db-log-page="${i}" type="button">${i}</button>`);
  }
  pagesEl.innerHTML = buttons.join("");

  qsa("[data-db-log-page]").forEach((button) => {
    button.addEventListener("click", () => loadDatabaseLogs(Number(button.dataset.dbLogPage || "1")));
  });
}

function setTextIfPresent(selector, value) {
  const node = qs(selector);
  if (node) {
    node.textContent = value;
  }
}

function formatMetricNumber(value) {
  return Number(value || 0).toLocaleString("zh-CN");
}

function formatMetricMb(value) {
  return `${Number(value || 0).toFixed(2)} MB`;
}

function syncLoadPanelGeometryText() {
  const firstCard = qsa("#metrics-load-tab .metrics-load-card")[0];
  if (!firstCard) return;

  const title = firstCard.querySelector(".metrics-load-card-head h3");
  const subtitle = firstCard.querySelector(".metrics-load-card-head span");
  const lines = firstCard.querySelectorAll(".metrics-load-lines p");

  if (title) title.textContent = "当前数据几何";
  if (subtitle) subtitle.textContent = "顶部摘要";
  if (lines[0]) lines[0].innerHTML = '<span class="metrics-load-label">当前数据几何大小：</span><span class="metrics-load-value">4KB / 每条</span>';
  if (lines[1]) lines[1].innerHTML = '<span class="metrics-load-label">数据规模：</span><span class="metrics-load-value">2^18 / 条</span>';
  if (lines[2]) lines[2].innerHTML = '<span class="metrics-load-label">单库容量：</span><span class="metrics-load-value">1GiB</span>';
}

async function loadMainMetricsLoadPanel() {
  const payload = await apiJson("/metrics/load-prototype");
  const totalDatabases = Number(payload.total_databases || 0);
  const pirexReadyCount = Number(payload.pirex_ready_count || 0);
  const pirexxReadyCount = Number(payload.pirexx_ready_count || 0);
  const pirexStorageMb = pirexReadyCount * 36.1;
  const pirexxStorageMb = pirexxReadyCount * 0.6;

  syncLoadPanelGeometryText();
  setTextIfPresent("#main-load-state-file-size", String(payload.state_file_size_text || "0 B"));
  setTextIfPresent("#main-load-auxiliary-file-size", String(payload.auxiliary_file_size_text || "0 B"));
  setTextIfPresent("#main-load-total-databases", formatMetricNumber(totalDatabases));
  setTextIfPresent("#main-load-pirex-ready", formatMetricNumber(pirexReadyCount));
  setTextIfPresent("#main-load-pirexx-ready", formatMetricNumber(pirexxReadyCount));
  setTextIfPresent("#main-load-pirex-storage", formatMetricMb(pirexStorageMb));
  setTextIfPresent("#main-load-pirexx-storage", formatMetricMb(pirexxStorageMb));
}

async function loadDatabaseLogs(page = 1) {
  const payload = await apiJson(`/logs/database?page=${page}&page_size=${state.databaseLogPageSize}`);
  state.databaseLogPage = Number(payload.page || 1);
  state.databaseLogTotalPages = Number(payload.total_pages || 1);
  renderDatabaseLogRows(payload.items || []);
  renderDatabaseLogPagination(state.databaseLogPage, state.databaseLogTotalPages);
  return payload;
}

function renderQueryLogRows(items) {
  const container = qs("#query-log-list");
  if (!container) return;

  if (!items || items.length === 0) {
    container.innerHTML = '<div class="user-log-empty">\u6682\u65e0\u67e5\u8be2\u65e5\u5fd7</div>';
    return;
  }

  const rows = items.map((item) => `
    <div class="user-log-row query-log-row">
      <span>${item.query_username || ""}</span>
      <span>${item.db_name || ""}</span>
      <span>${item.file_name || ""}</span>
      <span>${item.download_action || ""}</span>
      <span>${formatUserManagerLogTime(item.query_time_utc)}</span>
      <span>${item.download_result || ""}</span>
    </div>
  `);

  while (rows.length < state.queryLogPageSize) {
    rows.push(`
      <div class="user-log-row query-log-row user-log-row-empty">
        <span>&nbsp;</span>
        <span>&nbsp;</span>
        <span>&nbsp;</span>
        <span>&nbsp;</span>
        <span>&nbsp;</span>
        <span>&nbsp;</span>
      </div>
    `);
  }

  container.innerHTML = rows.join("");
}

function renderQueryLogPagination(page, totalPages) {
  const pagesEl = qs("#query-log-pages");
  const prevEl = qs("#query-log-prev");
  const nextEl = qs("#query-log-next");
  if (!pagesEl || !prevEl || !nextEl) return;

  prevEl.disabled = page <= 1;
  nextEl.disabled = page >= totalPages;

  const buttons = [];
  for (let i = 1; i <= totalPages; i += 1) {
    buttons.push(`<button class="log-page-button ${i === page ? "active" : ""}" data-query-log-page="${i}" type="button">${i}</button>`);
  }
  pagesEl.innerHTML = buttons.join("");

  qsa("[data-query-log-page]").forEach((button) => {
    button.addEventListener("click", () => loadQueryLogs(Number(button.dataset.queryLogPage || "1")));
  });
}

function setOverviewSelectedDatabase(dbName) {
  state.overviewSelectedDatabase = dbName || "";
  const input = qs("#overview-db-display");
  if (input) {
    input.value = state.overviewSelectedDatabase;
  }
}

function getOverviewSelectedDatabase() {
  return (qs("#overview-db-display")?.value || state.overviewSelectedDatabase || "").trim();
}

async function loadQueryLogs(page = 1) {
  const payload = await apiJson(`/logs/query?page=${page}&page_size=${state.queryLogPageSize}`);
  state.queryLogPage = Number(payload.page || 1);
  state.queryLogTotalPages = Number(payload.total_pages || 1);
  renderQueryLogRows(payload.items || []);
  renderQueryLogPagination(state.queryLogPage, state.queryLogTotalPages);
  return payload;
}

async function refreshUserManagerLogPanel() {
  return loadUserManagerLogs(state.userManagerLogPage || 1);
}

async function refreshDatabaseLogPanel() {
  return loadDatabaseLogs(state.databaseLogPage || 1);
}

async function refreshQueryLogPanel() {
  return loadQueryLogs(state.queryLogPage || 1);
}

async function refreshDatabases() {
  const data = await apiJson("/databases");
  state.databases = data.databases || [];
  renderDatabaseOptions();
  if (state.overviewSelectedDatabase && !state.databases.some((item) => item.db_name === state.overviewSelectedDatabase)) {
    setOverviewSelectedDatabase("");
  } else if (!state.overviewSelectedDatabase && state.databases.length > 0) {
    setOverviewSelectedDatabase(state.databases[0].db_name);
  }
  renderDatabaseListPanel();
  renderOverviewDatabaseListPanel();
  await fillOverviewFiles();
  await loadMainMetricsLoadPanel().catch(() => {});
  return state.databases;
}

async function loadTmpFiles() {
  try {
    const data = await apiJson("/tmp-files");
    renderTmpFiles(data.files || []);
    return data.files || [];
  } catch (error) {
    setMessage("create-db-message", `\u8bfb\u53d6\u5f85\u4e0a\u4f20\u6587\u4ef6\u5931\u8d25\uff1a${error.message}`, true);
    setTmpFileCount(0);
    renderTmpFiles([]);
    return [];
  }
}

async function loadUploadLimits() {
  try {
    const data = await apiJson("/config/upload-limits");
    state.uploadLimits.datasetCapacityBytes = Number(data.dataset_capacity_bytes || 0);
    state.uploadLimits.showHint = Boolean(data.show_upload_limit_hint);
  } catch (error) {
    state.uploadLimits.datasetCapacityBytes = 0;
    state.uploadLimits.showHint = false;
    setMessage("create-db-message", `\u8bfb\u53d6\u4e0a\u4f20\u4e0a\u9650\u5931\u8d25\uff1a${error.message}`, true);
  }
  updateUploadLimitHint();
}

async function confirmDatabaseSelection() {
  const dbName = qs("#query-db-select").value;
  if (!dbName) {
    setMessage("query-message", "\u8bf7\u5148\u9009\u62e9\u6570\u636e\u5e93\u3002", true);
    return;
  }

  setMessage("query-message", `\u6b63\u5728\u5207\u6362\u5230\u6570\u636e\u5e93 ${dbName} ...`);
  try {
    const result = await apiJson("/databases/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ db_name: dbName }),
    });
    state.activeDatabase = result.db_name;
    state.activeServerAddr = result.server_addr || "";
    await queryFiles(true);

    if (result.selected_scheme === "pirexx") {
      setMessage("query-message", `\u6570\u636e\u5e93 ${dbName} \u5df2\u786e\u8ba4\uff0cpirex+ sread \u5df2\u5c31\u7eea\uff1a${result.server_addr}`);
    } else if (result.selected_scheme === "pirex") {
      setMessage("query-message", `\u6570\u636e\u5e93 ${dbName} \u5df2\u786e\u8ba4\uff0cpirex sread \u5df2\u5c31\u7eea\uff1a${result.server_addr}`);
    } else {
      setMessage("query-message", `\u6570\u636e\u5e93 ${dbName} \u5df2\u786e\u8ba4\uff0c\u5f53\u524d\u672a\u9884\u5904\u7406\uff0c\u4ec5\u5c55\u793a\u6587\u4ef6\u5217\u8868\u3002`);
    }
  } catch (error) {
    setMessage("query-message", `\u5207\u6362\u5931\u8d25\uff1a${error.message}`, true);
  }
}

async function queryFiles(showAll = false) {
  const dbName = state.activeDatabase || qs("#query-db-select").value;
  if (!dbName) {
    setMessage("query-message", "\u8bf7\u5148\u9009\u62e9\u6570\u636e\u5e93\u5e76\u70b9\u51fb\u786e\u8ba4\u3002", true);
    return;
  }

  const payload = await apiJson(`/databases/${encodeURIComponent(dbName)}/files`);
  const files = payload.files || [];
  const keyword = qs("#query-keyword").value.trim().toLowerCase();
  const filtered = showAll || !keyword
    ? files
    : files.filter((item) => item.file_name.toLowerCase().includes(keyword));
  renderQueryResults(filtered);
  setMessage("query-message", `\u6570\u636e\u5e93 ${dbName} \u5171\u8fd4\u56de ${filtered.length} \u9879\u3002`);
}

async function restoreFile(dbName, fileId, mode) {
  if (!dbName) {
    showModal("\u63d0\u793a", "\u8bf7\u5148\u786e\u8ba4\u76ee\u6807\u6570\u636e\u5e93\u3002");
    setMessage("query-message", "\u8bf7\u5148\u786e\u8ba4\u76ee\u6807\u6570\u636e\u5e93\u3002", true);
    return;
  }

  let endpoint = "/restore/direct";
  let schemeLabel = "\u76f4\u63a5\u6062\u590d";
  if (mode === "pirexx") {
    endpoint = "/restore/pirexx";
    schemeLabel = "pirex+\u6062\u590d";
  } else if (mode === "pirex") {
    endpoint = "/restore/pirex";
    schemeLabel = "pirex\u6062\u590d";
  }

  const startedAt = performance.now();
  const modalText = qs("#app-modal-text");
  let timerId = null;

  const updateWaitingModal = () => {
    if (!modalText) return;
    const elapsedSeconds = ((performance.now() - startedAt) / 1000).toFixed(1);
    modalText.textContent = `\u6570\u636e\u5e93 ${dbName}\n\u6587\u4ef6 ${fileId}\n\u7b49\u5f85${schemeLabel}\u4e2d...\n\u5df2\u5904\u7406 ${elapsedSeconds} \u79d2`;
  };

  showModal(schemeLabel, `\u6570\u636e\u5e93 ${dbName}\n\u6587\u4ef6 ${fileId}\n\u7b49\u5f85${schemeLabel}\u4e2d...\n\u5df2\u5904\u7406 0.0 \u79d2`);
  updateWaitingModal();
  timerId = window.setInterval(updateWaitingModal, 100);

  try {
    const result = await apiJson(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        db_name: dbName,
        file_id: fileId,
        force: true,
        query_user: state.user?.username || state.user?.nickname || "",
      }),
    });

    const elapsedSeconds = ((performance.now() - startedAt) / 1000).toFixed(2);
    if (timerId !== null) {
      window.clearInterval(timerId);
    }

    let detailText = `\u6570\u636e\u5e93 ${dbName}\n\u6587\u4ef6 ${fileId}\n${schemeLabel}\u6210\u529f\n\u8017\u65f6 ${elapsedSeconds} \u79d2`;
    if (result.output_path) {
      detailText += `\n\u5df2\u4fdd\u5b58\u5230 ${result.output_path}`;
    }
    if (mode === "pirexx" && typeof result.pirexx_avg_block_query_delay_ms === "number") {
      detailText += `\n\u5e73\u5747\u5757\u67e5\u8be2\u65f6\u95f4 ${result.pirexx_avg_block_query_delay_ms} ms`;
    } else if (mode === "pirex" && typeof result.pirex_avg_block_query_delay_ms === "number") {
      detailText += `\n\u5e73\u5747\u5757\u67e5\u8be2\u65f6\u95f4 ${result.pirex_avg_block_query_delay_ms} ms`;
    }

    await refreshQueryLogPanel().catch(() => {});
    showModal(schemeLabel, detailText);
  } catch (error) {
    if (timerId !== null) {
      window.clearInterval(timerId);
    }
    await refreshQueryLogPanel().catch(() => {});
    const elapsedSeconds = ((performance.now() - startedAt) / 1000).toFixed(2);
    showModal(schemeLabel, `\u6570\u636e\u5e93 ${dbName}\n\u6587\u4ef6 ${fileId}\n${schemeLabel}\u5931\u8d25\n\u8017\u65f6 ${elapsedSeconds} \u79d2`);
  }
}


async function createDatabase() {
  const input = qs("#create-db-name");
  const dbName = input.value.trim();
  if (!dbName) {
    resetCreateDbInputVisual();
    setDbInlineStatus("");
    setMessage("create-db-message", "\u8bf7\u8f93\u5165\u6570\u636e\u5e93\u540d\u79f0\u3002", true);
    return;
  }

  try {
    await apiJson("/databases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ db_name: dbName }),
    });
    await refreshDatabases();
    await refreshDatabaseLogPanel().catch(() => {});
    qs("#query-db-select").value = dbName;
    setOverviewSelectedDatabase(dbName);
    resetCreateDbInputVisual();
    setDbInlineStatus("");
    setMessage("create-db-message", "");
    input.value = dbName;
    showModal("\u63d0\u793a", `\u6570\u636e\u5e93 ${dbName} \u6dfb\u52a0\u6210\u529f`);
    await loadTmpFiles();
    await refreshDatabaseLogPanel().catch(() => {});
  } catch (error) {
    const message = String(error.message || "");
    if (message.includes("database already exists")) {
      setCreateDbInputState("error");
      setDbInlineStatus("");
      setMessage("create-db-message", "");
      showModal("\u63d0\u793a", `\u6570\u636e\u5e93 ${dbName} \u5df2\u5b58\u5728\uff0c\u8bf7\u66f4\u6362\u540d\u79f0`);
      return;
    }
    resetCreateDbInputVisual();
    setDbInlineStatus("");
    setMessage("create-db-message", `\u521b\u5efa\u5931\u8d25\uff1a${message}`, true);
  }
}

function getStagingDbName() {
  return state.activeDatabase || qs("#query-db-select").value.trim() || getOverviewSelectedDatabase();
}

function getCreateDbName() {
  return qs("#create-db-name")?.value.trim() || "";
}

async function stageFilesToTmp() {
  const dbName = getCreateDbName();
  const input = qs("#upload-files-input");
  if (!dbName) {
    setMessage("create-db-message", "\u8bf7\u5148\u8f93\u5165\u521b\u5efa\u9875\u6570\u636e\u5e93\u540d\u79f0\u3002", true);
    return;
  }
  if (!input.files || input.files.length === 0) {
    setMessage("create-db-message", "\u8bf7\u5148\u9009\u62e9\u8981\u52a0\u5165\u7684\u6587\u4ef6\u3002", true);
    return;
  }

  const formData = new FormData();
  Array.from(input.files).forEach((file) => formData.append("files", file));

  try {
    const response = await fetch(`/databases/${encodeURIComponent(dbName)}/tmp-files`, {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "stage failed");
    }

    const currentFiles = await loadTmpFiles();
    input.value = "";
    const skipped = data.skipped_files || [];
    const skippedText = skipped.length ? `\uff0c\u5df2\u5254\u9664\u540c\u540d\u6587\u4ef6 ${skipped.join("\u3001")}` : "";
    setMessage("create-db-message", `\u5f85\u4e0a\u4f20\u5217\u8868\u5f53\u524d\u5171 ${currentFiles.length} \u4e2a\u6587\u4ef6${skippedText}\u3002`);
  } catch (error) {
    setMessage("create-db-message", `\u52a0\u5165\u5931\u8d25\uff1a${error.message}`, true);
  }
}

async function uploadStagedFiles() {
  const dbName = getCreateDbName();
  if (!dbName) {
    setMessage("create-db-message", "\u8bf7\u5148\u8f93\u5165\u521b\u5efa\u9875\u6570\u636e\u5e93\u540d\u79f0\u3002", true);
    return;
  }

  try {
    const result = await apiJson(`/databases/${encodeURIComponent(dbName)}/upload`, {
      method: "POST",
    });
    await loadTmpFiles();
    await refreshDatabases();
    await refreshDatabaseLogPanel().catch(() => {});
    setMessage("create-db-message", result.message || "\u4e0a\u4f20\u6210\u529f");
  } catch (error) {
    setMessage("create-db-message", `\u4e0a\u4f20\u5931\u8d25\uff1a${error.message}`, true);
  }
}

function formatPreprocessElapsed(elapsedMs) {
  const totalSeconds = Math.floor(elapsedMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}\u5206${String(seconds).padStart(2, "0")}\u79d2`;
}

function renderPreprocessRunningModal(session) {
  session.modalMode = "running";
  const schemeLabel = session.scheme === "pirexx" ? "pirex+" : "pirex";
  const estimateText = session.scheme === "pirexx" ? "7-9min" : "30s";
  const elapsedText = formatPreprocessElapsed(performance.now() - session.startedAtMs);
  state.modalLocked = true;
  showModal(
    "\u9884\u5904\u7406\u4e2d",
    `\u6b63\u5728\u5bf9 ${session.dbName} \u6570\u636e\u5e93\u8fdb\u884c ${schemeLabel} \u9884\u5904\u7406
\u9884\u8ba1\u65f6\u95f4\uff1a${estimateText}
\u5df2\u7ecf\u5904\u7406 ${elapsedText}`
  );
  setModalBody(`
    <div class="app-modal-actions">
      <button id="preprocess-cancel-button" class="btn btn-danger" type="button">\u7ec8\u6b62\u9884\u5904\u7406</button>
    </div>
  `);
  qs("#preprocess-cancel-button")?.addEventListener("click", () => renderPreprocessCancelConfirm(session));
}

function renderPreprocessCancelConfirm(session) {
  session.modalMode = "confirm-cancel";
  const schemeLabel = session.scheme === "pirexx" ? "pirex+" : "pirex";
  showModal("\u786e\u8ba4\u7ec8\u6b62", `\u4f60\u786e\u5b9a\u7ec8\u6b62 ${session.dbName} \u6570\u636e\u5e93\u7684 ${schemeLabel} \u9884\u5904\u7406\u5417\uff1f`);
  setModalBody(`
    <div class="app-modal-actions">
      <button id="confirm-preprocess-cancel-button" class="btn btn-danger" type="button">\u786e\u5b9a</button>
      <button id="back-preprocess-cancel-button" class="btn btn-ghost" type="button">\u8fd4\u56de</button>
    </div>
  `);
  qs("#confirm-preprocess-cancel-button")?.addEventListener("click", () => requestPreprocessCancel(session));
  qs("#back-preprocess-cancel-button")?.addEventListener("click", () => renderPreprocessRunningModal(session));
}

function clearActivePreprocessSession() {
  const session = state.activePreprocessSession;
  if (!session) return;
  if (session.timerId) {
    window.clearInterval(session.timerId);
  }
  if (session.pollId) {
    window.clearInterval(session.pollId);
  }
  state.activePreprocessSession = null;
}

async function requestPreprocessCancel(session) {
  try {
    session.modalMode = "cancelling";
    await apiJson("/preprocess/jobs/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ db_name: session.dbName, scheme: session.scheme }),
    });
    showModal("\u7ec8\u6b62\u4e2d", `\u6b63\u5728\u7ec8\u6b62 ${session.dbName} \u6570\u636e\u5e93\u7684 ${session.scheme === "pirexx" ? "pirex+" : "pirex"} \u9884\u5904\u7406`);
    setModalBody("");
  } catch (error) {
    showModal("\u7ec8\u6b62\u5931\u8d25", error.message);
    setModalBody(`
      <div class="app-modal-actions">
        <button id="back-preprocess-cancel-button" class="btn btn-ghost" type="button">\u8fd4\u56de</button>
      </div>
    `);
    qs("#back-preprocess-cancel-button")?.addEventListener("click", () => renderPreprocessRunningModal(session));
  }
}

async function pollPreprocessSession(session) {
  const payload = await apiJson(`/preprocess/jobs/status?scheme=${encodeURIComponent(session.scheme)}`);
  if (payload.status === "running") {
    return;
  }

  clearActivePreprocessSession();
  state.modalLocked = false;
  await refreshDatabases();
  await refreshDatabaseLogPanel().catch(() => {});

  const schemeLabel = session.scheme === "pirexx" ? "pirex+" : "pirex";
  const elapsedText = formatPreprocessElapsed(Number(payload.elapsed_ms || 0));
  if (payload.status === "completed") {
    showModal("\u9884\u5904\u7406\u5b8c\u6210", `${session.dbName} \u6570\u636e\u5e93 ${schemeLabel}\u9884\u5904\u7406\u5b8c\u6210\n\u7528\u65f6 ${elapsedText}`);
    setModalBody("");
    setMessage("create-db-message", `${session.dbName} \u5df2\u5b8c\u6210 ${schemeLabel} \u9884\u5904\u7406\u3002`);
    return;
  }

  showModal("\u9884\u5904\u7406\u5931\u8d25", `${session.dbName} \u6570\u636e\u5e93 ${schemeLabel} \u9884\u5904\u7406\u5931\u8d25\n\u7528\u65f6 ${elapsedText}`);
  setModalBody("");
  setMessage(
    "create-db-message",
    payload.status === "cancelled" ? `${schemeLabel} \u9884\u5904\u7406\u5df2\u7ec8\u6b62` : `${schemeLabel} \u9884\u5904\u7406\u5931\u8d25\uff1a${payload.error || ""}`,
    true
  );
}

async function runDatabasePreprocessWithModal(dbName, scheme) {
  if (!dbName) {
    showModal("\u63d0\u793a", "\u8bf7\u5148\u8f93\u5165\u6216\u9009\u62e9\u6570\u636e\u5e93\u540d\u79f0\u3002");
    return;
  }

  if (state.activePreprocessSession) {
    showModal("\u63d0\u793a", "\u5f53\u524d\u5df2\u6709\u9884\u5904\u7406\u4efb\u52a1\u6b63\u5728\u6267\u884c\uff0c\u8bf7\u5148\u7b49\u5f85\u7ed3\u675f\u6216\u7ec8\u6b62\u3002");
    return;
  }

  const session = {
    dbName,
    scheme,
    startedAtMs: performance.now(),
    timerId: null,
    pollId: null,
  };

  try {
    await apiJson("/preprocess/jobs/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ db_name: dbName, scheme }),
    });
  } catch (error) {
    showModal("\u9884\u5904\u7406\u5931\u8d25", error.message);
    throw error;
  }

  state.activePreprocessSession = session;
  renderPreprocessRunningModal(session);
  session.timerId = window.setInterval(() => {
    if (session.modalMode === "running") {
      renderPreprocessRunningModal(session);
    }
  }, 1000);
  session.pollId = window.setInterval(() => {
    pollPreprocessSession(session).catch((error) => {
      clearActivePreprocessSession();
      state.modalLocked = false;
      showModal("\u9884\u5904\u7406\u5931\u8d25", error.message);
      setModalBody("");
    });
  }, 1000);
  return { ok: true };
}

async function startExistingDatabasePreprocess(dbName, scheme) {
  try {
    await runDatabasePreprocessWithModal(dbName, scheme);
    setMessage("create-db-message", `${dbName} \u5df2\u542f\u52a8 ${scheme === "pirexx" ? "pirex+" : "pirex"} \u9884\u5904\u7406\u3002`);
  } catch (error) {
    return;
  }
}

async function startPirexxPreprocess() {
  const dbName = getCreateDbName();
  if (!dbName) {
    setMessage("create-db-message", "\u8bf7\u5148\u8f93\u5165\u521b\u5efa\u9875\u6570\u636e\u5e93\u540d\u79f0\u3002", true);
    return;
  }

  try {
    await runDatabasePreprocessWithModal(dbName, "pirexx");
    setMessage("create-db-message", `${dbName} \u5df2\u542f\u52a8 pirex+ \u9884\u5904\u7406\u3002`);
  } catch (error) {
    const message = String(error.message || "");
    if (message.includes("\u6570\u636e\u672a\u4e0a\u4f20")) {
      setMessage("create-db-message", "\u6570\u636e\u672a\u4e0a\u4f20", true);
      return;
    }
    setMessage("create-db-message", `pirex+ \u9884\u5904\u7406\u5931\u8d25\uff1a${message}`, true);
  }
}

async function startPirexPreprocess() {
  const dbName = getCreateDbName();
  if (!dbName) {
    setMessage("create-db-message", "\u8bf7\u5148\u8f93\u5165\u521b\u5efa\u9875\u6570\u636e\u5e93\u540d\u79f0\u3002", true);
    return;
  }

  try {
    await runDatabasePreprocessWithModal(dbName, "pirex");
    setMessage("create-db-message", `${dbName} \u5df2\u542f\u52a8 pirex \u9884\u5904\u7406\u3002`);
  } catch (error) {
    const message = String(error.message || "");
    if (message.includes("\u6570\u636e\u672a\u4e0a\u4f20")) {
      setMessage("create-db-message", "\u6570\u636e\u672a\u4e0a\u4f20", true);
      return;
    }
    setMessage("create-db-message", `pirex \u9884\u5904\u7406\u5931\u8d25\uff1a${message}`, true);
  }
}

async function unfinishedClearDatabase() {
  const dbName = getCreateDbName();
  if (!dbName) {
    setMessage("create-db-message", "\u8bf7\u5148\u8f93\u5165\u8981\u6e05\u7a7a\u521b\u5efa\u7684\u6570\u636e\u5e93\u540d\u79f0\u3002", true);
    return;
  }

  const confirmed = window.confirm(`\u786e\u8ba4\u6e05\u7a7a\u5e76\u5220\u9664\u672a\u5b8c\u6210\u6570\u636e\u5e93 ${dbName} \u5417\uff1f`);
  if (!confirmed) {
    return;
  }

  try {
    await apiJson(`/databases/${encodeURIComponent(dbName)}/unfinished-clear`, {
      method: "POST",
    });
    await loadTmpFiles();
    await refreshDatabases();
    await refreshDatabaseLogPanel().catch(() => {});
    if (qs("#create-db-name")) {
      qs("#create-db-name").value = "";
    }
    setMessage("create-db-message", `\u672a\u5b8c\u6210\u6570\u636e\u5e93 ${dbName} \u5df2\u6e05\u7a7a\u5e76\u5220\u9664\u3002`);
  } catch (error) {
    setMessage("create-db-message", `\u6e05\u7a7a\u521b\u5efa\u5931\u8d25\uff1a${error.message}`, true);
  }
}

async function fillOverviewFiles() {
  const dbName = getOverviewSelectedDatabase();
  if (!dbName) {
    qs("#overview-files-text").value = "\u6682\u65e0\u6570\u636e\u5e93\u3002";
    return;
  }

  try {
    const payload = await apiJson(`/databases/${encodeURIComponent(dbName)}/files`);
    const files = payload.files || [];
    qs("#overview-files-text").value = files.length
      ? files.map((item) => `${item.file_name} (${item.size_bytes} bytes)`).join("\n")
      : "\u5f53\u524d\u6570\u636e\u5e93\u6ca1\u6709\u6587\u4ef6\u3002";
  } catch (error) {
    qs("#overview-files-text").value = `\u8bfb\u53d6\u5931\u8d25\uff1a${error.message}`;
  }
}

function applyRole() {
  const isAdmin = state.user?.role === "admin";
  qsa(".admin-only").forEach((element) => {
    element.style.display = isAdmin ? "" : "none";
  });
}

function filterUsers() {
  const keyword = (qs("#user-search-input")?.value || "").trim();
  loadUsers(keyword).catch((error) => {
    showModal("\u63d0\u793a", `\u67e5\u8be2\u7528\u6237\u5931\u8d25\uff1a${error.message}`);
  });
}

async function deleteAccount(username) {
  if (!username) return;
  const confirmed = window.confirm(`\u786e\u8ba4\u5220\u9664\u7528\u6237 ${username} \u5417\uff1f`);
  if (!confirmed) return;

  try {
    await apiJson("/accounts/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        admin_username: state.user?.username || "",
      }),
    });
    await loadUsers(qs("#user-search-input")?.value || "");
    await refreshUserManagerLogPanel().catch(() => {});
    showModal("\u63d0\u793a", `\u7528\u6237 ${username} \u5df2\u5220\u9664\u3002`);
  } catch (error) {
    showModal("\u63d0\u793a", `\u5220\u9664\u7528\u6237 ${username} \u5931\u8d25\uff1a${error.message}`);
  }
}

async function resetAccountPassword(username) {
  if (!username) return;
  const newPassword = window.prompt(`\u8bf7\u8f93\u5165\u7528\u6237 ${username} \u7684\u65b0\u5bc6\u7801`);
  if (newPassword === null) return;

  try {
    await apiJson("/accounts/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        new_password: newPassword,
        admin_username: state.user?.username || "",
      }),
    });
    await refreshUserManagerLogPanel().catch(() => {});
    showModal("\u63d0\u793a", `\u7528\u6237 ${username} \u5bc6\u7801\u5df2\u91cd\u7f6e\u3002`);
  } catch (error) {
    showModal("\u63d0\u793a", `\u91cd\u7f6e\u7528\u6237 ${username} \u5bc6\u7801\u5931\u8d25\uff1a${error.message}`);
  }
}


function openAddUserModal() {
  const html = `
    <form class="app-modal-form" autocomplete="off">
      <input type="text" name="fake-username" autocomplete="username" tabindex="-1" aria-hidden="true" style="position:absolute;left:-9999px;top:auto;width:1px;height:1px;opacity:0;">
      <input type="password" name="fake-password" autocomplete="new-password" tabindex="-1" aria-hidden="true" style="position:absolute;left:-9999px;top:auto;width:1px;height:1px;opacity:0;">
      <label class="app-modal-field">
        <span>\u6635\u79f0</span>
        <input id="add-user-nickname" name="add-user-nickname-field" type="text" inputmode="text" placeholder="\u8bf7\u8f93\u5165\u6635\u79f0" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false" data-form-type="other">
      </label>
      <label class="app-modal-field">
        <span>\u8d26\u53f7</span>
        <input id="add-user-username" name="add-user-username-field" type="text" inputmode="text" placeholder="\u8bf7\u8f93\u5165\u8d26\u53f7" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false" data-form-type="other">
      </label>
      <label class="app-modal-field">
        <span>\u5bc6\u7801</span>
        <input id="add-user-password" name="add-user-password-field" type="password" placeholder="\u81f3\u5c11 6 \u4f4d" autocomplete="new-password" autocorrect="off" autocapitalize="none" spellcheck="false" data-form-type="other">
      </label>
      <p id="add-user-error" class="app-modal-error"></p>
      <div class="app-modal-actions">
        <button id="add-user-submit" class="btn btn-primary" type="button">\u6dfb\u52a0</button>
      </div>
    </form>
  `;
  showModal("\u6dfb\u52a0\u7528\u6237", "");
  setModalBody(html);
  const submitButton = qs("#add-user-submit");
  if (submitButton) {
    submitButton.addEventListener("click", submitAddUser);
  }
}

function showAddUserError(message) {
  const el = qs("#add-user-error");
  if (el) {
    el.textContent = message || "";
  }
}

async function submitAddUser() {
  const nickname = qs("#add-user-nickname")?.value.trim() || "";
  const username = qs("#add-user-username")?.value.trim() || "";
  const password = qs("#add-user-password")?.value || "";

  showAddUserError("");

  try {
    const result = await apiJson("/accounts/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nickname,
        username,
        password,
        admin_username: state.user?.username || "",
      }),
    });
    await loadUsers(qs("#user-search-input")?.value || "");
    await refreshUserManagerLogPanel().catch(() => {});
    const user = result.user || {};
    const successBody = `
      <div class="app-modal-result">
        <div>\u6635\u79f0\uff1a${user.nickname || ""}</div>
        <div>\u8d26\u53f7\uff1a${user.username || ""}</div>
        <div>\u5bc6\u7801\uff1a${password}</div>
      </div>
    `;
    showModal("\u521b\u5efa\u6210\u529f", "");
    setModalBody(successBody);
  } catch (error) {
    const message = String(error.message || "");
    if (message.includes("nickname already exists")) {
      showAddUserError("\u6635\u79f0\u91cd\u590d");
      return;
    }
    if (message.includes("username already exists")) {
      showAddUserError("\u8d26\u53f7\u91cd\u590d");
      return;
    }
    if (message.includes("password must be at least 6 characters")) {
      showAddUserError("\u5bc6\u7801\u4e0d\u5f97\u5c0f\u4e8e\u516d\u4f4d");
      return;
    }
    showAddUserError(message);
  }
}

function logout() {
  state.user = null;
  state.activeDatabase = "";
  state.activeServerAddr = "";
  qs("#dashboard").classList.add("hidden");
  qs("#login-screen").classList.remove("hidden");
  qs("#login-form").reset();
  qs("#login-username").value = "admin";
  qs("#login-password").value = "admin123";
  setMessage("login-message", "");
}

async function handleLogin(event) {
  event.preventDefault();
  const username = qs("#login-username").value.trim();
  const password = qs("#login-password").value;
  setMessage("login-message", "\u6b63\u5728\u767b\u5f55...");

  try {
    const payload = await apiJson("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    state.user = payload.user;
    qs("#user-nickname").textContent = payload.user.nickname;
    qs("#user-role").textContent = payload.user.role;
    applyRole();
    qs("#login-screen").classList.add("hidden");
    qs("#dashboard").classList.remove("hidden");
    await refreshDatabases();
    await fillOverviewFiles();
    await loadTmpFiles();
    await loadUsers();
    await loadUserManagerLogs();
    await loadDatabaseLogs();
    await loadQueryLogs();
    switchView("query-view");
    setMessage("query-message", "\u767b\u5f55\u6210\u529f\uff0c\u5148\u9009\u6570\u636e\u5e93\uff0c\u518d\u70b9\u51fb\u786e\u8ba4\u3002");
  } catch (error) {
    setMessage("login-message", `\u767b\u5f55\u5931\u8d25\uff1a${error.message}`, true);
  }
}

function bindEvents() {
  qs("#login-form").addEventListener("submit", handleLogin);
  qs("#logout-button").addEventListener("click", logout);
  qs("#refresh-databases-button").addEventListener("click", confirmDatabaseSelection);
  qs("#query-search-button").addEventListener("click", () => queryFiles(false));
  qs("#query-all-button").addEventListener("click", () => queryFiles(true));
  qs("#overview-files-button").addEventListener("click", fillOverviewFiles);
  qs("#overview-delete-button").addEventListener("click", async () => {
    const dbName = getOverviewSelectedDatabase();
    if (!dbName) {
      qs("#overview-files-text").value = "\u8bf7\u5148\u5728\u53f3\u4fa7\u5217\u8868\u4e2d\u9009\u4e2d\u6570\u636e\u5e93\u3002";
      return;
    }

    const confirmed = window.confirm(`\u786e\u8ba4\u5220\u9664\u6570\u636e\u5e93 ${dbName} \u5417\uff1f`);
    if (!confirmed) {
      return;
    }

    try {
      await apiJson(`/databases/${encodeURIComponent(dbName)}`, {
        method: "DELETE",
      });
      if (state.activeDatabase === dbName) {
        state.activeDatabase = "";
        state.activeServerAddr = "";
      }
      if (state.overviewSelectedDatabase === dbName) {
        setOverviewSelectedDatabase("");
      }
      await refreshDatabases();
      await refreshDatabaseLogPanel().catch(() => {});
      qs("#overview-files-text").value = "";
      showModal("\u63d0\u793a", `\u6570\u636e\u5e93 ${dbName} \u5df2\u5220\u9664`);
    } catch (error) {
      showModal("\u63d0\u793a", `\u5220\u9664\u6570\u636e\u5e93 ${dbName} \u5931\u8d25\uff1a${error.message}`);
    }
  });
  qs("#create-db-button").addEventListener("click", createDatabase);
  qs("#create-db-name").addEventListener("input", () => {
    resetCreateDbInputVisual();
    setDbInlineStatus("");
    setMessage("create-db-message", "");
  });
  qs("#upload-files-input").addEventListener("change", stageFilesToTmp);
  qs("#upload-files-button").addEventListener("click", uploadStagedFiles);
  qs("#unfinished-clear-button").addEventListener("click", unfinishedClearDatabase);
  qs("#pack-db-button").addEventListener("click", startPirexxPreprocess);
  qs("#pack-pirex-button").addEventListener("click", startPirexPreprocess);
  qs("#app-modal").addEventListener("click", (event) => {
    if (event.target.id === "app-modal") {
      hideModal();
    }
  });

  qsa(".side-link").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });
  qsa("[data-db-tab]").forEach((button) => {
    button.addEventListener("click", () => switchDbTab(button.dataset.dbTab));
  });
  qsa("[data-metrics-tab]").forEach((button) => {
    button.addEventListener("click", () => switchMetricsTab(button.dataset.metricsTab));
  });
  qsa("[data-perf-geometry-tab]").forEach((button) => {
    button.addEventListener("click", () => switchPerfGeometryTab(button.dataset.perfGeometryTab));
  });
  qsa("[data-log-tab]").forEach((button) => {
    button.addEventListener("click", () => switchLogTab(button.dataset.logTab));
  });
  qs("#open-add-user-button").addEventListener("click", openAddUserModal);
  qs("#user-search-button").addEventListener("click", filterUsers);
  qs("#user-log-prev").addEventListener("click", () => {
    if (state.userManagerLogPage > 1) {
      loadUserManagerLogs(state.userManagerLogPage - 1).catch(() => {});
    }
  });
  qs("#user-log-next").addEventListener("click", () => {
    if (state.userManagerLogPage < state.userManagerLogTotalPages) {
      loadUserManagerLogs(state.userManagerLogPage + 1).catch(() => {});
    }
  });
  qs("#db-log-prev").addEventListener("click", () => {
    if (state.databaseLogPage > 1) {
      loadDatabaseLogs(state.databaseLogPage - 1).catch(() => {});
    }
  });
  qs("#db-log-next").addEventListener("click", () => {
    if (state.databaseLogPage < state.databaseLogTotalPages) {
      loadDatabaseLogs(state.databaseLogPage + 1).catch(() => {});
    }
  });
  qs("#query-log-prev").addEventListener("click", () => {
    if (state.queryLogPage > 1) {
      loadQueryLogs(state.queryLogPage - 1).catch(() => {});
    }
  });
  qs("#query-log-next").addEventListener("click", () => {
    if (state.queryLogPage < state.queryLogTotalPages) {
      loadQueryLogs(state.queryLogPage + 1).catch(() => {});
    }
  });
  qs("#user-search-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      filterUsers();
    }
  });
}

function init() {
  bindEvents();
  loadUploadLimits();
  loadTmpFiles();
  loadMainMetricsLoadPanel().catch(() => {});
  loadUsers().catch(() => {});
  loadUserManagerLogs().catch(() => {});
  loadDatabaseLogs().catch(() => {});
  loadQueryLogs().catch(() => {});
}

document.addEventListener("DOMContentLoaded", init);
