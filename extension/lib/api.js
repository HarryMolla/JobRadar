/**
 * API client for the JobRadar backend & GitHub Direct Cloud Mode.
 * Talks to the local server (http://127.0.0.1:8765) or directly to GitHub repository state.
 */

export const api = {
  async fetchJobs(baseUrl, { min_score = 0, limit = 200, status = null, apiKey = '' } = {}) {
    const url = new URL(`${baseUrl}/jobs`);
    url.searchParams.set('min_score', min_score);
    url.searchParams.set('limit', limit);
    if (status) url.searchParams.set('status', status);

    const headers = { 'Content-Type': 'application/json' };
    if (apiKey) headers['X-API-Key'] = apiKey;

    const resp = await fetch(url.toString(), { headers });
    if (!resp.ok) throw new Error(`API error ${resp.status}: ${await resp.text()}`);
    return resp.json();
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
  async fetchJobsFromGitHub(repo, { branch = 'main', token = '', min_score = 0, limit = 200 } = {}) {
    const cleanRepo = repo.replace(/^https?:\/\/github\.com\//, '').replace(/\/+$/, '');
    let jobs = [];

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
      const data = await resp.json();
      jobs = Object.values(data.jobs || {});
    } else {
      // Public repository raw content
      const rawUrl = `https://raw.githubusercontent.com/${cleanRepo}/${branch}/data/job_state.json?t=${Date.now()}`;
      const resp = await fetch(rawUrl);
      if (!resp.ok) throw new Error(`GitHub fetch error ${resp.status}. For private repos, provide a GitHub Token in settings.`);
      const data = await resp.json();
      jobs = Object.values(data.jobs || {});
    }

    // Filter by score and sort newest first
    jobs = jobs.filter((j) => (j.match_score || 0) >= min_score);
    jobs.sort((a, b) => new Date(b.detected_at || 0) - new Date(a.detected_at || 0));

    return { jobs: jobs.slice(0, limit) };
  },
};
