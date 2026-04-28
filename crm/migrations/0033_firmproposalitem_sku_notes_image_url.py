from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0032_activity_polymorphic_entity'),
    ]

    operations = [
        migrations.AddField(
            model_name='firmproposalitem',
            name='sku',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='firmproposalitem',
            name='notes',
            field=models.TextField(blank=True, default='', help_text='Rich text notes / detailed description (HTML).'),
        ),
        migrations.AddField(
            model_name='firmproposalitem',
            name='image_url',
            field=models.URLField(blank=True, default='', max_length=1000, help_text='Product/service image URL.'),
        ),
    ]
