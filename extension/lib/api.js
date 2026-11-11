/**
 * API client for the JobRadar backend & GitHub Direct Cloud Mode.
 * Talks to the local server (http://127.0.0.1:8765) or directly to GitHub repository state.
 */

export function isWithinPostingAge(job, maxAgeHours = 24) {
  if (!job || job.timestamp_reliable === false || !job.posted_at) {
    return false;
  }
  const raw = String(job.posted_at).trim();
  if (!raw || /^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    return false;
  }
  const normalized = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(raw)
    ? raw.replace(' ', 'T') + 'Z'
    : raw;
  const postedMs = Date.parse(normalized);
  if (Number.isNaN(postedMs)) {
    return false;
  }
  const ageHours = (Date.now() - postedMs) / 3600000;
  return ageHours >= 0 && ageHours <= maxAgeHours;
}

export const api = {
  async fetchJobs(baseUrl, { min_score = 0, limit = 200, status = null, apiKey = '', max_age_hours = 24 } = {}) {
    const url = new URL(`${baseUrl}/jobs`);
    url.searchParams.set('min_score', min_score);
    url.searchParams.set('limit', limit);
    url.searchParams.set('max_age_hours', max_age_hours);
    if (status) url.searchParams.set('status', status);

    const headers = { 'Content-Type': 'application/json' };
    if (apiKey) headers['X-API-Key'] = apiKey;

    const resp = await fetch(url.toString(), { headers });
    if (!resp.ok) throw new Error(`API error ${resp.status}: ${await resp.text()}`);
    const data = await resp.json();
    if (Array.isArray(data.jobs)) {
      data.jobs = data.jobs.filter((j) =>
        j.application_status === 'saved' ||
        j.application_status === 'applied' ||
        isWithinPostingAge(j, max_age_hours)
      );
    }
    return data;
  },

  async fetchStats(baseUrl, { apiKey = '' } = {}) {
    const headers = {};
    if (apiKey) headers['X-API-Key'] = apiKey;
    const resp = await fetch(`${baseUrl}/jobs/stats`, { headers });
    if (!resp.ok) throw new Error(`Stats API error ${resp.status}`);
    return resp.json();
  },

  async updateJobStatus(baseUrl, fingerprint, status, { apiKey = '' } = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (apiKey) headers['X-API-Key'] = apiKey;
    const resp = await fetch(`${baseUrl}/jobs/update`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ fingerprint, application_status: status }),
    });
    if (!resp.ok) throw new Error(`Update error ${resp.status}`);
    return resp.json();
  },

  async checkHealth(baseUrl, { apiKey = '' } = {}) {
    const headers = {};
    if (apiKey) headers['X-API-Key'] = apiKey;
    try {
      const resp = await fetch(`${baseUrl}/health`, { headers, signal: AbortSignal.timeout(5000) });
      return resp.ok;
    } catch {
      return false;
    }
  },

  /**
   * Direct GitHub Cloud Mode:
   * Fetches data/job_state.json directly from GitHub without needing a local server!
   * Works with public repos (raw.githubusercontent.com) or private repos (via optional GitHub token).
   */
  async fetchJobsFromGitHub(repo, { branch = 'main', token = '', min_score = 0, limit = 200, max_age_hours = 24 } = {}) {
    const cleanRepo = repo.replace(/^https?:\/\/github\.com\//, '').replace(/\/+$/, '');
    let data = {};

    if (token) {
      // Private repository access via GitHub API
      const apiUrl = `https://api.github.com/repos/${cleanRepo}/contents/data/job_state.json?ref=${branch}`;
      const resp = await fetch(apiUrl, {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github.v3.raw',
        },
      });
      if (!resp.ok) throw new Error(`GitHub API error ${resp.status}: ${await resp.text()}`);
      data = await resp.json();
    } else {
      // Public repository raw content
      const rawUrl = `https://raw.githubusercontent.com/${cleanRepo}/${branch}/data/job_state.json?t=${Date.now()}`;
      const resp = await fetch(rawUrl);
      if (!resp.ok) throw new Error(`GitHub fetch error ${resp.status}. For private repos, provide a GitHub Token in settings.`);
      data = await resp.json();
    }

    let jobs = Object.values(data.jobs || {});

    // Filter by score + strict posting age window and sort newest first
    jobs = jobs.filter((j) =>
      (j.match_score || 0) >= min_score && isWithinPostingAge(j, max_age_hours)
    );
    jobs.sort((a, b) => new Date(b.posted_at || b.detected_at || 0) - new Date(a.posted_at || a.detected_at || 0));

    return { jobs: jobs.slice(0, limit), uae_sources: data.uae_sources || [] };
  },

  async fetchUaeSources(baseUrl, { apiKey = '' } = {}) {
    const headers = {};
    if (apiKey) headers['X-API-Key'] = apiKey;
    const resp = await fetch(`${baseUrl}/sources/uae`, { headers });
    if (!resp.ok) throw new Error(`UAE sources API error ${resp.status}`);
    return resp.json();
  },
};
