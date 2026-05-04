from django.db import migrations


class Migration(migrations.Migration):
    """Drop legacy crm_milestone table that may still exist in databases
    created before the squash-migration rebuild.
    This table is no longer managed by Django, so ``manage.py flush``
    does not include it in its TRUNCATE list.  PostgreSQL then refuses
    to truncate tables it references via foreign-key constraints
    (crm_milestone → users_user), causing ``docker compose up`` to fail.
    Using IF EXISTS makes this migration a no-op on fresh databases.
    """

    dependencies = [
        ("crm", "0003_drop_legacy_realization"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS crm_milestone CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
