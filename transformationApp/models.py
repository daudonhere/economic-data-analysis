from django.db import models
from common.models import BaseModel

class TransformationData(BaseModel):
    content = models.JSONField()
    source = models.URLField()
    frequency = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, default=0.00
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, default=0.00
    )

    class Meta:
        db_table = "tb_transformation_data"
