from django.contrib import admin

from crm.models import (
    Activity,
    Customer,
    DashboardLayout,
    ImportJob,
    PipelineRecord,
    RecordScoringRule,
    Notification,
    Proposal,
    ProposalItem,
    ProposalTemplate,
    ProposalTemplateItem,
    PushSubscription,
    SavedView,
    Task,
    StreamlineItem,
    TaskDependency,
    TaskTemplate,
)


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    fields = ("type", "user", "content_text", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ("title", "assigned_to", "due_date", "is_completed", "completed_at")
    readonly_fields = ("completed_at",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "company_name", "firm")
    list_filter = ("firm",)
    search_fields = ("first_name", "last_name", "email", "company_name")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("firm", "first_name", "last_name", "email", "phone", "company_name")}),
        ("Extra", {"fields": ("tags", "metadata")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(PipelineRecord)
class PipelineRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "source", "assigned_to", "value", "currency", "firm", "created_at")
    list_filter = ("firm", "status", "source")
    search_fields = ("title",)
    autocomplete_fields = ["customer", "assigned_to"]
    readonly_fields = ("created_at", "updated_at")
    inlines = [ActivityInline, TaskInline]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("type", "record", "user", "created_at")
    list_filter = ("type",)
    search_fields = ("content_text", "record__title")
    readonly_fields = ("created_at",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "record", "assigned_to", "due_date", "is_completed", "firm")
    list_filter = ("firm", "is_completed")
    search_fields = ("title", "record__title")
    readonly_fields = ("completed_at", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "firm", "is_read", "created_at")
    list_filter = ("firm", "is_read", "event")
    search_fields = ("event", "user__email")
    readonly_fields = ("created_at",)


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("type", "status", "firm", "user", "total", "processed", "failed_count", "created_at", "finished_at")
    list_filter = ("firm", "type", "status")
    search_fields = ("firm__name", "user__email", "original_filename")
    readonly_fields = ("created_at", "finished_at")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "push_enabled", "created_at")
    list_filter = ("push_enabled",)
    search_fields = ("user__email", "endpoint")
    readonly_fields = ("created_at",)


@admin.register(DashboardLayout)
class DashboardLayoutAdmin(admin.ModelAdmin):
    list_display = ("user", "firm", "updated_at")
    list_filter = ("firm",)
    search_fields = ("user__email",)
    readonly_fields = ("updated_at",)


@admin.register(RecordScoringRule)
class RecordScoringRuleAdmin(admin.ModelAdmin):
    list_display = ("field", "operand", "score_delta", "firm")
    list_filter = ("firm", "field")
    search_fields = ("field",)


@admin.register(SavedView)
class SavedViewAdmin(admin.ModelAdmin):
    list_display = ("name", "entity", "user", "firm", "created_at")
    list_filter = ("firm", "entity")
    search_fields = ("name", "user__email")
    readonly_fields = ("created_at",)


# ---------------------------------------------------------------------------
# Proposals & Quote Builder (v2.3)
# ---------------------------------------------------------------------------

class ProposalItemInline(admin.TabularInline):
    model = ProposalItem
    extra = 0
    fields = ("description", "quantity", "unit_price", "discount", "vat_rate", "position")
    ordering = ("position",)


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "record", "currency", "view_count", "firm", "created_at")
    list_filter = ("firm", "status")
    search_fields = ("title", "record__title")
    readonly_fields = ("public_token", "view_count", "first_viewed_at", "sent_at", "responded_at", "created_at", "updated_at")
    inlines = [ProposalItemInline]


@admin.register(ProposalItem)
class ProposalItemAdmin(admin.ModelAdmin):
    list_display = ("description", "quantity", "unit_price", "discount", "vat_rate", "proposal")
    list_filter = ("proposal__firm",)
    search_fields = ("description", "proposal__title")


class ProposalTemplateItemInline(admin.TabularInline):
    model = ProposalTemplateItem
    extra = 0
    fields = ("description", "quantity", "unit_price", "discount", "vat_rate", "position")
    ordering = ("position",)


@admin.register(ProposalTemplate)
class ProposalTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "firm", "created_at")
    list_filter = ("firm",)
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [ProposalTemplateItemInline]





@admin.register(TaskDependency)
class TaskDependencyAdmin(admin.ModelAdmin):
    list_display = ("from_task", "type", "to_task", "created_by", "created_at")
    list_filter = ("type",)
    search_fields = ("from_task__title", "to_task__title")
    readonly_fields = ("created_at",)


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "firm", "priority", "estimated_minutes", "created_by", "created_at")
    list_filter = ("firm", "priority")
    search_fields = ("name", "firm__name")
    readonly_fields = ("created_at", "updated_at")
