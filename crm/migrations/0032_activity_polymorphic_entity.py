# Generated migration — Phase 4.x: Unified activity timeline
#
# Changes:
#   1. crm_activity.lead  → nullable (existing lead activities are unchanged)
#   2. crm_activity.realization added (nullable FK → Realization)
#   3. crm_activity.management  added (nullable FK → Management)
#   4. New indexes for the two new FKs

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0031_add_condition_logic_to_automationrule'),
    ]

    operations = [
        # 1. Make lead nullable (existing rows are unaffected; DB column already
        #    allows NULLs after this ALTER — previously NOT NULL).
        migrations.AlterField(
            model_name='activity',
            name='lead',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='activities',
                to='crm.lead',
            ),
        ),

        # 2. Add realization FK
        migrations.AddField(
            model_name='activity',
            name='realization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='activities',
                to='crm.realization',
            ),
        ),

        # 3. Add management FK
        migrations.AddField(
            model_name='activity',
            name='management',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='activities',
                to='crm.management',
            ),
        ),

        # 4. Add indexes for new FKs
        migrations.AddIndex(
            model_name='activity',
            index=models.Index(
                fields=['realization', '-created_at'],
                name='crm_activit_realiz_created_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='activity',
            index=models.Index(
                fields=['management', '-created_at'],
                name='crm_activit_mgmt_created_idx',
            ),
        ),
    ]
