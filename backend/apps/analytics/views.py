from rest_framework.views import APIView
from rest_framework.response import Response
from apps.tenancy.permissions import IsStoreMemberPermission
from .services import calculate_store_overview_metrics

class OverviewAnalyticsAPIView(APIView):
    permission_classes = [IsStoreMemberPermission]

    def get(self, request):
        days_param = request.query_params.get('days', '30')
        try:
            days = int(days_param)
        except ValueError:
            days = 30

        metrics = calculate_store_overview_metrics(store=request.store, days=days)
        return Response(metrics)
