export type BillingSummary = {
  has_subscription: boolean;
  status: string | null;
  seat_count: number | null;
  seats_used: number;
  price_per_seat_cents: number | null;
  currency: string | null;
  billing_cycle_start: string | null;
  billing_cycle_end: string | null;
  payment_provider_id: string | null;
  next_renewal_total_cents: number | null;
  payment_method_summary: string | null;
  grace_period_ends_at: string | null;
  first_payment_failed_at: string | null;
  /** Purchased seats after pending change (from Dodo), if different from `seat_count` */
  scheduled_billed_seats?: number | null;
  /** ISO datetime when pending seat/plan change applies */
  scheduled_seat_change_effective_at?: string | null;
};

export type InvoiceRow = {
  id: string;
  amount_cents: number;
  currency: string;
  description: string | null;
  pdf_url: string | null;
  issued_at: string;
  provider_invoice_id: string | null;
  provider_payment_id?: string | null;
};

export type InvoiceListResponse = {
  invoices: InvoiceRow[];
};

export type SeatPreviewResponse = {
  current_seats: number;
  new_seats: number;
  estimated_charge_cents: number;
  currency: string;
  /** True when seats were already scheduled to drop at renewal */
  had_scheduled_reduction?: boolean;
  /** Purchased seats after next renewal when it differs from `new_seats` mid-cycle */
  renewal_target_seats?: number | null;
  /** True when charge is a local estimate (Dodo cannot preview until confirm) */
  estimated_charge_is_approximate?: boolean;
};
