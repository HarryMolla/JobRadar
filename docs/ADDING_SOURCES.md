# Guide: Adding New Job Sources & Employer Career Boards

JobRadar is built with a modular adapter pattern. You can add new companies and feeds **without editing any Python code** simply by updating `sources_config.yaml`.

---

## 1. Adding a Greenhouse-Powered Employer

Companies using Greenhouse host their job board at `boards.greenhouse.io/{board_token}`.

1. Find the company's Greenhouse token. For example, if the career page URL is `https://boards.greenhouse.io/figma`, the token is `figma`.
2. Open `sources_config.yaml`.
3. Add the company under `greenhouse_boards`:
```yaml
greenhouse_boards:
  - token: "airbnb"
    company: "Airbnb"
```

---

## 2. Adding a Lever-Powered Employer

Companies using Lever host their job board at `jobs.lever.co/{slug}`.

1. For example, `https://jobs.lever.co/netflix` has slug `netflix`.
2. Add under `lever_companies`:
```yaml
lever_companies:
  - slug: "netflix"
    company: "Netflix"
```

---

## 3. Adding an Ashby-Powered Employer

Companies using Ashby host their job board at `jobs.ashbyhq.com/{slug}`.

1. For example, `https://jobs.ashbyhq.com/linear` has slug `linear`.
2. Add under `ashby_companies`:
```yaml
ashby_companies:
  - slug: "retool"
    company: "Retool"
```

---

## 4. Adding a Personio-Powered Employer

Companies using Personio provide an open XML feed at `https://{slug}.jobs.personio.de/xml`.

Add under `personio_companies`:
```yaml
personio_companies:
  - slug: "mycompany"
    company: "My Company"
```

---

## 5. Adding Custom RSS/Atom Feeds

Add any RSS or Atom feed under `rss_feeds`:
```yaml
rss_feeds:
  - url: "https://example.com/careers/feed.xml"
    source_name: "custom_feed"
    company: "Acme"
    remote_type: "remote_worldwide"
```

---

## 6. Disabling a Source

If a source is temporarily experiencing outages or anti-bot rate limits, silence it under `disabled_sources`:
```yaml
disabled_sources:
  - "wellfound"
  - "ycombinator"
```

