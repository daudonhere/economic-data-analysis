import uuid
from django.db import models
from django.utils.timezone import now
from decimal import Decimal

class VisualizationData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analyzed_endpoint = models.CharField(max_length=255, db_index=True)
    input_transformed_data = models.JSONField(default=list, blank=True)
    all_phrases_analysis = models.JSONField(default=list, blank=True)
    global_frequency_stats = models.JSONField(default=dict, blank=True)
    global_percentage_stats = models.JSONField(default=dict, blank=True)
    per_source_stats = models.JSONField(default=dict, blank=True)
    probabilistic_insights = models.JSONField(default=dict, null=True, blank=True)
    inferential_stats_summary = models.JSONField(default=dict, null=True, blank=True)
    createdAt = models.DateTimeField(auto_now_add=True, db_index=True)
    updatedAt = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        db_table = "tb_visualization_data"
        ordering = ['-createdAt']

    def __str__(self):
        return f"Analysis of {self.analyzed_endpoint} at {self.createdAt.strftime('%Y-%m-%d %H:%M')}"