const STORAGE_KEY = "commercial-insight-founder-jobs-v1";
const state = { files: [], extractedText: [], currentBrief: null, currentView: "inbox", jobs: loadJobs(), service: null, lastArtifact: null };

const elements = {
  request: document.querySelector("#requestInput"),
  url: document.querySelector("#urlInput"),
  privacy: document.querySelector("#privacyInput"),
  audience: document.querySelector("#audienceInput"),
  deliverable: document.querySelector("#deliverableInput"),
  constraints: document.querySelector("#constraintsInput"),
  fileInput: document.querySelector("#fileInput"),
  fileList: document.querySelector("#fileList"),
  dropZone: document.querySelector("#dropZone"),
  briefSection: document.querySelector("#briefSection"),
  stateBadge: document.querySelector("#stateBadge"),
  budgetBadge: document.querySelector("#budgetBadge"),
  tokenEstimate: document.querySelector("#tokenEstimate"),
  retrievalEstimate: document.querySelector("#retrievalEstimate"),
  evidenceSources: document.querySelector("#evidenceSources"),
  recentJobs: document.querySelector("#recentJobs"),
  recentHeading: document.querySelector("#recentHeading"),
  jobCount: document.querySelector("#jobCount"),
  activeCount: document.querySelector("#activeCount"),
  workspaceTitle: document.querySelector("#workspaceTitle"),
  toast: document.querySelector("#toast"),
  briefGoal: document.querySelector("#briefGoal"),
  briefAudience: document.querySelector("#briefAudience"),
  briefDeliverable: document.querySelector("#briefDeliverable"),
  briefInputs: document.querySelector("#briefInputs"),
  briefConstraints: document.querySelector("#briefConstraints"),
  briefAssumptions: document.querySelector("#briefAssumptions"),
  briefQueries: document.querySelector("#briefQueries"),
  briefQuestions: document.querySelector("#briefQuestions"),
  generationSection: document.querySelector("#generationSection"),
  provider: document.querySelector("#providerInput"),
  artifactEditor: document.querySelector("#artifactEditor"),
  generationMeta: document.querySelector("#generationMeta"),
  retrievedEvidence: document.querySelector("#retrievedEvidenceList"),
  serviceStatus: document.querySelector("#serviceStatus"),
  serviceStatusText: document.querySelector("#serviceStatusText"),
  runButton: document.querySelector("#runButton"),
  revision: document.querySelector("#revisionInput"),
  reviseButton: document.querySelector("#reviseButton"),
  saveArtifactButton: document.querySelector("#saveArtifactButton"),
  approveArtifactButton: document.querySelector("#approveArtifactButton"),
  artifactHistory: document.querySelector("#artifactHistory"),
  signalSection: document.querySelector("#signalSection"),
  signalCount: document.querySelector("#signalCount"),
  signalDate: document.querySelector("#signalDate"),
  signalTotal: document.querySelector("#signalTotal"),
  signalErrors: document.querySelector("#signalErrors"),
  signalSchedule: document.querySelector("#signalSchedule"),
  signalBoundary: document.querySelector("#signalBoundary"),
  signalWatchlist: document.querySelector("#signalWatchlist"),
  signalResults: document.querySelector("#signalResults"),
  signalErrorList: document.querySelector("#signalErrorList"),
  signalResultMeta: document.querySelector("#signalResultMeta"),
  signalSourceType: document.querySelector("#signalSourceType"),
  signalSourceValue: document.querySelector("#signalSourceValue"),
  collectSignalsButton: document.querySelector("#collectSignalsButton"),
  addSignalSourceButton: document.querySelector("#addSignalSourceButton"),
};

const deliverableLabels = {
  short_video_script: "短视频口播稿、标题与分镜建议",
  article_outline: "公众号文章大纲与标题候选",
  material_analysis: "结构化素材拆解卡",
  daily_digest: "行业日报与重点跟进项",
  topic_pool: "带评分的内容选题池",
};

