from django.utils import timezone
from django.db.models import Count, Q
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound

from apps.tenancy.permissions import (
    IsStoreMemberPermission,
    TenantFilterBackend,
    get_request_store,
    user_has_store_permission
)
from apps.features.permissions import RequiresFeature
from .models import (
    TaskCategory,
    Task,
    TaskStatus,
    TaskChecklistItem,
    TaskComment
)
from .serializers import (
    TaskCategorySerializer,
    TaskListSerializer,
    TaskDetailSerializer,
    TaskCreateUpdateSerializer,
    TaskStatusChangeInputSerializer,
    TaskVerificationInputSerializer,
    TaskCommentSerializer,
    TaskCommentInputSerializer,
    TaskChecklistItemSerializer
)
from .services import TaskService


class TaskCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = TaskCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission, RequiresFeature('tasks.planner')]
    filter_backends = [TenantFilterBackend]
    queryset = TaskCategory.objects.all()

    def perform_create(self, serializer):
        store = get_request_store(self.request)
        serializer.save(store=store)


class TaskViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission, RequiresFeature('tasks.planner')]
    filter_backends = [TenantFilterBackend]
    queryset = Task.objects.select_related(
        'store', 'category', 'creator', 'assignee', 'reviewer', 'related_product', 'related_order'
    ).prefetch_related('checklist_items', 'comments', 'activity_logs').all()

    def get_serializer_class(self):
        if self.action == 'list':
            return TaskListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return TaskCreateUpdateSerializer
        return TaskDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        store = get_request_store(self.request)
        membership = getattr(self.request, 'membership', None)

        # RBAC Check: View Assigned Only vs View All
        has_view_all = user_has_store_permission(membership, 'tasks.view_all')
        has_view_assigned = user_has_store_permission(membership, 'tasks.view_assigned')

        if not (has_view_all or has_view_assigned):
            return qs.none()

        if not has_view_all and has_view_assigned:
            qs = qs.filter(Q(assignee=self.request.user) | Q(creator=self.request.user))

        # Query Filters
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        priority_param = self.request.query_params.get('priority')
        if priority_param:
            qs = qs.filter(priority=priority_param)

        category_param = self.request.query_params.get('category')
        if category_param:
            qs = qs.filter(category_id=category_param)

        assignee_param = self.request.query_params.get('assignee')
        if assignee_param:
            qs = qs.filter(assignee_id=assignee_param)

        my_tasks = self.request.query_params.get('my_tasks')
        if my_tasks in ['true', '1']:
            qs = qs.filter(assignee=self.request.user)

        overdue = self.request.query_params.get('overdue')
        if overdue in ['true', '1']:
            qs = qs.filter(
                due_date__lt=timezone.now().date()
            ).exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED])

        return qs

    def perform_create(self, serializer):
        membership = getattr(self.request, 'membership', None)
        if not user_has_store_permission(membership, 'tasks.create'):
            raise PermissionDenied("شما دسترسی لازم برای ایجاد وظیفه را ندارید.")

        store = get_request_store(self.request)
        validated_data = serializer.validated_data
        checklist_items = validated_data.pop('checklist_items', [])

        task = TaskService.create_task(
            store=store,
            creator=self.request.user,
            data=validated_data,
            checklist_items=checklist_items
        )
        serializer.instance = task

    @action(detail=True, methods=['post'], url_path='status')
    def change_status(self, request, pk=None):
        task = self.get_object()
        membership = getattr(request, 'membership', None)
        
        # User must have tasks.complete or tasks.edit or be the assignee
        can_complete = (
            user_has_store_permission(membership, 'tasks.complete')
            or user_has_store_permission(membership, 'tasks.edit')
            or task.assignee_id == request.user.id
        )
        if not can_complete:
            raise PermissionDenied("دسترسی تغییر وضعیت این وظیفه را ندارید.")

        input_serializer = TaskStatusChangeInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        new_status = input_serializer.validated_data['status']
        evidence = input_serializer.validated_data.get('completion_evidence', '')

        updated_task = TaskService.update_task_status(
            task=task,
            new_status=new_status,
            actor=request.user,
            completion_evidence=evidence
        )

        return Response(TaskDetailSerializer(updated_task).data)

    @action(detail=True, methods=['post'], url_path='verify')
    def verify(self, request, pk=None):
        task = self.get_object()
        membership = getattr(request, 'membership', None)

        can_verify = (
            user_has_store_permission(membership, 'tasks.verify')
            or (task.reviewer_id and task.reviewer_id == request.user.id)
            or (task.creator_id == request.user.id)
        )
        if not can_verify:
            raise PermissionDenied("شما دسترسی لازم جهت بازبینی و تایید این وظیفه را ندارید.")

        input_serializer = TaskVerificationInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        approved = input_serializer.validated_data.get('approved', True)
        feedback = input_serializer.validated_data.get('feedback', '')

        updated_task = TaskService.verify_task(
            task=task,
            reviewer=request.user,
            approved=approved,
            feedback=feedback
        )

        return Response(TaskDetailSerializer(updated_task).data)

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None):
        task = self.get_object()
        if request.method == 'GET':
            comments = task.comments.select_related('author').all()
            return Response(TaskCommentSerializer(comments, many=True).data)

        # POST: add comment
        input_serializer = TaskCommentInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        comment = TaskService.add_comment(
            task=task,
            author=request.user,
            content=input_serializer.validated_data['content']
        )
        return Response(TaskCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='checklist')
    def add_checklist_item(self, request, pk=None):
        task = self.get_object()
        title = request.data.get('title', '').strip()
        if not title:
            return Response({'title': 'عنوان نمی‌تواند خالی باشد.'}, status=status.HTTP_400_BAD_REQUEST)

        order = task.checklist_items.count()
        item = TaskChecklistItem.objects.create(task=task, title=title, order=order)
        return Response(TaskChecklistItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path=r'checklist/(?P<item_id>[^/.]+)/toggle')
    def toggle_checklist(self, request, pk=None, item_id=None):
        task = self.get_object()
        try:
            item = task.checklist_items.get(id=item_id)
        except TaskChecklistItem.DoesNotExist:
            raise NotFound("مورد چک‌لیست یافت نشد.")

        updated_item = TaskService.toggle_checklist_item(item, request.user)
        return Response(TaskChecklistItemSerializer(updated_item).data)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Returns statistics for task dashboard cards"""
        qs = self.get_queryset()
        counts = {
            'total': qs.count(),
            'todo': qs.filter(status=TaskStatus.TODO).count(),
            'in_progress': qs.filter(status=TaskStatus.IN_PROGRESS).count(),
            'in_review': qs.filter(status=TaskStatus.IN_REVIEW).count(),
            'completed': qs.filter(status=TaskStatus.COMPLETED).count(),
            'overdue': qs.filter(
                due_date__lt=timezone.now().date()
            ).exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED]).count(),
            'my_tasks': qs.filter(assignee=request.user).count(),
        }
        return Response(counts)
