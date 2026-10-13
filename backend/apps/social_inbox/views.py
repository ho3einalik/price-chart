from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ConversationThread, ChatMessage, ThreadStatus
from .serializers import ConversationThreadSerializer, ChatMessageSerializer
from .services import generate_ai_suggested_reply, send_agent_message
from apps.tenancy.permissions import IsStoreMemberPermission

class ConversationThreadViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationThreadSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return ConversationThread.objects.none()
        qs = ConversationThread.objects.filter(store=store).select_related('customer', 'assigned_to').prefetch_related('messages')
        
        channel = self.request.query_params.get('channel')
        if channel:
            qs = qs.filter(channel=channel)

        status_val = self.request.query_params.get('status')
        if status_val:
            qs = qs.filter(status=status_val)

        return qs

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)

    @action(detail=True, methods=['post'], url_path='send-message')
    def send_message(self, request, pk=None):
        thread = self.get_object()
        text = request.data.get('text', '').strip()
        if not text:
            return Response({'error': 'متن پیام نمی‌تواند خالی باشد.'}, status=status.HTTP_400_BAD_REQUEST)

        is_ai = request.data.get('is_ai_generated', False)
        was_edited = request.data.get('was_edited_by_human', False)

        msg = send_agent_message(
            thread=thread,
            text=text,
            user=request.user,
            is_ai=is_ai,
            was_edited=was_edited
        )
        return Response(ChatMessageSerializer(msg).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='suggest-ai-reply')
    def suggest_ai_reply(self, request, pk=None):
        thread = self.get_object()
        result = generate_ai_suggested_reply(thread)
        return Response(result)

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve_thread(self, request, pk=None):
        thread = self.get_object()
        thread.status = ThreadStatus.RESOLVED
        thread.save(update_fields=['status'])
        return Response({'message': 'مکالمه با موفقیت بسته و حل‌وفصل شد.'})

    @action(detail=True, methods=['post'], url_path='assign')
    def assign_agent(self, request, pk=None):
        thread = self.get_object()
        user_id = request.data.get('user_id')
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                thread.assigned_to = user
            except User.DoesNotExist:
                return Response({'error': 'کاربر انتخاب‌شده یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            thread.assigned_to = request.user

        thread.save(update_fields=['assigned_to'])
        return Response(ConversationThreadSerializer(thread).data)

    @action(detail=True, methods=['post'], url_path='link-order')
    def link_order(self, request, pk=None):
        thread = self.get_object()
        order_id = request.data.get('order_id')
        if not order_id:
            thread.order = None
            thread.save(update_fields=['order'])
            return Response(ConversationThreadSerializer(thread).data)

        from apps.orders.models import Order
        order = Order.objects.filter(store=request.store, id=order_id).first()
        if not order:
            return Response({'error': 'سفارش یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        thread.order = order
        thread.save(update_fields=['order'])
        return Response(ConversationThreadSerializer(thread).data)

    @action(detail=True, methods=['post'], url_path='update-notes')
    def update_notes(self, request, pk=None):
        thread = self.get_object()
        internal_notes = request.data.get('internal_notes')
        auto_reply = request.data.get('auto_reply_enabled')
        tags = request.data.get('tags')

        fields_to_update = []
        if internal_notes is not None:
            thread.internal_notes = internal_notes
            fields_to_update.append('internal_notes')
        if auto_reply is not None:
            thread.auto_reply_enabled = bool(auto_reply)
            fields_to_update.append('auto_reply_enabled')
        if tags is not None and isinstance(tags, list):
            thread.tags = tags
            fields_to_update.append('tags')

        if fields_to_update:
            thread.save(update_fields=fields_to_update)

        return Response(ConversationThreadSerializer(thread).data)
