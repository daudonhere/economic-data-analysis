from django.db import models
from common.models import BaseModel

class VisualizationData(BaseModel):
    analyzed_endpoint = models.CharField(max_length=255)
    input_transformed_data = models.JSONField(default=list) 
    all_phrases_analysis = models.JSONField(default=list) 
    global_frequency_stats = models.JSONField(default=dict)
    global_percentage_stats = models.JSONField(default=dict)
    per_source_stats = models.JSONField(default=dict)
    probabilistic_insights = models.JSONField(default=dict, null=True, blank=True)
    inferential_stats_summary = models.JSONField(default=dict, null=True, blank=True)

    class Meta:
        db_table = "tb_visualization_data"
        ordering = ['-createdAt']

    def __str__(self):
        return f"Analysis of {self.analyzed_endpoint} at {self.createdAt.strftime('%Y-%m-%d %H:%M')}"