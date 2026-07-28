const form = document.querySelector("#workflow-form");
const startButton = document.querySelector("#start-button");
const approveButton = document.querySelector("#approve-button");
const rejectButton = document.querySelector("#reject-button");
const emptyState = document.querySelector("#empty-state");
const reviewContent = document.querySelector("#review-content");
const errorMessage = document.querySelector("#error-message");
const runStatus = document.querySelector("#run-status");
const threadLabel = document.querySelector("#thread-id");
const tokenUsage = document.querySelector("#token-usage");
const claimList = document.querySelector("#claim-list");
const blockedList = document.querySelector("#blocked-list");
const blockedSection = document.querySelector("#blocked-section");
const decisionBar = document.querySelector("#decision-bar");
const downloadButton = document.querySelector("#download-button");
const apiStatus = document.querySelector("#api-status");
const evidenceFiles = document.querySelector("#evidence-files");
const dropZone = document.querySelector("#drop-zone");
const fileList = document.querySelector("#file-list");
const historyList = document.querySelector("#history-list");
const accessToken = document.querySelector("#access-token");
const generatedMaterials = document.querySelector("#generated-materials");
const applicationSummary = document.querySelector("#application-summary");
const coverLetter = document.querySelector("#cover-letter");
const applicationForm = document.querySelector("#application-form");
const applicationBoard = document.querySelector("#application-board");
const applicationFilters = document.querySelector("#application-filters");
let activeThreadId = null;
let activeClaims = [];
let uploadedDocuments = [];
accessToken.value = sessionStorage.getItem("jobpilot-token") || "";
accessToken.addEventListener("change", () => { sessionStorage.setItem("jobpilot-token", accessToken.value); loadHistory(); });
function authHeaders() { return accessToken.value ? { "X-JobPilot-Token": accessToken.value } : {}; }

