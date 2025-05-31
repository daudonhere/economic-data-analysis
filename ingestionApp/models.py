from django.db import models
from common.models import BaseModel

class IngestionData(BaseModel):
    content = models.JSONField()
    source = models.CharField(max_length=255)

    class Meta:
        db_table = 'tb_ingestion_data'

    def __str__(self):
        return f"Ingestion from {self.source} at {self.createdAt}"
