from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import AutomationRule, AutomationExecutionLog
from .serializers import AutomationRuleSerializer, AutomationExecutionLogSerializer
from .services import execute_actions, evaluate_conditions
from apps.tenancy.permissions import IsStoreMemberPermission

class AutomationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = AutomationRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return AutomationRule.objects.none()
        return AutomationRule.objects.filter(store=store).prefetch_related('logs')

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)

    @action(detail=True, methods=['post'], url_path='test-run')
    def test_run(self, request, pk=None):
        rule = self.get_object()
        sample_payload = request.data.get('payload', {})
        dry_run = request.data.get('dry_run', True)
        matches = evaluate_conditions(rule.conditions, sample_payload)
        if not matches:
            return Response({
                'matched': False,
                'message': 'داده‌های تستی ارسالی با شرایط تعیین‌شده در این قانون مطابقت ندارند.'
            })

        output = execute_actions(rule, rule.actions, sample_payload, dry_run=dry_run)
        return Response({
            'matched': True,
            'dry_run': dry_run,
            'message': 'قانون اتوماسیون با موفقیت شبیه‌سازی و تست شد.' if dry_run else 'قانون اتوماسیون با موفقیت تست و اجرا شد.',
            'execution_output': output
        })
