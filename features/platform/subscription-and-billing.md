# Subscription & Billing

> **Category:** Platform & Infrastructure
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

Contruo uses a simple **per-seat, annual billing** model with a **single plan** (plus custom Enterprise pricing for large organizations). The price is displayed as a monthly equivalent but billed annually. There is **no free trial and no freemium tier** -- customers pay from day one. Mid-cycle seat additions are **prorated** to the organization's billing cycle. Payment processing is handled via **DodoPayments**.

## User Stories

- As an org owner, I want to subscribe to Contruo and pay annually per seat so that my team can start using the product.
- As an org owner, I want to see the price displayed per month (for easy comparison) but pay annually so that I get a clear annual commitment.
- As an admin, I want to add a new team member and have the system automatically charge a prorated fee for the remaining months in our billing cycle so that billing is fair and transparent.
- As an org owner, I want to see an upcoming renewal summary showing my total seats and annual cost so that I can budget for the renewal.
- As an org owner, I want to download invoices for my records so that I can submit them to accounting.
- As an org owner, I want to update my payment method so that billing continues uninterrupted.

## Key Requirements

### Pricing Model
- **Single plan**: one price per seat, no tiers or feature gating at MVP
- **Annual billing only**: price displayed as monthly equivalent (e.g., "$X/user/month, billed annually at $Y/user/year")
- **Custom Enterprise**: for organizations needing custom terms, volume discounts, or invoiced billing -- handled via sales, not self-serve
- **No free trial**: customers pay upfront (demo available on request)
- **No freemium tier**: no permanently free plan
- Guest accounts are free and do not count as seats

### Seat Management with Proration

**Adding a seat mid-cycle:**
- Admin invites a new team member
- System calculates the prorated charge for the remaining months until the org's next annual renewal date
- A confirmation dialog shows the prorated charge: *"Adding 1 seat. You'll be charged $X for the remaining N months. Your next annual renewal will include this seat at $Y/year."*
- Admin confirms -> payment is processed immediately -> new user gets access
- At the next annual renewal, the new seat renews at the full annual rate

**Removing a seat mid-cycle:**
- Admin removes a team member (or deactivates their account)
- **No refund** for the remaining months -- the seat was paid for through the end of the cycle
- The seat is **not renewed** at the next annual renewal
- The removed user loses access immediately

