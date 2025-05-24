from django.db import models

class CleansedData(models.Model):
    content = models.JSONField()
    source = models.CharField(max_length=255)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tb_cleansed_data'

    def __str__(self):
        return f"Cleansed from {self.source} at {self.createdAt}"
