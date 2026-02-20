# CloudWatch Logs Insights Query Reference

All queries target the log group(s) for the relevant Lambda function(s).
Select the appropriate log group in the Logs Insights console before running.

---

## Find all ERROR and CRITICAL events in the last hour

```
filter level in ["ERROR", "CRITICAL"]
| sort @timestamp desc
| limit 50
```

## Count errors per function in the last 24 hours

```
stats count() as error_count by function_name
| filter level in ["ERROR", "CRITICAL"]
| sort error_count desc
```

## Measure p50/p95/p99 handler duration (all functions)

```
filter ispresent(duration_ms)
| stats
    pct(duration_ms, 50) as p50_ms,
    pct(duration_ms, 95) as p95_ms,
    pct(duration_ms, 99) as p99_ms
  by function_name
```

## Trace all log lines for a single Lambda invocation

```
filter request_id = "YOUR-REQUEST-ID-HERE"
| sort @timestamp asc
```

## Count PHI scrubber triggers (compliance check)

```
filter @message like /\[REDACTED\]/
| stats count() as phi_attempts by function_name
| sort phi_attempts desc
```

## Find all 404 Not Found errors (possible probing/abuse)

```
filter error_code = "NOT_FOUND"
| stats count() as not_found_count by bin(1h)
| sort @timestamp desc
```

## YouTube API errors over time

```
filter function_name = "education-videos"
  and error_code = "EXTERNAL_SERVICE_ERROR"
| stats count() as yt_errors by bin(30m)
```

## Slow queries (DB calls over 500ms)

```
filter ispresent(duration_ms) and duration_ms > 500
| sort duration_ms desc
| fields @timestamp, function_name, message, duration_ms, query_template
| limit 20
```
