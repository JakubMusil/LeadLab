"""
Migration 0012 – v2.8: add Membership.last_expiry_notification_at

Tracks when the last expiry-warning email was sent so the nightly
notify_expiring_memberships task does not send duplicate warnings.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0011_membership_expires_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="last_expiry_notification_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text=(
                    "Set by the notify_expiring_memberships task when it sends a warning email. "
                    "Used to prevent duplicate notifications within the same warning window."
                ),
            ),
        ),
    ]
