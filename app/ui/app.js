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
let activeThreadId = null;
let uploadedDocuments = [];

function setBusy(button, busy, label) { button.disabled = busy; if (!button.dataset.label) button.dataset.label = button.innerHTML; button.innerHTML = busy ? label : button.dataset.label; }
function showError(message) { errorMessage.textContent = message; errorMessage.classList.remove("hidden"); }
function clearError() { errorMessage.classList.add("hidden"); errorMessage.textContent = ""; }
function escapeHtml(value) { const element = document.createElement("div"); element.textContent = value; return element.innerHTML; }
function claimCard(claim, blocked = false) {
  const evidence = (claim.evidence_ids || []).map((id) => `<span>${escapeHtml(id)}</span>`).join("");
  const reason = claim.review_reason ? `<p class="review-reason">${escapeHtml(claim.review_reason)}</p>` : "";
  return `<article class="claim-card ${blocked ? "blocked" : ""}"><div class="claim-state">${blocked ? "!" : "✓"}</div><div><p>${escapeHtml(claim.text)}</p>${reason}<div class="evidence-tags">${evidence || "<span>No evidence ID</span>"}</div></div></article>`;
}
function renderRun(run) {
  activeThreadId = run.thread_id; emptyState.classList.add("hidden"); reviewContent.classList.remove("hidden"); threadLabel.textContent = run.thread_id;
  runStatus.textContent = run.status.replaceAll("_", " "); runStatus.className = `run-status ${run.status}`;
  if (run.token_usage) { const cost = run.token_usage.estimated_cost_usd == null ? "" : ` · $${run.token_usage.estimated_cost_usd.toFixed(5)}`; tokenUsage.textContent = `${run.token_usage.total_tokens} tokens${cost}`; } else tokenUsage.textContent = "Local mode";
  claimList.innerHTML = (run.claims || []).map((claim) => claimCard(claim)).join("") || '<div class="claim-card blocked"><p>No exportable claims were produced.</p></div>';
  const blocked = run.blocked_claims || []; blockedList.innerHTML = blocked.map((claim) => claimCard(claim, true)).join(""); blockedSection.classList.toggle("hidden", blocked.length === 0);
  const pending = run.status === "pending_review"; decisionBar.classList.toggle("hidden", !pending); downloadButton.classList.toggle("hidden", run.status !== "completed");
  if (run.status === "completed") downloadButton.href = `/v1/workflows/${run.thread_id}/export`;
}
async function jsonRequest(url, options = {}) {
  const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Request failed with status ${response.status}.`); }
  return response.json();
}
async function uploadFiles(files) {
  clearError(); uploadedDocuments = []; if (!files.length) return;
  if (files.length > 5) { showError("Select no more than five files."); return; }
  fileList.innerHTML = `<span class="loading">Reading ${files.length} file${files.length === 1 ? "" : "s"}…</span>`;
  const body = new FormData(); files.forEach((file) => body.append("files", file));
  try {
    const response = await fetch("/v1/documents/upload", { method: "POST", body });
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || `Upload failed with status ${response.status}.`); }
    uploadedDocuments = await response.json();
    fileList.innerHTML = uploadedDocuments.map((doc) => `<span class="file-chip"><b>✓</b>${escapeHtml(doc.source_path)}</span>`).join("");
    dropZone.classList.add("has-files");
  } catch (error) { fileList.innerHTML = ""; showError(error.message); }
}
evidenceFiles.addEventListener("change", () => uploadFiles(Array.from(evidenceFiles.files || [])));
["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.add("dragging"); }));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.remove("dragging"); }));
dropZone.addEventListener("drop", (event) => uploadFiles(Array.from(event.dataTransfer.files || [])));
form.addEventListener("submit", async (event) => {
  event.preventDefault(); clearError();
  const pastedContent = document.querySelector("#evidence-content").value.trim();
  if (!uploadedDocuments.length && !pastedContent) { showError("Upload a document or paste evidence before continuing."); return; }
  setBusy(startButton, true, "Building evidence map…");
  const documents = uploadedDocuments.length ? uploadedDocuments : [{ source_id: document.querySelector("#source-id").value, source_path: document.querySelector("#source-path").value, content: pastedContent }];
  const payload = { job_description: document.querySelector("#job-description").value, language: document.querySelector("#language").value, documents };
  try { renderRun(await jsonRequest("/v1/workflows", { method: "POST", body: JSON.stringify(payload) })); }
  catch (error) { showError(error.message); }
  finally { setBusy(startButton, false, ""); }
});
async function submitDecision(approved) {
  if (!activeThreadId) return; clearError(); const button = approved ? approveButton : rejectButton; setBusy(button, true, approved ? "Approving…" : "Rejecting…");
  try { renderRun(await jsonRequest(`/v1/workflows/${activeThreadId}/decision`, { method: "POST", body: JSON.stringify({ approved }) })); }
  catch (error) { showError(error.message); }
  finally { setBusy(button, false, ""); }
}
approveButton.addEventListener("click", () => submitDecision(true)); rejectButton.addEventListener("click", () => submitDecision(false));
fetch("/health").then((response) => { if (!response.ok) throw new Error(); apiStatus.classList.add("online"); apiStatus.lastChild.textContent = " API online"; }).catch(() => { apiStatus.lastChild.textContent = " API unavailable"; });
