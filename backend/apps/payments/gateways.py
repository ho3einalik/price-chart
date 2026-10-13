import os
import json
import logging
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class GatewayPaymentResult:
    def __init__(self, success: bool, status: str, tracking_code: str = "", message: str = "", raw_response: Optional[Dict[str, Any]] = None):
        self.success = success
        self.status = status
        self.tracking_code = tracking_code
        self.message = message
        self.raw_response = raw_response or {}

    def to_dict(self):
        return {
            'success': self.success,
            'status': self.status,
            'tracking_code': self.tracking_code,
            'message': self.message,
            'raw_response': self.raw_response
        }


class BasePaymentGateway(ABC):
    gateway_name: str = ""

    @abstractmethod
    def request_payment(self, amount: Decimal, callback_url: str, description: str, order_id: str, store=None) -> Dict[str, Any]:
        """Initiate payment request with the gateway"""
        pass

    @abstractmethod
    def verify_payment(self, authority: str, amount: Decimal, store=None) -> GatewayPaymentResult:
        """Server-to-server payment verification"""
        pass


class ZarinpalGatewayAdapter(BasePaymentGateway):
    gateway_name = "zarinpal"

    def _get_merchant_id(self, store=None) -> Optional[str]:
        merchant_id = os.environ.get('ZARINPAL_MERCHANT_ID')
        if not merchant_id and store:
            settings = getattr(store, 'feature_settings', None)
            if settings and settings.feature_configs:
                merchant_id = settings.feature_configs.get('zarinpal_merchant_id')
        return merchant_id

    def _is_sandbox(self) -> bool:
        return os.environ.get('ZARINPAL_SANDBOX', 'False').lower() in ('true', '1', 't')

    def request_payment(self, amount: Decimal, callback_url: str, description: str, order_id: str, store=None) -> Dict[str, Any]:
        merchant_id = self._get_merchant_id(store)
        if not merchant_id:
            return {
                'success': False,
                'status': 'REQUIRES_GATEWAY_CONFIG',
                'message': 'مرچنت زرین‌پال در تنظیمات فروشگاه یا متغیرهای سیستمی پیکربندی نشده است.'
            }

        prefix = "sandbox" if self._is_sandbox() else "www"
        url = f"https://{prefix}.zarinpal.com/pg/rest/WebGate/PaymentRequest.json"

        payload = {
            'MerchantID': merchant_id,
            'Amount': int(amount),
            'CallbackURL': callback_url,
            'Description': description,
            'Metadata': {'order_id': order_id}
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                status_code = data.get('Status')
                authority = data.get('Authority')
                if status_code == 100 and authority:
                    payment_url = f"https://{prefix}.zarinpal.com/pg/StartPay/{authority}"
                    return {
                        'success': True,
                        'status': 'INITIATED',
                        'authority': authority,
                        'payment_url': payment_url
                    }
                return {
                    'success': False,
                    'status': 'GATEWAY_ERROR',
                    'error_code': status_code,
                    'message': f"پاسخ درگاه زرین‌پال با کد خطا: {status_code}"
                }
        except Exception as e:
            logger.error(f"Zarinpal request payment failed: {e}")
            return {
                'success': False,
                'status': 'COMMUNICATION_ERROR',
                'message': f"خطا در برقراری ارتباط با زرین‌پال: {str(e)}"
            }

    def verify_payment(self, authority: str, amount: Decimal, store=None) -> GatewayPaymentResult:
        merchant_id = self._get_merchant_id(store)
        if not merchant_id:
            return GatewayPaymentResult(
                success=False,
                status='REQUIRES_GATEWAY_CONFIG',
                message='مرچنت زرین‌پال در تنظیمات فروشگاه یا متغیرهای سیستمی پیکربندی نشده است.'
            )

        prefix = "sandbox" if self._is_sandbox() else "www"
        url = f"https://{prefix}.zarinpal.com/pg/rest/WebGate/PaymentVerification.json"
        payload = {
            'MerchantID': merchant_id,
            'Authority': authority,
            'Amount': int(amount)
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                status_code = data.get('Status')
                ref_id = str(data.get('RefID', ''))
                if status_code in (100, 101):
                    return GatewayPaymentResult(
                        success=True,
                        status='VERIFIED',
                        tracking_code=ref_id,
                        message='تراکنش با موفقیت در زرین‌پال تأیید شد.',
                        raw_response=data
                    )
                return GatewayPaymentResult(
                    success=False,
                    status='REJECTED_BY_GATEWAY',
                    message=f"تراکنش توسط درگاه تأیید نشد (کد وضعیت: {status_code}).",
                    raw_response=data
                )
        except Exception as e:
            logger.error(f"Zarinpal verification failed: {e}")
            return GatewayPaymentResult(
                success=False,
                status='COMMUNICATION_ERROR',
                message=f"خطا در استعلام از درگاه پرداخت: {str(e)}"
            )


GATEWAY_REGISTRY = {
    'zarinpal': ZarinpalGatewayAdapter(),
}


def get_payment_gateway(name: str = 'zarinpal') -> Optional[BasePaymentGateway]:
    return GATEWAY_REGISTRY.get(name)
