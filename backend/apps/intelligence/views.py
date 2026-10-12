from rest_framework.views import APIView
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from apps.orders.models import Order
from apps.tenancy.permissions import IsStoreMemberPermission
from .models import CustomerFeedback, CompetitorPriceTrack
from .serializers import CustomerFeedbackSerializer, CompetitorPriceTrackSerializer
from .services import calculate_demand_forecasts, calculate_slow_movers, evaluate_order_risk, ask_ai_business_copilot

class DemandForecastView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        forecasts = calculate_demand_forecasts(request.store, period_days=days)
        return Response(forecasts)


class SlowMoversView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get(self, request):
        days = int(request.query_params.get('days', 60))
        data = calculate_slow_movers(request.store, period_days=days)
        return Response(data)


class OrderRiskView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, store=request.store)
        except Order.DoesNotExist:
            return Response({'error': 'سفارش یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        risk = evaluate_order_risk(order)
        return Response(risk)


class AICopilotView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def post(self, request):
        question = request.data.get('question', '').strip()
        if not question:
            return Response({'error': 'پرسش نمی‌تواند خالی باشد.'}, status=status.HTTP_400_BAD_REQUEST)

        answer_data = ask_ai_business_copilot(request.store, question)
        return Response(answer_data)


class CustomerFeedbackViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]
    serializer_class = CustomerFeedbackSerializer

    def get_queryset(self):
        qs = CustomerFeedback.objects.filter(store=self.request.store).select_related('customer', 'order')
        cat = self.request.query_params.get('category')
        sentiment = self.request.query_params.get('sentiment')
        resolved = self.request.query_params.get('is_resolved')
        if cat:
            qs = qs.filter(category=cat)
        if sentiment:
            qs = qs.filter(sentiment=sentiment)
        if resolved is not None:
            qs = qs.filter(is_resolved=(resolved.lower() in ['true', '1']))
        return qs

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)


class CompetitorPriceTrackViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]
    serializer_class = CompetitorPriceTrackSerializer

    def get_queryset(self):
        return CompetitorPriceTrack.objects.filter(store=self.request.store).select_related('variant', 'variant__product')

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)
