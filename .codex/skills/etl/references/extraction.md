# Extraction

Use this reference before scraping websites, calling APIs, downloading files, or parsing source documents.

## Source Access

- Confirm the source permits automated access and respect applicable terms.
- Check robots.txt or published API rules when scraping websites.
- Prefer official APIs, feeds, exports, or downloadable files over brittle HTML scraping when available.
- Use rate limits, timeouts, retries with backoff, and a clear user agent.
- Avoid bypassing access controls, paywalls, CAPTCHAs, or anti-abuse systems.

## HTTP and HTML

- Keep network access separate from parsing so tests can use saved fixtures.
- Store representative HTML/JSON fixtures when source shape matters.
- Use stable selectors based on semantic structure, attributes, or labels where possible.
- Detect empty, blocked, login, and error pages explicitly.
- Handle encoding, locale-specific numbers, currencies, dates, and whitespace.
- For JavaScript-rendered pages, prefer an API endpoint if one exists; use browser automation only when necessary.

## Files and Feeds

- Validate file type, size, encoding, headers, and required columns before processing.
- Keep source filenames, checksums, timestamps, and origin URLs where practical.
- Make partial downloads and corrupted files fail clearly.

## Reliability

- Support dry runs and small `--limit` style execution for new sources.
- Make retries safe and bounded.
- Avoid infinite crawling.
- Keep extraction logs useful without storing sensitive data.
