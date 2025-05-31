from rest_framework import serializers

class BaseResponseWrapperSerializer(serializers.Serializer):
    status = serializers.CharField()
    code = serializers.IntegerField()
    messages = serializers.CharField()

class SuccessResponseSerializer(BaseResponseWrapperSerializer):
    data = serializers.JSONField(required=False, allow_null=True)
    status = serializers.CharField(default="success")

class ErrorResponseSerializer(BaseResponseWrapperSerializer):
    data = serializers.JSONField(required=False, allow_null=True)
    status = serializers.CharField(default="error")
