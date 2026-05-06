"""
v2.4 – Remove deprecated 'worker' value from MembershipRole / Invitation.role.

Data migration: converts any existing Invitation rows with role='worker' to
role='member' before the AlterField removes 'worker' from the allowed choices.
"""

from django.db import migrations, models


def forwards(apps, schema_editor):
    Invitation = apps.get_model("firms", "Invitation")
    Invitation.objects.filter(role="worker").update(role="member")


def backwards(apps, schema_editor):
    pass  # Non-destructive – we do not restore 'worker' values on rollback.


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0009_invitation_default_member"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="invitation",
            name="role",
            field=models.CharField(
                choices=[("owner", "Owner"), ("admin", "Admin"), ("member", "Member")],
                default="member",
                max_length=20,
            ),
        ),
    ]
