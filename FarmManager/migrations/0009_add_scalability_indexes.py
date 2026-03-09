# Generated migration — adds composite indexes to improve query performance
# at scale for the most frequently executed filter patterns.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("FarmManager", "0008_add_cluster_number_to_farm"),
    ]

    operations = [
        # --- Cow indexes ---
        migrations.AddIndex(
            model_name="cow",
            index=models.Index(
                fields=["farm", "is_deleted"],
                name="cow_farm_deleted_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="cow",
            index=models.Index(
                fields=["average_daily_milk"],
                name="cow_milk_idx",
            ),
        ),
        # --- Reproduction indexes ---
        migrations.AddIndex(
            model_name="reproduction",
            index=models.Index(
                fields=["is_cow_pregnant"],
                name="reproduction_pregnant_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reproduction",
            index=models.Index(
                fields=["is_cow_pregnant", "calving_date"],
                name="reproduction_pregnant_calving_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reproduction",
            index=models.Index(
                fields=["farm", "cow"],
                name="reproduction_farm_cow_idx",
            ),
        ),
        # --- Message indexes ---
        migrations.AddIndex(
            model_name="message",
            index=models.Index(
                fields=["farm", "message_type", "sent_date"],
                name="message_farm_type_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(
                fields=["farm", "cow", "message_type", "sent_date"],
                name="message_farm_cow_type_date_idx",
            ),
        ),
        # --- InseminationRecord indexes ---
        migrations.AddIndex(
            model_name="inseminationrecord",
            index=models.Index(
                fields=["farm", "cow"],
                name="insemination_farm_cow_idx",
            ),
        ),
    ]
