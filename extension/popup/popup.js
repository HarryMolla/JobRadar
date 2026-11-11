/**
 * JobRadar Popup Script
 * Renders the job dashboard and handles user interactions.
 */

import { storage } from '../lib/storage.js';
import { api, isWithinPostingAge } from '../lib/api.js';

let allJobs = [];
let currentFilter = 'all';
let currentCategory = '';
let currentRemote = '';
let searchQuery = '';
let settings = {};

// DOM refs
const jobList = document.getElementById('jobList');
const emptyState = document.getElementById('emptyState');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const syncBtn = document.getElementById('syncBtn');
const optionsBtn = document.getElementById('optionsBtn');
const searchInput = document.getElementById('searchInput');
const categoryFilter = document.getElementById('categoryFilter');
const remoteFilter = document.getElementById('remoteFilter');
const footerText = document.getElementById('footerText');

// Stat pills
const countAll = document.getElementById('countAll');
const countNew = document.getElementById('countNew');
const countSaved = document.getElementById('countSaved');
const countApplied = document.getElementById('countApplied');

// Initialize
(async () => {
  settings = await storage.getSettings();
  allJobs = await storage.pruneExpiredJobs(24);
  updateCounts();
  renderJobs();
  updateSyncStatus();
})();

// Sync button
syncBtn.addEventListener('click', async () => {
  syncBtn.classList.add('spinning');
  statusDot.className = 'status-dot syncing';
  statusText.textContent = 'Syncing...';

  try {
    const result = await chrome.runtime.sendMessage({ type: 'SYNC_NOW' });
    allJobs = await storage.getJobs();
    updateCounts();
    renderJobs();
    updateSyncStatus();
    footerText.textContent = result?.newJobs
      ? `✓ ${result.newJobs} new job${result.newJobs > 1 ? 's' : ''} found`
      : '✓ Up to date';
  } catch (err) {
    statusDot.className = 'status-dot error';
    statusText.textContent = 'Sync failed';
    footerText.textContent = `Error: ${err.message}`;
  } finally {
    syncBtn.classList.remove('spinning');
  }
});

// Options / Settings button
if (optionsBtn) {
  optionsBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (chrome.runtime.openOptionsPage) {
      chrome.runtime.openOptionsPage();
    } else {
      chrome.tabs.create({ url: chrome.runtime.getURL('options/options.html') });
    }
  });
}

// Tab filters
document.querySelectorAll('.stat-pill').forEach((pill) => {
  pill.addEventListener('click', () => {
    document.querySelectorAll('.stat-pill').forEach((p) => p.classList.remove('active'));
    pill.classList.add('active');
    currentFilter = pill.dataset.filter;
    renderJobs();
  });
});

// Search
let searchTimer;
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchQuery = searchInput.value.trim().toLowerCase();
    renderJobs();
  }, 200);
});

// Category filter
categoryFilter.addEventListener('change', () => {
  currentCategory = categoryFilter.value;
  renderJobs();
});

// Remote filter
remoteFilter.addEventListener('change', () => {
  currentRemote = remoteFilter.value;
  renderJobs();
});

function updateCounts() {
  const all = allJobs.filter((j) => isWithinPostingAge(j, 24)).length;
  const newC = allJobs.filter(
    (j) => (j.application_status || 'new') === 'new' && isWithinPostingAge(j, 24)
  ).length;
  const saved = allJobs.filter((j) => j.application_status === 'saved').length;
  const applied = allJobs.filter((j) => j.application_status === 'applied').length;

  countAll.textContent = all;
  countNew.textContent = newC;
  countSaved.textContent = saved;
  countApplied.textContent = applied;
}

function getFilteredJobs() {
  let jobs = [...allJobs];

  // Status filter
  if (currentFilter !== 'all') {
    jobs = jobs.filter((j) => (j.application_status || 'new') === currentFilter);
  }

  // Enforce 24-hour posting age filter in All and New tabs
  if (currentFilter === 'all' || currentFilter === 'new') {
    jobs = jobs.filter((j) => isWithinPostingAge(j, 24));
  }

  // Category filter
  if (currentCategory) {
    jobs = jobs.filter((j) => j.match_category === currentCategory);
  }

  // Remote/sponsorship filter
  if (currentRemote === 'remote_worldwide') {
    jobs = jobs.filter((j) => j.remote_type === 'remote_worldwide');
  } else if (currentRemote === 'remote_restricted') {
    jobs = jobs.filter((j) => j.remote_type === 'remote_restricted');
  } else if (currentRemote === 'sponsored') {
    jobs = jobs.filter((j) => j.sponsorship === 'sponsored');
  } else if (currentRemote === 'relocation') {
    jobs = jobs.filter((j) => j.relocation_offered);
  }

  // Search
  if (searchQuery) {
    jobs = jobs.filter(
      (j) =>
        j.title?.toLowerCase().includes(searchQuery) ||
        j.company?.toLowerCase().includes(searchQuery) ||
        j.location?.toLowerCase().includes(searchQuery) ||
        j.description?.toLowerCase().includes(searchQuery)
    );
  }

  // Sort by score desc, then detected_at desc
  jobs.sort((a, b) => {
    const scoreDiff = (b.match_score || 0) - (a.match_score || 0);
    if (scoreDiff !== 0) return scoreDiff;
    return new Date(b.detected_at || 0) - new Date(a.detected_at || 0);
  });

  return jobs;
}

