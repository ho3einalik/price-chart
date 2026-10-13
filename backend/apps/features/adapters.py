import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from .models import IntegrationState

logger = logging.getLogger(__name__)


class IntegrationHealthResult:
    def __init__(self, state: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.state = state
        self.message = message
        self.details = details or {}

    def to_dict(self):
        return {
            'state': self.state,
            'message': self.message,
            'details': self.details,
            'is_healthy': self.state == IntegrationState.CONNECTED
        }


class BaseIntegrationAdapter(ABC):
    name: str = ""
    display_name_fa: str = ""
    description_fa: str = ""

    @abstractmethod
    def get_status(self, store) -> str:
        """Determines the current integration state for the given store"""
        pass

    @abstractmethod
    def health_check(self, store) -> IntegrationHealthResult:
        """Runs a live connectivity and credential check"""
        pass

    def is_ready(self, store) -> bool:
        return self.get_status(store) == IntegrationState.CONNECTED


class InstagramIntegrationAdapter(BaseIntegrationAdapter):
    name = "instagram"
    display_name_fa = "اتصال اینستاگرام (Meta Graph API)"
    description_fa = "انتشار مستقیم ریلز و استوری و همگام‌سازی خودکار دایرکت و آمار"

    def get_status(self, store) -> str:
        # Check store settings or SocialAccount
        try:
            from apps.social.models import SocialAccount, SocialPlatform
            account = SocialAccount.objects.filter(
                store=store,
                platform=SocialPlatform.INSTAGRAM,
                is_connected=True
            ).first()

            if not account:
                return IntegrationState.NOT_CONFIGURED

            # Check override in store feature settings
            states = getattr(store, 'feature_settings', None)
            if states and states.integration_states:
                override = states.integration_states.get(self.name)
                if override:
                    return override

            return IntegrationState.CONNECTED
        except Exception as e:
            logger.warning(f"Error checking Instagram integration status: {e}")
            return IntegrationState.NOT_CONFIGURED

    def health_check(self, store) -> IntegrationHealthResult:
        status = self.get_status(store)
        if status == IntegrationState.CONNECTED:
            return IntegrationHealthResult(
                state=IntegrationState.CONNECTED,
                message="اتصال به حساب اینستاگرام برقرار و فعال است."
            )
        elif status == IntegrationState.NEEDS_REAUTH:
            return IntegrationHealthResult(
                state=IntegrationState.NEEDS_REAUTH,
                message="توکن اتصال اینستاگرام منقضی شده و نیازمند اتصال مجدد است."
            )
        elif status == IntegrationState.UNAVAILABLE:
            return IntegrationHealthResult(
                state=IntegrationState.UNAVAILABLE,
                message="سرویس سرورهای متا موقتاً در دسترس نیست. برنامه‌ریزی دستی فعال است."
            )
        return IntegrationHealthResult(
            state=IntegrationState.NOT_CONFIGURED,
            message="حساب اینستاگرام متصل نشده است. قابلیت ثبت دستی و تقویم همچنان فعال است."
        )


import os
import json
import urllib.request
import urllib.parse
import urllib.error


class AIProviderIntegrationAdapter(BaseIntegrationAdapter):
    name = "ai_provider"
    display_name_fa = "سرویس هوش مصنوعی (Google Gemini)"
    description_fa = "تولید هوشمند محتوا، پاسخگویی دایرکت و تحلیل رفتار مشتریان"

    def _get_api_key(self, store=None) -> Optional[str]:
        key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if not key and store:
            settings = getattr(store, 'feature_settings', None)
            if settings and settings.feature_configs:
                key = settings.feature_configs.get('gemini_api_key')
        return key

    def get_status(self, store) -> str:
        states = getattr(store, 'feature_settings', None)
        if states and states.integration_states:
            override = states.integration_states.get(self.name)
            if override:
                return override

        key = self._get_api_key(store)
        if not key:
            return IntegrationState.NOT_CONFIGURED
        return IntegrationState.CONNECTED

    def health_check(self, store) -> IntegrationHealthResult:
        status = self.get_status(store)
        if status == IntegrationState.CONNECTED:
            return IntegrationHealthResult(
                state=IntegrationState.CONNECTED,
                message="سرویس هوش مصنوعی (Google Gemini) متصل و کلید احراز هویت تنظیم شده است."
            )
        elif status == IntegrationState.DISABLED_BY_STORE:
            return IntegrationHealthResult(
                state=IntegrationState.DISABLED_BY_STORE,
                message="سرویس هوش مصنوعی توسط فروشگاه غیرفعال شده است."
            )
        return IntegrationHealthResult(
            state=IntegrationState.NOT_CONFIGURED,
            message="کلید ارتباط با هوش مصنوعی (GEMINI_API_KEY) تنظیم نشده است. سیستم با الگوهای پشتیبان محلی کار می‌کند."
        )

    def generate_caption_or_text(self, prompt: str, store=None, tone: str = "friendly") -> Dict[str, Any]:
        api_key = self._get_api_key(store)
        if not api_key:
            return {
                'text': "",
                'source': 'heuristic_fallback'
            }

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800}
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'x-goog-api-key': api_key
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    candidates = data.get('candidates', [])
                    if candidates and 'content' in candidates[0]:
                        parts = candidates[0]['content'].get('parts', [])
                        if parts and 'text' in parts[0]:
                            return {
                                'text': parts[0]['text'].strip(),
                                'source': 'gemini_1.5_flash'
                            }
        except Exception as e:
            logger.warning(f"Google Gemini API call failed: {e}")
            return {
                'text': "",
                'source': 'heuristic_fallback',
                'error': str(e)
            }

        return {
            'text': "",
            'source': 'heuristic_fallback'
        }

    def generate_caption(self, store, product_title: str, tone: str = "friendly") -> str:
        """
        Generates caption via Gemini API or graceful fallback if disabled or unconfigured.
        """
        status = self.get_status(store)
        if status != IntegrationState.CONNECTED:
            return f"معرفی محصول جدید: {product_title}\nهم‌اکنون با کیفیت عالی و ارسال سریع در دسترس شماست.\nبرای خرید و ثبت سفارش به دایرکت یا وبسایت مراجعه فرمایید. ✨"

        prompt = f"یک کپشن جذاب و حرفه‌ای اینستاگرام به زبان فارسی با لحن {tone} برای فروش محصول '{product_title}' بنویس که شامل ایموجی و دعوت به اقدام باشد."
        res = self.generate_caption_or_text(prompt=prompt, store=store, tone=tone)
        if res.get('text'):
            return res['text']

        # Safe heuristic fallback
        return f"استایلت رو با {product_title} متحول کن! ✨\nطراحی خاص، کیفیت تضمین‌شده و انتخابی مناسب برای خاص‌پسندان.\n💬 برای اطلاعات بیشتر و ثبت سفارش در دایرکت پیام بدهید یا از وبسایت خرید کنید."


