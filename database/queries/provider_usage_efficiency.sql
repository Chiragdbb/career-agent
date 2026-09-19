-- Provider usage efficiency report (§4.4)
-- Run against PostgreSQL. Adjust the date window as needed.

-- Scraper split (jobs): Playwright vs Firecrawl
SELECT
  CASE
    WHEN provider_name ILIKE '%playwright%' THEN 'playwright'
    WHEN provider_name ILIKE '%firecrawl%' THEN 'firecrawl'
    ELSE 'other'
  END AS scraper,
  COUNT(*) AS attempts,
  COUNT(*) FILTER (WHERE success) AS successes
FROM provider_usage
WHERE operation IN ('job_extraction', 'scrape', 'scrape_cached')
  AND created_at >= now() - interval '7 days'
GROUP BY 1
ORDER BY attempts DESC;

-- Contact cache hit rate + tier fallback
SELECT
  COALESCE(payload->>'tier', 'unknown') AS tier,
  COUNT(*) AS attempts,
  COUNT(*) FILTER (WHERE success) AS successes,
  COUNT(*) FILTER (
    WHERE success AND (payload->>'cache_hit')::boolean IS TRUE
  ) AS cache_hits
FROM provider_usage
WHERE operation = 'contact_lookup'
  AND created_at >= now() - interval '7 days'
GROUP BY 1
ORDER BY attempts DESC;

-- Free-tier headroom (requests/day by provider)
SELECT
  provider_name,
  date_trunc('day', created_at) AS day,
  SUM(COALESCE(requests_count, 1)) AS requests,
  SUM(COALESCE(token_count, 0) + COALESCE(tokens_input, 0) + COALESCE(tokens_output, 0)) AS tokens,
  SUM(COALESCE(cost_estimate, 0)) AS cost_usd,
  COUNT(*) FILTER (WHERE NOT success) AS failures
FROM provider_usage
WHERE created_at >= now() - interval '7 days'
GROUP BY 1, 2
ORDER BY day DESC, requests DESC;

-- Cost per successful job / contact (approx)
SELECT
  'job' AS entity,
  SUM(COALESCE(cost_estimate, 0))
    / NULLIF(COUNT(*) FILTER (
        WHERE operation IN ('job_extraction', 'scrape') AND success
      ), 0) AS cost_per_success_usd
FROM provider_usage
WHERE created_at >= now() - interval '7 days'
UNION ALL
SELECT
  'contact',
  SUM(COALESCE(cost_estimate, 0))
    / NULLIF(COUNT(*) FILTER (
        WHERE operation = 'contact_lookup' AND success
      ), 0)
FROM provider_usage
WHERE created_at >= now() - interval '7 days';
