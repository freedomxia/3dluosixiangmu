const elements = {
  serviceState: document.querySelector("#serviceState"),
  historyEmpty: document.querySelector("#historyEmpty"),
  historyList: document.querySelector("#historyList"),
  configTrigger: document.querySelector("#configTrigger"),
  configNotice: document.querySelector("#configNotice"),
  configMessage: document.querySelector("#configMessage"),
  configNoticeAction: document.querySelector("#configNoticeAction"),
  configStation: document.querySelector("#configStation"),
  configCloseButton: document.querySelector("#configCloseButton"),
  serviceConfigForm: document.querySelector("#serviceConfigForm"),
  modelConfigStatus: document.querySelector("#modelConfigStatus"),
  styleConfigStatus: document.querySelector("#styleConfigStatus"),
  pixparkConfigStatus: document.querySelector("#pixparkConfigStatus"),
  modelBaseUrlInput: document.querySelector("#modelBaseUrlInput"),
  modelNameInput: document.querySelector("#modelNameInput"),
  modelApiKeyInput: document.querySelector("#modelApiKeyInput"),
  clearModelApiKeyInput: document.querySelector("#clearModelApiKeyInput"),
  modelKeyState: document.querySelector("#modelKeyState"),
  pixparkTokenInput: document.querySelector("#pixparkTokenInput"),
  clearPixparkTokenInput: document.querySelector("#clearPixparkTokenInput"),
  pixparkTokenState: document.querySelector("#pixparkTokenState"),
  imageGenerationInput: document.querySelector("#imageGenerationInput"),
  configSaveStatus: document.querySelector("#configSaveStatus"),
  configSaveButton: document.querySelector("#configSaveButton"),
  configError: document.querySelector("#configError"),
  productionLine: document.querySelector(".production-line"),
  uploadForm: document.querySelector("#uploadForm"),
  revisionContext: document.querySelector("#revisionContext"),
  revisionTitle: document.querySelector("#revisionTitle"),
  revisionHint: document.querySelector("#revisionHint"),
  cancelRevisionButton: document.querySelector("#cancelRevisionButton"),
  imageInput: document.querySelector("#imageInput"),
  dropzone: document.querySelector("#dropzone"),
  dropzoneEmpty: document.querySelector("#dropzoneEmpty"),
  dropzonePreview: document.querySelector("#dropzonePreview"),
  previewMedia: document.querySelector("#previewMedia"),
  maxUploadLabel: document.querySelector("#maxUploadLabel"),
  uploadError: document.querySelector("#uploadError"),
  fileName: document.querySelector("#fileName"),
  fileSize: document.querySelector("#fileSize"),
  noteInput: document.querySelector("#noteInput"),
  noteCount: document.querySelector("#noteCount"),
  enrichmentInput: document.querySelector("#enrichmentInput"),
  submitButton: document.querySelector("#submitButton"),
  intakeSummary: document.querySelector(".intake-station .station-heading p"),
  processStation: document.querySelector("#processStation"),
  processTitle: document.querySelector("#processTitle"),
  processMessage: document.querySelector("#processMessage"),
  workingIndicator: document.querySelector("#workingIndicator"),
  stageRail: document.querySelector("#stageRail"),
  clarificationForm: document.querySelector("#clarificationForm"),
  clarificationQuestion: document.querySelector("#clarificationQuestion"),
  clarificationInput: document.querySelector("#clarificationInput"),
  clarificationError: document.querySelector("#clarificationError"),
  backgroundTaskButton: document.querySelector("#backgroundTaskButton"),
  cancelButton: document.querySelector("#cancelButton"),
  stallNotice: document.querySelector("#stallNotice"),
  errorState: document.querySelector("#errorState"),
  errorMessage: document.querySelector("#errorMessage"),
  retryButton: document.querySelector("#retryButton"),
  resultStation: document.querySelector("#resultStation"),
  resultTitle: document.querySelector("#resultTitle"),
  resultSubtitle: document.querySelector("#resultSubtitle"),
  resultActions: document.querySelector("#resultActions"),
  reviewContext: document.querySelector("#reviewContext"),
  sourceReviewButton: document.querySelector("#sourceReviewButton"),
  sourceThumbFrame: document.querySelector("#sourceThumbFrame"),
  sourceReviewName: document.querySelector("#sourceReviewName"),
  sourceDialog: document.querySelector("#sourceDialog"),
  sourceDialogMedia: document.querySelector("#sourceDialogMedia"),
  resultImageDialog: document.querySelector("#resultImageDialog"),
  resultImageDialogMedia: document.querySelector("#resultImageDialogMedia"),
  resultImageDialogCount: document.querySelector("#resultImageDialogCount"),
  resultImagePreviousButton: document.querySelector("#resultImagePreviousButton"),
  resultImageNextButton: document.querySelector("#resultImageNextButton"),
  resultImageDownload: document.querySelector("#resultImageDownload"),
  imageResult: document.querySelector("#imageResult"),
  generatedImageGrid: document.querySelector("#generatedImageGrid"),
  imageEmpty: document.querySelector("#imageEmpty"),
  imageEmptyTitle: document.querySelector("#imageEmptyTitle"),
  imageEmptyText: document.querySelector("#imageEmptyText"),
  imageResumeButton: document.querySelector("#imageResumeButton"),
  imageRegeneration: document.querySelector("#imageRegeneration"),
  regenerateImageButton: document.querySelector("#regenerateImageButton"),
  promptApproval: document.querySelector("#promptApproval"),
  promptApprovalText: document.querySelector("#promptApprovalText"),
  regeneratePromptButton: document.querySelector("#regeneratePromptButton"),
  generateImageButton: document.querySelector("#generateImageButton"),
  imageCaption: document.querySelector("#imageCaption"),
  resultTabImage: document.querySelector("#resultTabImage"),
  promptResults: document.querySelector("#promptResults"),
  positivePrompt: document.querySelector("#positivePrompt"),
  negativePrompt: document.querySelector("#negativePrompt"),
  auditSummary: document.querySelector("#auditSummary"),
  detailList: document.querySelector("#detailList"),
  resultTabs: [...document.querySelectorAll("[data-result-tab]")],
  resultPanels: [...document.querySelectorAll("[data-result-panel]")],
  reviseTaskButton: document.querySelector("#reviseTaskButton"),
  downloadButton: document.querySelector("#downloadButton"),
  newTaskButton: document.querySelector("#newTaskButton"),
  toast: document.querySelector("#toast"),
};

const state = {
  selectedFile: null,
  previewUrl: null,
  selectedJobId: null,
  revisionSourceJobId: null,
  revisionSourceFilename: "",
  runningJobIds: new Set(),
  taskStore: new Map(),
  historyItems: [],
  selectionVersion: 0,
  submitting: false,
  pendingDraft: null,
  ready: false,
  maxUploadMb: 15,
  maxImageDimension: 12000,
  pollTimer: null,
  stallTimer: null,
  submitController: null,
  imageGenerationReady: false,
  modelApiKeyConfigured: false,
  pixparkTokenConfigured: false,
  runtimeConfigLocation: ".runtime/runtime-settings.json",
  resultPreviewUrls: [],
  resultPreviewIndex: 0,
  resultPreviewAlt: "3D 建模参考结果图",
  pollInFlight: false,
};

const stageOrder = [
  "analyzing",
  "composing",
  "validating",
  "review_prompt",
  "generating_image",
];
const imageRecoveryStorageKey = "haoyue.pixpark.resume-job";
const selectedJobStorageKey = "haoyue.selected-job";
const taskUiStorageKey = "haoyue.task-ui";
const statusStage = {
  queued: "analyzing",
  analyzing: "analyzing",
  composing: "composing",
  validating: "validating",
  repairing: "validating",
  prompt_ready: "review_prompt",
  generating_image: "generating_image",
  needs_input: "analyzing",
  complete: "generating_image",
};
const pollingStatuses = new Set([
  "queued",
  "analyzing",
  "composing",
  "validating",
  "repairing",
  "generating_image",
]);
const terminalStatuses = new Set(["prompt_ready", "complete", "failed"]);

initialize();

async function initialize() {
  elements.productionLine.before(elements.configStation);
  bindEvents();
  await readServiceStatus();
  await loadHistory();
  await restoreSelectedTask();
  updateSubmitState();
}

async function restoreSelectedTask() {
  let jobId = "";
  try {
    jobId = window.sessionStorage.getItem(selectedJobStorageKey) || "";
  } catch {
    return;
  }
  if (/^[a-f0-9]{32}$/.test(jobId)) {
    await openHistoryJob(jobId);
  }
}