document.querySelector("#generateButton").addEventListener("click", generateBrief);
document.querySelector("#saveButton").addEventListener("click", saveCurrentJob);
document.querySelector("#exportButton").addEventListener("click", exportMarkdown);
elements.runButton.addEventListener("click", runGeneration);
document.querySelector("#regenerateButton").addEventListener("click", runGeneration);
document.querySelector("#downloadArtifactButton").addEventListener("click", downloadArtifact);
elements.reviseButton.addEventListener("click", reviseArtifact);
elements.saveArtifactButton.addEventListener("click", saveArtifactVersion);
elements.approveArtifactButton.addEventListener("click", approveArtifact);
elements.collectSignalsButton.addEventListener("click", collectSignals);
elements.addSignalSourceButton.addEventListener("click", addSignalSource);
document.querySelector("#resetButton").addEventListener("click", () => elements.briefSection.classList.add("hidden"));
document.querySelector("#newJobButton").addEventListener("click", resetWorkspace);
document.querySelectorAll(".nav-item").forEach(button => button.addEventListener("click", () => changeView(button)));
elements.fileInput.addEventListener("change", event => handleFiles([...event.target.files]));

["dragenter", "dragover"].forEach(name => elements.dropZone.addEventListener(name, event => {
  event.preventDefault();
  elements.dropZone.classList.add("dragover");
}));
["dragleave", "drop"].forEach(name => elements.dropZone.addEventListener(name, event => {
  event.preventDefault();
  elements.dropZone.classList.remove("dragover");
}));
elements.dropZone.addEventListener("drop", event => handleFiles([...event.dataTransfer.files]));

[elements.request, elements.url, elements.constraints].forEach(input => input.addEventListener("input", updateContextEstimate));
elements.privacy.addEventListener("change", updatePrivacyState);

function selectedMode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

async function handleFiles(files) {
  state.files = deduplicateFiles([...state.files, ...files]);
  state.extractedText = [];
  for (const file of state.files) {
    if (isReadableText(file) && file.size <= 2_000_000) {
      try {
        const text = await file.text();
        state.extractedText.push({ name: file.name, text: text.slice(0, 12000) });
      } catch (_) {
        state.extractedText.push({ name: file.name, text: "" });
      }
    }
  }
  renderFiles();
  updateContextEstimate();
}

