
# 50 — Security & Compliance
JWT, RBAC, HSTS, CSP, CORS; ClamAV; audit logs; DMCA; rate limits; dependency scans.

### ✅ Progress
- RBAC checks enforce active memberships and role-based permissions on core API routes.
- Audit log repository and endpoints persist job control events for forensic review.
- DMCA notice intake endpoints document takedown requests and review decisions for compliance.
- Scoped rate limiting guards sensitive endpoints with configurable quotas per organization member.
- Webhook endpoint secrets and delivery audits provide traceability for outbound integrations.
- Midtrans webhook signature verification and environment-managed API keys keep payment processing compliant without hardcoded secrets.
- Background workers authenticate with an environment-managed `X-Worker-Token` when calling the dedicated job status endpoint, preventing untrusted systems from mutating pipeline state.