async function restoreInterruptedImageTask() {
  let jobId = "";
  try {
    jobId = window.sessionStorage.getItem(imageRecoveryStorageKey) || "";
  } catch {
    return;
  }
  if (!/^[a-f0-9]{32}$/.test(jobId)) {
    forgetImageTask();
    return;
  }

  try {
    const response = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
    const data = await readJson(response);
    if ([404, 410].includes(response.status)) {
      forgetImageTask(jobId);
      return;
    }
    if (!response.ok || !data.result?.image) return;

    mergeTask(data);
    state.selectedJobId = jobId;
    rememberSelectedJob(jobId);
    if (pollingStatuses.has(data.status)) state.runningJobIds.add(jobId);
    restoreTaskContext(jobId);
    applyJob(data);
    if (state.runningJobIds.has(jobId)) {
      setInputLocked(true);
      schedulePoll();
      scheduleStallNotice();
    }
  } catch {
    // A temporary network failure must not erase a recoverable remote task id.
  }
}

function rememberSelectedJob(jobId) {
  try {
    if (jobId) window.sessionStorage.setItem(selectedJobStorageKey, jobId);
    else window.sessionStorage.removeItem(selectedJobStorageKey);
  } catch {
    // Selection recovery is helpful but never required for task execution.
  }
}

function rememberImageTask(jobId) {
  if (!state.imageGenerationReady || !/^[a-f0-9]{32}$/.test(jobId || "")) return;
  try {
    window.sessionStorage.setItem(imageRecoveryStorageKey, jobId);
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }
}

function forgetImageTask(jobId = "") {
  try {
    const saved = window.sessionStorage.getItem(imageRecoveryStorageKey);
    if (!jobId || !saved || saved === jobId) {
      window.sessionStorage.removeItem(imageRecoveryStorageKey);
    }
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }
}

function bindEvents() {
  elements.configTrigger.addEventListener("click", openServiceConfig);
  elements.configNoticeAction.addEventListener("click", openServiceConfig);
  elements.configCloseButton.addEventListener("click", closeServiceConfig);
  elements.serviceConfigForm.addEventListener("submit", saveServiceConfig);
  elements.clearModelApiKeyInput.addEventListener("change", () => {
    syncSecretClearState(
      elements.clearModelApiKeyInput,
      elements.modelApiKeyInput,
    );
  });
  elements.clearPixparkTokenInput.addEventListener("change", () => {
    syncSecretClearState(
      elements.clearPixparkTokenInput,
      elements.pixparkTokenInput,
    );
  });
  elements.modelApiKeyInput.addEventListener("input", () => {
    if (elements.modelApiKeyInput.value) {
      elements.clearModelApiKeyInput.checked = false;
    }
  });
  elements.pixparkTokenInput.addEventListener("input", () => {
    if (elements.pixparkTokenInput.value) {
      elements.clearPixparkTokenInput.checked = false;
    }
  });

  elements.dropzone.addEventListener("click", () => elements.imageInput.click());
  elements.imageInput.addEventListener("change", () => {
    const [file] = elements.imageInput.files;
    if (file) void selectFile(file);
  });

  for (const eventName of ["dragenter", "dragover"]) {
    elements.dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropzone.classList.add("dragging");
    });
  }
  for (const eventName of ["dragleave", "drop"]) {
    elements.dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropzone.classList.remove("dragging");
    });
  }
  elements.dropzone.addEventListener("drop", (event) => {
    const [file] = event.dataTransfer.files;
    if (file) void selectFile(file);
  });

  elements.noteInput.addEventListener("input", () => {
    elements.noteCount.value = `${elements.noteInput.value.length} / 1000`;
  });
  elements.uploadForm.addEventListener("submit", submitJob);
  elements.reviseTaskButton.addEventListener("click", beginRevision);
  elements.cancelRevisionButton.addEventListener("click", cancelRevision);
  elements.clarificationForm.addEventListener("submit", resumeJob);
  elements.retryButton.addEventListener("click", handleFailureAction);
  elements.backgroundTaskButton.addEventListener("click", startNewDraft);
  elements.cancelButton.addEventListener("click", cancelJob);
  elements.generateImageButton.addEventListener("click", generateImage);
  elements.regeneratePromptButton.addEventListener("click", regeneratePrompt);
  elements.regenerateImageButton.addEventListener("click", regenerateImage);
  elements.imageResumeButton.addEventListener("click", resumeImage);
  elements.newTaskButton.addEventListener("click", requestNewTask);
  elements.downloadButton.addEventListener("click", downloadResult);
  elements.sourceReviewButton.addEventListener("click", () => {
    if (typeof elements.sourceDialog.showModal === "function") {
      elements.sourceDialog.showModal();
    }
  });
  elements.resultImagePreviousButton.addEventListener("click", () => {
    stepResultImagePreview(-1);
  });
  elements.resultImageNextButton.addEventListener("click", () => {
    stepResultImagePreview(1);
  });
  elements.resultImageDialog.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      stepResultImagePreview(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      stepResultImagePreview(1);
    }
  });

  document.querySelectorAll("[data-copy-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.copyTarget);
      copyText(target.textContent, button);
    });
  });

  elements.resultTabs.forEach((tab, index) => {
    tab.tabIndex = index === 0 ? 0 : -1;
    tab.addEventListener("click", () => activateResultTab(tab.dataset.resultTab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const availableTabs = elements.resultTabs.filter(
        (item) => window.getComputedStyle(item).display !== "none",
      );
      if (availableTabs.length < 2) return;
      event.preventDefault();
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const currentIndex = availableTabs.indexOf(tab);
      const nextIndex =
        (currentIndex + direction + availableTabs.length) %
        availableTabs.length;
      const nextTab = availableTabs[nextIndex];
      activateResultTab(nextTab.dataset.resultTab);
      nextTab.focus();
    });
  });
}

function readTaskUiState(jobId) {
  try {
    const payload = JSON.parse(window.sessionStorage.getItem(taskUiStorageKey) || "{}");
    const value = payload[jobId];
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

function persistTaskUiState(jobId, values) {
  if (!jobId) return;
  try {
    const payload = JSON.parse(window.sessionStorage.getItem(taskUiStorageKey) || "{}");
    payload[jobId] = { ...(payload[jobId] || {}), ...values };
    window.sessionStorage.setItem(taskUiStorageKey, JSON.stringify(payload));
  } catch {
    // UI tab recovery must not affect task data.
  }
}

function mergeTask(job, seed = {}) {
  const existing = state.taskStore.get(job.id) || {};
  const ui = readTaskUiState(job.id);
  const task = {
    ...existing,
    ...seed,
    ...job,
    file: seed.file ?? existing.file ?? null,
    previewUrl:
      seed.previewUrl ??
      existing.previewUrl ??
      job.source_image_url ??
      null,
    activeTab: existing.activeTab || ui.activeTab || "positive",
    resultHandled: Boolean(existing.resultHandled),
    resultRendered: Boolean(existing.resultRendered),
    notifiedStatus: existing.notifiedStatus || null,
    pollErrorNotified: false,
  };
  state.taskStore.set(job.id, task);
  return { task, previousStatus: existing.status };
}

function selectedTask() {
  return state.selectedJobId
    ? state.taskStore.get(state.selectedJobId) || null
    : null;
}

async function loadHistory() {
  try {
    const response = await fetch("/api/jobs?limit=30", { cache: "no-store" });
    const data = await readJson(response);
    if (!response.ok) throw new Error(getErrorMessage(data));
    const items = Array.isArray(data.items) ? data.items : [];
    state.historyItems = items;
    items.forEach((item) => {
      mergeTask(item);
      if (pollingStatuses.has(item.status)) {
        state.runningJobIds.add(item.id);
      } else {
        state.runningJobIds.delete(item.id);
      }
    });
    renderHistory(items);
    schedulePoll();
  } catch {
    elements.historyEmpty.hidden = false;
    elements.historyEmpty.querySelector("strong").textContent =
      "暂时无法读取历史";
    elements.historyEmpty.querySelector("p").textContent =
      "当前任务不受影响，稍后再打开即可重试。";
  }
}

function renderHistory(items) {
  elements.historyList.replaceChildren();
  elements.historyEmpty.hidden = items.length > 0;
  if (!items.length) {
    elements.historyEmpty.querySelector("strong").textContent = "还没有记录";
    elements.historyEmpty.querySelector("p").textContent =
      "完成第一次提示词解析后，会出现在这里。";
    return;
  }

  const statusLabels = {
    queued: "排队中",
    analyzing: "识别需求",
    composing: "生成提示词",
    validating: "审查中",
    repairing: "修正中",
    needs_input: "待补充",
    prompt_ready: "待确认",
    generating_image: "生图中",
    complete: "已完成",
    failed: "未完成",
  };

  items.forEach((item) => {
    const button = document.createElement("button");
    const thumbnail = document.createElement("span");
    const content = document.createElement("span");
    const top = document.createElement("span");
    const name = document.createElement("strong");
    const status = document.createElement("span");
    const meta = document.createElement("small");
    const shortId = document.createElement("code");

    button.type = "button";
    button.className = "history-item";
    button.dataset.jobId = item.id;
    button.classList.toggle("active", item.id === state.selectedJobId);
    button.addEventListener("click", () => openHistoryJob(item.id));

    thumbnail.className = "history-thumbnail";
    if (item.source_image_url) {
      const image = document.createElement("img");
      image.src = item.source_image_url;
      image.alt = "";
      image.loading = "lazy";
      thumbnail.append(image);
    } else {
      thumbnail.textContent = "无图";
    }

    name.textContent = item.filename || "未命名需求图";
    status.textContent = statusLabels[item.status] || item.step || "处理中";
    status.className = `history-status ${item.status || ""}`;
    top.append(name, status);
    shortId.textContent = `#${item.short_id || item.id.slice(0, 8).toUpperCase()}`;
    meta.textContent = `${formatHistoryTime(item.updated_at)} · ${
      item.has_prompt ? "提示词已保存" : item.message || "处理中"
    }`;
    content.className = "history-item-content";
    content.append(top, shortId, meta);
    button.append(thumbnail, content);
    elements.historyList.append(button);
  });
}

async function openHistoryJob(jobId) {
  const selectionVersion = ++state.selectionVersion;
  if (state.revisionSourceJobId) {
    clearDraftSource();
    clearRevisionMode();
  } else {
    stashPendingDraft();
  }
  state.selectedJobId = jobId;
  rememberSelectedJob(jobId);
  const loadingTask = state.taskStore.get(jobId);
  if (loadingTask) loadingTask.resultRendered = false;
  renderHistory(state.historyItems);
  clearStallTimer();
  clearDraftSource();
  resetProcessMessages();
  prepareResultForProcessing();
  showProcess("queued", "正在读取任务", "正在恢复这项任务的需求图与独立状态。 ");
  setInputLocked(true);
  try {
    const response = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
    const job = await readJson(response);
    if (
      selectionVersion !== state.selectionVersion ||
      state.selectedJobId !== jobId
    ) {
      return;
    }
    if (!response.ok) throw new Error(getErrorMessage(job));
    mergeTask(job);
    restoreTaskContext(job.id);
    if (pollingStatuses.has(job.status)) {
      state.runningJobIds.add(job.id);
    } else {
      state.runningJobIds.delete(job.id);
    }
    if (!job.result && terminalStatuses.has(job.status)) {
      applyJob(job);
    } else if (!job.result && !state.runningJobIds.has(job.id) && job.status !== "needs_input") {
      showToast(job.error || job.message || "这条记录还没有可查看的结果。");
      return;
    } else {
      applyJob(job);
    }
    schedulePoll();
    await loadHistory();
  } catch (error) {
    if (
      selectionVersion !== state.selectionVersion ||
      state.selectedJobId !== jobId
    ) {
      return;
    }
    showToast(error.message || "无法打开这条历史记录。");
    state.selectedJobId = null;
    rememberSelectedJob(null);
    returnToInput();
  }
}

function formatHistoryTime(timestamp) {
  const date = new Date(Number(timestamp || 0) * 1000);
  if (Number.isNaN(date.getTime())) return "时间未知";
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return date.toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  });
}

