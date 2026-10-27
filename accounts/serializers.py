from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

User = get_user_model()

PHONE_ERROR = "Mobile number must be 8 to 10 digits."


class RegisterSerializer(serializers.ModelSerializer):
    phone_number = serializers.RegexField(
        regex=r"^\d{8,10}$",
        error_messages={"invalid": PHONE_ERROR},
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="A user with this phone number already exists.",
            )
        ],
    )
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "phone_number",
            "password",
            "confirm_password",
        )

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.RegexField(
        regex=r"^\d{8,10}$",
        error_messages={"invalid": PHONE_ERROR},
    )
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["phone_number"],
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError("Invalid phone number or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled.")
        attrs["user"] = user
        return attrs