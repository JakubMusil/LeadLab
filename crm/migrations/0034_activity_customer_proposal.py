# Generated migration — Phase 5: Streamline for Customer and Proposal
#
# Changes:
#   1. crm_activity.customer  added (nullable FK → Customer)
#   2. crm_activity.proposal  added (nullable FK → Proposal)
#   3. New indexes for the two new FKs

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0033_firmproposalitem_sku_notes_image_url'),
    ]

    operations = [
        # 1. Add customer FK
        migrations.AddField(
            model_name='activity',
            name='customer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='activities',
                to='crm.customer',
            ),
        ),

        # 2. Add proposal FK
        migrations.AddField(
            model_name='activity',
            name='proposal',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='activities',
                to='crm.proposal',
            ),
        ),

        # 3. Add indexes
        migrations.AddIndex(
            model_name='activity',
            index=models.Index(
                fields=['customer', '-created_at'],
                name='crm_activit_cust_created_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='activity',
            index=models.Index(
                fields=['proposal', '-created_at'],
                name='crm_activit_prop_created_idx',
            ),
        ),
    ]
