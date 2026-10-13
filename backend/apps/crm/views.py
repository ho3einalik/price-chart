from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Sum
from .models import CustomerProfile, CustomerInteraction, CustomerSegment
from .serializers import CustomerProfileSerializer, CustomerInteractionSerializer
from .services import recalculate_customer_rfm, recalculate_all_store_customers
from apps.tenancy.permissions import IsStoreMemberPermission

class CustomerProfileViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return CustomerProfile.objects.none()
        qs = CustomerProfile.objects.filter(store=store).select_related('customer').prefetch_related('interactions')
        
        segment = self.request.query_params.get('segment')
        if segment:
            qs = qs.filter(segment=segment)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(customer__full_name__icontains=search) | qs.filter(customer__phone_number__icontains=search)
            
        return qs

    @action(detail=False, methods=['post'], url_path='recalculate-all')
    def recalculate_all(self, request):
        count = recalculate_all_store_customers(request.store)
        return Response({
            'message': f'شاخص‌های RFM و ارزش طول عمر {count} مشتری با موفقیت به‌روزرسانی شد.',
            'count': count
        })

    @action(detail=True, methods=['post'], url_path='add-interaction')
    def add_interaction(self, request, pk=None):
        profile = self.get_object()
        data = request.data
        interaction = CustomerInteraction.objects.create(
            profile=profile,
            interaction_type=data.get('interaction_type', 'INTERNAL_NOTE'),
            summary=data.get('summary', 'تعامل با مشتری'),
            details=data.get('details', ''),
            follow_up_needed=data.get('follow_up_needed', False),
            follow_up_date=data.get('follow_up_date'),
            created_by=request.user
        )
        return Response(CustomerInteractionSerializer(interaction).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='segments-summary')
    def segments_summary(self, request):
        store = request.store
        data = []
        for segment_code, segment_label in CustomerSegment.choices:
            count = CustomerProfile.objects.filter(store=store, segment=segment_code).count()
            total_val = CustomerProfile.objects.filter(store=store, segment=segment_code).aggregate(s=Sum('monetary_total_spent'))['s'] or 0
            data.append({
                'segment': segment_code,
                'label': segment_label,
                'count': count,
                'total_revenue': str(total_val)
            })
        return Response(data)
