# Service Level Agreement (SLA)

_Effective date: 2025-01-01_

## Scope

This SLA applies to LeadLab **Cloud** (managed hosting). Self-hosted deployments are not covered.

## Uptime commitment

| Plan | Monthly uptime target |
|---|---|
| Free | Best effort |
| Pro | 99.5% |

Uptime is calculated as: `(total_minutes − downtime_minutes) / total_minutes × 100`.

Scheduled maintenance windows (announced 48 h in advance) are excluded from downtime.

## Support response times

| Priority | Description | Pro response | Free response |
|---|---|---|---|
| P1 – Critical | Service unavailable / data loss risk | 4 h | 48 h |
| P2 – High | Major feature broken, no workaround | 8 h | 72 h |
| P3 – Medium | Feature degraded, workaround exists | 2 business days | Best effort |
| P4 – Low | Questions, feature requests | 5 business days | Best effort |

Contact: **support@leadlab.io**

## Credits

If uptime falls below the target in any calendar month:

| Actual uptime | Credit |
|---|---|
| 99.0–99.5% | 10% of monthly fee |
| 95.0–99.0% | 25% of monthly fee |
| < 95.0% | 50% of monthly fee |

Credits must be requested within 30 days of the incident.

## Exclusions

- Downtime caused by the customer's own code or integrations
- Force majeure events
- Free plan accounts
