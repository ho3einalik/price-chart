from .permissions import get_request_store

class TenantContextMiddleware:
    """Extracts X-Store-Id header and binds active store & membership to request"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        get_request_store(request)
        response = self.get_response(request)
        return response