function deduplicateFiles(files) {
  const seen = new Set();
  return files.filter(file => {
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function isReadableText(file) {
  return file.type.startsWith("text/") || /\.(md|txt|json|csv)$/i.test(file.name);
}

function renderFiles() {
  elements.fileList.innerHTML = state.files.map(file => `
    <div class="file-row"><span>${escapeHtml(file.name)}</span><small>${formatBytes(file.size)}</small></div>
  `).join("");
  renderEvidence();
}

function generateBrief() {
  const requestText = elements.request.value.trim();
  const sourceText = state.extractedText.map(item => item.text).join("\n");
  const combinedText = [requestText, sourceText].filter(Boolean).join("\n");
  const url = elements.url.value.trim();

  if (url && !elements.url.checkValidity()) {
    showToast("网页链接格式不正确");
    elements.url.focus();
    return;
  }

  if (!combinedText && !url && state.files.length === 0) {
    showToast("请先输入一段描述、链接或文件");
    elements.request.focus();
    return;
  }

  const mode = selectedMode();
  const audience = elements.audience.value.trim();
  const deliverable = deliverableLabels[elements.deliverable.value];
  const goal = deriveGoal(requestText || sourceText || url, deliverable);
  const constraints = splitItems(elements.constraints.value);
  const inputs = [
    requestText ? "用户任务描述" : null,
    url || null,
    ...state.files.map(file => `${file.name}（${formatBytes(file.size)}）`),
  ].filter(Boolean);
  const querySource = [combinedText, url, ...state.files.map(file => file.name)].filter(Boolean).join("\n");
  const queries = deriveQueries(querySource);
  const questions = [];
  if (!audience) questions.push("这份内容最希望影响谁？");
  if (!deliverable) questions.push("需要输出什么具体产物？");
  // External-model consent is requested only when the user explicitly selects that provider.

  const budget = deriveBudget(combinedText, state.files.length, mode);
  state.currentBrief = {
    id: crypto.randomUUID ? crypto.randomUUID() : `job-${Date.now()}`,
    createdAt: new Date().toISOString(),
    mode,
    state: "brief_review",
    privacy: elements.privacy.value,
    goal,
    audience: audience || "待确认",
    inputs,
    constraints,
    deliverable,
    deliverableType: elements.deliverable.value,
    confirmedDecisions: ["先确认简报，再进行高消耗分析"],
    assumptions: ["真人表达优先，不生成完整 AI 视频", "使用常温、克制、顾问型表达"],
    blockingQuestions: questions.slice(0, 3),
    knowledgeQueries: queries,
    budgetProfile: budget,
  };

  populateBrief(state.currentBrief);
  elements.briefSection.classList.remove("hidden");
  elements.stateBadge.textContent = "简报待确认";
  elements.workspaceTitle.textContent = goal.slice(0, 28);
  elements.retrievalEstimate.textContent = `${Math.min(Math.max(queries.length * 2, 4), 8)} 个知识片段`;
  elements.briefSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function populateBrief(brief) {
  elements.briefGoal.value = brief.goal;
  elements.briefAudience.value = brief.audience;
  elements.briefDeliverable.value = brief.deliverable;
  elements.briefInputs.value = brief.inputs.join("\n");
  elements.briefConstraints.value = brief.constraints.join("\n");
  elements.briefAssumptions.value = brief.assumptions.join("\n");
  elements.briefQueries.value = brief.knowledgeQueries.join("\n");
  elements.briefQuestions.value = brief.blockingQuestions.join("\n") || "无阻塞问题";
  elements.budgetBadge.textContent = { light: "轻量预算", standard: "标准预算", deep: "深度预算" }[brief.budgetProfile];
}

function readEditedBrief() {
  if (!state.currentBrief) return null;
  return {
    ...state.currentBrief,
    goal: elements.briefGoal.value.trim(),
    audience: elements.briefAudience.value.trim(),
    deliverable: elements.briefDeliverable.value.trim(),
    inputs: splitLines(elements.briefInputs.value),
    constraints: splitLines(elements.briefConstraints.value),
    assumptions: splitLines(elements.briefAssumptions.value),
    knowledgeQueries: splitLines(elements.briefQueries.value),
    blockingQuestions: elements.briefQuestions.value.trim() === "无阻塞问题" ? [] : splitLines(elements.briefQuestions.value).slice(0, 3),
  };
}

function saveCurrentJob() {
  const brief = readEditedBrief();
  if (!brief) return;
  const existingIndex = state.jobs.findIndex(job => job.id === brief.id);
  const saved = { ...brief, state: brief.blockingQuestions.length ? "needs_input" : "ready", updatedAt: new Date().toISOString() };
  if (existingIndex >= 0) state.jobs[existingIndex] = saved;
  else state.jobs.unshift(saved);
  state.currentBrief = saved;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.jobs.slice(0, 50)));
  elements.stateBadge.textContent = saved.state === "ready" ? "可开始分析" : "需要补充信息";
  renderJobs();
  showToast("任务已保存在当前浏览器");
}

function exportMarkdown() {
  const brief = readEditedBrief();
  if (!brief) return;
  const markdown = `---\ntype: task-brief\nmode: ${brief.mode}\nprivacy: ${brief.privacy}\nbudget_profile: ${brief.budgetProfile}\ncreated_at: ${brief.createdAt}\n---\n\n# ${brief.goal}\n\n## 目标受众\n\n${brief.audience}\n\n## 产物\n\n${brief.deliverable}\n\n## 输入来源\n\n${asMarkdownList(brief.inputs)}\n\n## 约束条件\n\n${asMarkdownList(brief.constraints)}\n\n## 工作假设\n\n${asMarkdownList(brief.assumptions)}\n\n## 知识库检索词\n\n${asMarkdownList(brief.knowledgeQueries)}\n\n## 待确认问题\n\n${asMarkdownList(brief.blockingQuestions.length ? brief.blockingQuestions : ["无"])}\n`;
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${safeFileName(brief.goal)}.md`;
  link.click();
  URL.revokeObjectURL(link.href);
  persistExportedBrief(brief);
  showToast("Markdown 简报已导出");
}

function renderJobs() {
  elements.jobCount.textContent = state.jobs.length;
  elements.activeCount.textContent = state.jobs.filter(job => !["exported", "archived"].includes(job.state)).length;
  const visibleJobs = filterJobs(state.jobs, state.currentView);
  const viewLabels = {
    inbox: "最近任务",
    active: "进行中",
    drafts: "内容草稿",
    signals: "信号雷达",
    knowledge: "知识库状态",
    exports: "导出记录",
  };
  elements.recentHeading.textContent = viewLabels[state.currentView];
  if (!visibleJobs.length) {
    const copy = state.currentView === "knowledge"
      ? "知识素材由本地 Obsidian Vault 管理"
      : state.currentView === "signals" ? "观察名单与采集结果显示在主工作区"
      : "当前视图还没有任务";
    elements.recentJobs.innerHTML = `<p class="empty-copy">${copy}</p>`;
    return;
  }
  elements.recentJobs.innerHTML = visibleJobs.slice(0, 8).map(job => `
    <button class="recent-job" type="button" data-job-id="${job.id}">
      <strong>${escapeHtml(job.goal)}</strong>
      <span>${formatDate(job.updatedAt || job.createdAt)} · ${stateLabel(job.state)}</span>
    </button>
  `).join("");
  elements.recentJobs.querySelectorAll("[data-job-id]").forEach(button => button.addEventListener("click", () => loadJob(button.dataset.jobId)));
}

function changeView(button) {
  state.currentView = button.dataset.view;
  document.querySelectorAll(".nav-item").forEach(item => {
    const active = item === button;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  const signalView = state.currentView === "signals";
  elements.signalSection.classList.toggle("hidden", !signalView);
  document.querySelector(".stepper").classList.toggle("hidden", signalView);
  elements.request.closest(".input-section").classList.toggle("hidden", signalView);
  if (signalView) {
    elements.briefSection.classList.add("hidden");
    elements.generationSection.classList.add("hidden");
    elements.workspaceTitle.textContent = "公开信号雷达";
    elements.stateBadge.textContent = "公开来源";
    loadSignalRadar();
  } else {
    if (state.currentBrief) elements.briefSection.classList.remove("hidden");
    if (state.lastArtifact) elements.generationSection.classList.remove("hidden");
    elements.workspaceTitle.textContent = state.currentBrief ? state.currentBrief.goal.slice(0, 28) : "整理新素材";
    elements.stateBadge.textContent = state.currentBrief ? stateLabel(state.currentBrief.state) : "待输入";
  }
  renderJobs();
}

function filterJobs(jobs, view) {
  if (view === "active") return jobs.filter(job => !["exported", "archived"].includes(job.state));
  if (view === "drafts") return jobs.filter(job => ["brief_review", "ready", "needs_input", "generated"].includes(job.state));
  if (view === "exports") return jobs.filter(job => job.state === "exported");
  if (["knowledge", "signals"].includes(view)) return [];
  return jobs;
}

function persistExportedBrief(brief) {
  const exported = { ...brief, state: "exported", updatedAt: new Date().toISOString() };
  const existingIndex = state.jobs.findIndex(job => job.id === exported.id);
  if (existingIndex >= 0) state.jobs[existingIndex] = exported;
  else state.jobs.unshift(exported);
  state.currentBrief = exported;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.jobs.slice(0, 50)));
  elements.stateBadge.textContent = "已导出";
  renderJobs();
}

function loadJob(jobId) {
  const job = state.jobs.find(item => item.id === jobId);
  if (!job) return;
  state.currentBrief = job;
  populateBrief(job);
  elements.briefSection.classList.remove("hidden");
  elements.workspaceTitle.textContent = job.goal.slice(0, 28);
  elements.stateBadge.textContent = stateLabel(job.state);
  elements.privacy.value = job.privacy;
  updatePrivacyState();
  elements.generationSection.classList.remove("hidden");
  loadArtifactHistory(job.id, true);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function resetWorkspace() {
  state.files = [];
  state.extractedText = [];
  state.currentBrief = null;
  elements.request.value = "";
  elements.url.value = "";
  elements.fileInput.value = "";
  elements.briefSection.classList.add("hidden");
  elements.generationSection.classList.add("hidden");
  elements.artifactEditor.value = "";
  elements.revision.value = "";
  elements.artifactHistory.innerHTML = '<p class="empty-copy">尚无版本</p>';
  state.lastArtifact = null;
  elements.fileList.innerHTML = "";
  elements.workspaceTitle.textContent = "整理新素材";
  elements.stateBadge.textContent = "待输入";
  elements.retrievalEstimate.textContent = "未生成";
  renderEvidence();
  updateContextEstimate();
  elements.request.focus();
}

async function checkService() {
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    if (!response.ok) throw new Error("服务不可用");
    state.service = await response.json();
    elements.serviceStatus.className = "local-status connected";
    elements.serviceStatusText.textContent = `本地服务 · ${state.service.knowledge.notes} 条笔记`;
    elements.generationMeta.textContent = state.service.generation.openaiConfigured
      ? `已连接知识库；自动模式使用 ${state.service.generation.defaultModel}，受限资料保持本地。`
      : "已连接知识库；未配置模型时自动使用本地证据模式。";
  } catch (_) {
    state.service = null;
    elements.serviceStatus.className = "local-status disconnected";
    elements.serviceStatusText.textContent = "离线页面";
  }
}

async function runGeneration() {
  const brief = readEditedBrief();
  if (!brief) return;
  if (!state.service) {
    showToast("请通过本地服务地址打开工作台");
    return;
  }
  if (brief.blockingQuestions.length) {
    showToast("请先处理简报中的待确认问题");
    elements.briefQuestions.focus();
    return;
  }
  const allowExternalModel = brief.privacy === "restricted" && elements.provider.value === "openai"
    ? window.confirm("这会把受限 Brief 和检索证据片段发送给外部模型，确认继续吗？")
    : false;
  if (brief.privacy === "restricted" && elements.provider.value === "openai" && !allowExternalModel) return;

  setGenerationBusy(true);
  elements.generationSection.classList.remove("hidden");
  elements.artifactEditor.value = "正在检索知识库并生成工作稿…";
  elements.generationSection.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const materialExcerpts = state.extractedText
      .filter(item => item.text)
      .slice(0, 6)
      .map(item => ({ name: item.name, text: item.text.slice(0, 12000) }));
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief: { ...brief, materialExcerpts }, provider: elements.provider.value, allowExternalModel, topK: 8 }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "生成失败");
    state.currentBrief = { ...brief, state: "generated" };
    state.lastArtifact = payload.result;
    elements.artifactEditor.value = payload.result.markdown;
    const mode = payload.result.provider === "openai" ? payload.result.model : "本地证据模式";
    elements.generationMeta.textContent = `已生成 · ${mode} · 本地版本：${payload.result.artifact_path}`;
    renderRetrievedEvidence(payload.evidence);
    elements.stateBadge.textContent = "待人工审核";
    persistGeneratedJob(state.currentBrief);
    await loadArtifactHistory(brief.id);
    showToast(`已生成并保存 ${payload.evidence.length} 条证据`);
  } catch (error) {
    elements.artifactEditor.value = "";
    elements.generationMeta.textContent = error.message;
    showToast(error.message);
  } finally {
    setGenerationBusy(false);
  }
}

function setGenerationBusy(busy) {
  elements.runButton.disabled = busy;
  document.querySelector("#regenerateButton").disabled = busy;
  elements.reviseButton.disabled = busy;
  elements.saveArtifactButton.disabled = busy;
  elements.approveArtifactButton.disabled = busy;
  elements.serviceStatus.className = `local-status ${busy ? "busy" : "connected"}`;
  if (busy) elements.serviceStatusText.textContent = "正在生成";
  else if (state.service) elements.serviceStatusText.textContent = `本地服务 · ${state.service.knowledge.notes} 条笔记`;
}

async function saveArtifactVersion() {
  const brief = readEditedBrief();
  const markdown = elements.artifactEditor.value.trim();
  if (!brief || !markdown) {
    showToast("当前没有可保存的工作稿");
    return;
  }
  await submitArtifactAction("/api/artifacts/save", { brief, markdown }, "正在保存版本", payload => {
    state.lastArtifact = payload.result;
    elements.generationMeta.textContent = `人工修改已保存 · ${payload.result.artifact_path}`;
    renderArtifactHistory(payload.artifacts);
    showToast("当前修改已保存为新版本");
  });
}

async function reviseArtifact() {
  const brief = readEditedBrief();
  const markdown = elements.artifactEditor.value.trim();
  const instruction = elements.revision.value.trim();
  if (!brief || !markdown || !instruction) {
    showToast("请填写具体修改要求");
    elements.revision.focus();
    return;
  }
  const allowExternalModel = brief.privacy === "restricted"
    ? window.confirm("本轮修改会把受限工作稿发送给外部模型，确认继续吗？")
    : false;
  if (brief.privacy === "restricted" && !allowExternalModel) return;
  await submitArtifactAction(
    "/api/artifacts/revise",
    { brief, markdown, instruction, allowExternalModel },
    "正在按要求修改",
    payload => {
      state.lastArtifact = payload.result;
      elements.artifactEditor.value = payload.result.markdown;
      elements.revision.value = "";
      elements.generationMeta.textContent = `修改完成 · ${payload.result.model} · ${payload.result.artifact_path}`;
      renderArtifactHistory(payload.artifacts);
      showToast("已生成新的修改版本");
    },
  );
}

async function approveArtifact() {
  const brief = readEditedBrief();
  const markdown = elements.artifactEditor.value.trim();
  if (!brief || !markdown) {
    showToast("当前没有可审核的工作稿");
    return;
  }
  if (!window.confirm("确认当前事实、引用和表达已人工核验，并写入 Obsidian 40_Content？")) return;
  await submitArtifactAction("/api/artifacts/approve", { brief, markdown }, "正在写入知识库", payload => {
    state.lastArtifact = payload.result;
    state.currentBrief = { ...brief, state: "approved", vaultPath: payload.vaultPath };
    elements.stateBadge.textContent = "已审核";
    elements.generationMeta.textContent = `已写入 Obsidian · ${payload.vaultPath}`;
    renderArtifactHistory(payload.artifacts);
    persistGeneratedJob(state.currentBrief);
    showToast("审核稿已写入 Obsidian");
  });
}

async function submitArtifactAction(path, body, busyText, onSuccess) {
  if (!state.service) {
    showToast("本地服务未连接");
    return;
  }
  setGenerationBusy(true);
  elements.serviceStatusText.textContent = busyText;
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "操作失败");
    onSuccess(payload);
  } catch (error) {
    showToast(error.message);
  } finally {
    setGenerationBusy(false);
  }
}

async function loadArtifactHistory(jobId, loadLatest = false) {
  if (!state.service || !jobId) return;
  try {
    const response = await fetch(`/api/artifacts?jobId=${encodeURIComponent(jobId)}`, { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "读取版本失败");
    renderArtifactHistory(payload.artifacts);
    if (loadLatest && payload.artifacts.length) selectArtifact(payload.artifacts[0]);
  } catch (error) {
    showToast(error.message);
  }
}

function renderArtifactHistory(artifacts) {
  elements.artifactHistory.innerHTML = artifacts.length ? artifacts.map((artifact, index) => `
    <button class="artifact-version" type="button" data-artifact-index="${index}">
      <strong>v${escapeHtml(artifact.version)} · ${artifact.status === "approved" ? "已审核" : artifact.provider === "human" ? "人工保存" : "生成稿"}</strong>
      <span>${escapeHtml(formatDate(artifact.created_at))}${artifact.revision_instruction ? ` · ${escapeHtml(artifact.revision_instruction.slice(0, 24))}` : ""}</span>
    </button>
  `).join("") : '<p class="empty-copy">尚无版本</p>';
  elements.artifactHistory.querySelectorAll("[data-artifact-index]").forEach(button => {
    button.addEventListener("click", () => selectArtifact(artifacts[Number(button.dataset.artifactIndex)]));
  });
}

function selectArtifact(artifact) {
  elements.artifactEditor.value = artifact.markdown;
  state.lastArtifact = artifact;
  elements.generationMeta.textContent = `已载入 v${artifact.version} · ${artifact.artifact_path}`;
}

async function loadSignalRadar() {
  if (!state.service) {
    showToast("请先通过本地服务地址打开工作台");
    return;
  }
  try {
    const response = await fetch("/api/signals/status", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "读取信号雷达失败");
    renderSignalRadar(payload);
  } catch (error) {
    showToast(error.message);
  }
}

async function collectSignals() {
  if (!state.service) {
    showToast("本地服务未连接");
    return;
  }
  elements.collectSignalsButton.disabled = true;
  elements.collectSignalsButton.textContent = "采集中…";
  elements.signalResultMeta.textContent = "正在访问公开来源、评分去重并写入 Obsidian，请保持页面打开。";
  try {
    const response = await fetch("/api/signals/collect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "采集失败");
    renderSignalRadar(payload);
    elements.signalResultMeta.textContent = `已写入 ${payload.report.note}，知识索引已更新。`;
    showToast(`采集完成：${payload.report.signals} 条有效信号`);
  } catch (error) {
    elements.signalResultMeta.textContent = error.message;
    showToast(error.message);
  } finally {
    elements.collectSignalsButton.disabled = false;
    elements.collectSignalsButton.textContent = "立即采集";
  }
}

async function addSignalSource() {
  const sourceType = elements.signalSourceType.value;
  const value = elements.signalSourceValue.value.trim();
  if (!value) {
    showToast("请输入账号、仓库或公开 URL");
    elements.signalSourceValue.focus();
    return;
  }
  elements.addSignalSourceButton.disabled = true;
  try {
    const response = await fetch("/api/signals/sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sourceType, value }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "添加来源失败");
    elements.signalSourceValue.value = "";
    renderSignalRadar(payload);
    const manualOnly = ["x_account", "facebook_page"].includes(sourceType);
    showToast(manualOnly ? "已加入观察名单；需公开帖子 URL 才能自动采集" : "来源已加入采集配置");
  } catch (error) {
    showToast(error.message);
  } finally {
    elements.addSignalSourceButton.disabled = false;
  }
}

function renderSignalRadar(payload) {
  const latest = payload.latest || {};
  const signals = latest.signals || [];
  const errors = latest.errors || [];
  const configured = payload.configured || {};
  elements.signalDate.textContent = latest.date || "尚未运行";
  elements.signalTotal.textContent = String(latest.signal_count ?? signals.length);
  elements.signalCount.textContent = String(latest.signal_count ?? signals.length);
  elements.signalErrors.textContent = String(errors.length);
  elements.signalSchedule.textContent = payload.scheduleInstalled ? "已安装" : "未安装";
  elements.signalBoundary.textContent = payload.accessBoundary;
  const lines = [
    ["X 观察账号", configured.xAccounts],
    ["GitHub 用户", configured.githubUsers],
    ["GitHub 仓库", configured.githubRepositories],
    ["RSS", configured.feeds],
    ["公开帖子", configured.publicPostUrls],
  ];
  elements.signalWatchlist.innerHTML = lines.map(([label, values]) => `
    <div class="watchlist-line"><strong>${label}：</strong>${values?.length ? escapeHtml(values.slice(0, 8).join("、")) + (values.length > 8 ? ` 等 ${values.length} 个` : "") : "未配置"}</div>
  `).join("");
  elements.signalResults.innerHTML = signals.length ? signals.slice(0, 30).map(signal => `
    <article class="signal-item">
      <div class="signal-item-head">
        <h4>${escapeHtml(signal.title)}</h4>
        <span class="signal-score">${signal.business_value_score} 分</span>
      </div>
      <p>${escapeHtml(signal.summary || signal.raw_excerpt || "无摘要")}</p>
      <div class="signal-meta">${escapeHtml(signal.platform)} · ${escapeHtml(signal.author || signal.company || "未识别")} · ${escapeHtml((signal.categories || []).join(" / ") || "待分类")} · <a href="${escapeHtml(signal.source_url)}" target="_blank" rel="noopener noreferrer">原始链接</a></div>
    </article>
  `).join("") : '<p class="empty-copy">尚无符合阈值的公开信号。可添加 RSS、GitHub 或具体公开帖子 URL 后采集。</p>';
  elements.signalErrorList.innerHTML = errors.length
    ? `<strong>采集异常</strong><br>${errors.slice(0, 12).map(error => escapeHtml(error)).join("<br>")}`
    : "";
}

function renderRetrievedEvidence(evidence) {
  elements.retrievedEvidence.innerHTML = evidence.length ? evidence.map(item => `
    <div class="evidence-item">
      <strong>${escapeHtml(item.title)}</strong>
      <span>${escapeHtml(item.excerpt)}</span>
      <em>${escapeHtml(item.citation)}</em>
    </div>
  `).join("") : '<p class="empty-copy">未命中直接证据，请调整检索词或补充知识库。</p>';
}

function downloadArtifact() {
  const markdown = elements.artifactEditor.value.trim();
  if (!markdown) {
    showToast("当前没有可下载的工作稿");
    return;
  }
  const brief = readEditedBrief() || { goal: "content-draft" };
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${safeFileName(brief.goal)}-内容工作稿.md`;
  link.click();
  URL.revokeObjectURL(link.href);
  showToast("当前工作稿已下载");
}

function persistGeneratedJob(brief) {
  const saved = { ...brief, updatedAt: new Date().toISOString(), artifactPath: state.lastArtifact?.artifact_path };
  const existingIndex = state.jobs.findIndex(job => job.id === saved.id);
  if (existingIndex >= 0) state.jobs[existingIndex] = saved;
  else state.jobs.unshift(saved);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.jobs.slice(0, 50)));
  renderJobs();
}

