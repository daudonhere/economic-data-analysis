import uuid
from django.db import models
from django.utils.timezone import now

class CleaningData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.JSONField()
    source = models.URLField()
    createdAt = models.DateTimeField(default=now)
    updatedAt = models.DateTimeField(default=now)

    class Meta:
        db_table = "tb_cleaning_data"
