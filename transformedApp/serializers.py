from rest_framework import serializers
from transformedApp.models import CleansedData

class CleansedDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = CleansedData
        fields = ['id', 'content', 'source', 'createdAt', 'updatedAt']
        
class GetCleansedDataSerializer(serializers.ModelSerializer):
    result = serializers.JSONField(source='content')
    updatedAt = serializers.DateTimeField()

    class Meta:
        model = CleansedData
        fields = ['id', 'result', 'source', 'updatedAt']