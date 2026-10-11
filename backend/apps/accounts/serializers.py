from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'phone_number', 'full_name', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    business_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    store_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'phone_number', 'full_name', 'password', 'business_name', 'store_name']

    def create(self, validated_data):
        business_name = validated_data.pop('business_name', None)
        store_name = validated_data.pop('store_name', None)
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        
        # Proactively bootstrap first business & store for new user
        from apps.tenancy.models import Business, Store, StoreMembership, Role
        biz_name = business_name or f"کسب‌وکار {user.full_name}"
        st_name = store_name or "فروشگاه اصلی"
        business = Business.objects.create(name=biz_name, owner=user)
        store = Store.objects.create(business=business, name=st_name)
        StoreMembership.objects.create(
            store=store,
            user=user,
            role=Role.OWNER,
            is_active=True
        )
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        phone = attrs.get('phone_number')
        password = attrs.get('password')

        user = None
        if email:
            user = authenticate(username=email, password=password)
        elif phone:
            try:
                u = User.objects.get(phone_number=phone)
                if u.check_password(password):
                    user = u
            except User.DoesNotExist:
                pass

        if not user:
            raise serializers.ValidationError('اطلاعات ورود نامعتبر است.')
        if not user.is_active:
            raise serializers.ValidationError('حساب کاربری غیرفعال است.')

        refresh = RefreshToken.for_user(user)
        return {
            'user': user,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }
