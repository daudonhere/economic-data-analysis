from rest_framework import serializers

class TrendingTopicSerializer(serializers.Serializer):
    trend = serializers.CharField()
    value = serializers.IntegerField()
    startFrom = serializers.DateTimeField()
    volume = serializers.CharField()
    dayName = serializers.CharField()
    hour = serializers.IntegerField()
    percentage = serializers.CharField()
    is_peak = serializers.BooleanField()
