/**
 * API client for the JobRadar backend.
 * Talks to the local server (http://127.0.0.1:8765) or Supabase directly.
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
   * Direct Supabase query (alternative when local server is not running).
   * Uses anon key — only reads public data.
   */
  async fetchJobsFromSupabase(supabaseUrl, anonKey, { min_score = 0, limit = 200 } = {}) {
    const url = `${supabaseUrl}/rest/v1/jobs?select=*&match_score=gte.${min_score}&order=detected_at.desc&limit=${limit}`;
    const resp = await fetch(url, {
      headers: {
        apikey: anonKey,
        Authorization: `Bearer ${anonKey}`,
        'Content-Type': 'application/json',
      },
    });
    if (!resp.ok) throw new Error(`Supabase error ${resp.status}`);
    const jobs = await resp.json();
    return { jobs };
  },
};

