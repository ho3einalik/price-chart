from rest_framework import serializers
from .models import Business, Store, StoreMembership

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']

class StoreSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ['id', 'business', 'business_name', 'name', 'currency', 'timezone', 'is_active', 'my_role', 'created_at']
        read_only_fields = ['id', 'business_name', 'my_role', 'created_at']

    def get_my_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            membership = obj.memberships.filter(user=request.user, is_active=True).first()
            if membership:
                return membership.role
        return None

class StoreMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = StoreMembership
        fields = ['id', 'store', 'user', 'user_email', 'user_name', 'role', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
