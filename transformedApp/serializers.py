from rest_framework import serializers
from .models import TransformedData

class TransformedDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransformedData
        fields = ['id', 'content', 'source', 'frequency', 'percentage', 'createdAt', 'updatedAt']
        
class GetTransformedDataSerializer(serializers.ModelSerializer):
    result = serializers.JSONField(source='content')
    updatedAt = serializers.DateTimeField()

    class Meta:
        model = TransformedData
        fields = ['id', 'result', 'source', 'updatedAt']