async function readServiceStatus() {
  try {
    const response = await fetch("/api/config", { cache: "no-store" });
    if (!response.ok) throw new Error("status");
    const data = await response.json();
    applyServiceConfiguration(data);
    return data;
  } catch {
    state.ready = false;
    elements.serviceState.className = "service-state not-ready";
    elements.serviceState.lastElementChild.textContent = "服务状态未知";
    elements.configMessage.textContent = "暂时无法读取服务状态，请刷新页面重试。";
    elements.configNotice.hidden = false;
    setConfigStatus(elements.modelConfigStatus, "模型接口 · 状态未知", "warning");
    setConfigStatus(elements.styleConfigStatus, "固定图2 · 状态未知", "warning");
    setConfigStatus(elements.pixparkConfigStatus, "PixPark · 状态未知", "warning");
    return null;
  }
}

function applyServiceConfiguration(data) {
  state.ready = Boolean(data.ready);
  state.maxUploadMb = Number(data.max_upload_mb || 15);
  state.maxImageDimension = Number(data.max_image_dimension || 12000);
  state.imageGenerationReady = Boolean(data.image_generation_ready);
  state.modelApiKeyConfigured = Boolean(data.model_api_key_configured);
  state.pixparkTokenConfigured = Boolean(data.pixpark_token_configured);
  state.runtimeConfigLocation =
    data.runtime_config_location || ".runtime/runtime-settings.json";
  elements.maxUploadLabel.textContent = `${state.maxUploadMb} MB`;

  elements.modelBaseUrlInput.value = data.model_base_url || "";
  elements.modelNameInput.value = data.model_name || "";
  elements.modelApiKeyInput.value = "";
  elements.pixparkTokenInput.value = "";
  elements.clearModelApiKeyInput.checked = false;
  elements.clearPixparkTokenInput.checked = false;
  syncSecretClearState(
    elements.clearModelApiKeyInput,
    elements.modelApiKeyInput,
  );
  syncSecretClearState(
    elements.clearPixparkTokenInput,
    elements.pixparkTokenInput,
  );
  elements.imageGenerationInput.checked = Boolean(
    data.image_generation_enabled,
  );

  elements.modelKeyState.textContent = state.modelApiKeyConfigured
    ? "已配置"
    : "未配置";
  elements.pixparkTokenState.textContent = state.pixparkTokenConfigured
    ? "已配置"
    : "未配置";
  elements.modelApiKeyInput.placeholder = state.modelApiKeyConfigured
    ? "已配置；留空保持不变"
    : "输入新的 API Key";
  elements.pixparkTokenInput.placeholder = state.pixparkTokenConfigured
    ? "已配置；留空保持不变"
    : "输入新的 PixPark Token";

  setConfigStatus(
    elements.modelConfigStatus,
    data.model_configured ? "模型接口 · 已配置" : "模型接口 · 未配置",
    data.model_configured ? "ready" : "warning",
  );
  setConfigStatus(
    elements.styleConfigStatus,
    data.style_reference_configured ? "固定图2 · 已配置" : "固定图2 · 缺少",
    data.style_reference_configured ? "ready" : "warning",
  );
  setConfigStatus(
    elements.pixparkConfigStatus,
    data.pixpark_configured
      ? data.image_generation_enabled
        ? "PixPark · 已启用"
        : "PixPark · 已配置，生成关闭"
      : "PixPark · 未配置",
    data.pixpark_configured ? "ready" : "warning",
  );

  if (state.ready) {
    elements.serviceState.className = "service-state ready";
    elements.serviceState.lastElementChild.textContent = "服务已就绪";
    elements.configNotice.hidden = true;
  } else {
    const missing = [];
    if (!data.model_configured) missing.push("解析模型");
    if (!data.style_reference_configured) missing.push("固定图2参考图");
    elements.serviceState.className = "service-state not-ready";
    elements.serviceState.lastElementChild.textContent = "服务待配置";
    elements.configMessage.textContent = `还需要配置${missing.join("和")}。`;
    elements.configNotice.hidden = false;
  }
  updateSubmitState();
}

function setConfigStatus(element, text, tone) {
  element.className = `config-status ${tone}`;
  element.lastChild.textContent = text;
}

function syncSecretClearState(checkbox, input) {
  input.disabled = checkbox.checked;
  if (checkbox.checked) input.value = "";
}

async function openServiceConfig() {
  if (state.submitting || state.runningJobIds.size) {
    showToast("仍有后台任务未结束，结束后才能修改服务配置。");
    return;
  }
  document.body.dataset.configOpen = "true";
  elements.configStation.hidden = false;
  elements.productionLine.hidden = true;
  elements.configError.hidden = true;
  elements.configSaveStatus.textContent =
    `配置保存在 ${state.runtimeConfigLocation}；此页面只显示配置状态。`;
  await readServiceStatus();
  elements.modelBaseUrlInput.focus({ preventScroll: true });
}

function closeServiceConfig() {
  delete document.body.dataset.configOpen;
  elements.configStation.hidden = true;
  elements.productionLine.hidden = false;
  elements.configError.hidden = true;
  elements.configTrigger.focus({ preventScroll: true });
}

async function saveServiceConfig(event) {
  event.preventDefault();
  elements.configError.hidden = true;
  if (!elements.serviceConfigForm.reportValidity()) return;

  const payload = {
    model_base_url: elements.modelBaseUrlInput.value.trim(),
    model_name: elements.modelNameInput.value.trim(),
    model_api_key: elements.modelApiKeyInput.value.trim(),
    clear_model_api_key: elements.clearModelApiKeyInput.checked,
    pixpark_token: elements.pixparkTokenInput.value.trim(),
    clear_pixpark_token: elements.clearPixparkTokenInput.checked,
    image_generation_enabled: elements.imageGenerationInput.checked,
  };
  const label = elements.configSaveButton.querySelector("span");
  elements.configSaveButton.disabled = true;
  label.textContent = "正在保存";
  elements.configSaveStatus.textContent = "正在把配置安全写入本机后端。";

  try {
    const response = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(getErrorMessage(data));
    applyServiceConfiguration(data);
    elements.configSaveStatus.textContent = data.message || "配置已保存并生效。";
    showToast("服务配置已保存");
  } catch (error) {
    elements.configSaveStatus.textContent = "配置没有改变。";
    elements.configError.textContent =
      error.message || "配置保存失败，请检查后重试。";
    elements.configError.hidden = false;
  } finally {
    elements.configSaveButton.disabled = false;
    label.textContent = "保存并应用";
  }
}

