# Sprint 14: Billing & Subscription

> **Phase:** 5 - Collaboration & Billing
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint 03 (org management, team members)

## Sprint Goal

Integrate DodoPayments for subscription billing. At the end of this sprint, organizations can subscribe, pay annually per seat, add/remove seats with proration, view invoices, and manage their payment method.

---

## Tasks

### 1. DodoPayments Integration
- [ ] Set up DodoPayments account and API credentials
- [ ] Install DodoPayments SDK/client library
- [ ] Create `billing_service.py` for all payment-related logic
- [ ] Implement webhook handler: `POST /api/v1/webhooks/dodopayments`
  - Signature verification
  - Handle events: payment success, payment failure, subscription renewal, etc.
  - Idempotent processing (handle duplicate webhooks)

### 2. Subscription Creation
- [ ] During org signup (Sprint 02), redirect to DodoPayments checkout for initial payment
- [ ] Create subscription with: seat count = 1, annual billing, price per seat
- [ ] On payment success: activate subscription, create `subscriptions` record
- [ ] On payment failure: show error, allow retry
- [ ] Alternative: integrate payment form directly in the app (embedded checkout)

### 3. Billing Dashboard UI
- [ ] Create Billing tab in settings (Owner-only access)
- [ ] Current plan summary: seats, price per seat, annual total
- [ ] Next renewal date and expected charge
- [ ] Payment method on file: last 4 digits, card type, expiry
- [ ] "Update Payment Method" button -> DodoPayments hosted form or embedded form
- [ ] Seat usage indicator: X of Y seats used

### 4. Seat Management with Proration
- [ ] "Add Seat" flow:
  - Show prorated charge preview: "$X for remaining N months"
  - Confirmation dialog
  - Process prorated payment via DodoPayments
  - Increment seat count in subscription
  - Allow inviting the new team member
- [ ] "Remove Seat" flow:
  - Deactivate the team member
  - Decrement seat count (takes effect at next renewal)
  - No refund for remaining period
- [ ] Enforce seat limits: block invitations when all seats are occupied
- [ ] Show "Add Seat" prompt when trying to invite beyond current seat count

### 5. Invoice Management
- [ ] Generate invoices for every payment (initial, prorated additions, renewals)
- [ ] Store invoice references from DodoPayments
- [ ] Invoice history list in billing dashboard
- [ ] Download invoice as PDF
- [ ] Auto-email invoices to org owner on each payment

### 6. Failed Payment Handling
- [ ] Webhook handler for failed payments
- [ ] Retry logic: automatic retry after 1, 3, and 7 days
- [ ] Email notifications to owner on each failure
- [ ] Grace period: 14 days of full access after first failure
- [ ] After grace period: downgrade to read-only (view but can't create/edit)
- [ ] After 30 days: suspend account (data preserved, requires payment to reactivate)
- [ ] Subscription state machine: `active` -> `past_due` -> `grace_period` -> `read_only` -> `suspended`

### 7. Subscription State Enforcement
- [ ] Middleware to check subscription status on every API request
- [ ] `active` / `past_due` / `grace_period`: full access
- [ ] `read_only`: block write operations, allow reads
- [ ] `suspended`: block all access, show reactivation page
- [ ] Frontend: show banners for past_due and grace_period states

---

## Acceptance Criteria

- [ ] New organizations can subscribe and pay annually via DodoPayments
- [ ] Billing dashboard shows plan details, payment method, and next renewal
- [ ] Owner can add a seat with prorated charge shown and confirmed
- [ ] Owner can remove a seat (no refund, seat drops at renewal)
- [ ] Seat limits are enforced (can't invite beyond available seats)
- [ ] Invoices are generated and downloadable for every payment
- [ ] Failed payments trigger retry logic and email notifications
- [ ] After grace period, account downgrades to read-only
- [ ] Subscription state is enforced across all API endpoints

---

## Key References

- [Subscription & Billing Feature](../features/platform/subscription-and-billing.md)
- [Backend Architecture](../docs/architecture/backend.md) -- subscription schema, webhook handling
