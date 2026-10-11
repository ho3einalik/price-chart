from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from apps.tenancy.permissions import IsStoreMemberPermission, TenantFilterBackend
from .models import DailyAction, ActionStatus
from .serializers import DailyActionSerializer, UpdateActionStatusSerializer
from .services import sync_daily_actions_for_store

class DailyActionViewSet(viewsets.ModelViewSet):
    serializer_class = DailyActionSerializer
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'severity']
    ordering_fields = ['created_at', 'severity']
    queryset = DailyAction.objects.all()

    def list(self, request, *args, **kwargs):
        # Always run sync to surface active operational alerts
        sync_daily_actions_for_store(request.store)
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        daily_action = self.get_object()
        serializer = UpdateActionStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        note = serializer.validated_data.get('resolution_note', '')

        daily_action.status = new_status
        if note:
            daily_action.resolution_note = note
        if new_status in [ActionStatus.RESOLVED, ActionStatus.DISMISSED]:
            daily_action.resolved_at = timezone.now()
        daily_action.save()

        return Response(DailyActionSerializer(daily_action).data, status=status.HTTP_200_OK)
