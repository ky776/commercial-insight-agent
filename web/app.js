const STORAGE_KEY = "commercial-insight-founder-jobs-v1";
const state = { files: [], extractedText: [], currentBrief: null, currentView: "inbox", jobs: loadJobs() };

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
  const queries = deriveQueries(combinedText || url);
  const questions = [];
  if (!audience) questions.push("这份内容最希望影响谁？");
  if (!deliverable) questions.push("需要输出什么具体产物？");
  if (mode === "execute" && elements.privacy.value === "restricted") questions.push("受限资料是否允许发送给外部模型？");

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
    knowledge: "知识库状态",
    exports: "导出记录",
  };
  elements.recentHeading.textContent = viewLabels[state.currentView];
  if (!visibleJobs.length) {
    const copy = state.currentView === "knowledge"
      ? "知识素材由本地 Obsidian Vault 管理"
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
  renderJobs();
}

function filterJobs(jobs, view) {
  if (view === "active") return jobs.filter(job => !["exported", "archived"].includes(job.state));
  if (view === "drafts") return jobs.filter(job => ["brief_review", "ready", "needs_input"].includes(job.state));
  if (view === "exports") return jobs.filter(job => job.state === "exported");
  if (view === "knowledge") return [];
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
  elements.fileList.innerHTML = "";
  elements.workspaceTitle.textContent = "整理新素材";
  elements.stateBadge.textContent = "待输入";
  elements.retrievalEstimate.textContent = "未生成";
  renderEvidence();
  updateContextEstimate();
  elements.request.focus();
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
  const vocabulary = ["广告效果", "获客成本", "平台流量", "企业号", "本地生活", "电商", "短剧", "漫剧", "商单", "代理商", "归因", "结算", "品牌", "内容生态", "AI 营销"];
  const matches = vocabulary.filter(term => text.includes(term));
  const words = text.replace(/[，。；：！？、,.!?;:\n]/g, " ").split(/\s+/).filter(word => word.length >= 2 && word.length <= 12);
  return [...new Set([...matches, ...words.slice(0, 4)])].slice(0, 6);
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
function stateLabel(value) { return ({ brief_review: "简报待确认", ready: "可开始分析", needs_input: "需要补充信息", exported: "已导出", archived: "已归档" })[value] || value; }
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