function renderJobs() {
  const filtered = getFilteredJobs();
  jobList.innerHTML = '';

  if (filtered.length === 0) {
    emptyState.style.display = 'flex';
    footerText.textContent = allJobs.length ? 'No jobs match current filters' : 'No jobs yet — click sync';
    return;
  }

  emptyState.style.display = 'none';

  for (const job of filtered) {
    jobList.appendChild(createJobCard(job));
  }

  footerText.textContent = `Showing ${filtered.length} of ${allJobs.length} jobs`;
}

function createJobCard(job) {
  const card = document.createElement('div');
  const status = job.application_status || 'new';
  card.className = `job-card${status === 'dismissed' ? ' dismissed' : ''}`;
  card.dataset.fingerprint = job.fingerprint;

  // Score badge
  const score = job.match_score || 0;
  const scoreClass = score >= 70 ? 'score-high' : score >= 50 ? 'score-mid' : 'score-low';

  // Tags
  const tags = [];
  if (job.remote_type === 'remote_worldwide') {
    tags.push(`<span class="tag tag-remote-worldwide">🌍 Worldwide Remote</span>`);
  } else if (job.remote_type === 'remote_restricted') {
    tags.push(`<span class="tag tag-remote-restricted">Remote</span>`);
  }
  if (job.sponsorship === 'sponsored') {
    tags.push(`<span class="tag tag-sponsored">✈️ Visa Sponsor</span>`);
  }
  if (job.relocation_offered) {
    tags.push(`<span class="tag tag-relocation">📦 Relocation</span>`);
  }
  if (job.match_category && job.match_category !== 'irrelevant') {
    tags.push(`<span class="tag tag-category">${capitalize(job.match_category)}</span>`);
  }
  if (job.salary_min) {
    const sal = `${job.salary_currency || '$'}${formatSalary(job.salary_min)}${job.salary_max ? `–${formatSalary(job.salary_max)}` : '+'}`;
    tags.push(`<span class="tag tag-salary">💰 ${sal}</span>`);
  }
  tags.push(`<span class="tag tag-source">${job.source || '?'}</span>`);

  // Date (show original posting time first so real age is transparent)
  const dateStr = formatDate(job.posted_at || job.detected_at);

  // Reason
  const reason = job.match_reasons?.slice(0, 2).join('; ') || '';

  // Action button states
  const isSaved = status === 'saved';
  const isApplied = status === 'applied';
  const isDismissed = status === 'dismissed';

  card.innerHTML = `
    <div class="card-top">
      <div class="card-title">${escHtml(job.title || 'Untitled')}</div>
      <span class="score-badge ${scoreClass}">${score}/100</span>
    </div>
    <div class="card-company">${escHtml(job.company || '?')} · ${escHtml(job.location || 'Remote')}</div>
    ${tags.length ? `<div class="card-tags">${tags.join('')}</div>` : ''}
    ${reason ? `<div class="card-reason">"${escHtml(reason)}"</div>` : ''}
    <div class="card-actions">
      <a href="${escHtml(job.url || '#')}" target="_blank" rel="noopener noreferrer" class="btn-apply">Apply →</a>
      <button class="btn-action ${isSaved ? 'active' : ''}" data-action="saved">
        ${isSaved ? '★ Saved' : '☆ Save'}
      </button>
      <button class="btn-action ${isApplied ? 'active' : ''}" data-action="applied">
        ${isApplied ? '✓ Applied' : 'Applied?'}
      </button>
      <button class="btn-action ${isDismissed ? 'active' : ''}" data-action="dismissed">
        ${isDismissed ? 'Hidden' : '✕'}
      </button>
      <span class="card-date">${dateStr}</span>
    </div>
  `;

  // Action buttons
  card.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const action = btn.dataset.action;
      const fp = card.dataset.fingerprint;
      const currentStatus = job.application_status || 'new';

      // Toggle: clicking active status → revert to 'new'
      const newStatus = currentStatus === action ? 'new' : action;
      job.application_status = newStatus;

      await storage.updateJobStatus(fp, newStatus);

      // Also update backend
      const apiUrl = settings.apiUrl || 'http://127.0.0.1:8765';
      try {
        await api.updateJobStatus(apiUrl, fp, newStatus, { apiKey: settings.apiKey });
      } catch {
        // Backend may not be running — local extension storage update succeeded
      }

      updateCounts();
      renderJobs();
    });
  });

  return card;
}

async function updateSyncStatus() {
  const sync = await storage.getLastSync();
  if (!sync) {
    statusDot.className = 'status-dot';
    statusText.textContent = 'Never synced';
    return;
  }
  if (sync.status === 'ok') {
    statusDot.className = 'status-dot ok';
    const ago = timeAgo(sync.at);
    statusText.textContent = `Synced ${ago}`;
  } else {
    statusDot.className = 'status-dot error';
    statusText.textContent = 'Sync error';
  }
}

// Utilities
function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function capitalize(str) {
  return str ? str[0].toUpperCase() + str.slice(1) : '';
}

function formatSalary(n) {
  if (n >= 1000) return `${Math.round(n / 1000)}k`;
  return String(n);
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return '';
  const diffMs = Date.now() - d.getTime();
  const diffHours = Math.floor(diffMs / 3600000);
  if (diffHours < 1) return 'Just now';
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return '1d ago';
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function timeAgo(isoStr) {
  if (!isoStr) return 'unknown';
  const mins = Math.floor((Date.now() - new Date(isoStr)) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

