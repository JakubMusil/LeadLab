from django.contrib import admin

from firms.models import Firm, Membership


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
