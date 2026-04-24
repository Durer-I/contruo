# Sprint 14: Billing & Subscription

> **Phase:** 5 - Collaboration & Billing
> **Duration:** 2 weeks
> **Status:** In Progress (invoice email done; Celery / failure-email optional)
> **Depends On:** Sprint 03 (org management, team members)

## Sprint Goal

Integrate DodoPayments for subscription billing. At the end of this sprint, organizations can subscribe, pay annually per seat, add/remove seats with proration, view invoices, and manage their payment method.

---

## Tasks

### 1. DodoPayments Integration
- [x] Set up DodoPayments account and API credentials *(user env)*
- [x] Install DodoPayments SDK/client library (`dodopayments` in `backend/requirements.txt`)
- [x] Create `billing_service.py` for payment-related logic
- [x] Implement webhook handler: `POST /api/v1/webhooks/dodopayments`
  - [x] Signature verification when `DODOPAYMENTS_WEBHOOK_SECRET` is set; dev `unsafe_unwrap` if secret empty and `ENVIRONMENT=development`
  - [x] Handle events: `subscription.active|renewed|updated`, `payment.succeeded|failed`, `subscription.on_hold|failed`, `subscription.cancelled|expired` — persist subscription, invoices, failure state
  - [x] Idempotent processing by `webhook-id` (`billing_webhook_deliveries` table)

### 2. Subscription Creation
- [x] After org signup, redirect new owner to `/settings/billing?checkout=1` when `needs_subscription` (no `subscriptions` row yet)
- [x] `POST /api/v1/billing/checkout-session` — Dodo checkout with `product_cart` from `DODOPAYMENTS_SUBSCRIPTION_PRODUCT_ID`, metadata `org_id`
- [x] On payment success webhook: upsert `subscriptions`, record invoice, clear failure flags
- [x] On payment failure webhook: `past_due` + 14-day grace timestamps
- [x] Hosted checkout (return/cancel URLs use `APP_URL`)

### 3. Billing Dashboard UI
- [x] Billing tab (Owner — `MANAGE_BILLING`)
- [x] Plan summary, renewal window, seat usage
- [x] Payment method summary (from last `payment.succeeded` card fields)
- [x] “Update payment method” → Dodo `update_payment_method` payment link
- [x] Seat usage + actions: add seat (preview + confirm), remove 1 seat at next renewal

### 4. Seat Management with Proration
- [x] “Add seat”: `preview-add` + `add-confirm` via Dodo `preview_change_plan` / `change_plan` (`prorated_immediately`)
- [x] “Remove seat at renewal”: Dodo `change_plan` with `effective_at=next_billing_date`, `do_not_bill` + member deactivate schedules same in `org_service`
- [x] Enforce seat limits on **member** invites (`NO_SEATS_AVAILABLE`); guest invites skip seat check
- [x] Billing page surfaces add-seat flow when subscribed

### 5. Invoice Management
- [x] Store invoice per `payment.succeeded` (`provider_payment_id` dedupe, `pdf_url` from Dodo)
- [x] Invoice list in billing dashboard; open Dodo `invoice_url` when present
- [x] `GET /api/v1/billing/invoices/{id}/file` redirects to stored PDF URL *(owner JWT still required for route; prefer `pdf_url` in UI)*
- [x] Auto-email invoices to org owner on each payment (`email_service` + Resend; owner email from Supabase Auth)

### 6. Failed Payment Handling
- [x] Webhook handler for `payment.failed` / `subscription.on_hold`
- [ ] Celery beat: automatic retries at 1 / 3 / 7 days *(Dodo retries deliveries; add owner digest task later)*
- [ ] Email notifications to owner on each failure *(log today; Resend hook optional)*
- [x] Grace period: 14 days after first failure (`grace_period_ends_at`) — still **full API access** until transition
- [x] After grace: `read_only` (writes blocked except billing checkout / payment / seat endpoints)
- [x] After 30 days from first failure: `suspended` (only `/api/v1/billing/*` and `/api/v1/auth/me`)
- [x] State transitions evaluated lazily on authenticated requests (`refresh_subscription_automatic_transitions`)

### 7. Subscription State Enforcement
- [x] `enforce_org_subscription_state` dependency on all routes except health, auth, webhooks
- [x] `active` / `past_due`: full access (past_due shows banner via `/auth/me` `billing_banner`)
- [x] `read_only`: block mutating HTTP methods except billing payment/seat/checkout paths
- [x] `suspended`: block except billing + `GET /auth/me`
- [x] Frontend: banner from `user.billing_banner` (`AppShell`)

---

## Acceptance Criteria

- [x] New organizations can start Dodo checkout from Billing after signup redirect
- [x] Billing dashboard shows plan, payment method summary, renewal window when subscription exists
- [x] Owner can preview/add seat with proration via Dodo APIs
- [x] Owner can schedule seat removal at next renewal; deactivating a member attempts the same
- [x] Seat limits enforced on member invites when subscription exists
- [x] Invoices recorded from successful payments with PDF link when Dodo provides it
- [ ] Failed payments: full email + Celery retry calendar *(partial: webhooks + state machine + banner)*
- [x] After grace period, account downgrades to read-only API behavior
- [x] Subscription state enforced across authenticated API routes

---

## Configuration

Set in backend `.env.local`:

- `DODOPAYMENTS_API_KEY`
- `DODOPAYMENTS_WEBHOOK_SECRET`
- `DODOPAYMENTS_ENVIRONMENT` — `test_mode` or `live_mode`
- `DODOPAYMENTS_SUBSCRIPTION_PRODUCT_ID` — annual per-seat product id from Dodo dashboard
- `APP_URL` — used for checkout return/cancel URLs
- `EMAIL_API_KEY`, `EMAIL_PROVIDER=resend`, `EMAIL_FROM` — required for **invoice receipt** emails to the org owner (same as team invitations); if `EMAIL_API_KEY` is empty, receipts are skipped and logged.

Run migrations: `007_subscriptions_billing_webhooks`, `008_subscription_billing_extensions`.

---

## Key References

- [Subscription & Billing Feature](../features/platform/subscription-and-billing.md)
- [Backend Architecture](../docs/architecture/backend.md) -- subscription schema, webhook handling