**Renewal:**
- All seats renew on the same date (the org's annual renewal date)
- One invoice for all active seats
- Renewal reminder sent via email 30 days and 7 days before renewal
- Auto-renewal by default (charges the payment method on file)

### Example Billing Scenario

```
Org created: March 1, 2027
Annual price: $600/seat/year ($50/mo displayed)
Initial seats: 3

March 1, 2027: Charged $1,800 (3 seats x $600)

September 1, 2027: Admin adds 1 seat (6 months remaining)
  -> Prorated charge: $300 (6/12 x $600)
  -> Total seats: 4

November 1, 2027: Admin removes 1 seat (4 months remaining)
  -> No refund
  -> Total seats going forward: 3

March 1, 2028 (renewal): Charged $1,800 (3 seats x $600)
```

### Payment Processing (DodoPayments)
- Integration with DodoPayments for payment processing
- Support for credit/debit cards and any methods DodoPayments offers
- Secure card storage (PCI-compliant via DodoPayments -- Contruo never touches raw card data)
- Automatic recurring billing on the annual renewal date
- Failed payment handling: retry logic, grace period, notification to org owner
- Payment method management: add, update, remove payment methods

### Billing Dashboard (Owner-Only)
- Current plan summary: seats, price per seat, annual total
- Next renewal date and expected charge
- Billing history: list of all past invoices with downloadable PDF invoices
- Payment method on file (last 4 digits, expiry, update button)
- Seat usage: current seats vs. active team members
- Add/remove seats action (with proration preview)

### Invoicing
- Automatic invoice generated for every payment (initial, prorated seat additions, renewals)
- Invoice includes: org name, billing address, line items (seats x price), taxes if applicable, total
- Downloadable as PDF from the billing dashboard
- Invoice emailed to the org owner automatically

### Failed Payment Handling
- If annual renewal payment fails:
  - Retry automatically after 1 day, 3 days, and 7 days
  - Email notification to org owner on each failure
  - Grace period (e.g., 14 days) during which the account remains active
  - After grace period: account downgraded to read-only (can view but not create/edit)
  - After extended non-payment (e.g., 30 days): account suspended with data preserved
  - Data is never deleted due to non-payment -- always recoverable upon re-subscription

## Nice-to-Have

- **Monthly billing option**: allow monthly payment at a higher effective rate (e.g., 20% more than the annual equivalent)
- **Volume discounts**: automatic discount for organizations with 10+, 25+, 50+ seats
- **Tiered plans**: Starter, Pro, Enterprise with different feature access and pricing
- **Usage-based add-ons**: metered billing for AI features (e.g., AI takeoff pages consumed)
- **Annual prepayment discount**: additional discount for multi-year commitments (2-year, 3-year)
- **Referral credits**: earn account credits for referring new organizations
- **Billing email delegation**: send invoices to an accounting email address different from the owner
- **Tax handling**: automatic tax calculation based on org location (may be required for compliance)

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Perpetual desktop license ($1,600-$2,600 one-time) or subscription ($89-$129/mo per seat). No team billing -- individual licenses. |
| Bluebeam | Subscription: $240-$400/year per seat depending on tier. Volume licensing for teams. Traditional software licensing model. |
| On-Screen Takeoff | Subscription: ~$200/mo per seat or annual plans. Per-seat licensing. No team billing dashboard. |
| Togal.AI | SaaS subscription pricing. Per-seat or per-project models. Pricing not publicly listed (contact sales). |

## Open Questions

- [ ] What is the actual price per seat? (This is a business decision, not a feature decision)
- [ ] Does DodoPayments support prorated subscription modifications natively, or do we need to calculate and charge manually?
- [ ] What currencies should be supported? (USD only? USD + INR? Multi-currency?)
- [ ] Should tax/GST be handled automatically or is it the customer's responsibility?
- [ ] What is the grace period length for failed payments before restricting access?
- [ ] Should Enterprise customers be billed via invoice (net-30/net-60) instead of credit card?

## Technical Considerations

- **DodoPayments integration**: use their SDK/API for subscription management, payment processing, and invoice generation. Evaluate whether DodoPayments handles proration natively or if custom logic is needed.
- **Subscription state machine**: each org's subscription has states: `active`, `past_due`, `grace_period`, `read_only`, `suspended`, `cancelled`. State transitions are triggered by payment events and timers.
- **Webhook handling**: DodoPayments (or any payment provider) sends webhooks for payment success, failure, subscription renewal, etc. These webhooks must be processed reliably (idempotent handlers, retry logic, dead letter queue for failures).
- **Seat count tracking**: the billing system must stay in sync with the actual user count. A reconciliation job should run periodically to catch any discrepancies.
- **Billing isolation**: billing data (payment methods, invoices, subscription state) should be in a separate schema or service from the application data for security and compliance.
- **Currency**: decide on a single currency at MVP (likely USD for international SaaS) and add multi-currency later if needed.
- **PCI compliance**: by using DodoPayments for all card handling, Contruo avoids PCI scope. Never store, log, or transmit raw card numbers.

## Notes

- The single-plan model is the simplest possible billing setup and is perfect for MVP. No tier confusion, no feature gating logic, no "which plan am I on?" support tickets. One price, one plan, all features included. Tiers can come later when there are distinct feature sets worth differentiating (e.g., AI features as a premium tier).
- No free trial is a bold but defensible choice for a professional B2B tool. Construction estimating firms have budget for software tools -- they're replacing $1,600+ PlanSwift licenses or $200+/mo OST subscriptions. A demo-on-request approach qualifies leads and ensures customers are serious.
- Annual-only billing simplifies cash flow and reduces churn (annual customers churn at much lower rates than monthly). The monthly price display is just for comparison shopping -- actual billing is annual.
- Proration for mid-cycle seat additions is fair and transparent. The confirmation dialog showing the exact charge before processing is critical for trust -- no surprise charges.
- The no-refund policy for removed seats is industry standard for annual billing and avoids complex refund/credit logic at MVP.
