// Shared API configuration via localStorage
const API_CONFIG_KEY = "tasksync_api_config";

// ── Inject Settings Modal CSS ─────────────────────────────────────────────────
(function injectStyles() {
  const style = document.createElement('style');
  style.textContent = `
.nav-btn-settings {
  position: absolute;
  bottom: 0;
  height: 44px;
  width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  cursor: pointer;
  color: #007aff;
  padding: 0;
  -webkit-tap-highlight-color: transparent;
}
._sm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 500;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.25s ease;
}
._sm-overlay.visible { opacity: 1; }
._sm-sheet {
  background: #fff;
  border-radius: 20px 20px 0 0;
  width: 100%;
  max-width: 600px;
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
  transform: translateY(100%);
  transition: transform 0.35s cubic-bezier(0.32,0.72,0,1);
}
._sm-overlay.visible ._sm-sheet { transform: translateY(0); }
._sm-handle {
  width: 36px;
  height: 4px;
  background: #d1d1d6;
  border-radius: 2px;
  margin: 10px auto 0;
}
._sm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
}
._sm-title {
  font-size: 17px;
  font-weight: 600;
  color: #1c1c1e;
}
._sm-close {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #e5e5ea;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #6e6e73;
  line-height: 1;
  padding: 0;
}
._sm-group {
  margin: 0 16px 16px;
  background: #f2f2f7;
  border-radius: 12px;
  overflow: hidden;
}
._sm-row {
  display: flex;
  align-items: center;
  padding: 0 14px;
  min-height: 52px;
  gap: 12px;
}
._sm-row + ._sm-row {
  border-top: 0.5px solid rgba(60,60,67,0.18);
}
._sm-icon {
  font-size: 20px;
  width: 28px;
  text-align: center;
  flex-shrink: 0;
}
._sm-label {
  font-size: 15px;
  color: #1c1c1e;
  width: 72px;
  flex-shrink: 0;
}
._sm-input {
  flex: 1;
  border: none !important;
  background: transparent !important;
  font-size: 15px !important;
  color: #1c1c1e !important;
  padding: 0 !important;
  margin: 0 !important;
  outline: none !important;
  min-height: 0 !important;
  border-radius: 0 !important;
  width: 100% !important;
  text-align: right;
}
._sm-input::placeholder { color: #aeaeb2; }
._sm-btn-save {
  display: block;
  width: calc(100% - 32px);
  margin: 0 16px 10px;
  min-height: 50px;
  background: #007aff;
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 17px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
._sm-btn-save.saved { background: #34c759; }
._sm-btn-clear {
  display: block;
  width: calc(100% - 32px);
  margin: 0 16px 4px;
  min-height: 44px;
  background: transparent;
  color: #ff3b30;
  border: none;
  font-size: 17px;
  font-weight: 500;
  cursor: pointer;
}
@media (prefers-color-scheme: dark) {
  ._sm-sheet { background: #1c1c1e; }
  ._sm-title { color: #fff; }
  ._sm-close { background: #3a3a3c; color: #aeaeb2; }
  ._sm-group { background: #2c2c2e; }
  ._sm-row + ._sm-row { border-top-color: rgba(255,255,255,0.1); }
  ._sm-label { color: #fff; }
  ._sm-input { color: #fff !important; }
}
`;
  document.head.appendChild(style);
})();

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
let _smPageIds = null;

function _getOrCreateModal() {
  let overlay = document.getElementById('_smOverlay');
  if (overlay) return overlay;

  overlay = document.createElement('div');
  overlay.id = '_smOverlay';
  overlay.className = '_sm-overlay';
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) closeSettingsModal();
  });

  overlay.innerHTML = `
    <div class="_sm-sheet" id="_smSheet">
      <div class="_sm-handle"></div>
      <div class="_sm-header">
        <span class="_sm-title">API 配置</span>
        <button class="_sm-close" onclick="closeSettingsModal()" aria-label="关闭">✕</button>
      </div>
      <div class="_sm-group">
        <div class="_sm-row">
          <span class="_sm-icon">🔑</span>
          <span class="_sm-label">API Key</span>
          <input class="_sm-input" type="password" id="_cfgApiKey" placeholder="sk-…" autocomplete="off">
        </div>
        <div class="_sm-row">
          <span class="_sm-icon">🌐</span>
          <span class="_sm-label">Base URL</span>
          <input class="_sm-input" type="url" id="_cfgBaseUrl" placeholder="https://api.example.com/v1" autocomplete="off">
        </div>
        <div class="_sm-row">
          <span class="_sm-icon">🤖</span>
          <span class="_sm-label">模型</span>
          <input class="_sm-input" type="text" id="_cfgModelName" placeholder="claude-sonnet-4-5" autocomplete="off">
        </div>
      </div>
      <button class="_sm-btn-save" id="_smSaveBtn" onclick="_smSave()">保存配置</button>
      <button class="_sm-btn-clear" onclick="_smClear()">清除配置</button>
    </div>`;

  document.body.appendChild(overlay);
  return overlay;
}

function openSettingsModal(pageIds) {
  _smPageIds = pageIds || null;
  const overlay = _getOrCreateModal();
  const cfg = loadApiConfig();
  document.getElementById('_cfgApiKey').value = cfg.apiKey || '';
  document.getElementById('_cfgBaseUrl').value = cfg.baseUrl || '';
  document.getElementById('_cfgModelName').value = cfg.modelName || '';
  const saveBtn = document.getElementById('_smSaveBtn');
  saveBtn.textContent = '保存配置';
  saveBtn.classList.remove('saved');
  // Trigger animation
  overlay.style.display = 'flex';
  requestAnimationFrame(() => {
    requestAnimationFrame(() => overlay.classList.add('visible'));
  });
}

function closeSettingsModal() {
  const overlay = document.getElementById('_smOverlay');
  if (!overlay) return;
  overlay.classList.remove('visible');
  setTimeout(() => { overlay.style.display = 'none'; }, 350);
}

function _smSave() {
  const apiKey = document.getElementById('_cfgApiKey').value.trim();
  const baseUrl = document.getElementById('_cfgBaseUrl').value.trim();
  const modelName = document.getElementById('_cfgModelName').value.trim();
  saveApiConfig({ apiKey, baseUrl, modelName });
  if (_smPageIds) fillApiConfigInputs(_smPageIds);
  const btn = document.getElementById('_smSaveBtn');
  btn.textContent = '✓ 已保存';
  btn.classList.add('saved');
  setTimeout(() => {
    btn.textContent = '保存配置';
    btn.classList.remove('saved');
    closeSettingsModal();
  }, 1500);
}

function _smClear() {
  clearApiConfig();
  document.getElementById('_cfgApiKey').value = '';
  document.getElementById('_cfgBaseUrl').value = '';
  document.getElementById('_cfgModelName').value = '';
  if (_smPageIds) {
    if (_smPageIds.apiKey) document.getElementById(_smPageIds.apiKey).value = '';
    if (_smPageIds.baseUrl) document.getElementById(_smPageIds.baseUrl).value = '';
    if (_smPageIds.modelName) document.getElementById(_smPageIds.modelName).value = '';
  }
}

// Legacy compat wrappers (called from old HTML with explicit pageIds args)
function saveSettingsModal(pageIds) {
  if (pageIds) _smPageIds = pageIds;
  _smSave();
}

function clearSettingsModal(pageIds) {
  if (pageIds) _smPageIds = pageIds;
  _smClear();
}
