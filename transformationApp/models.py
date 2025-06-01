import uuid
from django.db import models

class TransformationData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.JSONField()
    source = models.URLField()
    frequency = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, default=0.00
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, default=0.00
    )
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True) 

    class Meta:
        db_table = "tb_transformation_data"
