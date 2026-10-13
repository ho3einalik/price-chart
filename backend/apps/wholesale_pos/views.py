from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.tenancy.permissions import IsStoreMemberPermission
from .models import B2BClientProfile, VolumeTierDiscount, POSTerminal, POSRegisterSession, POSSessionStatus, ProformaInvoice
from .serializers import (
    B2BClientProfileSerializer,
    VolumeTierDiscountSerializer,
    POSTerminalSerializer,
    POSRegisterSessionSerializer,
    ProformaInvoiceSerializer
)
from .services import pos_quick_checkout, convert_proforma_to_order

class B2BClientProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]
    serializer_class = B2BClientProfileSerializer

    def get_queryset(self):
        return B2BClientProfile.objects.filter(store=self.request.store).select_related('customer')

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)


class VolumeTierDiscountViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]
    serializer_class = VolumeTierDiscountSerializer

    def get_queryset(self):
        qs = VolumeTierDiscount.objects.filter(store=self.request.store).select_related('variant')
        variant_id = self.request.query_params.get('variant_id')
        if variant_id:
            qs = qs.filter(variant_id=variant_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)


class POSTerminalViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]
    serializer_class = POSTerminalSerializer

    def get_queryset(self):
        return POSTerminal.objects.filter(store=self.request.store).select_related('warehouse')

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)


class POSRegisterSessionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]
    serializer_class = POSRegisterSessionSerializer

    def get_queryset(self):
        return POSRegisterSession.objects.filter(store=self.request.store).select_related('terminal', 'opened_by', 'closed_by')

    def perform_create(self, serializer):
        serializer.save(
            store=self.request.store,
            opened_by=self.request.user,
            status=POSSessionStatus.OPEN
        )

    @action(detail=True, methods=['post'], url_path='close-session')
    def close_session(self, request, pk=None):
        session = self.get_object()
        if session.status == POSSessionStatus.CLOSED:
            return Response({'error': 'این شیفت صندوقداری قبلاً بسته شده است.'}, status=status.HTTP_400_BAD_REQUEST)

        closing_cash = request.data.get('closing_cash', session.opening_cash)
        notes = request.data.get('notes', '')

        session.status = POSSessionStatus.CLOSED
        session.closed_by = request.user
        session.closed_at = timezone.now()
        session.closing_cash = closing_cash
        if notes:
            session.notes = (session.notes + "\n" + notes).strip()
        session.save()

        return Response(POSRegisterSessionSerializer(session).data)


class ProformaInvoiceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]
    serializer_class = ProformaInvoiceSerializer

    def get_queryset(self):
        return ProformaInvoice.objects.filter(store=self.request.store).select_related('client', 'client__customer')

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)

    @action(detail=True, methods=['post'], url_path='convert-to-order')
    def convert_to_order_action(self, request, pk=None):
        proforma = self.get_object()
        try:
            order = convert_proforma_to_order(proforma, user=request.user)
            return Response({
                'message': 'پیش‌فاکتور با موفقیت به سفارش نهایی تبدیل و موجودی رزرو شد.',
                'order_id': str(order.id),
                'order_number': order.order_number,
                'grand_total': str(order.grand_total)
            })
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)


class POSQuickCheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def post(self, request):
        session_id = request.data.get('session_id')
        items = request.data.get('items', [])
        customer_phone = request.data.get('customer_phone', '09000000000')
        customer_name = request.data.get('customer_name', 'خریدار حضوری')
        payment_method = request.data.get('payment_method', 'POS_TERMINAL')
        notes = request.data.get('notes', '')

        if not session_id:
            return Response({'error': 'شناسه شیفت صندوق (session_id) الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)
        if not items:
            return Response({'error': 'سبد خرید صندوق خالی است.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = pos_quick_checkout(
                store=request.store,
                session_id=session_id,
                items_data=items,
                customer_phone=customer_phone,
                customer_name=customer_name,
                payment_method=payment_method,
                user=request.user,
                notes=notes
            )
            return Response({
                'message': 'فروش حضوری با موفقیت ثبت شد و فاکتور صادر گردید.',
                'order_id': str(order.id),
                'order_number': order.order_number,
                'grand_total': str(order.grand_total),
                'currency': order.currency,
                'items_count': len(items)
            }, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f"خطا در ثبت فروش صندوق: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
