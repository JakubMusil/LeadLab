from django.contrib import admin

from firms.models import (
    APIToken,
    Firm,
    Invitation,
    Membership,
    PermissionRecord,
    Role,
    RolePermission,
    Team,
    TeamMembership,
    WebhookDelivery,
    WebhookEndpoint,
)


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 1
    autocomplete_fields = ["user"]
    fields = ("user", "role", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Firm)
class FirmAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "subscription_tier", "subscription_active", "is_active", "created_at")
    list_filter = ("is_active", "subscription_tier", "subscription_active")
    search_fields = ("name", "slug", "stripe_customer_id")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at",)
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "firm", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__email", "firm__name")
    autocomplete_fields = ["user", "firm"]
    readonly_fields = ("created_at",)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "firm", "role", "invited_by", "created_at", "expires_at", "accepted_at")
    list_filter = ("role", "firm")
    search_fields = ("email", "firm__name")
    readonly_fields = ("token", "created_at", "accepted_at")


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ("name", "prefix", "firm", "user", "is_active", "created_at", "last_used_at", "revoked_at")
    list_filter = ("firm",)
    search_fields = ("name", "prefix", "user__email", "firm__name")
    readonly_fields = ("token_hash", "prefix", "created_at", "last_used_at")


class WebhookDeliveryInline(admin.TabularInline):
    model = WebhookDelivery
    extra = 0
    fields = ("event", "status_code", "success", "delivered_at", "duration_ms")
    readonly_fields = ("event", "status_code", "success", "delivered_at", "duration_ms")
    ordering = ("-delivered_at",)
    max_num = 20


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("url", "firm", "is_active", "created_at")
    list_filter = ("firm", "is_active")
    search_fields = ("url", "firm__name")
    readonly_fields = ("secret", "created_at", "updated_at")
    inlines = [WebhookDeliveryInline]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("event", "endpoint", "status_code", "success", "delivered_at", "duration_ms")
    list_filter = ("success", "event")
    search_fields = ("event", "endpoint__url")
    readonly_fields = ("delivered_at",)


# ---------------------------------------------------------------------------
# Phase 2 – Permission catalogue, Roles, Teams
# ---------------------------------------------------------------------------


@admin.register(PermissionRecord)
class PermissionRecordAdmin(admin.ModelAdmin):
    list_display = ("code", "group", "description")
    list_filter = ("group",)
    search_fields = ("code", "description")
    readonly_fields = ("code",)


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0
    autocomplete_fields = ["permission"]
    fields = ("permission",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "firm", "is_system", "created_at")
    list_filter = ("is_system", "firm")
    search_fields = ("name", "code", "firm__name")
    readonly_fields = ("id", "created_at")
    inlines = [RolePermissionInline]


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0
    autocomplete_fields = ["membership"]
    fields = ("membership", "joined_at")
    readonly_fields = ("joined_at",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "firm", "color", "created_at")
    list_filter = ("firm",)
    search_fields = ("name", "slug", "firm__name")
    readonly_fields = ("id", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [TeamMembershipInline]
