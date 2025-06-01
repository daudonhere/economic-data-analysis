from django.db import models

class IngestionData(models.Model):
    content = models.JSONField()
    source = models.CharField(max_length=255)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tb_ingestion_data'

    def __str__(self):
        return f"Ingestion from {self.source} at {self.createdAt}"
