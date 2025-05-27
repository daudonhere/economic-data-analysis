from rest_framework import serializers
from cleaningApp.models import CleaningData
        
class GetCleaningDataSerializer(serializers.ModelSerializer):
    result = serializers.JSONField(source='content')
    updatedAt = serializers.DateTimeField()

    class Meta:
        model = CleaningData
        fields = ['id', 'result', 'source', 'updatedAt']