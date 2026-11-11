/**
 * Chrome extension storage layer.
 * Wraps chrome.storage.local for type safety and convenience.
 */

import { isWithinPostingAge } from './api.js';

const JOBS_KEY = 'jobradar_jobs';
const SETTINGS_KEY = 'jobradar_settings';
const SYNC_KEY = 'jobradar_last_sync';
const FINGERPRINTS_KEY = 'jobradar_fingerprints';

export const storage = {
  async getSettings() {
    const result = await chrome.storage.local.get(SETTINGS_KEY);
    return result[SETTINGS_KEY] || {};
  },

  async setSettings(settings) {
    await chrome.storage.local.set({ [SETTINGS_KEY]: settings });
  },

  async getJobs() {
    const result = await chrome.storage.local.get(JOBS_KEY);
    return result[JOBS_KEY] || [];
  },

  async saveJobs(jobs, maxAgeHours = 24) {
    // Merge new jobs with existing, keeping application_status from local
    const existing = await this.getJobs();
    const existingMap = {};
    for (const job of existing) {
      const st = job.application_status || 'new';
      // Drop cached un-saved jobs older than maxAgeHours
      if (st === 'saved' || st === 'applied' || isWithinPostingAge(job, maxAgeHours)) {
        existingMap[job.fingerprint] = job;
      }
    }

    // Track all fingerprints we've ever seen
    const fpSet = await this.getKnownFingerprints();

    for (const job of jobs) {
      if (!isWithinPostingAge(job, maxAgeHours)) {
        continue;
      }
      if (!fpSet.has(job.fingerprint)) {
        fpSet.add(job.fingerprint);
      }
      // Preserve local application_status if set
      const local = existingMap[job.fingerprint];
      if (local && local.application_status && local.application_status !== 'new') {
        job.application_status = local.application_status;
      }
      existingMap[job.fingerprint] = job;
    }

    const allJobs = Object.values(existingMap);
    // Sort by posted_at/detected_at desc, keep last 2000
    allJobs.sort((a, b) => new Date(b.posted_at || b.detected_at || 0) - new Date(a.posted_at || a.detected_at || 0));
    const trimmed = allJobs.slice(0, 2000);

    await chrome.storage.local.set({ [JOBS_KEY]: trimmed });
    await chrome.storage.local.set({ [FINGERPRINTS_KEY]: [...fpSet] });
  },

  async pruneExpiredJobs(maxAgeHours = 24) {
    const jobs = await this.getJobs();
    const kept = jobs.filter((job) => {
      const st = job.application_status || 'new';
      return st === 'saved' || st === 'applied' || isWithinPostingAge(job, maxAgeHours);
    });
    if (kept.length !== jobs.length) {
      await chrome.storage.local.set({ [JOBS_KEY]: kept });
    }
    return kept;
  },

  async getKnownFingerprints() {
    const result = await chrome.storage.local.get(FINGERPRINTS_KEY);
    return new Set(result[FINGERPRINTS_KEY] || []);
  },

  async getJobByFingerprint(fp) {
    const jobs = await this.getJobs();
    return jobs.find((j) => j.fingerprint === fp) || null;
  },

  async updateJobStatus(fingerprint, status) {
    const jobs = await this.getJobs();
    const idx = jobs.findIndex((j) => j.fingerprint === fingerprint);
    if (idx !== -1) {
      jobs[idx].application_status = status;
      await chrome.storage.local.set({ [JOBS_KEY]: jobs });
    }
  },

  async getNewJobCount() {
    const jobs = await this.getJobs();
    return jobs.filter((j) => j.application_status === 'new').length;
  },

  async setLastSync(data) {
    await chrome.storage.local.set({ [SYNC_KEY]: data });
  },

  async getLastSync() {
    const result = await chrome.storage.local.get(SYNC_KEY);
    return result[SYNC_KEY] || null;
  },

  async clearAll() {
    await chrome.storage.local.clear();
  },
};