function renderEvidence() {
  const items = [];
  if (elements.request.value.trim()) items.push({ title: "任务描述", detail: `${elements.request.value.trim().length} 字符` });
  if (elements.url.value.trim()) items.push({ title: "网页链接", detail: elements.url.value.trim() });
  state.files.forEach(file => items.push({ title: file.name, detail: `${file.type || "未知类型"} · ${formatBytes(file.size)}` }));
  elements.evidenceSources.innerHTML = items.length ? items.map(item => `
    <div class="evidence-item"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.detail)}</span></div>
  `).join("") : '<p class="empty-copy">添加文本、链接或文件后显示</p>';
}

function updateContextEstimate() {
  const extracted = state.extractedText.reduce((sum, item) => sum + item.text.length, 0);
  const text = `${elements.request.value}${elements.url.value}${elements.constraints.value}`;
  const estimate = estimateTokens(text) + Math.round(extracted * 0.45);
  elements.tokenEstimate.textContent = `${estimate.toLocaleString()} tokens`;
  renderEvidence();
}

function updatePrivacyState() {
  const restricted = elements.privacy.value === "restricted";
  const riskList = document.querySelector("#riskList");
  riskList.innerHTML = restricted
    ? '<li class="ok">不自动上传素材</li><li>外部模型处理前必须确认</li><li>导出前需要检查脱敏</li>'
    : '<li class="ok">不自动上传素材</li><li class="ok">不自动发布内容</li><li>生成后需人工核验事实</li>';
}

