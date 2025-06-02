from rest_framework import serializers
from ingestionApp.models import IngestionData
from cleaningApp.models import CleaningData
from transformationApp.models import TransformationData
from visualizationApp.models import VisualizationData

class GlobalDeleteSerializer(serializers.Serializer):
    class Meta:
        fields = []

class IngestionDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionData
        fields = '__all__'

class TransformationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransformationData
        fields = '__all__'

class CleaningDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = CleaningData
        fields = '__all__'

class VisualizationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisualizationData
        fields = '__all__'