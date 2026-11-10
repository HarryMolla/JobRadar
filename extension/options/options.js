/**
 * JobRadar Options Page Script
 */

import { storage } from '../lib/storage.js';
import { api } from '../lib/api.js';

let settings = {};

// DOM refs
const apiUrlInput = document.getElementById('apiUrl');
const githubRepoInput = document.getElementById('githubRepo');
const githubTokenInput = document.getElementById('githubToken');
const minScoreInput = document.getElementById('minScore');
const minScoreVal = document.getElementById('minScoreVal');
const notifEnabled = document.getElementById('notificationsEnabled');
const syncIntervalSelect = document.getElementById('syncInterval');
const saveBtn = document.getElementById('saveBtn');
const resetBtn = document.getElementById('resetBtn');
const testBtn = document.getElementById('testConnection');
const testResult = document.getElementById('testResult');
const saveBanner = document.getElementById('saveBanner');
const refreshStatsBtn = document.getElementById('refreshStats');

// Initialize
(async () => {
  settings = await storage.getSettings();
  loadSettingsToUI();
  loadSourceStats();
})();

function loadSettingsToUI() {
  apiUrlInput.value = settings.apiUrl || 'http://127.0.0.1:8765';
  githubRepoInput.value = settings.githubRepo || 'HarryMolla/JobRadar';
  githubTokenInput.value = settings.githubToken || '';
  minScoreInput.value = settings.minScore ?? 50;
  minScoreVal.textContent = settings.minScore ?? 50;
  notifEnabled.checked = settings.notificationsEnabled !== false;
  syncIntervalSelect.value = String(settings.syncIntervalMinutes || 30);

  // Categories
  const cats = settings.categories || ['design', 'frontend', 'wordpress'];
  document.querySelectorAll('[name="category"]').forEach((cb) => {
    cb.checked = cats.includes(cb.value);
  });
}

// Score range live update
minScoreInput.addEventListener('input', () => {
  minScoreVal.textContent = minScoreInput.value;
});

// Save
saveBtn.addEventListener('click', async () => {
  const categories = [...document.querySelectorAll('[name="category"]:checked')]
    .map((cb) => cb.value);

  const updated = {
    ...settings,
    apiUrl: apiUrlInput.value.trim(),
    githubRepo: githubRepoInput.value.trim(),
    githubToken: githubTokenInput.value.trim(),
    minScore: parseInt(minScoreInput.value, 10),
    notificationsEnabled: notifEnabled.checked,
    syncIntervalMinutes: parseInt(syncIntervalSelect.value, 10),
    categories,
  };

  await storage.setSettings(updated);
  settings = updated;

  // Update alarm interval
  await chrome.alarms.clear('jobradar-sync');
  chrome.alarms.create('jobradar-sync', {
    delayInMinutes: 1,
    periodInMinutes: updated.syncIntervalMinutes,
  });

  showBanner();
});

function showBanner() {
  saveBanner.style.display = 'block';
  setTimeout(() => { saveBanner.style.display = 'none'; }, 3000);
}

// Test connection
testBtn.addEventListener('click', async () => {
  testResult.className = 'test-result';
  testResult.textContent = 'Testing connection...';
  const url = apiUrlInput.value.trim() || 'http://127.0.0.1:8765';
  const repo = githubRepoInput.value.trim();
  const token = githubTokenInput.value.trim();

  const ok = await api.checkHealth(url);
  if (ok) {
    testResult.className = 'test-result ok';
    testResult.textContent = '✓ Connected to Local API!';
  } else if (repo) {
    try {
      const ghRes = await api.fetchJobsFromGitHub(repo, { token, limit: 1 });
      testResult.className = 'test-result ok';
      testResult.textContent = `✓ Connected directly to GitHub (${ghRes.jobs.length} jobs available in cloud state)!`;
    } catch (err) {
      testResult.className = 'test-result err';
      testResult.textContent = `✗ GitHub connection failed: ${err.message}`;
    }
  } else {
    testResult.className = 'test-result err';
    testResult.textContent = '✗ Could not connect. Run "node scripts/server.js" or enter your GitHub Repo!';
  }
});

// Source health
async function loadSourceStats() {
  const container = document.getElementById('sourceHealth');
  const url = settings.apiUrl || 'http://127.0.0.1:8765';
  const key = settings.apiKey || '';
  try {
    const data = await api.fetchStats(url, { apiKey: key });
    const sources = data.sources || [];
    if (sources.length === 0) {
      container.innerHTML = '<div class="loading">No source statistics yet. Run the collector first.</div>';
      return;
    }
    const rows = sources.map((s) => `
      <tr>
        <td><strong>${s.source}</strong></td>
        <td>${s.total_jobs || 0}</td>
        <td class="${s.last_success ? 'status-ok' : ''}">${formatDate(s.last_success)}</td>
        <td>${s.last_error ? `<span class="status-error">⚠ ${s.last_error.slice(0,60)}</span>` : '✓ OK'}</td>
      </tr>
    `).join('');
    container.innerHTML = `
      <table class="source-table">
        <thead><tr><th>Source</th><th>Jobs Found</th><th>Last Success</th><th>Last Status</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  } catch (err) {
    container.innerHTML = `<div class="loading">Run the backend server to inspect live source health stats.</div>`;
  }
}

refreshStatsBtn.addEventListener('click', loadSourceStats);

// Reset
resetBtn.addEventListener('click', async () => {
  if (!confirm('This will delete all stored jobs and reset settings to default. Proceed?')) return;
  await storage.clearAll();
  location.reload();
});

function formatDate(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