function deriveGoal(text, deliverable) {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!clean) return `基于现有素材生成${deliverable}`;
  const firstSentence = clean.split(/[。！？!?\n]/)[0].trim();
  return firstSentence.length > 80 ? `${firstSentence.slice(0, 80)}…` : firstSentence;
}

function deriveQueries(text) {
  const vocabulary = ["广告效果", "获客成本", "平台流量", "企业号", "本地生活", "电商", "短剧", "漫剧", "商单", "代理商", "归因", "结算", "品牌", "内容生态", "AI 营销", "AI应用", "AI算力", "Agent", "商业化", "软件行业", "生成式AI"];
  const matches = vocabulary.filter(term => text.includes(term));
  const stopWords = new Set(["分析这份报告", "提炼核心观点", "生成自媒体内容", "生成", "报告", "素材", "用户任务描述"]);
  const words = text
    .replace(/【[^】]*】/g, " ")
    .replace(/\.(pdf|md|txt)$/gi, " ")
    .replace(/[，。；：！？、,.!?;:\n（）()\[\]]/g, " ")
    .split(/\s+/)
    .map(word => word.trim())
    .filter(word => word.length >= 2 && word.length <= 16 && !stopWords.has(word));
  return [...new Set([...matches, ...words])].slice(0, 8);
}

