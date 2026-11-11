/**
 * JobRadar Popup Script
 * Renders the job dashboard and handles user interactions.
 */

import { storage } from '../lib/storage.js';
import { api } from '../lib/api.js';
import {
  DEFAULT_UAE_SOURCES,
  buildUaeSearchUrl,
} from '../lib/uae_sources.js';
import {
  applyCommonJobFilters,
  buildUaeDropdownOptions,
  filterUaeJobs,
  formatDescriptionPreview,
  getJobApplyUrl,
  getJobDetailUrl,
  getRelocationStatus,
  getVisaStatus,
  isUaeJob,
  isWithinPostingAge,
} from '../lib/filters.js';

let allJobs = [];
let uaeSources = [...DEFAULT_UAE_SOURCES];
let currentFilter = 'all';
let currentSource = '';
let currentCategory = '';
let currentVisa = '';
let currentRemote = '';
let searchQuery = '';
let selectedUaeKeyword = '';
let selectedUaeLocation = '';
let showUaePortals = false;
let settings = {};

// DOM refs
const jobList = document.getElementById('jobList');
const emptyState = document.getElementById('emptyState');
const filterBar = document.getElementById('filterBar');
const uaeToolbar = document.getElementById('uaeToolbar');
const uaeKeywordFilter = document.getElementById('uaeKeywordFilter');
const uaeLocationFilter = document.getElementById('uaeLocationFilter');
const uaePortalsToggle = document.getElementById('uaePortalsToggle');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const syncBtn = document.getElementById('syncBtn');
const optionsBtn = document.getElementById('optionsBtn');
const searchInput = document.getElementById('searchInput');
const sourceFilter = document.getElementById('sourceFilter');
const categoryFilter = document.getElementById('categoryFilter');
const visaFilter = document.getElementById('visaFilter');
const remoteFilter = document.getElementById('remoteFilter');
const footerText = document.getElementById('footerText');

// Stat pills
const countAll = document.getElementById('countAll');
const countNew = document.getElementById('countNew');
const countSaved = document.getElementById('countSaved');
const countApplied = document.getElementById('countApplied');
const countUae = document.getElementById('countUae');

// Initialize
(async () => {
  settings = await storage.getSettings();
  allJobs = await storage.pruneExpiredJobs(24);
  const storedUae = await storage.getUaeSources();
  if (Array.isArray(storedUae) && storedUae.length > 0) {
    uaeSources = storedUae;
  }
  populateSourceFilter();
  populateUaeFilters();
  updateCounts();
  renderCurrentView();
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
    const storedUae = await storage.getUaeSources();
    if (Array.isArray(storedUae) && storedUae.length > 0) {
      uaeSources = storedUae;
    }
    populateSourceFilter();
    populateUaeFilters();
    updateCounts();
    renderCurrentView();
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
    renderCurrentView();
  });
});

// Search
let searchTimer;
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchQuery = searchInput.value.trim().toLowerCase();
    renderCurrentView();
  }, 200);
});

// Source filter
if (sourceFilter) {
  sourceFilter.addEventListener('change', () => {
    currentSource = sourceFilter.value;
    renderCurrentView();
  });
}

// Category filter
categoryFilter.addEventListener('change', () => {
  currentCategory = categoryFilter.value;
  renderCurrentView();
});

// Visa filter
if (visaFilter) {
  visaFilter.addEventListener('change', () => {
    currentVisa = visaFilter.value;
    renderCurrentView();
  });
}

// Remote / Benefits filter
remoteFilter.addEventListener('change', () => {
  currentRemote = remoteFilter.value;
  renderCurrentView();
});

// UAE filter dropdown 1: role / benefit / source / keyword
if (uaeKeywordFilter) {
  uaeKeywordFilter.addEventListener('change', () => {
    selectedUaeKeyword = uaeKeywordFilter.value;
    renderCurrentView();
  });
}

// UAE filter dropdown 2: emirate / location
if (uaeLocationFilter) {
  uaeLocationFilter.addEventListener('change', () => {
    selectedUaeLocation = uaeLocationFilter.value;
    renderCurrentView();
  });
}

// Toggle 19 UAE portals directory panel
if (uaePortalsToggle) {
  uaePortalsToggle.addEventListener('click', () => {
    showUaePortals = !showUaePortals;
    uaePortalsToggle.classList.toggle('active', showUaePortals);
    renderCurrentView();
  });
}

