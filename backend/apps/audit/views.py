import csv
from django.http import HttpResponse
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action

from apps.tenancy.permissions import IsStoreMemberPermission
from .models import AuditLog, Notification, NotificationPreference
from .serializers import AuditLogSerializer, NotificationSerializer, NotificationPreferenceSerializer

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        qs = AuditLog.objects.filter(store=self.request.store).select_related('user')
        action_name = self.request.query_params.get('action')
        target_type = self.request.query_params.get('target_type')
        if action_name:
            qs = qs.filter(action__icontains=action_name)
        if target_type:
            qs = qs.filter(target_type=target_type)
        return qs


class NotificationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(store=self.request.store).filter(
            Q(user=self.request.user) | Q(user__isnull=True)
        )
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            qs = qs.filter(is_read=(is_read.lower() in ['true', '1']))
        return qs

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response({'message': 'اعلان به عنوان خوانده‌شده علامت‌گذاری شد.'})

    @action(detail=False, methods=['post'], url_path='read-all')
    def mark_all_read(self, request):
        Notification.objects.filter(store=request.store).filter(
            Q(user=request.user) | Q(user__isnull=True)
        ).update(is_read=True)
        return Response({'message': 'تمامی اعلان‌ها به عنوان خوانده‌شده علامت‌گذاری شدند.'})


class NotificationPreferenceView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get(self, request):
        pref, _ = NotificationPreference.objects.get_or_create(
            user=request.user,
            store=request.store
        )
        return Response(NotificationPreferenceSerializer(pref).data)

    def put(self, request):
        pref, _ = NotificationPreference.objects.get_or_create(
            user=request.user,
            store=request.store
        )
        serializer = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TeamActivitySummaryView(APIView):
    """
    Team workload and action audit overview.
    Aggregates log events per team member over the last N days.
    """
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        cutoff = timezone.now() - timedelta(days=days)

        logs = AuditLog.objects.filter(store=request.store, created_at__gte=cutoff).exclude(user__isnull=True)

        user_counts = logs.values('user__id', 'user__username', 'user__first_name', 'user__last_name').annotate(
            total_actions=Count('id')
        ).order_by('-total_actions')

        activities = []
        for uc in user_counts:
            full_name = f"{uc['user__first_name']} {uc['user__last_name']}".strip() or uc['user__username']
            # Top actions by this user
            top_acts = AuditLog.objects.filter(
                store=request.store,
                user_id=uc['user__id'],
                created_at__gte=cutoff
            ).values('action').annotate(cnt=Count('id')).order_by('-cnt')[:3]

            activities.append({
                'user_id': str(uc['user__id']),
                'user_name': full_name,
                'total_actions': uc['total_actions'],
                'top_actions': list(top_acts)
            })

        return Response({
            'period_days': days,
            'team_activities': activities
        })


class AuditExportCSVView(APIView):
    """
    Export immutable audit log to CSV with Persian UTF-8 BOM.
    """
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['شناسه', 'کاربر', 'عملیات', 'نوع موجودیت', 'شناسه موجودیت', 'آدرس IP', 'زمان ثبت'])

        logs = AuditLog.objects.filter(store=request.store).select_related('user').order_by('-created_at')[:1000]
        for log in logs:
            writer.writerow([
                str(log.id),
                log.user.username if log.user else 'سیستم خودکار',
                log.action,
                log.target_type,
                log.target_id,
                log.ip_address or '-',
                log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

        return response
