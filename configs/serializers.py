from rest_framework import serializers
from configs.models import IngestionData

class IngestionDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionData
        fields = ['id', 'content', 'source', 'createdAt', 'updatedAt']
        
class GetIngestionDataSerializer(serializers.ModelSerializer):
    result = serializers.JSONField(source='content')
    updatedAt = serializers.DateTimeField()

    class Meta:
        model = IngestionData
        fields = ['id', 'result', 'source', 'updatedAt']