function setBusy(button, busy, label) {
  button.disabled = busy;
  if (!button.dataset.label) button.dataset.label = button.innerHTML;
  button.innerHTML = busy ? label : button.dataset.label;
}
function showError(message) { errorMessage.textContent = message; errorMessage.classList.remove("hidden"); }
function clearError() { errorMessage.classList.add("hidden"); errorMessage.textContent = ""; }
function escapeHtml(value) { const element = document.createElement("div"); element.textContent = value; return element.innerHTML; }
async function jsonRequest(url, options = {}) {
  const response = await fetch(url, { headers: { "Content-Type": "application/json", ...authHeaders() }, ...options });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Request failed with status ${response.status}.`); }
  if (response.status === 204) return null;
  return response.json();
}
function claimCard(claim, blocked = false, index = -1, editable = false) {
  const evidence = (claim.evidence_ids || []).map((id) => `<span>${escapeHtml(id)}</span>`).join("");
  const reason = claim.review_reason ? `<p class="review-reason">${escapeHtml(claim.review_reason)}</p>` : "";
  const content = editable ? `<textarea class="claim-editor" data-index="${index}" rows="3">${escapeHtml(claim.text)}</textarea><small class="edit-note">Edits are revalidated against the cited evidence before approval.</small>` : `<p>${escapeHtml(claim.text)}</p>`;
  return `<article class="claim-card ${blocked ? "blocked" : ""}"><div class="claim-state">${blocked ? "!" : "OK"}</div><div>${content}${reason}<div class="evidence-tags">${evidence || "<span>No evidence ID</span>"}</div></div></article>`;
}
function renderRun(run) {
  activeThreadId = run.thread_id;
  activeClaims = run.claims || [];
  emptyState.classList.add("hidden"); reviewContent.classList.remove("hidden"); threadLabel.textContent = run.thread_id;
  runStatus.textContent = run.status.replaceAll("_", " "); runStatus.className = `run-status ${run.status}`;
  if (run.token_usage) { const cost = run.token_usage.estimated_cost_usd == null ? "" : ` / $${run.token_usage.estimated_cost_usd.toFixed(5)}`; tokenUsage.textContent = `${run.token_usage.total_tokens} tokens${cost}`; } else tokenUsage.textContent = "Local mode";
  const pending = run.status === "pending_review";
  claimList.innerHTML = activeClaims.map((claim, index) => claimCard(claim, false, index, pending)).join("") || '<div class="claim-card blocked"><p>No exportable claims were produced.</p></div>';
  const blocked = run.blocked_claims || []; blockedList.innerHTML = blocked.map((claim) => claimCard(claim, true)).join(""); blockedSection.classList.toggle("hidden", blocked.length === 0);
  decisionBar.classList.toggle("hidden", !pending); downloadButton.classList.toggle("hidden", run.status !== "completed");
  if (run.status === "completed") downloadButton.href = `/v1/workflows/${run.thread_id}/export`;
  const result = run.result || {};
  const hasMaterials = Boolean(result.application_summary || result.cover_letter);
  generatedMaterials.classList.toggle("hidden", !hasMaterials);
  applicationSummary.textContent = result.application_summary || "";
  coverLetter.textContent = result.cover_letter || "";
}
async function loadHistory() {
  try {
    const runs = await jsonRequest("/v1/workflows?limit=12");
    historyList.innerHTML = runs.length ? runs.map((run) => `<article class="history-card"><button class="history-open" data-id="${run.thread_id}"><span class="history-status ${run.status}">${escapeHtml(run.status.replaceAll("_", " "))}</span><code>${run.thread_id.slice(0, 8)}</code><small>${run.claims.length} claims</small></button><div><button data-action="clone" data-id="${run.thread_id}">Clone</button><button data-action="archive" data-id="${run.thread_id}">Archive</button><button class="danger-link" data-action="delete" data-id="${run.thread_id}">Delete</button></div></article>`).join("") : '<p class="history-empty">No saved workflows yet.</p>';
  } catch (error) { historyList.innerHTML = `<p class="history-empty">${escapeHtml(error.message)}</p>`; }
}
historyList.addEventListener("click", async (event) => {
  const button = event.target.closest("button"); if (!button) return;
  const id = button.dataset.id;
  try {
    if (button.dataset.action === "delete") { await jsonRequest(`/v1/workflows/${id}`, { method: "DELETE" }); if (activeThreadId === id) location.reload(); }
    else if (button.dataset.action === "archive") await jsonRequest(`/v1/workflows/${id}/archive`, { method: "POST", body: JSON.stringify({ archived: true }) });
    else if (button.dataset.action === "clone") renderRun(await jsonRequest(`/v1/workflows/${id}/clone`, { method: "POST" }));
    else renderRun(await jsonRequest(`/v1/workflows/${id}`));
    await loadHistory(); document.querySelector("#workflow").scrollIntoView();
  } catch (error) { showError(error.message); }
});
async function uploadFiles(files) {
  clearError(); uploadedDocuments = []; if (!files.length) return;
  if (files.length > 5) { showError("Select no more than five files."); return; }
  fileList.innerHTML = `<span class="loading">Reading ${files.length} file${files.length === 1 ? "" : "s"}...</span>`;
  const body = new FormData(); files.forEach((file) => body.append("files", file));
  try {
    const response = await fetch("/v1/documents/upload", { method: "POST", headers: authHeaders(), body });
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || `Upload failed with status ${response.status}.`); }
    uploadedDocuments = await response.json();
    fileList.innerHTML = uploadedDocuments.map((doc) => `<span class="file-chip"><b>OK</b>${escapeHtml(doc.source_path)}</span>`).join(""); dropZone.classList.add("has-files");
  } catch (error) { fileList.innerHTML = ""; showError(error.message); }
}
evidenceFiles.addEventListener("change", () => uploadFiles(Array.from(evidenceFiles.files || [])));
["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.add("dragging"); }));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.remove("dragging"); }));
dropZone.addEventListener("drop", (event) => uploadFiles(Array.from(event.dataTransfer.files || [])));
form.addEventListener("submit", async (event) => {
  event.preventDefault(); clearError(); const pastedContent = document.querySelector("#evidence-content").value.trim();
  if (!uploadedDocuments.length && !pastedContent) { showError("Upload a document or paste evidence before continuing."); return; }
  setBusy(startButton, true, "Building evidence map...");
  const documents = uploadedDocuments.length ? uploadedDocuments : [{ source_id: document.querySelector("#source-id").value, source_path: document.querySelector("#source-path").value, content: pastedContent }];
  const payload = { job_description: document.querySelector("#job-description").value, language: document.querySelector("#language").value, documents };
  try { renderRun(await jsonRequest("/v1/workflows", { method: "POST", body: JSON.stringify(payload) })); await loadHistory(); }
  catch (error) { showError(error.message); }
  finally { setBusy(startButton, false, ""); }
});
async function submitDecision(approved) {
  if (!activeThreadId) return; clearError(); const button = approved ? approveButton : rejectButton; setBusy(button, true, approved ? "Approving..." : "Rejecting...");
  const claims = approved ? Array.from(document.querySelectorAll(".claim-editor")).map((editor) => ({ text: editor.value.trim(), evidence_ids: activeClaims[Number(editor.dataset.index)].evidence_ids })) : null;
  try { renderRun(await jsonRequest(`/v1/workflows/${activeThreadId}/decision`, { method: "POST", body: JSON.stringify({ approved, claims }) })); await loadHistory(); }
  catch (error) { showError(error.message); }
  finally { setBusy(button, false, ""); }
}
approveButton.addEventListener("click", () => submitDecision(true)); rejectButton.addEventListener("click", () => submitDecision(false));
fetch("/health").then((response) => { if (!response.ok) throw new Error(); apiStatus.classList.add("online"); apiStatus.lastChild.textContent = " API online"; }).catch(() => { apiStatus.lastChild.textContent = " API unavailable"; });
loadHistory();

async function loadApplications(status = "") {
  try {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    const applications = await jsonRequest(`/v1/applications${query}`);
    applicationBoard.innerHTML = applications.length
      ? applications.map((item) => `<article class="application-card" data-id="${item.id}"><div class="application-card-top"><span class="application-status ${escapeHtml(item.status)}">${escapeHtml(item.status)}</span><button class="danger-link" data-action="delete-application">Delete</button></div><h3>${escapeHtml(item.role)}</h3><strong>${escapeHtml(item.company)}</strong><label>Next action<input data-field="next_action" value="${escapeHtml(item.next_action || "")}" placeholder="Define the next step" /></label><div class="application-card-row"><select data-field="status"><option value="draft" ${item.status === "draft" ? "selected" : ""}>Draft</option><option value="applied" ${item.status === "applied" ? "selected" : ""}>Applied</option><option value="interview" ${item.status === "interview" ? "selected" : ""}>Interview</option><option value="offer" ${item.status === "offer" ? "selected" : ""}>Offer</option><option value="closed" ${item.status === "closed" ? "selected" : ""}>Closed</option></select><input data-field="due_date" type="date" value="${item.due_date || ""}" /></div><div class="application-card-actions"><button data-action="start-tailoring">Tailor materials</button><button data-action="save-application">Save</button></div></article>`).join("")
      : '<p class="history-empty">No applications in this view.</p>';
  } catch (error) {
    applicationBoard.innerHTML = `<p class="history-empty">${escapeHtml(error.message)}</p>`;
  }
}

applicationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    company: document.querySelector("#application-company").value.trim(),
    role: document.querySelector("#application-role").value.trim(),
    status: document.querySelector("#application-status").value,
    next_action: document.querySelector("#application-next-action").value.trim() || null,
    due_date: document.querySelector("#application-due-date").value || null,
  };
  try {
    await jsonRequest("/v1/applications", { method: "POST", body: JSON.stringify(payload) });
    applicationForm.reset();
    await loadApplications();
  } catch (error) { showError(error.message); }
});

applicationFilters.addEventListener("click", async (event) => {
  const button = event.target.closest("button"); if (!button) return;
  applicationFilters.querySelectorAll("button").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  await loadApplications(button.dataset.status || "");
});

applicationBoard.addEventListener("click", async (event) => {
  const button = event.target.closest("button"); if (!button) return;
  const card = button.closest(".application-card");
  const id = card.dataset.id;
  try {
    if (button.dataset.action === "delete-application") {
      await jsonRequest(`/v1/applications/${id}`, { method: "DELETE" });
      card.remove();
    } else if (button.dataset.action === "save-application") {
      const payload = {};
      card.querySelectorAll("[data-field]").forEach((field) => { payload[field.dataset.field] = field.value || null; });
      await jsonRequest(`/v1/applications/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      await loadApplications(applicationFilters.querySelector(".active").dataset.status || "");
    } else if (button.dataset.action === "start-tailoring") {
      document.querySelector("#job-description").focus();
      document.querySelector("#workflow").scrollIntoView();
    }
  } catch (error) { showError(error.message); }
});

downloadButton.addEventListener("click", async (event) => {
  if (!activeThreadId || !accessToken.value) return;
  event.preventDefault();
  try {
    const response = await fetch(`/v1/workflows/${activeThreadId}/export`, { headers: authHeaders() });
    if (!response.ok) throw new Error("Export download failed.");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url; link.download = `jobpilot-${activeThreadId}.docx`; link.click();
    URL.revokeObjectURL(url);
  } catch (error) { showError(error.message); }
});

loadApplications();
const requestedThread = new URLSearchParams(window.location.search).get("thread");
if (requestedThread) {
  jsonRequest(`/v1/workflows/${requestedThread}`)
    .then((run) => renderRun(run))
    .catch((error) => showError(error.message));
}