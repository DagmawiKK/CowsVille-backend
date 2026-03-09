from django.db.models import Count, Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Cow, Farm


@receiver(post_save, sender=Cow)
@receiver(post_delete, sender=Cow)
def update_farm_counts(sender, instance, **kwargs):
    """
    Update Farm statistics whenever a Cow is added, updated, or deleted.

    Uses a single aggregate query + update() instead of two separate count()
    queries followed by save(), which reduces DB round-trips from 3 to 2 and
    avoids triggering model signals/validation on the Farm instance.
    """
    from django.db.models import Count, Q

    result = Cow.objects.filter(farm=instance.farm, is_deleted=False).aggregate(
        total=Count("id"),
        milking=Count("id", filter=Q(average_daily_milk__gt=0)),
    )

    Farm.objects.filter(pk=instance.farm_id).update(
        total_number_of_cows=result["total"],
        number_of_milking_cows=result["milking"],
    )
