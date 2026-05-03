"""
ERP API — Time Entries, Expense Items, Revenue Items (Phase 4.0)

Endpoints:
  /api/v1/erp/time-entries      CRUD + list with filters
  /api/v1/erp/expenses          CRUD + list with filters
  /api/v1/erp/revenues          CRUD + list with filters
  /api/v1/erp/reports/summary   Aggregated P&L summary
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import List, Optional

from ninja import Router, Schema
from ninja.security import django_auth

from crm.models import Customer, ExpenseItem, Lead, Realization, RevenueItem, Task, TimeEntry
from crm.soft_delete import perform_soft_delete
from firms.auth import require_active_subscription, require_membership

router = Router(tags=["erp"])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _firm(request):
    return getattr(request, "firm", None)


# ---------------------------------------------------------------------------
# TimeEntry schemas
# ---------------------------------------------------------------------------

class TimeEntryIn(Schema):
    duration_minutes: int
    description: str = ""
    is_billable: bool = True
    hourly_rate: Optional[Decimal] = None
    started_at: Optional[dt.datetime] = None
    ended_at: Optional[dt.datetime] = None
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    task_id: Optional[str] = None
    realization_id: Optional[str] = None


class TimeEntryPatch(Schema):
    duration_minutes: Optional[int] = None
    description: Optional[str] = None
    is_billable: Optional[bool] = None
    hourly_rate: Optional[Decimal] = None
    started_at: Optional[dt.datetime] = None
    ended_at: Optional[dt.datetime] = None
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    task_id: Optional[str] = None
    realization_id: Optional[str] = None


class TimeEntryOut(Schema):
    id: str
    firm_id: str
    user_id: Optional[str]
    user_name: Optional[str]
    lead_id: Optional[str]
    lead_title: Optional[str]
    customer_id: Optional[str]
    customer_name: Optional[str]
    task_id: Optional[str]
    task_title: Optional[str]
    realization_id: Optional[str]
    realization_title: Optional[str]
    duration_minutes: int
    description: str
    is_billable: bool
    hourly_rate: Optional[Decimal]
    started_at: Optional[dt.datetime]
    ended_at: Optional[dt.datetime]
    created_at: dt.datetime
    updated_at: dt.datetime

    @staticmethod
    def from_obj(obj: TimeEntry) -> "TimeEntryOut":
        user_name = None
        if obj.user:
            user_name = (
                f"{obj.user.first_name} {obj.user.last_name}".strip()
                or obj.user.email
            )
        return TimeEntryOut(
            id=str(obj.id),
            firm_id=str(obj.firm_id),
            user_id=str(obj.user_id) if obj.user_id else None,
            user_name=user_name,
            lead_id=str(obj.lead_id) if obj.lead_id else None,
            lead_title=obj.lead.title if obj.lead_id else None,
            customer_id=str(obj.customer_id) if obj.customer_id else None,
            customer_name=(
                f"{obj.customer.first_name} {obj.customer.last_name}".strip()
                if obj.customer_id
                else None
            ),
            task_id=str(obj.task_id) if obj.task_id else None,
            task_title=obj.task.title if obj.task_id else None,
            realization_id=str(obj.realization_id) if obj.realization_id else None,
            realization_title=obj.realization.title if obj.realization_id else None,
            duration_minutes=obj.duration_minutes,
            description=obj.description,
            is_billable=obj.is_billable,
            hourly_rate=obj.hourly_rate,
            started_at=obj.started_at,
            ended_at=obj.ended_at,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


# ---------------------------------------------------------------------------
# TimeEntry endpoints
# ---------------------------------------------------------------------------

@router.get("/time-entries", response=List[TimeEntryOut])
def list_time_entries(
    request,
    user_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    task_id: Optional[str] = None,
    realization_id: Optional[str] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
):
    require_membership(request)
    firm = _firm(request)
    qs = TimeEntry.objects.filter(firm=firm).select_related("user", "lead", "customer", "task", "realization")
    if user_id:
        qs = qs.filter(user_id=user_id)
    if lead_id:
        qs = qs.filter(lead_id=lead_id)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    if task_id:
        qs = qs.filter(task_id=task_id)
    if realization_id:
        qs = qs.filter(realization_id=realization_id)
    if date_from:
        qs = qs.filter(started_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(started_at__date__lte=date_to)
    return [TimeEntryOut.from_obj(e) for e in qs]


@router.post("/time-entries", response=TimeEntryOut)
def create_time_entry(request, payload: TimeEntryIn):
    require_membership(request)
    firm = _firm(request)
    realization = None
    if payload.realization_id:
        realization = Realization.objects.filter(firm=firm, id=payload.realization_id).first()
    entry = TimeEntry.objects.create(
        firm=firm,
        user=request.user,
        duration_minutes=payload.duration_minutes,
        description=payload.description,
        is_billable=payload.is_billable,
        hourly_rate=payload.hourly_rate,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        lead_id=payload.lead_id,
        customer_id=payload.customer_id,
        task_id=payload.task_id,
        realization=realization,
    )
    entry.refresh_from_db()
    return TimeEntryOut.from_obj(
        TimeEntry.objects.select_related("user", "lead", "customer", "task", "realization").get(pk=entry.pk)
    )


@router.get("/time-entries/{entry_id}", response=TimeEntryOut)
def get_time_entry(request, entry_id: str):
    require_membership(request)
    firm = _firm(request)
    try:
        entry = TimeEntry.objects.select_related("user", "lead", "customer", "task", "realization").get(
            pk=entry_id, firm=firm
        )
    except TimeEntry.DoesNotExist:
        from ninja import errors as ninja_errors
        raise ninja_errors.HttpError(404, "Not found")
    return TimeEntryOut.from_obj(entry)


@router.patch("/time-entries/{entry_id}", response=TimeEntryOut)
def update_time_entry(request, entry_id: str, payload: TimeEntryPatch):
    require_membership(request)
    firm = _firm(request)
    try:
        entry = TimeEntry.objects.select_related("user", "lead", "customer", "task", "realization").get(
            pk=entry_id, firm=firm
        )
    except TimeEntry.DoesNotExist:
        from ninja import errors as ninja_errors
        raise ninja_errors.HttpError(404, "Not found")
    update_data = payload.dict(exclude_unset=True)
    if "realization_id" in update_data:
        rid = update_data.pop("realization_id")
        entry.realization = Realization.objects.filter(firm=firm, id=rid).first() if rid else None
    for field, value in update_data.items():
        setattr(entry, field, value)
    entry.save()
    entry.refresh_from_db()
    return TimeEntryOut.from_obj(
        TimeEntry.objects.select_related("user", "lead", "customer", "task", "realization").get(pk=entry.pk)
    )


@router.delete("/time-entries/{entry_id}", response={204: None})
def delete_time_entry(request, entry_id: str):
    require_membership(request)
    firm = _firm(request)
    entry = TimeEntry.objects.filter(pk=entry_id, firm=firm).first()
    if not entry:
        from ninja import errors as ninja_errors
        raise ninja_errors.HttpError(404, "Not found")
    perform_soft_delete(entry, request.user)
    return 204, None


# ---------------------------------------------------------------------------
# ExpenseItem schemas
# ---------------------------------------------------------------------------

class ExpenseItemIn(Schema):
    title: str
    amount: Decimal
    currency: str = "CZK"
    date: dt.date
    recurrence: str = "once"
    notes: str = ""
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    task_id: Optional[str] = None


class ExpenseItemPatch(Schema):
    title: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    date: Optional[dt.date] = None
    recurrence: Optional[str] = None
    notes: Optional[str] = None
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    task_id: Optional[str] = None


class ExpenseItemOut(Schema):
    id: str
    firm_id: str
    user_id: Optional[str]
    user_name: Optional[str]
    lead_id: Optional[str]
    lead_title: Optional[str]
    customer_id: Optional[str]
    customer_name: Optional[str]
    task_id: Optional[str]
    task_title: Optional[str]
    title: str
    amount: Decimal
    currency: str
    date: dt.date
    recurrence: str
    notes: str
    created_at: dt.datetime

    @staticmethod
    def from_obj(obj: ExpenseItem) -> "ExpenseItemOut":
        user_name = None
        if obj.user:
            user_name = (
                f"{obj.user.first_name} {obj.user.last_name}".strip()
                or obj.user.email
            )
        return ExpenseItemOut(
            id=str(obj.id),
            firm_id=str(obj.firm_id),
            user_id=str(obj.user_id) if obj.user_id else None,
            user_name=user_name,
            lead_id=str(obj.lead_id) if obj.lead_id else None,
            lead_title=obj.lead.title if obj.lead_id else None,
            customer_id=str(obj.customer_id) if obj.customer_id else None,
            customer_name=(
                f"{obj.customer.first_name} {obj.customer.last_name}".strip()
                if obj.customer_id
                else None
            ),
            task_id=str(obj.task_id) if obj.task_id else None,
            task_title=obj.task.title if obj.task_id else None,
            title=obj.title,
            amount=obj.amount,
            currency=obj.currency,
            date=obj.date,
            recurrence=obj.recurrence,
            notes=obj.notes,
            created_at=obj.created_at,
        )


# ---------------------------------------------------------------------------
# ExpenseItem endpoints
# ---------------------------------------------------------------------------

@router.get("/expenses", response=List[ExpenseItemOut])
def list_expenses(
    request,
    lead_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
):
    require_membership(request)
    firm = _firm(request)
    qs = ExpenseItem.objects.filter(firm=firm).select_related("user", "lead", "customer", "task")
    if lead_id:
        qs = qs.filter(lead_id=lead_id)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return [ExpenseItemOut.from_obj(e) for e in qs]


@router.post("/expenses", response=ExpenseItemOut)
def create_expense(request, payload: ExpenseItemIn):
    require_membership(request)
    firm = _firm(request)
    obj = ExpenseItem.objects.create(
        firm=firm,
        user=request.user,
        title=payload.title,
        amount=payload.amount,
        currency=payload.currency,
        date=payload.date,
        recurrence=payload.recurrence,
        notes=payload.notes,
        lead_id=payload.lead_id,
        customer_id=payload.customer_id,
        task_id=payload.task_id,
    )
    return ExpenseItemOut.from_obj(
        ExpenseItem.objects.select_related("user", "lead", "customer", "task").get(pk=obj.pk)
    )


@router.patch("/expenses/{item_id}", response=ExpenseItemOut)
def update_expense(request, item_id: str, payload: ExpenseItemPatch):
    require_membership(request)
    firm = _firm(request)
    try:
        obj = ExpenseItem.objects.select_related("user", "lead", "customer", "task").get(
            pk=item_id, firm=firm
        )
    except ExpenseItem.DoesNotExist:
        from ninja import errors as ninja_errors
        raise ninja_errors.HttpError(404, "Not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    obj.save()
    return ExpenseItemOut.from_obj(
        ExpenseItem.objects.select_related("user", "lead", "customer", "task").get(pk=obj.pk)
    )


@router.delete("/expenses/{item_id}", response={204: None})
def delete_expense(request, item_id: str):
    require_membership(request)
    firm = _firm(request)
    item = ExpenseItem.objects.filter(pk=item_id, firm=firm).first()
    if not item:
        from ninja import errors as ninja_errors
        raise ninja_errors.HttpError(404, "Not found")
    perform_soft_delete(item, request.user)
    return 204, None


# ---------------------------------------------------------------------------
# RevenueItem schemas
# ---------------------------------------------------------------------------

class RevenueItemIn(Schema):
    title: str
    amount: Decimal
    currency: str = "CZK"
    date: dt.date
    recurrence: str = "once"
    notes: str = ""
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None


class RevenueItemPatch(Schema):
    title: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    date: Optional[dt.date] = None
    recurrence: Optional[str] = None
    notes: Optional[str] = None
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None


class RevenueItemOut(Schema):
    id: str
    firm_id: str
    user_id: Optional[str]
    user_name: Optional[str]
    lead_id: Optional[str]
    lead_title: Optional[str]
    customer_id: Optional[str]
    customer_name: Optional[str]
    title: str
    amount: Decimal
    currency: str
    date: dt.date
    recurrence: str
    notes: str
    created_at: dt.datetime

    @staticmethod
    def from_obj(obj: RevenueItem) -> "RevenueItemOut":
        user_name = None
        if obj.user:
            user_name = (
                f"{obj.user.first_name} {obj.user.last_name}".strip()
                or obj.user.email
            )
        return RevenueItemOut(
            id=str(obj.id),
            firm_id=str(obj.firm_id),
            user_id=str(obj.user_id) if obj.user_id else None,
            user_name=user_name,
            lead_id=str(obj.lead_id) if obj.lead_id else None,
            lead_title=obj.lead.title if obj.lead_id else None,
            customer_id=str(obj.customer_id) if obj.customer_id else None,
            customer_name=(
                f"{obj.customer.first_name} {obj.customer.last_name}".strip()
                if obj.customer_id
                else None
            ),
            title=obj.title,
            amount=obj.amount,
            currency=obj.currency,
            date=obj.date,
            recurrence=obj.recurrence,
            notes=obj.notes,
            created_at=obj.created_at,
        )


# ---------------------------------------------------------------------------
# RevenueItem endpoints
# ---------------------------------------------------------------------------

@router.get("/revenues", response=List[RevenueItemOut])
def list_revenues(
    request,
    lead_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
):
    require_membership(request)
    firm = _firm(request)
    qs = RevenueItem.objects.filter(firm=firm).select_related("user", "lead", "customer")
    if lead_id:
        qs = qs.filter(lead_id=lead_id)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return [RevenueItemOut.from_obj(r) for r in qs]


@router.post("/revenues", response=RevenueItemOut)
def create_revenue(request, payload: RevenueItemIn):
    require_membership(request)
    firm = _firm(request)
    obj = RevenueItem.objects.create(
        firm=firm,
        user=request.user,
        title=payload.title,
        amount=payload.amount,
        currency=payload.currency,
        date=payload.date,
        recurrence=payload.recurrence,
        notes=payload.notes,
        lead_id=payload.lead_id,
        customer_id=payload.customer_id,
    )
    return RevenueItemOut.from_obj(
        RevenueItem.objects.select_related("user", "lead", "customer").get(pk=obj.pk)
    )


@router.patch("/revenues/{item_id}", response=RevenueItemOut)
def update_revenue(request, item_id: str, payload: RevenueItemPatch):
    require_membership(request)
    firm = _firm(request)
    try:
        obj = RevenueItem.objects.select_related("user", "lead", "customer").get(
            pk=item_id, firm=firm
        )
    except RevenueItem.DoesNotExist:
        from ninja import errors as ninja_errors
        raise ninja_errors.HttpError(404, "Not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    obj.save()
    return RevenueItemOut.from_obj(
        RevenueItem.objects.select_related("user", "lead", "customer").get(pk=obj.pk)
    )


@router.delete("/revenues/{item_id}", response={204: None})
def delete_revenue(request, item_id: str):
    require_membership(request)
    firm = _firm(request)
    item = RevenueItem.objects.filter(pk=item_id, firm=firm).first()
    if not item:
        from ninja import errors as ninja_errors
        raise ninja_errors.HttpError(404, "Not found")
    perform_soft_delete(item, request.user)
    return 204, None


# ---------------------------------------------------------------------------
# Reports summary endpoint
# ---------------------------------------------------------------------------

class ReportSummaryOut(Schema):
    total_minutes: int
    billable_minutes: int
    total_expenses: Decimal
    total_revenues: Decimal
    profit_loss: Decimal
    mixed_currencies: bool = False


@router.get("/reports/summary", response=ReportSummaryOut)
def reports_summary(
    request,
    lead_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
):
    require_membership(request)
    firm = _firm(request)

    from django.db.models import Sum

    te_qs = TimeEntry.objects.filter(firm=firm)
    ex_qs = ExpenseItem.objects.filter(firm=firm)
    rev_qs = RevenueItem.objects.filter(firm=firm)

    if lead_id:
        te_qs = te_qs.filter(lead_id=lead_id)
        ex_qs = ex_qs.filter(lead_id=lead_id)
        rev_qs = rev_qs.filter(lead_id=lead_id)
    if customer_id:
        te_qs = te_qs.filter(customer_id=customer_id)
        ex_qs = ex_qs.filter(customer_id=customer_id)
        rev_qs = rev_qs.filter(customer_id=customer_id)
    if date_from:
        te_qs = te_qs.filter(started_at__date__gte=date_from)
        ex_qs = ex_qs.filter(date__gte=date_from)
        rev_qs = rev_qs.filter(date__gte=date_from)
    if date_to:
        te_qs = te_qs.filter(started_at__date__lte=date_to)
        ex_qs = ex_qs.filter(date__lte=date_to)
        rev_qs = rev_qs.filter(date__lte=date_to)

    # Filter aggregations to the workspace default currency to avoid mixing apples and oranges.
    default_currency = firm.default_currency
    same_currency_ex = ex_qs.filter(currency=default_currency)
    same_currency_rev = rev_qs.filter(currency=default_currency)
    mixed_currencies = (
        ex_qs.exclude(currency=default_currency).exists()
        or rev_qs.exclude(currency=default_currency).exists()
    )

    total_minutes = te_qs.aggregate(s=Sum("duration_minutes"))["s"] or 0
    billable_minutes = te_qs.filter(is_billable=True).aggregate(s=Sum("duration_minutes"))["s"] or 0
    total_expenses = same_currency_ex.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    total_revenues = same_currency_rev.aggregate(s=Sum("amount"))["s"] or Decimal("0")

    return ReportSummaryOut(
        total_minutes=total_minutes,
        billable_minutes=billable_minutes,
        total_expenses=total_expenses,
        total_revenues=total_revenues,
        profit_loss=total_revenues - total_expenses,
        mixed_currencies=mixed_currencies,
    )
