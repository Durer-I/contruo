# Sprint 16: Performance & Deployment

> **Phase:** 6 - Launch Prep
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint 15

## Sprint Goal

Optimize performance, set up the production infrastructure, and deploy Contruo for launch. At the end of this sprint, the product is live and accessible to customers.

---

## Tasks

### 1. Performance Optimization
- [ ] **Plan viewer rendering**: profile and optimize PDF rendering at various zoom levels
  - Consider hybrid rendering (vector at low zoom, rasterized tiles at high zoom)
  - Optimize large sheet rendering (construction plans can be 5000+ pixels wide)
- [ ] **Measurement rendering**: profile with 500+ measurements on a single sheet
  - Batch rendering, canvas layer caching
  - Ensure zoom/pan remains smooth with heavy overlays
- [ ] **Quantities panel**: verify virtualized rendering handles 1000+ rows
- [ ] **API response times**: profile and optimize slow endpoints
  - Add database indexes where needed
  - Optimize aggregation queries for measurements/subtotals
- [ ] **Bundle size**: analyze and optimize Next.js bundle
  - Code splitting, lazy loading for non-critical routes
  - Tree shaking for unused dependencies
- [ ] **PDF processing**: optimize Celery worker for large PDFs (200+ pages)

### 2. Testing
- [ ] Write integration tests for critical flows:
  - Auth flow (signup, login, password reset)
  - Measurement CRUD (create, edit, delete, override)
  - Condition CRUD with assembly calculations
  - Export generation
  - Billing flows (subscribe, add seat, remove seat)
- [ ] Write end-to-end tests for key user journeys:
  - Sign up -> create project -> upload plan -> calibrate -> measure -> export
  - Invite team member -> team member joins -> collaborate
- [ ] Load testing: simulate 5 concurrent users on the same project
- [ ] Security testing: verify RLS policies, permission enforcement, JWT validation
- [ ] Test with real-world construction PDFs (various sizes, formats, complexities)

### 3. Production Infrastructure
- [ ] Set up production environment:
  - Supabase production project (separate from dev/staging)
  - Production Redis instance
  - Production Celery workers
  - DodoPayments production API keys
  - Liveblocks production project
- [ ] Deploy FastAPI backend (containerized):
  - Docker build with multi-stage Dockerfile
  - Choose hosting: Railway, Render, AWS ECS, DigitalOcean App Platform, or similar
  - Auto-scaling configuration
- [ ] Deploy Next.js frontend:
  - Vercel (simplest for Next.js) or similar
  - Custom domain setup (app.contruo.com)
- [ ] Set up Celery workers deployment (same host as backend or separate)
- [ ] SSL/TLS certificates for all domains

### 4. Staging Environment
- [ ] Set up staging environment mirroring production
- [ ] Deploy to staging first for final verification
- [ ] Test all integrations in staging (DodoPayments, Liveblocks, Supabase, email)
- [ ] Staging smoke test checklist

### 5. Monitoring & Observability
- [ ] Error tracking: Sentry (or similar) for both frontend and backend
- [ ] Application logging: structured logs, log aggregation
- [ ] Uptime monitoring: health check endpoints, alerting
- [ ] API performance monitoring: request latency, error rates
- [ ] Database monitoring: query performance, connection pool
- [ ] Celery task monitoring: queue depth, task success/failure rates

### 6. DNS & Domain
- [ ] Configure DNS for app.contruo.com (or chosen domain)
- [ ] Configure DNS for api.contruo.com (if separate)
- [ ] SSL certificates provisioned and active
- [ ] CORS configuration for production domains

### 7. Pre-Launch Checklist
- [ ] All environment variables configured in production
- [ ] DodoPayments webhooks pointing to production endpoint
- [ ] Liveblocks configured for production
- [ ] Email sending works in production (invitation, verification, password reset)
- [ ] RLS policies verified in production database
- [ ] Rate limiting active on all public endpoints
- [ ] CORS restricted to production frontend domain
- [ ] Error tracking verified (test error appears in Sentry)
- [ ] Backup strategy for production database
- [ ] Runbook documented: how to deploy, rollback, handle incidents

### 8. Launch
- [ ] Final staging smoke test
- [ ] Deploy to production
- [ ] Verify all features working in production
- [ ] Monitor for errors in first 24 hours
- [ ] Celebrate

---

## Acceptance Criteria

- [ ] Plan viewer renders smoothly at all zoom levels with 500+ measurements
- [ ] API response times are < 200ms for common endpoints
- [ ] Quantities panel handles 1000+ rows without lag
- [ ] Integration and E2E tests pass
- [ ] Production infrastructure is deployed and accessible
- [ ] Staging environment works identically to production
- [ ] Monitoring and error tracking are active and receiving data
- [ ] All pre-launch checklist items verified
- [ ] Product is live at the production URL

---

## Key References

- [Backend Architecture](../docs/architecture/backend.md) -- deployment, infrastructure
- [Design System](../docs/design/design-system.md) -- responsive behavior, minimum resolution
- All feature files -- for final verification against requirements