function populateSourceFilter() {
  if (!sourceFilter) return;
  const currentVal = sourceFilter.value;
  const sourcesMap = new Map([
    ['himalayas', 'Himalayas'],
  ]);
  for (const job of allJobs) {
    if (job.source) {
      sourcesMap.set(job.source, job.source_name || job.source);
    }
  }
  for (const src of uaeSources) {
    if (src.mode === 'automated' && !sourcesMap.has(src.id)) {
      sourcesMap.set(src.id, src.name);
    }
  }
  sourceFilter.innerHTML = '<option value="">All Sources</option>';
  for (const [id, label] of [...sourcesMap.entries()].sort((a, b) => a[1].localeCompare(b[1]))) {
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = label;
    sourceFilter.appendChild(opt);
  }
  sourceFilter.value = currentVal;
}

function populateUaeFilters() {
  const uaeJobs = allJobs.filter((j) => isUaeJob(j) && isWithinPostingAge(j, 24));
  const { keywordOptions, locationOptions } = buildUaeDropdownOptions(uaeJobs);

  if (uaeKeywordFilter) {
    uaeKeywordFilter.innerHTML = '';
    for (const { value, label } of keywordOptions) {
      const opt = document.createElement('option');
      opt.value = value;
      opt.textContent = label;
      uaeKeywordFilter.appendChild(opt);
    }
    if ([...uaeKeywordFilter.options].some((o) => o.value === selectedUaeKeyword)) {
      uaeKeywordFilter.value = selectedUaeKeyword;
    } else {
      selectedUaeKeyword = '';
      uaeKeywordFilter.value = '';
    }
  }

  if (uaeLocationFilter) {
    uaeLocationFilter.innerHTML = '';
    for (const { value, label } of locationOptions) {
      const opt = document.createElement('option');
      opt.value = value;
      opt.textContent = label;
      uaeLocationFilter.appendChild(opt);
    }
    if ([...uaeLocationFilter.options].some((o) => o.value === selectedUaeLocation)) {
      uaeLocationFilter.value = selectedUaeLocation;
    } else {
      selectedUaeLocation = '';
      uaeLocationFilter.value = '';
    }
  }
}

function updateCounts() {
  const all = allJobs.filter((j) => isWithinPostingAge(j, 24)).length;
  const newC = allJobs.filter(
    (j) => (j.application_status || 'new') === 'new' && isWithinPostingAge(j, 24)
  ).length;
  const saved = allJobs.filter((j) => j.application_status === 'saved').length;
  const applied = allJobs.filter((j) => j.application_status === 'applied').length;
  const uaeCount = allJobs.filter((j) => isUaeJob(j) && isWithinPostingAge(j, 24)).length;

  countAll.textContent = all;
  countNew.textContent = newC;
  countSaved.textContent = saved;
  countApplied.textContent = applied;
  if (countUae) countUae.textContent = uaeCount;
}

function getCommonFilterState() {
  return {
    tab: currentFilter,
    source: currentSource,
    category: currentCategory,
    visa: currentVisa,
    remote: currentRemote,
    searchQuery,
    maxAgeHours: 24,
  };
}

function getFilteredJobs() {
  return applyCommonJobFilters(allJobs, getCommonFilterState());
}

function renderCurrentView() {
  if (filterBar) filterBar.style.display = 'flex';
  if (uaeToolbar) {
    uaeToolbar.style.display = currentFilter === 'uae_sources' ? 'flex' : 'none';
  }
  if (currentFilter === 'uae_sources') {
    renderUaeView();
  } else {
    renderJobs();
  }
}

