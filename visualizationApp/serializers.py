from rest_framework import serializers
from .models import VisualizationData

class VisualizationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisualizationData
        fields = [
            'id', 
            'analyzed_endpoint',
            'input_transformed_data',
            'all_phrases_analysis',
            'global_frequency_stats',
            'global_percentage_stats',
            'per_source_stats',
            'probabilistic_insights',
            'inferential_stats_summary',
            'createdAt',
            'updatedAt'
        ]