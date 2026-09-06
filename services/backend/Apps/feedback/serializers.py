from rest_framework import serializers

from .models import SupportAttachment, SupportRequest


class SupportRequestSerializer(serializers.ModelSerializer):
    attachment = serializers.FileField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = SupportRequest
        fields = ["id", "subject", "email", "message", "status", "attachment", "created_at"]
        read_only_fields = ["id", "status", "created_at"]

    def create(self, validated_data):
        attachment = validated_data.pop("attachment", None)
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        support_request = SupportRequest.objects.create(user=user, **validated_data)
        if attachment:
            SupportAttachment.objects.create(
                support_request=support_request, file=attachment
            )
        return support_request