function renderUaeView() {
  const filteredUae = filterUaeJobs(allJobs, {
    ...getCommonFilterState(),
    uaeKeyword: selectedUaeKeyword,
    uaeLocation: selectedUaeLocation,
  });

  jobList.innerHTML = '';

  if (filteredUae.length === 0) {
    emptyState.style.display = 'flex';
    const emptyTitle = emptyState.querySelector('.empty-title');
    const emptyDesc = emptyState.querySelector('.empty-desc');
    if (emptyTitle) emptyTitle.textContent = 'No matching UAE jobs in the last 24h';
    if (emptyDesc) {
      emptyDesc.textContent = 'Try clearing one of the UAE filters above, or click "🌐 Portals (19)" to run a manual UAE search.';
    }
    jobList.appendChild(emptyState);
  } else {
    emptyState.style.display = 'none';
    for (const job of filteredUae) {
      jobList.appendChild(createJobCard(job));
    }
  }

  if (showUaePortals) {
    renderUaePortalsPanel();
  }

  const totalUae = allJobs.filter((j) => isUaeJob(j) && isWithinPostingAge(j, 24)).length;
  footerText.textContent = `Showing ${filteredUae.length} of ${totalUae} UAE jobs (last 24h)`;
}

function renderUaePortalsPanel() {
  const panel = document.createElement('div');
  panel.className = 'uae-portals-panel';

  const groups = [
    ['general', 'General UAE Job Boards'],
    ['government', 'Government Recruitment Portals'],
    ['agency', 'Specialist Recruitment Agencies'],
    ['employer', 'Direct Employer Career Pages'],
  ];

  const manualKeyword = selectedUaeKeyword.startsWith('term:')
    ? selectedUaeKeyword.slice(5)
    : selectedUaeKeyword.startsWith('category:')
      ? selectedUaeKeyword.slice(9)
      : 'UI UX Designer';
  const manualLocation = selectedUaeLocation && selectedUaeLocation !== 'remote_uae'
    ? selectedUaeLocation
    : 'Dubai';

  for (const [catKey, groupLabel] of groups) {
    const items = uaeSources.filter((s) => s.category === catKey);
    if (items.length === 0) continue;

    const heading = document.createElement('div');
    heading.className = 'uae-group-title';
    heading.textContent = `${groupLabel} (${items.length})`;
    panel.appendChild(heading);

    for (const src of items) {
      const badgeClass =
        src.mode === 'automated'
          ? 'uae-badge-auto'
          : src.mode === 'email_or_manual'
            ? 'uae-badge-email'
            : 'uae-badge-manual';
      const badgeLabel =
        src.mode === 'automated'
          ? 'Auto (24h Verified)'
          : src.mode === 'email_or_manual'
            ? 'Email Alert / Manual'
            : 'Manual Search';

      const searchHref = buildUaeSearchUrl(src, manualKeyword, manualLocation);
      const checkedNote = src.last_checked_at
        ? `Checked ${timeAgo(src.last_checked_at)} (${src.last_success ? `${src.last_jobs_found || 0} found` : 'failed'})`
        : src.mode === 'automated'
          ? 'Pending next 6h run'
          : 'Respects robots/anti-bot rules';

      const card = document.createElement('div');
      card.className = 'uae-source-card';
      card.innerHTML = `
        <div class="uae-source-top">
          <span class="uae-source-name">${escHtml(src.name)}</span>
          <span class="${badgeClass}">${badgeLabel}</span>
        </div>
        <div class="uae-source-reason">${escHtml(src.reason || '')}</div>
        <div class="uae-source-actions">
          <span>${escHtml(checkedNote)}</span>
          <a href="${escHtml(searchHref)}" target="_blank" rel="noopener noreferrer" class="btn-apply">Open / Search →</a>
        </div>
      `;
      panel.appendChild(card);
    }
  }

  jobList.appendChild(panel);
}

