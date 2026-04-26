from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('firms', '0004_add_weekly_digest_enabled'),
    ]
    operations = [
        migrations.AddField(
            model_name='firm',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='firm_logos/'),
        ),
        migrations.AddField(
            model_name='firm',
            name='primary_color',
            field=models.CharField(blank=True, default='#dc2626', max_length=7),
        ),
    ]
