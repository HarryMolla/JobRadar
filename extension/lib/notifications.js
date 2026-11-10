/**
 * Chrome notification helpers.
 */

export async function showJobNotification(job) {
  const notifId = `jobradar-job-${job.fingerprint}`;

  const remoteLabel = {
    remote_worldwide: '🌍 Remote (Worldwide)',
    remote_restricted: '🔒 Remote (Restricted)',
    hybrid: '🏢 Hybrid',
    onsite: '🏢 On-site',
    unknown: '',
  }[job.remote_type] || '';

  const sponsorLabel = job.sponsorship === 'sponsored' ? ' · ✈️ Visa Sponsor' : '';

  const locationLine = [job.location, remoteLabel, sponsorLabel]
    .filter(Boolean)
    .join(' · ');

  const reasonText = job.match_reasons?.slice(0, 2).join('; ') || 'Matched your criteria';

  await chrome.notifications.create(notifId, {
    type: 'basic',
    iconUrl: 'icons/icon48.png',
    title: `${job.title} @ ${job.company}`,
    message: `${locationLine}\nScore: ${job.match_score}/100 — ${reasonText}`,
    priority: 2,
    buttons: [{ title: 'Apply Now' }],
  });
}