async function selectFile(file) {
  setUploadError("");
  const accepted = ["image/png", "image/jpeg", "image/webp"];
  if (!accepted.includes(file.type)) {
    setUploadError("只支持 PNG、JPEG 或 WebP 图片，请重新选择。");
    return;
  }
  if (!file.size) {
    setUploadError("这张图片是空文件，请重新导出后上传。");
    return;
  }
  if (file.size > state.maxUploadMb * 1024 * 1024) {
    setUploadError(
      `图片不能超过 ${state.maxUploadMb} MB，请压缩后重新上传。`,
    );
    return;
  }

  const candidateUrl = URL.createObjectURL(file);
  const previewImage = document.createElement("img");
  previewImage.src = candidateUrl;
  previewImage.alt = "已选择需求图预览";

  try {
    await previewImage.decode();
  } catch {
    URL.revokeObjectURL(candidateUrl);
    setUploadError("图片文件损坏或无法解码，请重新导出后上传。");
    return;
  }

  if (previewImage.naturalWidth < 320 || previewImage.naturalHeight < 320) {
    URL.revokeObjectURL(candidateUrl);
    setUploadError("图片尺寸过小，宽高都需要至少 320 像素。");
    return;
  }
  if (
    previewImage.naturalWidth > state.maxImageDimension ||
    previewImage.naturalHeight > state.maxImageDimension
  ) {
    URL.revokeObjectURL(candidateUrl);
    setUploadError(
      `图片宽高不能超过 ${state.maxImageDimension} 像素，请缩小后上传。`,
    );
    return;
  }

  if (state.previewUrl && !isRetainedTaskPreview(state.previewUrl)) {
    URL.revokeObjectURL(state.previewUrl);
  }
  state.selectedFile = file;
  state.previewUrl = candidateUrl;
  elements.previewMedia.replaceChildren(previewImage);
  elements.fileName.textContent = file.name;
  elements.fileSize.textContent = formatBytes(file.size);
  elements.dropzoneEmpty.hidden = true;
  elements.dropzonePreview.hidden = false;
  elements.dropzone.classList.add("has-file");
  updateSubmitState();
}

function setUploadError(message) {
  elements.uploadError.textContent = message;
  elements.uploadError.hidden = !message;
  elements.dropzone.setAttribute("aria-invalid", String(Boolean(message)));
}

function rememberTaskContext(jobId, job = {}) {
  const task = state.taskStore.get(jobId) || {};
  state.taskStore.set(jobId, {
    ...task,
    id: jobId,
    filename:
      job.filename ||
      state.selectedFile?.name ||
      state.revisionSourceFilename ||
      "未命名需求图",
    file: state.selectedFile,
    previewUrl: state.previewUrl,
    note: elements.noteInput.value,
    enrichment_enabled: elements.enrichmentInput.checked,
    status: task.status || "queued",
    result: null,
    activeTab: "positive",
    resultHandled: false,
    resultRendered: false,
    notifiedStatus: null,
    pollErrorNotified: false,
  });
}

function updateTaskContextFromJob(job) {
  const { task, previousStatus } = mergeTask(job);
  return { context: task, previousStatus };
}

function restoreTaskContext(jobId) {
  const context = state.taskStore.get(jobId);
  if (!context) {
    clearDraftSource();
    return;
  }

  state.selectedFile = context.file || null;
  state.previewUrl = context.previewUrl || null;
  elements.noteInput.value = context.note || "";
  elements.noteCount.value = `${elements.noteInput.value.length} / 1000`;
  elements.enrichmentInput.checked = Boolean(context.enrichment_enabled);
  setUploadError("");

  if (context.previewUrl) {
    const image = document.createElement("img");
    image.src = context.previewUrl;
    image.alt = "当前任务的需求图预览";
    elements.previewMedia.replaceChildren(image);
    elements.fileName.textContent = context.filename;
    elements.fileSize.textContent = context.file
      ? formatBytes(context.file.size)
      : "服务端临时保存";
    elements.dropzone.classList.add("has-file");
    elements.dropzoneEmpty.hidden = true;
    elements.dropzonePreview.hidden = false;
  } else {
    clearDraftSource({ keepNote: true });
  }
}

function stashPendingDraft() {
  if (state.selectedJobId || !state.selectedFile || !state.previewUrl) return;
  state.pendingDraft = {
    file: state.selectedFile,
    filename: state.selectedFile.name,
    previewUrl: state.previewUrl,
    note: elements.noteInput.value,
    enrichmentEnabled: elements.enrichmentInput.checked,
  };
}

function restorePendingDraft() {
  const draft = state.pendingDraft;
  if (!draft) return false;
  state.pendingDraft = null;
  state.selectedFile = draft.file;
  state.previewUrl = draft.previewUrl;
  elements.noteInput.value = draft.note || "";
  elements.noteCount.value = `${elements.noteInput.value.length} / 1000`;
  elements.enrichmentInput.checked = Boolean(draft.enrichmentEnabled);
  const image = document.createElement("img");
  image.src = draft.previewUrl;
  image.alt = "未提交需求图预览";
  elements.previewMedia.replaceChildren(image);
  elements.fileName.textContent = draft.filename;
  elements.fileSize.textContent = formatBytes(draft.file.size);
  elements.dropzone.classList.add("has-file");
  elements.dropzoneEmpty.hidden = true;
  elements.dropzonePreview.hidden = false;
  setUploadError("");
  updateSubmitState();
  return true;
}

function clearDraftSource(options = {}) {
  const keepNote = Boolean(options.keepNote);
  if (state.previewUrl && !isRetainedTaskPreview(state.previewUrl)) {
    URL.revokeObjectURL(state.previewUrl);
  }
  state.selectedFile = null;
  state.previewUrl = null;
  elements.imageInput.value = "";
  if (!keepNote) {
    elements.noteInput.value = "";
    elements.noteCount.value = "0 / 1000";
    elements.enrichmentInput.checked = false;
  }
  elements.dropzone.classList.remove("has-file");
  elements.dropzoneEmpty.hidden = false;
  elements.dropzonePreview.hidden = true;
  elements.previewMedia.replaceChildren();
  setUploadError("");
}

function isRetainedTaskPreview(previewUrl) {
  if (!String(previewUrl || "").startsWith("blob:")) return true;
  return (
    state.pendingDraft?.previewUrl === previewUrl ||
    [...state.taskStore.values()].some(
      (context) => context.previewUrl === previewUrl,
    )
  );
}

function updateSubmitState() {
  const busy = state.submitting || Boolean(state.selectedJobId);
  const hasRevisionSource = Boolean(state.revisionSourceJobId);
  elements.submitButton.disabled =
    !state.ready || (!state.selectedFile && !hasRevisionSource) || busy;
  elements.configTrigger.disabled = state.submitting || state.runningJobIds.size > 0;
}

