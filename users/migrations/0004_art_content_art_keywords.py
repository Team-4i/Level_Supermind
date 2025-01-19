# Generated by Django 5.1.5 on 2025-01-18 22:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_art_options_remove_art_category_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='art',
            name='content',
            field=models.JSONField(blank=True, default=dict, help_text='Collected video content and data'),
        ),
        migrations.AddField(
            model_name='art',
            name='keywords',
            field=models.JSONField(blank=True, default=list, help_text='Generated keywords for the analysis'),
        ),
    ]
