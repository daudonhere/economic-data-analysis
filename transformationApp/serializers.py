from rest_framework import serializers
from transformationApp.models import TransformationData

class TransformationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransformationData
        fields = ['id', 'content', 'source', 'frequency', 'percentage', 'createdAt', 'updatedAt']