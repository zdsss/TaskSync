// Shared API configuration via localStorage
const API_CONFIG_KEY = "tasksync_api_config";

function loadApiConfig() {
  try {
    return JSON.parse(localStorage.getItem(API_CONFIG_KEY) || "{}");
  } catch { return {}; }
}

function saveApiConfig(cfg) {
  const existing = loadApiConfig();
  localStorage.setItem(API_CONFIG_KEY, JSON.stringify({ ...existing, ...cfg }));
}

function clearApiConfig() {
  localStorage.removeItem(API_CONFIG_KEY);
}

// ids: { apiKey, baseUrl, modelName } — element IDs on the current page
function fillApiConfigInputs(ids) {
  const cfg = loadApiConfig();
  if (ids.apiKey && cfg.apiKey) document.getElementById(ids.apiKey).value = cfg.apiKey;
  if (ids.baseUrl && cfg.baseUrl) document.getElementById(ids.baseUrl).value = cfg.baseUrl;
  if (ids.modelName && cfg.modelName) document.getElementById(ids.modelName).value = cfg.modelName;
}

function collectAndSaveApiConfig(ids) {
  const cfg = {};
  if (ids.apiKey) cfg.apiKey = document.getElementById(ids.apiKey).value.trim();
  if (ids.baseUrl) cfg.baseUrl = document.getElementById(ids.baseUrl).value.trim();
  if (ids.modelName) cfg.modelName = document.getElementById(ids.modelName).value.trim();
  saveApiConfig(cfg);
}

// ── Settings Modal ────────────────────────────────────────────────────────────
function openSettingsModal() {
  const cfg = loadApiConfig();
  document.getElementById("_cfgApiKey").value = cfg.apiKey || "";
  document.getElementById("_cfgBaseUrl").value = cfg.baseUrl || "";
  document.getElementById("_cfgModelName").value = cfg.modelName || "";
  document.getElementById("_settingsModal").classList.remove("hidden");
}

function closeSettingsModal() {
  document.getElementById("_settingsModal").classList.add("hidden");
}

function saveSettingsModal(pageIds) {
  const apiKey = document.getElementById("_cfgApiKey").value.trim();
  const baseUrl = document.getElementById("_cfgBaseUrl").value.trim();
  const modelName = document.getElementById("_cfgModelName").value.trim();
  saveApiConfig({ apiKey, baseUrl, modelName });
  // Sync to current page inputs
  if (pageIds) fillApiConfigInputs(pageIds);
  closeSettingsModal();
}

function clearSettingsModal(pageIds) {
  clearApiConfig();
  document.getElementById("_cfgApiKey").value = "";
  document.getElementById("_cfgBaseUrl").value = "";
  document.getElementById("_cfgModelName").value = "";
  // Clear page inputs too
  if (pageIds) {
    if (pageIds.apiKey) document.getElementById(pageIds.apiKey).value = "";
    if (pageIds.baseUrl) document.getElementById(pageIds.baseUrl).value = "";
    if (pageIds.modelName) document.getElementById(pageIds.modelName).value = "";
  }
}
