'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import {
  Sparkles,
  TrendingUp,
  AlertTriangle,
  Clock,
  Send,
  Boxes,
  HelpCircle,
  Lightbulb,
  ArrowUpRight,
  ShieldCheck
} from 'lucide-react';

export default function IntelligencePage() {
  const [forecasts, setForecasts] = useState<any[]>([]);
  const [loadingForecasts, setLoadingForecasts] = useState(true);

  // Copilot chat state
  const [copilotQuestion, setCopilotQuestion] = useState('');
  const [copilotHistory, setCopilotHistory] = useState<Array<{ q: string; a: string; source: string }>>([
    {
      q: 'کدام محصولات در هفته آینده در معرض اتمام موجودی هستند و حاشیه سود بالاتری دارند؟',
      a: 'بر اساس بررسی آماری فروشگاه:\n۱. پیراهن نخی اعلا دارای شتاب فروش ۲.۱ عدد در روز است و تا ۴ روز دیگر موجودی آن به اتمام می‌رسد.\n۲. حاشیه سود ناخالص این محصول ۵۲٪ است که بالاتر از میانگین فروشگاه می‌باشد.\n\nاقدامات پیشنهادی:\n• صدور سفارش خرید (PO) حداقل ۶۰ عدد برای تامین‌کننده انبار مرکزی.\n• اعمال اولویت ارسال برای سفارشات ثبت‌شده با این کالا.\n• بررسی افزایش قیمت ۲ الی ۳ درصدی به منظور حفظ تعادل عرضه و تقاضا.',
      source: 'grounded_tenant_analytics'
    }
  ]);
  const [isAsking, setIsAsking] = useState(false);

  useEffect(() => {
    const fetchForecasts = async () => {
      try {
        const res = await api.getDemandForecasts(30);
        setForecasts(Array.isArray(res) ? res : []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoadingForecasts(false);
      }
    };
    fetchForecasts();
  }, []);

  const handleAskCopilot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!copilotQuestion.trim() || isAsking) return;

    const q = copilotQuestion.trim();
    setCopilotQuestion('');
    setIsAsking(true);

    try {
      const res = await api.askAICopilot(q);
      setCopilotHistory((prev) => [...prev, { q, a: res.answer, source: res.source }]);
    } catch (err: any) {
      alert(err.message || 'خطا در دریافت پاسخ دستیار');
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <div className="flex-1 p-6 space-y-6 max-w-7xl mx-auto w-full text-slate-100">
      {/* Header */}
      <div className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] p-6 rounded-3xl shadow-xl flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">هوش تجاری و پیش‌بینی تقاضا (BI & AI)</h1>
            <p className="text-xs text-slate-400 mt-1">شتاب فروش، پیش‌بینی روزهای اتمام موجودی کالاها و دستیار هوشمند تصمیم‌گیری مدیر فروشگاه</p>
          </div>
        </div>
      </div>

      {/* Grid: Left = Demand Forecasting, Right = AI Copilot */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Demand Forecasting Table (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] rounded-3xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-cyan-400" />
                پیش‌بینی اتمام موجودی و سفارش مجدد کالاها
              </h2>
              <span className="text-[11px] text-slate-400">بر اساس شتاب فروش ۳۰ روزه</span>
            </div>

            {loadingForecasts ? (
              <div className="p-8 text-center text-slate-400 text-xs">در حال پردازش داده‌های انبار و فروش...</div>
            ) : forecasts.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">داده‌ای برای پیش‌بینی موجودی یافت نشد.</div>
            ) : (
              <div className="space-y-3">
                {forecasts.map((f) => (
                  <div
                    key={f.variant_id}
                    className="p-4 rounded-2xl bg-[#0b101d] border border-white/[0.06] flex items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white">{f.product_name}</span>
                        <span className="text-[11px] text-slate-400 font-mono">({f.sku})</span>
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-slate-400">
                        <span>موجودی آزاد: <strong className="text-slate-200">{f.total_available} عدد</strong></span>
                        <span>شتاب روزانه: <strong className="text-slate-200">{f.daily_velocity} عدد/روز</strong></span>
                      </div>
                    </div>

                    <div className="text-left shrink-0 space-y-1">
                      <span
                        className={`inline-block text-[11px] px-2.5 py-0.5 rounded-lg border font-medium ${
                          f.urgency === 'CRITICAL'
                            ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            : f.urgency === 'WARNING'
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        }`}
                      >
                        {f.days_remaining <= 30 ? `${f.days_remaining} روز تا اتمام` : 'موجودی کافی'}
                      </span>

                      {f.reorder_suggested_qty > 0 && (
                        <p className="text-[10px] text-cyan-400">
                          پیشنهاد خرید: {f.reorder_suggested_qty} عدد
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* AI Operations Copilot (5 Cols) */}
        <div className="lg:col-span-5 flex flex-col bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] rounded-3xl p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-300" />
              دستیار هوشمند عملیاتی فروشگاه
            </h2>
            <span className="text-[10px] px-2 py-0.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              داده‌های موثق فروشگاه
            </span>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 space-y-4 overflow-y-auto max-h-[420px] pr-1">
            {copilotHistory.map((item, idx) => (
              <div key={idx} className="space-y-2">
                <div className="p-3 rounded-2xl bg-blue-600/15 border border-blue-500/20 text-xs text-blue-200">
                  <p className="font-semibold text-white mb-1">پرسش مدیر:</p>
                  <p>{item.q}</p>
                </div>

                <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/[0.08] text-xs text-slate-200 leading-relaxed space-y-2">
                  <p className="font-bold text-amber-300 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5" />
                    تحلیل و پیشنهادات عملیاتی:
                  </p>
                  <div className="whitespace-pre-wrap">{item.a}</div>
                </div>
              </div>
            ))}

            {isAsking && (
              <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] text-xs text-slate-400 animate-pulse">
                دستیار در حال تحلیل تراکنش‌ها و موجودی انبار شماست...
              </div>
            )}
          </div>

          {/* Question Input */}
          <form onSubmit={handleAskCopilot} className="pt-3 border-t border-white/[0.06] flex items-center gap-2">
            <input
              value={copilotQuestion}
              onChange={(e) => setCopilotQuestion(e.target.value)}
              placeholder="هر سوالی در مورد فروش، سود، انبار یا مشتریان دارید بپرسید..."
              className="flex-1 px-4 py-2.5 bg-[#0b101d] border border-white/10 rounded-2xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={isAsking}
              className="p-2.5 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white shadow-[0_0_15px_rgba(99,102,241,0.3)] disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
