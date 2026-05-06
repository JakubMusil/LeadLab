"""
Migration 0011 – v2.7: add Membership.expires_at

Allows time-limited memberships for deputies, external auditors, etc.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0010_remove_worker_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="expires_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text=(
                    "Optional expiry date-time for this membership.  After this point the "
                    "member will be treated as if they have no membership (403 on all requests). "
                    "A Celery task runs nightly to hard-delete expired memberships."
                ),
            ),
        ),
    ]
