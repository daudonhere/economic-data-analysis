from django.db import models
from common.models import BaseModel

class CleaningData(BaseModel):
    content = models.JSONField()
    source = models.URLField()

    class Meta:
        db_table = "tb_cleaning_data"