async function submitJob(event) {
  event.preventDefault();
  const revisionSourceJobId = state.revisionSourceJobId;
  const isRevision = Boolean(revisionSourceJobId);
  if (
    (!state.selectedFile && !isRevision) ||
    !state.ready ||
    state.submitting
  ) {
    return;
  }

  clearStallTimer();
  resetProcessMessages();
  state.submitting = true;
  state.selectedJobId = null;
  rememberSelectedJob(null);
  document.body.dataset.mode = "running";
  const sourceFilename =
    state.selectedFile?.name || state.revisionSourceFilename || "原任务需求图";
  elements.intakeSummary.textContent = isRevision
    ? `${sourceFilename} · 已作为修改版图1`
    : `${sourceFilename} · 已锁定为当前图1`;
  updateSubmitState();
  setInputLocked(true);
  prepareResultForProcessing();
  showProcess(
    "queued",
    isRevision ? "正在提交修改" : "正在提交",
    isRevision ? "正在建立新的修改版本。" : "正在安全上传需求图。",
  );

  const body = new FormData();
  if (state.selectedFile) body.append("image", state.selectedFile);
  body.append("note", elements.noteInput.value.trim());
  body.append("enrichment_enabled", String(elements.enrichmentInput.checked));
  state.submitController = new AbortController();

  try {
    const endpoint = isRevision
      ? `/api/jobs/${revisionSourceJobId}/revise`
      : "/api/jobs";
    const response = await fetch(endpoint, {
      method: "POST",
      body,
      signal: state.submitController.signal,
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(getErrorMessage(data));
    state.selectedJobId = data.id;
    rememberSelectedJob(data.id);
    state.runningJobIds.add(data.id);
    mergeTask(data, {
      file: state.selectedFile,
      previewUrl: state.previewUrl,
    });
    rememberTaskContext(data.id, data);
    clearRevisionMode({ preserveLabel: true });
    state.pendingDraft = null;
    applyJob(data);
    schedulePoll();
    scheduleStallNotice();
  } catch (error) {
    if (error.name === "AbortError") return;
    state.selectedJobId = null;
    rememberSelectedJob(null);
    showFailure(error.message || "任务提交失败，请重试。");
    if (isRevision) setSubmitLabel("提交修改");
  } finally {
    state.submitting = false;
    state.submitController = null;
    updateSubmitState();
  }
}

async function pollJob() {
  if (state.pollInFlight) return;
  const jobIds = [...state.runningJobIds];
  if (!jobIds.length) return;
  state.pollInFlight = true;
  try {
    const updates = await Promise.all(
      jobIds.map(async (jobId) => {
        try {
          const response = await fetch(`/api/jobs/${jobId}`, {
            cache: "no-store",
          });
          const data = await readJson(response);
          return { jobId, response, data };
        } catch (error) {
          return { jobId, error };
        }
      }),
    );

    for (const update of updates) {
      const { jobId, response, data, error } = update;
      const isViewed = state.selectedJobId === jobId;
      if (error) {
        const context = state.taskStore.get(jobId);
        if (context && !context.pollErrorNotified) {
          context.pollErrorNotified = true;
          if (!isViewed) showToast(`${context.filename} 暂时无法更新，正在自动重试。`);
        }
        if (isViewed) {
          showFailure("暂时无法读取任务状态，后台会继续自动重试。", {
            retryPolling: true,
          });
        }
        continue;
      }
      if ([404, 410].includes(response.status)) {
        state.runningJobIds.delete(jobId);
        state.taskStore.delete(jobId);
        void loadHistory();
        if (isViewed) {
          state.selectedJobId = null;
          rememberSelectedJob(null);
          showFailure(
            "这个任务已经超过临时保留时间，需求图与任务状态已清理。",
          );
        }
        continue;
      }
      if (!response.ok) {
        if (isViewed) {
          showFailure(getErrorMessage(data), { retryPolling: true });
        }
        continue;
      }

      if (isViewed) applyJob(data);
      else handleBackgroundJob(data);
    }
  } finally {
    state.pollInFlight = false;
    schedulePoll();
  }
}

function schedulePoll() {
  clearPolling();
  if (!state.runningJobIds.size) return;
  state.pollTimer = window.setTimeout(pollJob, 1200);
}

function clearPolling() {
  if (state.pollTimer) window.clearTimeout(state.pollTimer);
  state.pollTimer = null;
}

function scheduleStallNotice() {
  clearStallTimer();
  state.stallTimer = window.setTimeout(() => {
    if (
      state.selectedJobId &&
      state.runningJobIds.has(state.selectedJobId)
    ) {
      elements.stallNotice.hidden = false;
    }
  }, 60000);
}

function clearStallTimer() {
  if (state.stallTimer) window.clearTimeout(state.stallTimer);
  state.stallTimer = null;
  elements.stallNotice.hidden = true;
}

function handleBackgroundJob(job) {
  const update = updateTaskContextFromJob(job);
  const context = update?.context;
  const statusChanged = update && update.previousStatus !== job.status;
  if (!pollingStatuses.has(job.status)) {
    state.runningJobIds.delete(job.id);
  }
  if (statusChanged) void loadHistory();
  if (!context || context.notifiedStatus === job.status) return;

  const notifications = {
    needs_input: `${context.filename} 需要补充信息，请从历史记录打开。`,
    prompt_ready: `${context.filename} 的提示词已完成，等待确认。`,
    complete: `${context.filename} 的 4 张结果图已完成。`,
    failed: `${context.filename} 未完成，请从历史记录查看原因。`,
  };
  const message = notifications[job.status];
  if (message) {
    context.notifiedStatus = job.status;
    showToast(message);
  }
}

function applyJob(job) {
  const update = updateTaskContextFromJob(job);
  const task = update.context;
  if (pollingStatuses.has(job.status)) state.runningJobIds.add(job.id);
  else state.runningJobIds.delete(job.id);
  if (state.selectedJobId !== job.id) {
    handleBackgroundJob(job);
    return;
  }
  if (update.previousStatus !== job.status) {
    scheduleStallNotice();
    void loadHistory();
  }
  showProcess(job.status, job.step, job.message);

  if (job.status === "needs_input") {
    state.runningJobIds.delete(job.id);
    elements.workingIndicator.hidden = true;
    clearStallTimer();
    elements.clarificationQuestion.textContent =
      job.question || "请补充无法确认的要求。";
    elements.clarificationForm.hidden = false;
    elements.clarificationError.hidden = true;
    elements.clarificationInput.focus();
    return;
  }

  if (job.status === "failed") {
    state.runningJobIds.delete(job.id);
    clearStallTimer();
    showFailure(job.error || job.message || "任务处理失败。");
    schedulePoll();
    void loadHistory();
    return;
  }

  if (job.status === "generating_image" && job.result) {
    rememberImageTask(job.id);
    renderResult(job.result, {
      final: false,
      preferredTab: "image",
    });
    void loadHistory();
    return;
  }

  if (job.status === "prompt_ready") {
    state.runningJobIds.delete(job.id);
    forgetImageTask(job.id);
    clearStallTimer();
    elements.workingIndicator.hidden = true;
    renderResult(job.result, {
      final: true,
      promptReady: true,
      preferredTab: "positive",
    });
    setInputLocked(true);
    updateSubmitState();
    schedulePoll();
    void loadHistory();
    return;
  }

  if (job.status === "complete") {
    state.runningJobIds.delete(job.id);
    if (job.result?.image?.resumable) rememberImageTask(job.id);
    else forgetImageTask(job.id);
    clearStallTimer();
    elements.workingIndicator.hidden = true;
    renderResult(job.result, { final: true });
    setInputLocked(true);
    updateSubmitState();
    schedulePoll();
    void loadHistory();
  }
  if (task) task.status = job.status;
}

function showProcess(status, title, message) {
  elements.processStation.hidden = false;
  elements.errorState.hidden = true;
  elements.processTitle.textContent = title || "正在处理";
  elements.processMessage.textContent = message || "";
  elements.workingIndicator.hidden = [
    "prompt_ready",
    "complete",
    "failed",
    "needs_input",
  ].includes(status);
  elements.cancelButton.hidden = ["prompt_ready", "complete", "failed"].includes(
    status,
  );
  elements.backgroundTaskButton.hidden = [
    "prompt_ready",
    "complete",
    "failed",
  ].includes(status);
  elements.cancelButton.disabled = false;
  setSubmitLabel(status === "needs_input" ? "等待补充" : "解析中");

  const activeStage = statusStage[status] || "analyzing";
  const activeIndex = stageOrder.indexOf(activeStage);
  elements.stageRail.querySelectorAll("li").forEach((item, index) => {
    item.classList.toggle("done", index < activeIndex || status === "complete");
    item.classList.toggle("active", index === activeIndex && status !== "complete");
  });
}

function showFailure(message, options = {}) {
  const retryPolling = Boolean(
    options.retryPolling &&
    state.selectedJobId &&
    state.runningJobIds.has(state.selectedJobId),
  );
  clearStallTimer();
  elements.processStation.hidden = false;
  elements.workingIndicator.hidden = true;
  elements.clarificationForm.hidden = true;
  elements.cancelButton.hidden = true;
  elements.backgroundTaskButton.hidden = !retryPolling;
  elements.errorMessage.textContent = message;
  elements.errorState.hidden = false;
  elements.retryButton.dataset.action = retryPolling ? "poll" : "input";
  elements.retryButton.textContent = retryPolling ? "重新检查任务" : "返回检查输入";
  elements.processTitle.textContent = "处理失败";
  elements.processMessage.textContent = "请根据下面的信息检查后重试。";
  setSubmitLabel(retryPolling ? "检查中" : "重新解析");
  setInputLocked(Boolean(state.selectedJobId) || retryPolling);
  updateSubmitState();
  elements.errorState.focus({ preventScroll: true });
}

async function cancelJob() {
  const jobId = state.selectedJobId;
  if (!jobId) return;
  const wasGeneratingImage = selectedTask()?.status === "generating_image";

  if (state.submitting) {
    state.submitController?.abort();
    state.submitting = false;
    state.selectedJobId = null;
    rememberSelectedJob(null);
    returnToInput();
    showToast("已取消提交，原图和补充文字仍在。");
    return;
  }

  elements.cancelButton.disabled = true;
  try {
    const response = await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
    if (!response.ok && response.status !== 404) {
      const data = await readJson(response);
      throw new Error(getErrorMessage(data));
    }
    state.runningJobIds.delete(jobId);
    state.taskStore.delete(jobId);
    state.selectedJobId = null;
    rememberSelectedJob(null);
    returnToInput();
    void loadHistory();
    showToast(
      wasGeneratingImage
        ? "已停止本地等待；远端图片任务可能仍会继续。"
        : "任务已取消，原图和补充文字仍在。",
    );
  } catch (error) {
    elements.cancelButton.disabled = false;
    showToast(error.message || "暂时无法取消，请稍后重试。");
    schedulePoll();
  }
}

async function resumeJob(event) {
  event.preventDefault();
  const answer = elements.clarificationInput.value.trim();
  const jobId = state.selectedJobId;
  if (!answer || !jobId) return;

  const button = elements.clarificationForm.querySelector("button");
  elements.clarificationError.hidden = true;
  button.disabled = true;
  try {
    const response = await fetch(`/api/jobs/${jobId}/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer }),
    });
    const data = await readJson(response);
    if ([404, 410].includes(response.status)) {
      state.selectedJobId = null;
      rememberSelectedJob(null);
      showFailure(
        "这个任务已失效。原图和补充文字仍在，请返回后重新提交。",
      );
      return;
    }
    if (!response.ok) throw new Error(getErrorMessage(data));
    state.runningJobIds.add(jobId);
    elements.clarificationForm.hidden = true;
    elements.clarificationInput.value = "";
    button.disabled = false;
    applyJob(data);
    schedulePoll();
  } catch (error) {
    button.disabled = false;
    elements.clarificationError.textContent =
      error.message || "补充信息提交失败，请检查后重试。";
    elements.clarificationError.hidden = false;
  }
}

async function generateImage() {
  const jobId = state.selectedJobId;
  if (!jobId || state.runningJobIds.has(jobId)) return;

  elements.generateImageButton.disabled = true;
  elements.generateImageButton.textContent = "正在提交 4 张";
  setInputLocked(true);
  updateSubmitState();
  try {
    const response = await fetch(`/api/jobs/${jobId}/image`, {
      method: "POST",
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(getErrorMessage(data));
    state.runningJobIds.add(jobId);
    applyJob(data);
    activateResultTab("image");
    schedulePoll();
    scheduleStallNotice();
  } catch (error) {
    state.runningJobIds.delete(jobId);
    setInputLocked(true);
    updateSubmitState();
    elements.generateImageButton.disabled = false;
    elements.generateImageButton.textContent = "确认提示词，一次生成 4 张";
    showToast(error.message || "无法开始生成结果图。");
    await loadHistory();
  }
}

async function regeneratePrompt() {
  const jobId = state.selectedJobId;
  if (!jobId || state.runningJobIds.has(jobId)) return;
  if (
    !window.confirm(
      "将重新执行需求识别、创意生成和提示词审查，当前提示词与结果图会被本轮新结果替换。继续吗？",
    )
  ) {
    return;
  }

  elements.regeneratePromptButton.disabled = true;
  elements.regeneratePromptButton.textContent = "正在重新解析";
  prepareResultForProcessing();
  const task = selectedTask();
  if (task) task.resultRendered = false;
  setInputLocked(true);
  updateSubmitState();
  try {
    const response = await fetch(`/api/jobs/${jobId}/prompt/regenerate`, {
      method: "POST",
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(getErrorMessage(data));
    state.runningJobIds.add(jobId);
    applyJob(data);
    schedulePoll();
    scheduleStallNotice();
  } catch (error) {
    state.runningJobIds.delete(jobId);
    setInputLocked(true);
    updateSubmitState();
    elements.regeneratePromptButton.disabled = false;
    elements.regeneratePromptButton.textContent = "重新生成创意和提示词";
    showToast(error.message || "无法重新生成创意和提示词。");
    await loadHistory();
  }
}

async function regenerateImage() {
  const jobId = state.selectedJobId;
  if (!jobId || state.runningJobIds.has(jobId)) return;
  if (
    !window.confirm(
      "将保留当前提示词，创建新的 PixPark 四图任务并替换当前结果图。继续吗？",
    )
  ) {
    return;
  }

  elements.regenerateImageButton.disabled = true;
  elements.regenerateImageButton.textContent = "正在提交新一组";
  const task = selectedTask();
  if (task) task.resultRendered = false;
  setInputLocked(true);
  updateSubmitState();
  try {
    const response = await fetch(`/api/jobs/${jobId}/image/regenerate`, {
      method: "POST",
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(getErrorMessage(data));
    state.runningJobIds.add(jobId);
    applyJob(data);
    activateResultTab("image");
    schedulePoll();
    scheduleStallNotice();
  } catch (error) {
    state.runningJobIds.delete(jobId);
    setInputLocked(true);
    updateSubmitState();
    elements.regenerateImageButton.disabled = false;
    elements.regenerateImageButton.textContent = "重新生成 4 张结果图";
    showToast(error.message || "无法重新生成结果图。");
    await loadHistory();
  }
}

async function resumeImage() {
  const jobId = state.selectedJobId;
  if (!jobId || state.runningJobIds.has(jobId)) return;
  elements.imageResumeButton.disabled = true;
  setInputLocked(true);
  updateSubmitState();
  try {
    const response = await fetch(`/api/jobs/${jobId}/image/resume`, {
      method: "POST",
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(getErrorMessage(data));
    state.runningJobIds.add(jobId);
    applyJob(data);
    schedulePoll();
    scheduleStallNotice();
  } catch (error) {
    state.runningJobIds.delete(jobId);
    setInputLocked(true);
    updateSubmitState();
    elements.imageResumeButton.disabled = false;
    showToast(error.message || "无法继续查询结果图。");
  }
}

function renderResult(result, options = {}) {
  const task = selectedTask();
  const final = options.final !== false;
  const recoveredImageOnly = Boolean(result.recovered_image_only);
  const promptReady = Boolean(options.promptReady);
  if (final) document.body.dataset.mode = "complete";
  if (final) setSubmitLabel("开始解析");
  elements.resultStation.hidden = false;
  elements.resultTitle.textContent = recoveredImageOnly
    ? "已恢复结果图任务"
    : promptReady
      ? "提示词待确认"
      : final
        ? "任务结果"
        : "正在生成 4 张结果图";
  elements.reviewContext.hidden = recoveredImageOnly || !state.previewUrl;
  elements.sourceReviewName.textContent =
    task?.filename || state.selectedFile?.name || "当前需求图";
  if (state.previewUrl) {
    const sourceThumb = document.createElement("img");
    sourceThumb.src = state.previewUrl;
    sourceThumb.alt = "";
    const sourceDialogImage = document.createElement("img");
    sourceDialogImage.src = state.previewUrl;
    sourceDialogImage.alt = "当前任务的原始需求图";
    elements.sourceThumbFrame.replaceChildren(sourceThumb);
    elements.sourceDialogMedia.replaceChildren(sourceDialogImage);
  }
  if (task && !task.resultRendered) task.resultHandled = false;
  const image = result.image || {};
  const generatedUrls = getSafeGeneratedImageUrls(image);
  renderGeneratedImages(generatedUrls, image.alt);
  if (generatedUrls.length) {
    elements.imageEmpty.hidden = true;
    elements.imageResumeButton.hidden = true;
    elements.resultTabImage.textContent = `结果图 · ${generatedUrls.length} 张`;
    elements.imageCaption.textContent =
      `结果图 · ${generatedUrls.length} 张已与当前任务提示词关联`;
  } else {
    elements.imageEmpty.hidden = false;
    renderImageStatus(image);
  }

  const showApproval = final && !recoveredImageOnly;
  elements.promptApproval.hidden = !showApproval;
  elements.regeneratePromptButton.disabled = false;
  elements.regeneratePromptButton.textContent = "重新生成创意和提示词";
  elements.generateImageButton.disabled = false;
  elements.generateImageButton.textContent = "确认提示词，一次生成 4 张";
  if (promptReady && image.status === "ready") {
    elements.generateImageButton.hidden = false;
    elements.promptApprovalText.textContent =
      "不满意可重新走完整解析；确认无误后一次生成 4 张。";
  } else if (promptReady) {
    elements.generateImageButton.hidden = true;
    elements.promptApprovalText.textContent =
      image.message || "当前服务没有可用的结果图生成能力。";
  } else if (showApproval) {
    elements.generateImageButton.hidden = true;
    elements.promptApprovalText.textContent =
      "如果创意或提示词不满意，可保留原图与补充要求，重新走完整解析和审查。";
  }
  const canRegenerateImage =
    final &&
    !recoveredImageOnly &&
    generatedUrls.length > 0 &&
    !image.resumable;
  elements.imageRegeneration.hidden = !canRegenerateImage;
  elements.imageResult.classList.toggle(
    "has-regeneration",
    canRegenerateImage,
  );
  elements.regenerateImageButton.disabled = false;
  elements.regenerateImageButton.textContent = "重新生成 4 张结果图";

  elements.resultTabs.forEach((tab) => {
    tab.hidden = recoveredImageOnly && tab.dataset.resultTab !== "image";
  });
  elements.positivePrompt.textContent = result.positive_prompt || "未提取到正向提示词。";
  elements.negativePrompt.textContent = result.negative_prompt || "未提取到负面提示词。";
  elements.auditSummary.textContent =
    result.repair_attempts > 0
      ? `经过 ${result.repair_attempts} 次自动修正后，结构规则已通过；内容仍需人工核对。`
      : "已检查图号、复制区、背景硬句和内部字段；内容仍需人工核对。";

  renderDetails(result.sections || {});
  elements.promptResults.hidden = false;
  elements.resultActions.hidden = !final;
  elements.reviseTaskButton.hidden = recoveredImageOnly;
  elements.reviseTaskButton.disabled = false;
  elements.downloadButton.hidden = recoveredImageOnly;
  elements.resultSubtitle.textContent =
    recoveredImageOnly
      ? "仅恢复到旧版远端图片任务；新的完整任务会在临时保留期内恢复需求图和提示词。"
      : promptReady
        ? "结构规则检查已通过；先看提示词，确认满意后一次生成 4 张。"
        : final
          ? `提示词与 ${generatedUrls.length || 0} 张结果图已经关联；可继续查看或复制。`
          : "提示词已经锁定；正在生成关联的 4 张结果图，不会重新解析需求。";
  elements.resultStation.classList.add("complete");
  if (!task?.resultRendered) {
    activateResultTab(
      task?.activeTab ||
        options.preferredTab ||
        (recoveredImageOnly || generatedUrls.length ? "image" : "positive"),
    );
    if (task) task.resultRendered = true;
  }
  if (final) elements.resultTitle.focus({ preventScroll: true });
}

function renderImageStatus(image) {
  const status = image.status || "disabled";
  const labels = {
    ready: [
      "等待确认提示词",
      image.message || "请先查看正向提示词，确认满意后一次生成 4 张结果图。",
    ],
    queued: ["等待生成 4 张结果图", "提示词已通过审查，正在等待 PixPark 四图队列。"],
    uploading: ["正在上传参考图", image.message || "正在分别上传图1和固定图2。"],
    creating: ["正在创建四图任务", image.message || "正在创建唯一的 PixPark v3 四图任务。"],
    polling: ["PixPark 正在生成 4 张", image.message || "正在查询同一个远端四图任务。"],
    downloading: ["结果已通过审核", image.message || "正在安全下载审核通过的结果图。"],
    partial: ["已返回部分结果", image.message || "已保留审核通过的结果图。"],
    timeout: ["结果图仍在生成", image.message || "可稍后继续查询同一个远端任务。"],
    rejected: ["结果图未通过服务审核", image.message || "提示词结果不受影响。"],
    failed: ["结果图生成失败", image.message || "提示词结果不受影响。"],
    unavailable: ["PixPark 尚未配置", image.message || "提示词仍可正常使用。"],
    incompatible_aspect_ratio: [
      "当前画幅暂不自动生图",
      image.message || "当前接口固定为 1:1，已保留提示词结果。",
    ],
    disabled: ["结果图生成未启用", image.message || "提示词仍可正常使用。"],
  };
  const [title, text] = labels[status] || [
    "结果图状态未知",
    image.message || "请稍后重新检查任务。",
  ];
  elements.imageEmptyTitle.textContent = title;
  elements.imageEmptyText.textContent = text;
  elements.imageResumeButton.hidden = !image.resumable;
  elements.imageResumeButton.disabled = false;
  elements.imageCaption.textContent = "结果图 · 当前任务状态";
  elements.resultTabImage.textContent =
    ["completed", "partial"].includes(status) ? "结果图 · 已完成" : "结果图";
}

function getSafeGeneratedImageUrls(image) {
  const candidates = [
    ...(Array.isArray(image?.urls) ? image.urls : []),
    image?.url,
  ];
  return [
    ...new Set(
      candidates.filter((value) => isSafeGeneratedImageUrl(value)),
    ),
  ];
}

function renderGeneratedImages(urls, alt) {
  elements.generatedImageGrid.replaceChildren();
  elements.generatedImageGrid.hidden = !urls.length;
  elements.generatedImageGrid.dataset.count = String(urls.length);
  elements.imageResult.classList.toggle("has-images", Boolean(urls.length));
  document.querySelector("#generatedImage")?.remove();
  if (!urls.length) return;

  urls.forEach((url, index) => {
    const button = document.createElement("button");
    const image = document.createElement("img");
    const label = document.createElement("span");
    button.className = "generated-image-tile";
    button.type = "button";
    button.setAttribute("aria-label", `在当前页面查看第 ${index + 1} 张结果图`);
    button.addEventListener("click", () => {
      openResultImagePreview(urls, index, alt);
    });
    image.src = url;
    image.alt = `${alt || "3D 建模参考结果图"} · 方案 ${index + 1}`;
    image.loading = "lazy";
    label.className = "generated-image-index";
    label.textContent = `方案 ${index + 1}`;
    button.append(image, label);
    elements.generatedImageGrid.append(button);
  });
}

function openResultImagePreview(urls, index, alt) {
  if (!urls.length || typeof elements.resultImageDialog.showModal !== "function") {
    return;
  }
  state.resultPreviewUrls = [...urls];
  state.resultPreviewIndex = Math.max(0, Math.min(index, urls.length - 1));
  state.resultPreviewAlt = alt || "3D 建模参考结果图";
  updateResultImagePreview();
  elements.resultImageDialog.showModal();
}

function stepResultImagePreview(delta) {
  const total = state.resultPreviewUrls.length;
  if (total < 2) return;
  state.resultPreviewIndex = (state.resultPreviewIndex + delta + total) % total;
  updateResultImagePreview();
}

function updateResultImagePreview() {
  const total = state.resultPreviewUrls.length;
  const index = state.resultPreviewIndex;
  const url = state.resultPreviewUrls[index];
  if (!url || !isSafeGeneratedImageUrl(url)) return;
  const image = document.createElement("img");
  image.src = url;
  image.alt = `${state.resultPreviewAlt} · 方案 ${index + 1}`;
  elements.resultImageDialogMedia.replaceChildren(image);
  elements.resultImageDialogCount.textContent = `方案 ${index + 1} / ${total}`;
  elements.resultImageDownload.href = url;
  elements.resultImageDownload.download = `皓月3D结果图-方案${index + 1}.png`;
  const singleImage = total < 2;
  elements.resultImagePreviousButton.disabled = singleImage;
  elements.resultImageNextButton.disabled = singleImage;
}

function isSafeGeneratedImageUrl(value) {
  if (!value) return false;
  try {
    const url = new URL(value, window.location.origin);
    return (
      url.origin === window.location.origin &&
      url.pathname.startsWith("/generated/")
    );
  } catch {
    return false;
  }
}

function activateResultTab(name, options = {}) {
  elements.resultTabs.forEach((tab) => {
    const active = tab.dataset.resultTab === name;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  elements.resultPanels.forEach((panel) => {
    panel.hidden = panel.dataset.resultPanel !== name;
  });
  const task = selectedTask();
  if (task && options.persist !== false) {
    task.activeTab = name;
    persistTaskUiState(task.id, { activeTab: name });
  }
}

function renderDetails(sections) {
  const hiddenTitles = new Set([
    "纯净生图提示词复制区",
    "纯净负面提示词复制区",
  ]);
  elements.detailList.replaceChildren();

  for (const [title, content] of Object.entries(sections)) {
    if (hiddenTitles.has(title) || !content.trim()) continue;
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const body = document.createElement("pre");
    summary.textContent = title;
    body.className = "detail-content";
    body.textContent = content;
    details.append(summary, body);
    elements.detailList.append(details);
  }
}

function returnToInput() {
  clearStallTimer();
  state.selectedJobId = null;
  rememberSelectedJob(null);
  elements.errorState.hidden = true;
  elements.processStation.hidden = true;
  elements.cancelButton.hidden = true;
  elements.resultStation.hidden = false;
  document.body.dataset.mode = "idle";
  elements.intakeSummary.textContent =
    "上传包含主画面、批注、箭头和局部参考的完整图片。";
  setInputLocked(false);
  resetResultPlaceholder();
  updateSubmitState();
  schedulePoll();
  elements.dropzone.focus({ preventScroll: true });
}

function handleFailureAction() {
  if (
    elements.retryButton.dataset.action === "poll" &&
    state.selectedJobId &&
    state.runningJobIds.has(state.selectedJobId)
  ) {
    elements.errorState.hidden = true;
    elements.workingIndicator.hidden = false;
    elements.processTitle.textContent = "重新检查任务";
    elements.processMessage.textContent = "正在读取后台任务的最新状态。";
    schedulePoll();
    return;
  }
  returnToInput();
}

function requestNewTask() {
  if (state.pendingDraft) {
    resetTask({ preserveBackground: true, restorePendingDraft: true });
    showToast("已返回未提交的任务草稿。");
    return;
  }
  if (
    selectedTask()?.result &&
    !selectedTask()?.resultHandled &&
    !window.confirm("当前结果尚未复制或下载。确定开始新任务吗？")
  ) {
    return;
  }
  resetTask();
}

function beginRevision() {
  const jobId = state.selectedJobId;
  const task = selectedTask();
  if (!jobId || !task || state.runningJobIds.has(jobId)) return;
  const previewUrl = task.previewUrl || task.source_image_url || state.previewUrl;
  if (!previewUrl) {
    showToast("原任务需求图已经不可用，请新建任务并重新上传图片。");
    return;
  }

  state.revisionSourceJobId = jobId;
  state.revisionSourceFilename = task.filename || "原任务需求图";
  state.selectedJobId = null;
  rememberSelectedJob(null);
  state.selectedFile = null;
  state.previewUrl = previewUrl;
  elements.imageInput.value = "";
  elements.fileName.textContent = state.revisionSourceFilename;
  elements.fileSize.textContent = "沿用原图，可重新选择替换";
  elements.revisionTitle.textContent =
    `修改任务 #${jobId.slice(0, 8).toUpperCase()}`;
  elements.revisionHint.textContent =
    "补充要求可以继续编辑；重新选择图片会把它作为新版图1。";
  elements.revisionContext.hidden = false;
  elements.reviseTaskButton.hidden = true;
  elements.intakeSummary.textContent =
    "正在建立修改版本；旧任务和旧结果会继续保留。";
  elements.processStation.hidden = true;
  document.body.dataset.mode = "revision";
  setInputLocked(false);
  setSubmitLabel("提交修改");
  updateSubmitState();
  renderHistory(state.historyItems);
  elements.noteInput.focus({ preventScroll: true });
}

function cancelRevision() {
  const sourceJobId = state.revisionSourceJobId;
  if (!sourceJobId) return;
  clearDraftSource();
  clearRevisionMode();
  void openHistoryJob(sourceJobId);
}

function clearRevisionMode(options = {}) {
  state.revisionSourceJobId = null;
  state.revisionSourceFilename = "";
  elements.revisionContext.hidden = true;
  elements.reviseTaskButton.hidden = false;
  elements.reviseTaskButton.disabled = false;
  if (!options.preserveLabel) setSubmitLabel("开始解析");
}

function startNewDraft() {
  if (!state.selectedJobId) {
    requestNewTask();
    return;
  }
  if (state.submitting) {
    showToast("正在建立任务，请稍候一秒再另起任务。");
    return;
  }
  const context = state.taskStore.get(state.selectedJobId);
  const filename = context?.filename || "当前任务";
  const hasDraft = Boolean(state.pendingDraft);
  resetTask({ preserveBackground: true, restorePendingDraft: hasDraft });
  showToast(
    hasDraft
      ? `${filename} 继续在后台；已恢复未提交草稿。`
      : `${filename} 已转入后台，可从历史记录切回。`,
  );
}

function resetTask(options = {}) {
  clearStallTimer();
  state.selectedJobId = null;
  rememberSelectedJob(null);
  if (!state.runningJobIds.size) forgetImageTask();
  clearRevisionMode({ preserveLabel: true });
  clearDraftSource();
  elements.uploadForm.reset();
  elements.noteCount.value = "0 / 1000";
  elements.dropzone.classList.remove("has-file");
  elements.dropzoneEmpty.hidden = false;
  elements.dropzonePreview.hidden = true;
  elements.previewMedia.replaceChildren();
  setUploadError("");
  elements.processStation.hidden = true;
  elements.promptResults.hidden = false;
  elements.resultStation.hidden = false;
  elements.resultActions.hidden = true;
  elements.reviewContext.hidden = true;
  elements.sourceThumbFrame.replaceChildren();
  elements.sourceDialogMedia.replaceChildren();
  elements.resultStation.classList.remove("complete");
  elements.imageEmpty.hidden = false;
  elements.generatedImageGrid.hidden = true;
  elements.generatedImageGrid.replaceChildren();
  elements.generatedImageGrid.dataset.count = "0";
  elements.imageResult.classList.remove("has-images");
  elements.imageResult.classList.remove("has-regeneration");
  document.querySelector("#generatedImage")?.remove();
  elements.imageResumeButton.hidden = true;
  elements.imageResumeButton.disabled = false;
  elements.promptApproval.hidden = true;
  elements.imageRegeneration.hidden = true;
  elements.regeneratePromptButton.disabled = false;
  elements.regenerateImageButton.disabled = false;
  elements.generateImageButton.hidden = false;
  elements.generateImageButton.disabled = false;
  elements.generateImageButton.textContent = "确认提示词，一次生成 4 张";
  elements.imageEmptyTitle.textContent = "结果图状态";
  elements.imageEmptyText.textContent =
    "提交后将在这里显示生成进度或最终图片。";
  elements.resultTitle.textContent = "任务输出";
  elements.resultSubtitle.textContent =
    "解析后先核对提示词，确认满意再生成关联结果图。";
  elements.resultTabImage.textContent = "结果图";
  elements.resultTabs.forEach((tab) => {
    tab.hidden = false;
  });
  elements.downloadButton.hidden = false;
  elements.intakeSummary.textContent =
    "上传包含主画面、批注、箭头和局部参考的完整图片。";
  document.body.dataset.mode = "idle";
  resetResultPlaceholder();
  setInputLocked(false);
  if (options.restorePendingDraft) restorePendingDraft();
  updateSubmitState();
  schedulePoll();
  elements.dropzone.focus({ preventScroll: true });
  if (!options.preserveBackground) {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

function setInputLocked(locked) {
  elements.imageInput.disabled = locked;
  elements.dropzone.disabled = locked;
  elements.noteInput.disabled = locked;
  elements.enrichmentInput.disabled = locked;
  elements.configTrigger.disabled = state.submitting || state.runningJobIds.size > 0;
}

function setSubmitLabel(label) {
  const labelElement = elements.submitButton.querySelector("span");
  if (labelElement) labelElement.textContent = label;
}

function prepareResultForProcessing() {
  elements.resultStation.hidden = false;
  elements.resultStation.classList.remove("complete");
  elements.resultTitle.textContent = "正在解析需求图";
  elements.resultSubtitle.textContent =
    "原图和补充要求保留在左侧；通过审查的提示词会直接出现在这里。";
  elements.resultActions.hidden = true;
  elements.reviewContext.hidden = true;
  elements.promptApproval.hidden = true;
  elements.imageRegeneration.hidden = true;
  elements.imageResult.classList.remove("has-regeneration");
  elements.promptResults.hidden = false;
  elements.positivePrompt.textContent =
    "正在读取批注、箭头、文字和布局权限，请稍候…";
  elements.negativePrompt.textContent = "";
  elements.detailList.replaceChildren();
  elements.resultTabs.forEach((tab) => {
    tab.hidden = tab.dataset.resultTab !== "positive";
  });
  activateResultTab("positive", { persist: false });
}

function resetResultPlaceholder() {
  elements.processStation.hidden = true;
  elements.resultStation.hidden = false;
  elements.resultStation.classList.remove("complete");
  elements.resultTitle.textContent = "任务输出";
  elements.resultSubtitle.textContent =
    "解析后先核对提示词，确认满意再生成关联结果图。";
  elements.resultActions.hidden = true;
  elements.reviewContext.hidden = true;
  elements.promptApproval.hidden = true;
  elements.imageRegeneration.hidden = true;
  elements.imageResult.classList.remove("has-regeneration");
  elements.promptResults.hidden = false;
  elements.positivePrompt.textContent =
    "解析完成后，正向提示词会先出现在这里。";
  elements.negativePrompt.textContent = "";
  elements.detailList.replaceChildren();
  elements.resultTabs.forEach((tab) => {
    tab.hidden = false;
  });
  setSubmitLabel("开始解析");
  activateResultTab("positive", { persist: false });
}

function resetProcessMessages() {
  elements.clarificationForm.hidden = true;
  elements.clarificationError.hidden = true;
  elements.errorState.hidden = true;
  elements.workingIndicator.hidden = false;
}

async function copyText(text, button) {
  if (!text.trim()) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }

  const original = button.lastChild.textContent;
  const task = selectedTask();
  if (task) task.resultHandled = true;
  button.lastChild.textContent = " 已复制";
  showToast("已复制到剪贴板");
  window.setTimeout(() => {
    button.lastChild.textContent = original;
  }, 1300);
}

function downloadResult() {
  const task = selectedTask();
  if (!task?.result?.markdown) return;
  task.resultHandled = true;
  const blob = new Blob([task.result.markdown], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `皓月3D需求解析-${new Date().toISOString().slice(0, 10)}.md`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.classList.remove("visible");
  }, 2200);
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

function getErrorMessage(data) {
  if (typeof data.detail === "string") return data.detail.slice(0, 240);
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => item.msg || String(item))
      .join("；")
      .slice(0, 240);
  }
  return "请求没有成功，请稍后重试。";
}
