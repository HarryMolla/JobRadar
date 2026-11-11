/**
 * Zero-dependency Node.js API server for JobRadar.
 * Runs instantly with: node scripts/server.js
 * No python or npm packages required!
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = parseInt(process.env.PORT || '8765', 10);
const HOST = process.env.HOST || '127.0.0.1';
const PRIMARY_DB_FILE = path.join(__dirname, '..', 'data', 'job_state.json');
const FALLBACK_DB_FILE = path.join(__dirname, '..', 'jobs_fallback.json');

// Ensure local db file exists
function getDBPath() {
  if (fs.existsSync(PRIMARY_DB_FILE)) return PRIMARY_DB_FILE;
  if (fs.existsSync(FALLBACK_DB_FILE)) return FALLBACK_DB_FILE;
  return PRIMARY_DB_FILE;
}

function loadDB() {
  const filePath = getDBPath();
  if (fs.existsSync(filePath)) {
    try {
      const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
      // Ensure jobs dictionary
      data.jobs = data.jobs || {};
      data.source_runs = data.source_runs || [];
      return data;
    } catch (e) {
      console.error(`Error reading ${filePath}:`, e.message);
    }
  }
  return { version: 1, last_updated: new Date().toISOString(), stats: {}, jobs: {}, source_runs: [] };
}

function saveDB(data) {
  const targetDir = path.dirname(PRIMARY_DB_FILE);
  if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true });
  }
  fs.writeFileSync(PRIMARY_DB_FILE, JSON.stringify(data, null, 2), 'utf8');
}

// Initialize seed data if empty so the extension has demo jobs to display immediately
const db = loadDB();
if (!db.jobs || Object.keys(db.jobs).length === 0) {
  const fixturePath = path.join(__dirname, '..', 'backend', 'tests', 'fixtures', 'sample_jobs.json');
  if (fs.existsSync(fixturePath)) {
    try {
      const fixtures = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
      db.jobs = {};
      fixtures.forEach(j => {
        const fp = `${j.source}::${j.source_id}`;
        j.fingerprint = fp;
        db.jobs[fp] = j;
      });
      saveDB(db);
      console.log(`Loaded ${fixtures.length} sample jobs into local storage`);
    } catch (e) {
      console.error('Error loading sample fixtures:', e.message);
    }
  }
}

const server = http.createServer((req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-API-Key');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const parsedUrl = url.parse(req.url, true);
  const pathname = parsedUrl.pathname.replace(/\/+$/, '') || '/';
  const query = parsedUrl.query;

  // Health
  if (req.method === 'GET' && pathname === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', version: '1.0.0', runner: 'node' }));
    return;
  }

  // Get jobs
  if (req.method === 'GET' && pathname === '/jobs') {
    const minScore = parseInt(query.min_score || '0', 10);
    const status = query.status || null;
    const limit = parseInt(query.limit || '200', 10);
    const maxAgeHours = parseFloat(query.max_age_hours || process.env.MAX_POSTING_AGE_HOURS || '24');

    const currentDB = loadDB();
    let jobs = Object.values(currentDB.jobs || {});
    jobs = jobs.filter(j => (j.match_score || 0) >= minScore);
    if (status) {
      jobs = jobs.filter(j => (j.application_status || 'new') === status);
    }
    if (!status || (status !== 'saved' && status !== 'applied')) {
      const nowMs = Date.now();
      jobs = jobs.filter(j => {
        if (j.application_status === 'saved' || j.application_status === 'applied') return true;
        if (j.timestamp_reliable === false || !j.posted_at) return false;
        const postedMs = Date.parse(j.posted_at);
        if (Number.isNaN(postedMs)) return false;
        const ageHours = (nowMs - postedMs) / 3600000;
        return ageHours >= 0 && ageHours <= maxAgeHours;
      });
    }
    jobs.sort((a, b) => new Date(b.posted_at || b.detected_at || 0) - new Date(a.posted_at || a.detected_at || 0));

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ jobs: jobs.slice(0, limit), count: jobs.length }));
    return;
  }

  // Get stats
  if (req.method === 'GET' && pathname === '/jobs/stats') {
    const currentDB = loadDB();
    const jobs = Object.values(currentDB.jobs || {});
    const counts = {};
    jobs.forEach(j => {
      counts[j.source] = (counts[j.source] || 0) + 1;
    });
    const sources = Object.entries(counts).map(([src, count]) => ({
      source: src,
      total_jobs: count,
      last_success: new Date().toISOString(),
      last_error: ''
    }));

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ sources }));
    return;
  }

  // Update job status
  if (req.method === 'POST' && pathname === '/jobs/update') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        const { fingerprint, application_status } = data;
        if (!fingerprint || !application_status) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'fingerprint and application_status required' }));
          return;
        }

        const currentDB = loadDB();
        if (currentDB.jobs && currentDB.jobs[fingerprint]) {
          currentDB.jobs[fingerprint].application_status = application_status;
          saveDB(currentDB);
        }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, fingerprint, status: application_status }));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, HOST, () => {
  console.log(`\n======================================================`);
  console.log(`🎯 JobRadar API Server running at http://${HOST}:${PORT}`);
  console.log(`   Chrome Extension is now connected!`);
  console.log(`   Press Ctrl+C to stop.`);
  console.log(`======================================================\n`);
});

