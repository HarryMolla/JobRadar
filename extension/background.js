/**
 * JobRadar Background Service Worker (Manifest V3)
 * Handles alarms, notifications, and data sync.
 */

import { storage } from './lib/storage.js';
import { api, isWithinPostingAge } from './lib/api.js';
import { showJobNotification } from './lib/notifications.js';

const ALARM_NAME = 'jobradar-sync';
const SYNC_INTERVAL_MINUTES = 30; // Adjust as needed

// ----- Initialization -----
chrome.runtime.onInstalled.addListener(async (details) => {
  console.log('[JobRadar] Installed:', details.reason);

  // Set default settings
  const existing = await storage.getSettings();
  if (!existing.initialized) {
    await storage.setSettings({
      initialized: true,
      apiUrl: 'http://127.0.0.1:8765',
      apiKey: '',
      supabaseUrl: '',
      supabaseAnonKey: '',
      minScore: 50,
      syncIntervalMinutes: SYNC_INTERVAL_MINUTES,
      notificationsEnabled: true,
      categories: ['design', 'frontend', 'wordpress', 'marketing'],
      theme: 'system',
    });
  }

  // Create alarm
  await setupAlarm();
});

chrome.runtime.onStartup.addListener(setupAlarm);

async function setupAlarm() {
  const existing = await chrome.alarms.get(ALARM_NAME);
  if (!existing) {
    const settings = await storage.getSettings();
    const interval = settings.syncIntervalMinutes || SYNC_INTERVAL_MINUTES;
    chrome.alarms.create(ALARM_NAME, {
      delayInMinutes: 1,
      periodInMinutes: interval,
    });
    console.log(`[JobRadar] Alarm set: every ${interval} minutes`);
  }
}

// ----- Alarm handler -----
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === ALARM_NAME) {
    console.log('[JobRadar] Alarm fired — syncing jobs');
    await syncJobs();
  }
});

// ----- Manual sync via message -----
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'SYNC_NOW') {
    syncJobs().then((result) => sendResponse({ ok: true, ...result }));
    return true; // keep channel open for async
  }
  if (message.type === 'GET_BADGE') {
    storage.getNewJobCount().then((count) => sendResponse({ count }));
    return true;
  }
});

// ----- Core sync function -----
async function syncJobs() {
  const settings = await storage.getSettings();
  const apiUrl = settings.apiUrl || 'http://127.0.0.1:8765';
  const minScore = settings.minScore || 50;
  const categories = settings.categories || ['design', 'frontend', 'wordpress', 'marketing'];

  let newJobCount = 0;

  try {
    let result = null;

    // Try local API first
    const isLocalAlive = await api.checkHealth(apiUrl, { apiKey: settings.apiKey || '' });
    if (isLocalAlive) {
      result = await api.fetchJobs(apiUrl, {
        min_score: minScore,
        limit: 200,
        apiKey: settings.apiKey || '',
      });
      try {
        const uaeRes = await api.fetchUaeSources(apiUrl, { apiKey: settings.apiKey || '' });
        if (Array.isArray(uaeRes?.uae_sources) && uaeRes.uae_sources.length > 0) {
          await storage.setUaeSources(uaeRes.uae_sources);
        }
      } catch {
        // Ignore if UAE sources endpoint not available
      }
    } else if (settings.githubRepo) {
      // Direct Cloud Mode: fetch data/job_state.json directly from GitHub
      result = await api.fetchJobsFromGitHub(settings.githubRepo, {
        token: settings.githubToken || '',
        branch: settings.githubBranch || 'main',
        min_score: minScore,
        limit: 200,
      });
      if (Array.isArray(result?.uae_sources) && result.uae_sources.length > 0) {
        await storage.setUaeSources(result.uae_sources);
      }
    } else {
      throw new Error('Local API is offline. Run "node scripts/server.js" or enter your GitHub Repo in Settings.');
    }

    if (!result?.jobs || !Array.isArray(result.jobs)) {
      console.warn('[JobRadar] Invalid jobs response:', result);
      await storage.setLastSync({ status: 'error', error: 'Invalid response', at: new Date().toISOString() });
      return { newJobs: 0 };
    }

    // Filter by category and strict 24-hour posting age
    const filtered = result.jobs.filter((job) => {
      if (!isWithinPostingAge(job, 24)) return false;
      if (categories.length === 0) return true;
      return categories.includes(job.match_category);
    });

    // Find truly new jobs (not seen by extension before)
    const knownFingerprints = await storage.getKnownFingerprints();
    const newJobs = filtered.filter((job) => !knownFingerprints.has(job.fingerprint));

    // Store all filtered jobs locally
    await storage.saveJobs(filtered);

    // Show notification for new ones
    if (settings.notificationsEnabled && newJobs.length > 0) {
      newJobCount = newJobs.length;
      for (const job of newJobs.slice(0, 3)) {
        await showJobNotification(job);
      }
      if (newJobs.length > 3) {
        await chrome.notifications.create(`jobradar-bulk-${Date.now()}`, {
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: `JobRadar — ${newJobs.length} new jobs found`,
          message: `Tap to view all ${newJobs.length} new matching jobs`,
          priority: 1,
        });
      }
    }

    // Update badge
    const badgeCount = await storage.getNewJobCount();
    updateBadge(badgeCount);

    await storage.setLastSync({
      status: 'ok',
      at: new Date().toISOString(),
      newJobs: newJobCount,
      totalJobs: filtered.length,
    });

    console.log(`[JobRadar] Sync complete: ${newJobs.length} new, ${filtered.length} total`);
    return { newJobs: newJobCount };

  } catch (err) {
    console.error('[JobRadar] Sync error:', err.message);
    await storage.setLastSync({
      status: 'error',
      error: err.message,
      at: new Date().toISOString(),
    });
    return { newJobs: 0, error: err.message };
  }
}

function updateBadge(count) {
  if (count > 0) {
    chrome.action.setBadgeText({ text: count > 99 ? '99+' : String(count) });
    chrome.action.setBadgeBackgroundColor({ color: '#e74c3c' });
  } else {
    chrome.action.setBadgeText({ text: '' });
  }
}

// Handle notification clicks → open apply URL
chrome.notifications.onClicked.addListener(async (notifId) => {
  if (notifId.startsWith('jobradar-job-')) {
    const fp = notifId.replace('jobradar-job-', '');
    const job = await storage.getJobByFingerprint(fp);
    if (job?.url) {
      chrome.tabs.create({ url: job.url });
    }
  } else if (notifId.startsWith('jobradar-bulk-')) {
    chrome.action.openPopup();
  }
  chrome.notifications.clear(notifId);
});

chrome.notifications.onButtonClicked.addListener(async (notifId, btnIdx) => {
  if (notifId.startsWith('jobradar-job-') && btnIdx === 0) {
    const fp = notifId.replace('jobradar-job-', '');
    const job = await storage.getJobByFingerprint(fp);
    if (job?.url) {
      chrome.tabs.create({ url: job.url });
    }
    chrome.notifications.clear(notifId);
  }
});