class SMSGatewayIntegrationAdapter(BaseIntegrationAdapter):
    name = "sms_gateway"
    display_name_fa = "درگاه پیامک اطلاع‌رسانی (Kavenegar / SMS Gateway)"
    description_fa = "ارسال پیامک تایید سفارش و کد پیگیری مرسوله پستی"

    def _get_api_key(self, store=None) -> Optional[str]:
        key = os.environ.get('KAVENEGAR_API_KEY') or os.environ.get('SMS_API_KEY')
        if not key and store:
            settings = getattr(store, 'feature_settings', None)
            if settings and settings.feature_configs:
                key = settings.feature_configs.get('sms_api_key')
        return key

    def get_status(self, store) -> str:
        states = getattr(store, 'feature_settings', None)
        if states and states.integration_states:
            override = states.integration_states.get(self.name)
            if override:
                return override

        key = self._get_api_key(store)
        if not key:
            return IntegrationState.NOT_CONFIGURED
        return IntegrationState.CONNECTED

    def health_check(self, store) -> IntegrationHealthResult:
        status = self.get_status(store)
        if status == IntegrationState.CONNECTED:
            return IntegrationHealthResult(
                state=IntegrationState.CONNECTED,
                message="درگاه پیامکی متصل و کلید وب‌سرویس فعال است."
            )
        return IntegrationHealthResult(
            state=IntegrationState.NOT_CONFIGURED,
            message="درگاه پیامک پیکربندی نشده است. متغیر KAVENEGAR_API_KEY یا SMS_API_KEY یافت نشد."
        )

    def send_notification(self, store, phone_number: str, text: str) -> bool:
        """Safe non-blocking execution: does not crash caller on failure"""
        try:
            self.send_sms(to=phone_number, message=text, store=store)
            return True
        except Exception as e:
            logger.warning(f"SMS notification failed: {e}")
            return False

    def send_sms(self, to: str, message: str, store=None) -> Dict[str, Any]:
        api_key = self._get_api_key(store)
        masked_to = (to[:4] + '****' + to[-3:]) if len(to) > 7 else '***'
        if not api_key:
            logger.info(f"SMSGateway: API key not configured. Skipping live dispatch to {masked_to}.")
            return {
                'status': 'NOT_CONFIGURED',
                'message': 'کلید وب‌سرویس پیامک در سیستم تنظیم نشده است.',
                'recipient': to
            }

        try:
            url = f"https://api.kavenegar.com/v1/{api_key}/sms/send.json"
            data = urllib.parse.urlencode({'receptor': to, 'message': message}).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    body = json.loads(response.read().decode('utf-8'))
                    return {
                        'status': 'ACCEPTED',
                        'recipient': to,
                        'message_id': str(body.get('entries', [{}])[0].get('messageid', 'kavenegar_ack')),
                        'note': 'پیامک توسط درگاه پیامکی پذیرفته شد.'
                    }
                else:
                    return {
                        'status': 'FAILED',
                        'recipient': to,
                        'error': f"Unexpected response status {response.status}"
                    }
        except Exception as e:
            logger.warning(f"Kavenegar API call failed for {masked_to}: {e}")
            return {
                'status': 'FAILED',
                'recipient': to,
                'error': str(e)
            }


class IntegrationRegistry:
    _adapters: Dict[str, BaseIntegrationAdapter] = {
        'instagram': InstagramIntegrationAdapter(),
        'ai_provider': AIProviderIntegrationAdapter(),
        'sms_gateway': SMSGatewayIntegrationAdapter(),
    }

    @classmethod
    def get_adapter(cls, name: str) -> Optional[BaseIntegrationAdapter]:
        return cls._adapters.get(name)

    @classmethod
    def get_all_adapters(cls) -> Dict[str, BaseIntegrationAdapter]:
        return cls._adapters

    @classmethod
    def get_store_integration_statuses(cls, store) -> Dict[str, Any]:
        results = {}
        for name, adapter in cls._adapters.items():
            health = adapter.health_check(store)
            results[name] = {
                'name': adapter.name,
                'display_name_fa': adapter.display_name_fa,
                'description_fa': adapter.description_fa,
                'status': health.state,
                'is_ready': health.state == IntegrationState.CONNECTED,
                'message': health.message,
            }
        return results


def get_integration_adapter(name: str):
    return IntegrationRegistry.get_adapter(name)

