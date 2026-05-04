from django.db import migrations


class Migration(migrations.Migration):
    """Drop legacy crm_realization and crm_management tables that may still
    exist in databases created before the squash-migration rebuild.
    These tables are no longer managed by Django, so ``manage.py flush``
    does not include them in its TRUNCATE list.  PostgreSQL then refuses
    to truncate tables they reference via foreign-key constraints (e.g.
    crm_realization → crm_customer), causing ``docker compose up`` to fail.
    Using IF EXISTS makes this migration a no-op on fresh databases.
    """

    dependencies = [
        ("crm", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS crm_realization CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS crm_management CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
