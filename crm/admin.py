from django.contrib import admin

from crm.models import Activity, Customer, Lead, LeadAttachment, Notification, Task


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


class AttachmentInline(admin.TabularInline):
    model = LeadAttachment
    extra = 0
    fields = ("original_filename", "content_type", "size_bytes", "uploaded_by", "created_at")
    readonly_fields = ("created_at",)


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


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "source", "assigned_to", "value", "currency", "firm", "created_at")
    list_filter = ("firm", "status", "source")
    search_fields = ("title", "description")
    autocomplete_fields = ["customer", "assigned_to"]
    readonly_fields = ("created_at", "updated_at")
    inlines = [ActivityInline, TaskInline, AttachmentInline]


@admin.register(LeadAttachment)
class LeadAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "lead", "uploaded_by", "size_bytes", "content_type", "created_at")
    list_filter = ("firm",)
    search_fields = ("original_filename", "lead__title")
    readonly_fields = ("created_at",)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("type", "lead", "user", "created_at")
    list_filter = ("type",)
    search_fields = ("content_text", "lead__title")
    readonly_fields = ("created_at",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "lead", "assigned_to", "due_date", "is_completed", "firm")
    list_filter = ("firm", "is_completed")
    search_fields = ("title", "lead__title")
    readonly_fields = ("completed_at", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "firm", "is_read", "created_at")
    list_filter = ("firm", "is_read", "event")
    search_fields = ("event", "user__email")
    readonly_fields = ("created_at",)
