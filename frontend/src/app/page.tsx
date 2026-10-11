'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useStore } from '@/contexts/StoreContext';
import { useAuth } from '@/contexts/AuthContext';
import { OverviewMetrics, DailyAction } from '@/types';
import { formatCurrency, formatNumber, formatDate, cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  ShoppingCart,
  Boxes,
  AlertTriangle,
  CheckCircle,
  Clock,
  ArrowUpRight,
  ShieldCheck,
  RefreshCw,
  XCircle,
  HelpCircle
} from 'lucide-react';

export default function DashboardPage() {
  const { activeStore } = useStore();
  const { user, loading: authLoading } = useAuth();
  const [metrics, setMetrics] = useState<OverviewMetrics | null>(null);
  const [actions, setActions] = useState<DailyAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const loadData = async () => {
    if (!activeStore) return;
    setLoading(true);
    try {
      const [m, acts] = await Promise.all([
        api.getOverviewMetrics(days),
        api.getDailyActions(),
      ]);
      setMetrics(m);
      const actionList = Array.isArray(acts) ? acts : acts.results || [];
      setActions(actionList);
    } catch (err) {
      console.error('Error loading dashboard data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeStore) {
      loadData();
    }
  }, [activeStore, days]);

  const handleActionStatus = async (actionId: string, newStatus: string) => {
    try {
      await api.updateDailyActionStatus(actionId, newStatus, 'توسط کاربر از داشبورد اقدام شد');
      await loadData();
    } catch (err) {
      alert('خطا در به‌روزرسانی وضعیت اقدام');
    }
  };

  if (authLoading || (loading && !metrics)) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-sky-600 animate-spin" />
          <span className="text-sm font-medium text-slate-500">در حال دریافت اطلاعات داشبورد...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center max-w-md mx-auto mt-12 space-y-4">
        <h2 className="text-lg font-bold text-slate-800">به شاپ‌پایلوت خوش آمدید</h2>
        <p className="text-sm text-slate-600">برای مشاهده داشبورد و مدیریت فروشگاه، لطفاً وارد حساب خود شوید.</p>
        <a
          href="/login"
          className="inline-block bg-sky-600 hover:bg-sky-700 text-white font-medium px-6 py-2.5 rounded-xl transition"
        >
          ورود به پنل کاربری
        </a>
      </div>
    );
  }

  const currency = metrics?.currency || activeStore?.currency || 'IRT';

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">داشبورد و مرکز تصمیم‌گیری</h1>
          <p className="text-sm text-slate-500 mt-1">
            وضعیت عملیات، سودآوری و هشدارهای نیازمند اقدام فوری برای {activeStore?.name}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">بازه زمانی:</span>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="bg-white border border-slate-300 text-slate-700 text-sm rounded-lg py-1.5 px-3 font-medium cursor-pointer focus:ring-sky-500"
          >
            <option value={7}>۷ روز گذشته</option>
            <option value={14}>۱۴ روز گذشته</option>
            <option value={30}>۳۰ روز گذشته</option>
            <option value={90}>۳ ماه گذشته</option>
          </select>
          <button
            onClick={loadData}
            title="به‌روزرسانی داده‌ها"
            className="p-2 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-lg transition"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* Daily Action Center */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-gradient-to-l from-slate-50 to-white">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-100 text-amber-700 rounded-xl">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">مرکز اقدامات روزانه (Daily Action Center)</h2>
              <p className="text-xs text-slate-500">مواردی که مستقیماً بر درآمد، رضایت مشتری یا موجودی کالا تأثیر دارند</p>
            </div>
          </div>
          <span className="text-xs bg-slate-100 text-slate-700 font-bold px-2.5 py-1 rounded-full">
            {actions.filter((a) => a.status === 'NEW' || a.status === 'IN_PROGRESS').length} اقدام باز
          </span>
        </div>

        <div className="divide-y divide-slate-100">
          {actions.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-sm flex flex-col items-center gap-2">
              <CheckCircle className="w-8 h-8 text-emerald-500" />
              <span>تمام شاخص‌ها در وضعیت نرمال قرار دارند. اقدام معوقه‌ای ثبت نشده است.</span>
            </div>
          ) : (
            actions.map((act) => {
              const isResolved = act.status === 'RESOLVED' || act.status === 'DISMISSED';
              return (
                <div
                  key={act.id}
                  className={cn(
                    'p-5 transition flex flex-col md:flex-row md:items-center justify-between gap-4',
                    isResolved ? 'bg-slate-50/60 opacity-60' : 'hover:bg-slate-50/80'
                  )}
                >
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'text-xs font-bold px-2 py-0.5 rounded-md',
                          act.severity === 'CRITICAL' && 'bg-rose-100 text-rose-700',
                          act.severity === 'HIGH' && 'bg-amber-100 text-amber-800',
                          act.severity === 'MEDIUM' && 'bg-sky-100 text-sky-800',
                          act.severity === 'LOW' && 'bg-slate-100 text-slate-700'
                        )}
                      >
                        {act.severity_display}
                      </span>
                      <h3 className="text-sm font-bold text-slate-900">{act.title}</h3>
                      <span className="text-xs text-slate-400 font-medium">({act.status_display})</span>
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed">{act.explanation}</p>

                    <div className="flex flex-wrap items-center gap-4 text-xs pt-1">
                      <span className="text-slate-500 font-medium">
                        اقدام پیشنهادی: <strong className="text-slate-700">{act.suggested_action}</strong>
                      </span>
                      {act.evidence?.count && (
                        <span className="text-slate-400">تعداد رکوردهای متأثر: {formatNumber(act.evidence.count)}</span>
                      )}
                    </div>
                  </div>

                  {!isResolved && (
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => handleActionStatus(act.id, 'IN_PROGRESS')}
                        className="text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg transition"
                      >
                        در حال پیگیری
                      </button>
                      <button
                        onClick={() => handleActionStatus(act.id, 'RESOLVED')}
                        className="text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1.5 rounded-lg transition shadow-sm"
                      >
                        انجام شد
                      </button>
                      <button
                        onClick={() => handleActionStatus(act.id, 'DISMISSED')}
                        className="text-xs font-medium text-slate-400 hover:text-slate-600 p-1.5 rounded-lg transition"
                        title="رد کردن"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Gross Sales */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">فروش ناخالص اقلام</span>
            <div className="p-2 bg-sky-50 text-sky-600 rounded-xl">
              <DollarSign className="w-4 h-4" />
            </div>
          </div>
          <div>
            <div className="text-xl font-black text-slate-900">
              {formatCurrency(metrics?.gross_sales, currency)}
            </div>
            <div className="text-xs text-slate-400 mt-1">مجموع ارزش کالاهای فروخته شده</div>
          </div>
        </div>

        {/* Net Sales */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">فروش خالص (پس از تخفیف)</span>
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-xl">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div>
            <div className="text-xl font-black text-emerald-600">
              {formatCurrency(metrics?.net_sales, currency)}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              تخفیفات اعمال‌شده: {formatCurrency(metrics?.discounts, currency)}
            </div>
          </div>
        </div>

        {/* Gross Profit & Margin */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">سود ناخالص واقعی (COGS)</span>
            <div className="p-2 bg-violet-50 text-violet-600 rounded-xl">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div>
            <div className="text-xl font-black text-violet-700">
              {formatCurrency(metrics?.gross_profit, currency)}
            </div>
            <div className="text-xs text-violet-600 font-semibold mt-1">
              حاشیه سود ناخالص: {metrics?.gross_profit_margin_pct || 0}٪
            </div>
          </div>
        </div>

        {/* Outstanding Unpaid */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">تسویه نشده / معوق</span>
            <div className="p-2 bg-rose-50 text-rose-600 rounded-xl">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div>
            <div className="text-xl font-black text-rose-600">
              {formatCurrency(metrics?.outstanding_amount, currency)}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              وصول شده: {formatCurrency(metrics?.paid_revenue, currency)}
            </div>
          </div>
        </div>
      </div>

      {/* Secondary Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Orders */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-500 font-medium">تعداد کل سفارشات</div>
            <div className="text-lg font-bold text-slate-900 mt-0.5">
              {formatNumber(metrics?.order_count)} سفارش
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              لغو شده: {formatNumber(metrics?.cancelled_orders_count)}
            </div>
          </div>
          <div className="p-2.5 bg-slate-100 text-slate-600 rounded-xl">
            <ShoppingCart className="w-5 h-5" />
          </div>
        </div>

        {/* Average Order Value */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-500 font-medium">میانگین ارزش سفارش (AOV)</div>
            <div className="text-lg font-bold text-slate-900 mt-0.5">
              {formatCurrency(metrics?.average_order_value, currency)}
            </div>
            <div className="text-xs text-slate-400 mt-0.5">به ازای هر سبد خرید</div>
          </div>
          <div className="p-2.5 bg-slate-100 text-slate-600 rounded-xl">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>

        {/* Inventory Value */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-500 font-medium">ارزش ریالی موجودی انبار</div>
            <div className="text-lg font-bold text-slate-900 mt-0.5">
              {formatCurrency(metrics?.inventory_valuation, currency)}
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              موجودی فیزیکی: {formatNumber(metrics?.inventory_units_on_hand)} عدد
            </div>
          </div>
          <div className="p-2.5 bg-slate-100 text-slate-600 rounded-xl">
            <Boxes className="w-5 h-5" />
          </div>
        </div>

        {/* Low Stock Warning */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-500 font-medium">اقلام رو به اتمام</div>
            <div className="text-lg font-bold text-amber-600 mt-0.5">
              {formatNumber(metrics?.low_stock_count)} قلم کالا
            </div>
            <div className="text-xs text-rose-500 mt-0.5">
              ناموجود: {formatNumber(metrics?.out_of_stock_count)} قلم
            </div>
          </div>
          <div className="p-2.5 bg-amber-50 text-amber-600 rounded-xl">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Two-Column Analytics Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sales by Channel */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <h3 className="text-base font-bold text-slate-900">عملکرد کانال‌های فروش</h3>
          <div className="space-y-3">
            {metrics?.channels && metrics.channels.length > 0 ? (
              metrics.channels.map((ch) => {
                const pct = metrics.net_sales > 0 ? Math.round((ch.revenue / metrics.net_sales) * 100) : 0;
                return (
                  <div key={ch.channel} className="space-y-1">
                    <div className="flex items-center justify-between text-xs font-medium">
                      <span className="text-slate-700">{ch.channel_name}</span>
                      <span className="text-slate-900 font-bold">
                        {formatCurrency(ch.revenue, currency)} ({formatNumber(ch.order_count)} سفارش - {pct}٪)
                      </span>
                    </div>
                    <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-sky-600 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, Math.max(5, pct))}%` }}
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-xs text-slate-400 py-4 text-center">داده‌ای برای کانال‌های فروش یافت نشد.</div>
            )}
          </div>
        </div>

        {/* Top Selling Products */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <h3 className="text-base font-bold text-slate-900">پرفروش‌ترین کالاها</h3>
          <div className="divide-y divide-slate-100">
            {metrics?.top_products && metrics.top_products.length > 0 ? (
              metrics.top_products.map((tp, idx) => (
                <div key={tp.variant_sku} className="py-2.5 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-slate-100 text-slate-600 font-bold flex items-center justify-center text-[10px]">
                      {idx + 1}
                    </span>
                    <div>
                      <div className="font-bold text-slate-800">{tp.variant_name}</div>
                      <div className="text-slate-400 font-mono text-[11px]">{tp.variant_sku}</div>
                    </div>
                  </div>
                  <div className="text-left">
                    <div className="font-bold text-slate-900">{formatNumber(tp.total_quantity)} عدد</div>
                    <div className="text-slate-400">{formatCurrency(tp.total_sales, currency)}</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-400 py-4 text-center">سفارشی در این بازه زمانی ثبت نشده است.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
