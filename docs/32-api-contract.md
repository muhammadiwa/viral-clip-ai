
# 32 — API Contract (Selected)
> All collection endpoints support `limit` and `offset` query parameters and return a `pagination` object alongside `count` for consistent table rendering. Identity, project, pipeline, compliance, and billing surfaces now persist to Postgres via SQLAlchemy, and video ingest returns presigned MinIO upload credentials when direct uploads are requested.
>
> ✅ Clip discovery, subtitle styling, TTS, transcript alignment, export, and retell endpoints now enqueue Celery workers that persist generated media (clips, subtitles, audio, exports, retell scripts) to Postgres/MinIO and advance pipeline statuses automatically.
> ✅ Environment variables control clip scoring weights, subtitle presets, TTS loudness targets, and branded export assets (intro/outro keys, watermark placement) so deployments can tune heuristics without code changes.
> ✅ Clip metadata edits via `PATCH /v1/clips/{id}` and transcript segment updates persist directly to Postgres, enabling inline editorial adjustments without re-queuing workers while media previews stream from registered artifacts.
> ✅ Video payloads now surface duration, frame rate, and resolution metadata, clips include scoring breakdowns, artifacts register both dry narration and mixed stems, and billing usage increments happen automatically when workers report job success.
> ✅ The QA runner can post qa.* metrics and `/v1/observability/qa-runs` summaries, now including locale/genre coverage, frame-diff counts, and reference artifact IDs that the dashboard visualises alongside regression findings.
> ✅ QA findings expose overlay links/metadata plus assignee details, due dates, and multi-stage statuses; the API enforces active-member assignments, emits webhook events when ownership or schedules change, and the dashboard lets reviewers triage ownership without leaving the run view.
> ✅ Webhook endpoints can subscribe to `qa.finding.updated` and `qa.assignment.updated` alongside the existing catalogue so external systems receive status and due-date changes in real time.
> ✅ Brand kit APIs expose presigned asset uploads (`assets:presign` + register/list/delete) so watermark/logo/font/intro/outro media can be managed without touching storage credentials, and workers consume the registered assets during subtitle styling and export.
> WebSocket consumers must supply the `token` (JWT) and `org_id` query parameters because browsers cannot attach the required headers; the server validates both values and active membership before streaming updates.
- [x] POST /v1/projects
- [x] POST /v1/users
- [x] GET  /v1/users
- [x] GET  /v1/users/{id}
- [x] GET  /v1/users/{id}/organizations
- [x] POST /v1/organizations
- [x] GET  /v1/organizations
- [x] GET  /v1/organizations/{id}
- [x] GET  /v1/organizations/{id}/members
- [x] POST /v1/organizations/{id}/members
- [x] GET  /v1/organizations/{id}/members/{membership_id}
- [x] PATCH /v1/organizations/{id}/members/{membership_id}
- [x] POST /v1/videos:ingest
- [x] POST /v1/videos/{id}:transcode
- [x] GET  /v1/videos/{id}
- [x] GET  /v1/projects/{id}/videos
- [x] GET  /v1/jobs/{id}
- [x] GET  /v1/jobs/projects/{project_id}
- [x] PATCH /v1/jobs/{id}
- [x] PATCH /v1/jobs/{id}/worker-status (requires `X-Worker-Token`)
- [x] POST /v1/jobs/{id}:cancel
- [x] POST /v1/jobs/{id}:pause
- [x] POST /v1/jobs/{id}:resume
- [x] POST /v1/jobs/{id}:retry
- [x] POST /v1/audit/logs
- [x] GET  /v1/audit/logs
- [x] POST /v1/dmca/notices
- [x] GET  /v1/dmca/notices
- [x] GET  /v1/dmca/notices/{id}
- [x] PATCH /v1/dmca/notices/{id}
- [x] POST /v1/webhooks/endpoints
- [x] GET  /v1/webhooks/endpoints
- [x] GET  /v1/webhooks/endpoints/{id}
- [x] PATCH /v1/webhooks/endpoints/{id}
- [x] GET  /v1/webhooks/deliveries
- [x] PATCH /v1/webhooks/deliveries/{id}
- [x] POST /v1/videos/{id}/generate-clips
- [x] GET  /v1/videos/{id}/clips
- [x] PATCH /v1/clips/{id}
- [x] POST /v1/clips/{id}/subtitles:style
- [x] POST /v1/clips/{id}/tts
- [x] POST /v1/videos/{id}/transcripts
- [x] GET  /v1/videos/{id}/transcripts
- [x] GET  /v1/videos/{id}/transcripts/{transcript_id}
- [x] POST /v1/videos/{id}/transcripts/{transcript_id}:align
- [x] PATCH /v1/videos/{id}/transcripts/{transcript_id}
- [x] POST /v1/projects/{id}/export
- [x] WS   /v1/jobs/{id}/events
- [x] POST /v1/projects/{id}/retell
- [x] GET  /v1/projects/{id}/retell
- [x] PATCH /v1/projects/{id}/retell/{retell_id}
- [x] GET  /v1/projects/{id}/artifacts
- [x] POST /v1/projects/{id}/artifacts
- [x] GET  /v1/videos/{id}/artifacts
- [x] POST /v1/videos/{id}/artifacts
- [x] GET  /v1/clips/{id}/artifacts
- [x] POST /v1/clips/{id}/artifacts
- [x] GET  /v1/billing/subscription
- [x] PUT  /v1/billing/subscription
- [x] GET  /v1/billing/usage
- [x] POST /v1/billing/usage
- [x] POST /v1/billing/payments
- [x] GET  /v1/billing/payments
- [x] GET  /v1/billing/payments/{order_id}
- [x] POST /v1/billing/payments/notifications
- [x] POST /v1/auth/token
- [x] GET  /v1/auth/me
- [x] POST /v1/observability/metrics
- [x] GET  /v1/observability/metrics
- [x] GET  /v1/observability/metrics/summary
- [x] GET  /v1/observability/slo/job-completion
- [x] POST /v1/observability/qa-runs
- [x] GET  /v1/observability/qa-runs
- [x] GET  /v1/observability/qa-runs/{run_id}
- [x] POST /v1/observability/qa-runs/{run_id}/findings
- [x] GET  /v1/observability/qa-runs/{run_id}/findings
- [x] PATCH /v1/observability/qa-runs/{run_id}/findings/{finding_id}
- [x] POST /v1/observability/qa-runs/{run_id}/reviews
- [x] GET  /v1/observability/qa-runs/{run_id}/reviews
- [x] PATCH /v1/observability/qa-runs/{run_id}/reviews/{review_id}
- [x] POST /v1/branding/brand-kits
- [x] GET  /v1/branding/brand-kits
- [x] GET  /v1/branding/brand-kits/{brand_kit_id}
- [x] PATCH /v1/branding/brand-kits/{brand_kit_id}
- [x] POST /v1/branding/brand-kits/{brand_kit_id}/assets:presign
- [x] POST /v1/branding/brand-kits/{brand_kit_id}/assets
- [x] GET  /v1/branding/brand-kits/{brand_kit_id}/assets
- [x] DELETE /v1/branding/brand-kits/{brand_kit_id}/assets/{asset_id}