function renderJobs() {
  const filtered = getFilteredJobs();
  jobList.innerHTML = '';

  if (filtered.length === 0) {
    emptyState.style.display = 'flex';
    const emptyTitle = emptyState.querySelector('.empty-title');
    const emptyDesc = emptyState.querySelector('.empty-desc');
    if (emptyTitle) emptyTitle.textContent = allJobs.length ? 'No matching jobs' : 'No jobs yet';
    if (emptyDesc) {
      emptyDesc.textContent = allJobs.length
        ? 'Try clearing or widening your search and filter dropdowns.'
        : 'Click the sync button or wait for the automatic scan.';
    }
    jobList.appendChild(emptyState);
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

  // Tags & verified benefit indicators
  const tags = [];
  const visaStatus = getVisaStatus(job);
  if (visaStatus === 'confirmed') {
    tags.push(`<span class="tag tag-sponsored">✓ Visa Confirmed</span>`);
  } else if (visaStatus === 'unavailable') {
    tags.push(`<span class="tag tag-unavailable">✕ No Visa</span>`);
  } else {
    tags.push(`<span class="tag tag-unverified">? Visa Unverified</span>`);
  }

  const relocStatus = getRelocationStatus(job);
  if (relocStatus === 'confirmed') {
    tags.push(`<span class="tag tag-relocation">📦 Relocation Confirmed</span>`);
  } else if (relocStatus === 'unavailable') {
    tags.push(`<span class="tag tag-unavailable">✕ No Relocation</span>`);
  }

  if (job.flight_covered === 'confirmed') {
    tags.push(`<span class="tag tag-relocation">✈️ Flight Covered</span>`);
  } else if (job.flight_covered === 'unavailable') {
    tags.push(`<span class="tag tag-unavailable">✕ No Flight</span>`);
  }

  if (job.accommodation_covered === 'confirmed') {
    tags.push(`<span class="tag tag-relocation">🏠 Accommodation Covered</span>`);
  } else if (job.accommodation_covered === 'unavailable') {
    tags.push(`<span class="tag tag-unavailable">✕ No Accommodation</span>`);
  }

  if (job.remote_type === 'remote_worldwide') {
    tags.push(`<span class="tag tag-remote-worldwide">🌍 Worldwide Remote</span>`);
  } else if (job.remote_type === 'remote_restricted') {
    tags.push(`<span class="tag tag-remote-restricted">Remote</span>`);
  }
  if (job.match_category && job.match_category !== 'irrelevant') {
    tags.push(`<span class="tag tag-category">${capitalize(job.match_category)}</span>`);
  }
  if (job.salary_min) {
    const sal = `${job.salary_currency || '$'}${formatSalary(job.salary_min)}${job.salary_max ? `–${formatSalary(job.salary_max)}` : '+'}`;
    tags.push(`<span class="tag tag-salary">💰 ${sal}</span>`);
  }
  tags.push(`<span class="tag tag-source">${escHtml(job.source_name || job.source || '?')}</span>`);

  // Original posting time and age
  const postedIso = job.posted_at || job.detected_at;
  const ageStr = formatDate(postedIso);
  const utcLabel = postedIso ? new Date(postedIso).toISOString().slice(5, 16).replace('T', ' ') + ' UTC' : '';
  const dateStr = utcLabel ? `${ageStr} (${utcLabel})` : ageStr;
  const applyUrl = getJobApplyUrl(job);
  const detailUrl = getJobDetailUrl(job);
  const displayLoc = job.work_location || job.location || 'Location not specified';

  // Match reason & description preview
  const reason = job.match_reasons?.slice(0, 3).join('; ') || '';
  const descPreview = formatDescriptionPreview(job.description, 140);

  // Action button states
  const isSaved = status === 'saved';
  const isApplied = status === 'applied';
  const isDismissed = status === 'dismissed';

  const applyControlHtml = applyUrl
    ? `<a href="${escHtml(applyUrl)}" target="_blank" rel="noopener noreferrer" class="btn-apply" title="Open ${escHtml(applyUrl)}">Apply →</a>`
    : `<span class="btn-apply disabled" title="No direct job-specific URL available from this source">Direct link unavailable</span>`;

  const detailControlHtml = detailUrl && detailUrl !== applyUrl
    ? `<a href="${escHtml(detailUrl)}" target="_blank" rel="noopener noreferrer" class="btn-detail" title="View job listing on ${escHtml(job.source_name || job.source || 'source')}">Details</a>`
    : '';

  card.innerHTML = `
    <div class="card-top">
      <div class="card-title">${escHtml(job.title || 'Untitled')}</div>
      <span class="score-badge ${scoreClass}">${score}/100</span>
    </div>
    <div class="card-company">${escHtml(job.company || '?')} · ${escHtml(displayLoc)}</div>
    ${tags.length ? `<div class="card-tags">${tags.join('')}</div>` : ''}
    ${descPreview ? `<div class="card-description">${escHtml(descPreview)}</div>` : ''}
    ${reason ? `<div class="card-reason">${escHtml(reason)}</div>` : ''}
    <div class="card-actions">
      ${applyControlHtml}
      ${detailControlHtml}
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
      renderCurrentView();
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