function deriveBudget(text, fileCount, mode) {
  if (mode === "capture") return "light";
  if (mode === "decide" || text.length > 6000 || fileCount > 4) return "deep";
  return "standard";
}

function splitItems(value) { return value.split(/[；;\n]/).map(item => item.trim()).filter(Boolean); }
function splitLines(value) { return value.split("\n").map(item => item.trim()).filter(Boolean); }
function asMarkdownList(items) { return items.map(item => `- ${item}`).join("\n"); }
function safeFileName(value) { return value.replace(/[\\/:*?"<>|]/g, "-").slice(0, 60) || "task-brief"; }
function estimateTokens(text) {
  const cjk = (text.match(/[\u3400-\u9fff]/g) || []).length;
  const other = text.replace(/[\u3400-\u9fff\s]/g, "").length;
  return Math.round(cjk * 1.5 + other / 4);
}
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}
function formatDate(value) { return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }
function stateLabel(value) { return ({ brief_review: "简报待确认", ready: "可开始分析", needs_input: "需要补充信息", generated: "待人工审核", approved: "已审核", exported: "已导出", archived: "已归档" })[value] || value; }
function loadJobs() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
  catch (_) { return []; }
}
function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}
function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  window.setTimeout(() => elements.toast.classList.remove("show"), 1800);
}

renderJobs();
updateContextEstimate();
updatePrivacyState();
checkService();
