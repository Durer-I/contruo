"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { BillingSummary, InvoiceListResponse, SeatPreviewResponse } from "@/types/billing";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

function formatMoney(cents: number | null | undefined, currency: string | null | undefined) {
  if (cents == null) return "—";
  const cur = currency || "USD";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: cur }).format(
    cents / 100
  );
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeZone: "UTC",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default function BillingPage() {
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [invoices, setInvoices] = useState<InvoiceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [preview, setPreview] = useState<SeatPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [addQty, setAddQty] = useState(1);
  const [addWorking, setAddWorking] = useState(false);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [removeQty, setRemoveQty] = useState(1);
  const [removeWorking, setRemoveWorking] = useState(false);
  const [pmWorking, setPmWorking] = useState(false);
  const checkoutStarted = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, inv] = await Promise.all([
        api.get<BillingSummary>("/api/v1/billing"),
        api.get<InvoiceListResponse>("/api/v1/billing/invoices"),
      ]);
      setSummary(s);
      setInvoices(inv);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 403) {
        setError(
          e.message ||
            "You do not have permission to access billing (owner role required)."
        );
      } else if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Failed to load billing.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!addDialogOpen) return;
    const qty = Math.min(100, Math.max(1, Math.floor(addQty) || 1));
    const ac = new AbortController();
    const t = setTimeout(() => {
      void (async () => {
        setPreviewLoading(true);
        setError(null);
        try {
          const p = await api.post<SeatPreviewResponse>(
            "/api/v1/billing/seats/preview-add",
            { add: qty },
            { signal: ac.signal }
          );
          if (!ac.signal.aborted) setPreview(p);
        } catch (e: unknown) {
          if (ac.signal.aborted) return;
          if (e instanceof ApiError) setError(e.message);
          else setError("Could not preview seat add.");
          if (!ac.signal.aborted) setPreview(null);
        } finally {
          if (!ac.signal.aborted) setPreviewLoading(false);
        }
      })();
    }, 350);
    return () => {
      ac.abort();
      clearTimeout(t);
    };
  }, [addDialogOpen, addQty]);

  async function startCheckout() {
    setCheckoutLoading(true);
    setError(null);
    try {
      const { checkout_url } = await api.post<{ checkout_url: string }>(
        "/api/v1/billing/checkout-session",
        {
          return_path: "/settings/billing",
          cancel_path: "/settings/billing",
          seat_count: 1,
        }
      );
      window.location.href = checkout_url;
    } catch (e: unknown) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Could not start checkout.");
      }
      setCheckoutLoading(false);
    }
  }

  function openAddSeatDialog() {
    setError(null);
    setAddQty(1);
    setAddDialogOpen(true);
  }

  async function confirmAddSeat() {
    const add = Math.min(100, Math.max(1, Math.floor(addQty) || 1));
    setAddWorking(true);
    setError(null);
    try {
      await api.post("/api/v1/billing/seats/add-confirm", { add });
      setAddDialogOpen(false);
      setPreview(null);
      await load();
    } catch (e: unknown) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Could not add seats.");
    } finally {
      setAddWorking(false);
    }
  }

  function openRemoveSeatsDialog() {
    const purchased = summary?.seat_count ?? 0;
    const inUse = summary?.seats_used ?? 0;
    const maxRemovable = Math.max(0, Math.min(purchased > 0 ? purchased - 1 : 0, purchased - inUse));
    if (maxRemovable < 1) return;
    setError(null);
    setRemoveQty(1);
    setRemoveDialogOpen(true);
  }

  async function confirmScheduleRemoveSeats() {
    const purchased = summary?.seat_count ?? 0;
    const inUse = summary?.seats_used ?? 0;
    const maxRemovable = Math.max(0, Math.min(purchased > 0 ? purchased - 1 : 0, purchased - inUse));
    const remove = Math.min(maxRemovable, Math.max(1, Math.floor(removeQty) || 1));
    setRemoveWorking(true);
    setError(null);
    try {
      await api.post("/api/v1/billing/seats/schedule-remove", { remove });
      setRemoveDialogOpen(false);
      await load();
    } catch (e: unknown) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Could not schedule seat removal.");
    } finally {
      setRemoveWorking(false);
    }
  }

  async function updatePaymentMethod() {
    setPmWorking(true);
    setError(null);
    try {
      const { payment_url } = await api.post<{ payment_url: string }>(
        "/api/v1/billing/update-payment-method",
        { return_path: "/settings/billing" }
      );
      window.location.href = payment_url;
    } catch (e: unknown) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Could not open payment method update.");
      setPmWorking(false);
    }
  }

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("checkout");
    if (q === "1" && !checkoutStarted.current) {
      checkoutStarted.current = true;
      void startCheckout();
    }
    // startCheckout is stable for this page
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !summary) {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl">
          <h1 className="mb-2 text-xl font-semibold">Billing</h1>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  if (!summary || !invoices) {
    return null;
  }

  const purchasedSeats = summary.seat_count ?? 0;
  const billableSeatsInUse = summary.seats_used;
  const maxRemovableSeats = Math.max(
    0,
    Math.min(purchasedSeats > 0 ? purchasedSeats - 1 : 0, purchasedSeats - billableSeatsInUse)
  );

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-8">
        <div>
          <h1 className="text-xl font-semibold">Billing</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            DodoPayments subscription, seats, and invoices.
          </p>
        </div>

        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}

        <section className="rounded-lg border border-border bg-surface p-5">
          <h2 className="text-sm font-medium text-foreground">Plan</h2>
          {!summary.has_subscription ? (
            <div className="mt-4 space-y-3">
              {summary.status === "cancelled" || summary.status === "suspended" ? (
                <p className="text-sm text-muted-foreground">
                  This organization&apos;s subscription is{" "}
                  <span className="font-medium capitalize text-foreground">{summary.status}</span>.
                  Complete checkout below to start a new subscription and restore full access.
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Subscribe to enable paid seats. After checkout, webhooks activate your plan here.
                </p>
              )}
              <Button onClick={() => void startCheckout()} disabled={checkoutLoading}>
                {checkoutLoading ? "Redirecting…" : "Subscribe (checkout)"}
              </Button>
            </div>
          ) : (
            <>
              {summary.scheduled_billed_seats != null &&
              summary.scheduled_seat_change_effective_at != null &&
              summary.seat_count != null &&
              summary.scheduled_billed_seats !== summary.seat_count ? (
                <div
                  className="mb-4 rounded-md border border-border bg-muted/40 p-3 text-sm text-foreground"
                  role="status"
                >
                  <p className="font-medium">Upcoming seat change</p>
                  <p className="mt-1 text-muted-foreground">
                    You have <span className="font-medium text-foreground">{summary.seats_used}</span>{" "}
                    active member{summary.seats_used === 1 ? "" : "s"} using seats. This billing period
                    you remain entitled to{" "}
                    <span className="font-medium text-foreground">{summary.seat_count}</span> purchased
                    seat{summary.seat_count === 1 ? "" : "s"}.
                    {summary.scheduled_billed_seats < summary.seat_count ? (
                      <>
                        {" "}
                        <span className="font-medium text-foreground">
                          {summary.seat_count - summary.scheduled_billed_seats}
                        </span>{" "}
                        seat{summary.seat_count - summary.scheduled_billed_seats === 1 ? "" : "s"} will
                        drop off your plan at the end of the cycle (
                        <span className="font-medium text-foreground">
                          {formatDate(summary.scheduled_seat_change_effective_at)}
                        </span>
                        ), leaving{" "}
                        <span className="font-medium text-foreground">{summary.scheduled_billed_seats}</span>{" "}
                        purchased seat{summary.scheduled_billed_seats === 1 ? "" : "s"}.
                      </>
                    ) : (
                      <>
                        {" "}
                        Purchased seats will increase to{" "}
                        <span className="font-medium text-foreground">{summary.scheduled_billed_seats}</span> on{" "}
                        <span className="font-medium text-foreground">
                          {formatDate(summary.scheduled_seat_change_effective_at)}
                        </span>
                        .
                      </>
                    )}
                  </p>
                </div>
              ) : null}
              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground">Status</dt>
                  <dd className="font-medium capitalize">{summary.status ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Seats</dt>
                  <dd className="font-medium">
                    {summary.seats_used} active
                    {summary.seat_count != null ? ` · ${summary.seat_count} purchased this period` : ""}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Price / seat / year</dt>
                  <dd className="font-medium">
                    {formatMoney(summary.price_per_seat_cents, summary.currency)}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Next renewal total</dt>
                  <dd className="font-medium">
                    {formatMoney(summary.next_renewal_total_cents, summary.currency)}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-muted-foreground">Current period</dt>
                  <dd className="font-medium">
                    {formatDate(summary.billing_cycle_start)} —{" "}
                    {formatDate(summary.billing_cycle_end)}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-muted-foreground">Payment method</dt>
                  <dd className="font-medium">
                    {summary.payment_method_summary ?? "Not on file yet"}
                  </dd>
                </div>
              </dl>
              <div className="mt-6 flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => void updatePaymentMethod()} disabled={pmWorking}>
                  {pmWorking ? "Opening…" : "Update payment method"}
                </Button>
                <Button variant="secondary" onClick={openAddSeatDialog}>
                  Add seats (prorated)
                </Button>
                <Button
                  variant="outline"
                  onClick={openRemoveSeatsDialog}
                  disabled={removeWorking || maxRemovableSeats < 1}
                >
                  Remove seats at next renewal
                </Button>
              </div>
              {purchasedSeats >= 2 && maxRemovableSeats < 1 ? (
                <p className="mt-2 max-w-prose text-sm text-muted-foreground">
                  Scheduling fewer seats at renewal isn&apos;t available while every purchased seat is
                  covered by an active member. Remove or deactivate members first, then try again.
                </p>
              ) : null}
            </>
          )}
        </section>

        <section className="rounded-lg border border-border bg-surface p-5">
          <h2 className="text-sm font-medium text-foreground">Invoices</h2>
          {invoices.invoices.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">No invoices yet.</p>
          ) : (
            <ul className="mt-4 divide-y divide-border text-sm">
              {invoices.invoices.map((inv) => (
                <li
                  key={inv.id}
                  className="flex flex-wrap items-center justify-between gap-2 py-3"
                >
                  <div>
                    <p className="font-medium">{formatMoney(inv.amount_cents, inv.currency)}</p>
                    <p className="text-muted-foreground">
                      {formatDate(inv.issued_at)}
                      {inv.description ? ` · ${inv.description}` : ""}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {inv.pdf_url ? (
                      <a
                        href={inv.pdf_url}
                        className="text-primary underline-offset-4 hover:underline"
                        target="_blank"
                        rel="noreferrer"
                      >
                        PDF
                      </a>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <Dialog
        open={addDialogOpen}
        onOpenChange={(open) => {
          setAddDialogOpen(open);
          if (!open) setPreview(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add seats</DialogTitle>
            <DialogDescription>
              {preview?.had_scheduled_reduction
                ? "You already have purchased seats scheduled to come off your plan at the next renewal. Adding seats now updates or cancels that schedule and may change today’s charge."
                : "Seats are charged immediately with proration for the rest of this billing period."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <label htmlFor="add-seat-qty" className="text-sm font-medium text-foreground">
                Number of seats to add
              </label>
              <Input
                id="add-seat-qty"
                type="number"
                min={1}
                max={100}
                className="max-w-[8rem]"
                value={addQty}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  if (Number.isNaN(n)) return;
                  setAddQty(Math.min(100, Math.max(1, Math.floor(n))));
                }}
              />
            </div>
            <p className="text-sm text-muted-foreground">
              {previewLoading
                ? "Calculating estimate…"
                : preview
                  ? (() => {
                      const charge = formatMoney(preview.estimated_charge_cents, preview.currency);
                      const now = preview.new_seats;
                      const renew = preview.renewal_target_seats;
                      const mid = `${preview.current_seats} → ${now} purchased seats this billing period`;
                      const renewLine =
                        renew != null && renew !== now
                          ? ` After next renewal: ${renew} purchased seats.`
                          : "";
                      if (preview.estimated_charge_cents === 0 && preview.had_scheduled_reduction) {
                        return `No charge today for this step. ${mid}.${renewLine}`;
                      }
                      const approx =
                        preview.estimated_charge_is_approximate === true
                          ? " Approximate — final amount is set when you confirm."
                          : "";
                      return `Estimated immediate charge: ${charge} (${mid}).${renewLine}${approx}`;
                    })()
                  : "Enter a quantity to see an estimate."}
            </p>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => void confirmAddSeat()}
              disabled={addWorking || previewLoading || !preview}
            >
              {addWorking
                ? "Processing…"
                : preview &&
                    preview.estimated_charge_cents === 0 &&
                    preview.had_scheduled_reduction
                  ? "Confirm"
                  : "Confirm & charge"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={removeDialogOpen} onOpenChange={setRemoveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove seats at renewal</DialogTitle>
            <DialogDescription>
              Purchased seats stay until the end of this period. Choose how many seats to drop from
              your plan starting at the next renewal (no refund for the current period). At least one
              purchased seat must remain, and you cannot schedule going below the number of purchased
              seats currently used by active members.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            {purchasedSeats - 1 > maxRemovableSeats && maxRemovableSeats >= 1 ? (
              <p className="text-sm text-muted-foreground">
                You have {billableSeatsInUse} active member{billableSeatsInUse === 1 ? "" : "s"} using
                purchased seats, so you can schedule removing at most {maxRemovableSeats} at renewal. To
                schedule a larger drop, remove or deactivate members first.
              </p>
            ) : null}
            <div className="grid gap-2">
              <label htmlFor="remove-seat-qty" className="text-sm font-medium text-foreground">
                Seats to remove at next renewal (max {maxRemovableSeats})
              </label>
              <Input
                id="remove-seat-qty"
                type="number"
                min={1}
                max={maxRemovableSeats}
                className="max-w-[8rem]"
                value={removeQty}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  if (Number.isNaN(n)) return;
                  setRemoveQty(Math.min(maxRemovableSeats, Math.max(1, Math.floor(n))));
                }}
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setRemoveDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void confirmScheduleRemoveSeats()} disabled={removeWorking}>
              {removeWorking ? "Scheduling…" : "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
