'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import {
  Tag,
  Zap,
  Plus,
  Play,
  CheckCircle2,
  AlertCircle,
  Percent,
  Calendar,
  Layers,
  ArrowRight
} from 'lucide-react';

export default function MarketingPage() {
  const [activeTab, setActiveTab] = useState<'coupons' | 'automation'>('coupons');
  
  // Coupons state
  const [coupons, setCoupons] = useState<any[]>([]);
  const [showCreateCoupon, setShowCreateCoupon] = useState(false);
  const [newCoupon, setNewCoupon] = useState({
    code: '',
    discount_type: 'PERCENTAGE',
    discount_value: 15,
    min_order_amount: 100000,
    max_discount_amount: 50000,
  });

  // Coupon Simulator
  const [testCode, setTestCode] = useState('');
  const [testAmount, setTestAmount] = useState(250000);
  const [simResult, setSimResult] = useState<any | null>(null);

  // Automation state
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [coupRes, ruleRes] = await Promise.all([
        api.getCoupons(),
        api.getAutomationRules(),
      ]);
      setCoupons(Array.isArray(coupRes) ? coupRes : (coupRes?.results || []));
      setRules(Array.isArray(ruleRes) ? ruleRes : (ruleRes?.results || []));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createCoupon(newCoupon);
      setShowCreateCoupon(false);
      setNewCoupon({
        code: '',
        discount_type: 'PERCENTAGE',
        discount_value: 15,
        min_order_amount: 100000,
        max_discount_amount: 50000,
      });
      fetchData();
    } catch (err: any) {
      alert(err.message || 'خطا در ثبت کد تخفیف');
    }
  };

  const handleSimulateCoupon = async () => {
    if (!testCode) return;
    try {
      const res = await api.validateCoupon(testCode, testAmount);
      setSimResult(res);
    } catch (err: any) {
      setSimResult({ is_valid: false, message: err.message });
    }
  };

  const handleTestRule = async (ruleId: string) => {
    try {
      const res = await api.testRunAutomationRule(ruleId, {
        customer_phone: '09121234567',
        min_amount: 500000
      });
      alert(`نتیجه تست اتوماسیون:\n${res.message}\n${res.execution_output || ''}`);
      fetchData();
    } catch (err: any) {
      alert(err.message || 'خطا در اجرای تست');
    }
  };

  return (
    <div className="flex-1 p-6 space-y-6 max-w-7xl mx-auto w-full text-slate-100">
      {/* Header */}
      <div className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] p-6 rounded-3xl shadow-xl flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-amber-600/20 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <Tag className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">تخفیف‌ها، وفاداری و موتور اتوماسیون</h1>
            <p className="text-xs text-slate-400 mt-1">مدیریت کوپن‌های مناسبتی، اعتبارسنجی سبد خرید و گردش‌کارهای خودکار محرک-اقدام</p>
          </div>
        </div>

        {activeTab === 'coupons' && (
          <button
            onClick={() => setShowCreateCoupon(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-all shadow-[0_0_20px_rgba(37,99,235,0.3)]"
          >
            <Plus className="w-4 h-4" />
            <span>ایجاد کد تخفیف جدید</span>
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-white/[0.06] pb-3">
        <button
          onClick={() => setActiveTab('coupons')}
          className={`flex items-center gap-2 px-5 py-2 rounded-2xl text-xs font-medium transition-all ${
            activeTab === 'coupons'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Tag className="w-3.5 h-3.5" />
          <span>کدهای تخفیف فعال ({coupons.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('automation')}
          className={`flex items-center gap-2 px-5 py-2 rounded-2xl text-xs font-medium transition-all ${
            activeTab === 'automation'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Zap className="w-3.5 h-3.5" />
          <span>قوانین اتوماسیون خودکار ({rules.length})</span>
        </button>
      </div>

      {/* Tab 1: Coupons */}
      {activeTab === 'coupons' ? (
        <div className="space-y-6">
          {/* Coupon Simulator Card */}
          <div className="bg-[#0e1628]/60 border border-white/[0.08] rounded-3xl p-5 space-y-4">
            <h2 className="text-xs font-bold text-white flex items-center gap-2">
              <Play className="w-4 h-4 text-emerald-400" />
              تستر و شبیه‌ساز آنی کد تخفیف در سبد خرید
            </h2>
            <div className="flex flex-col sm:flex-row items-center gap-3">
              <input
                value={testCode}
                onChange={(e) => setTestCode(e.target.value)}
                placeholder="کد تخفیف (مثلاً NOROOZ20)..."
                className="w-full sm:w-60 px-4 py-2 bg-[#0b101d] border border-white/10 rounded-xl text-xs text-white"
              />
              <input
                type="number"
                value={testAmount}
                onChange={(e) => setTestAmount(Number(e.target.value))}
                placeholder="مبلغ سفارش (تومان)..."
                className="w-full sm:w-48 px-4 py-2 bg-[#0b101d] border border-white/10 rounded-xl text-xs text-white"
              />
              <button
                onClick={handleSimulateCoupon}
                className="w-full sm:w-auto px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-medium transition-all"
              >
                تست اعمال تخفیف
              </button>
            </div>

            {simResult && (
              <div className={`p-3.5 rounded-2xl border text-xs ${
                simResult.is_valid
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}>
                <p className="font-bold">{simResult.message}</p>
                {simResult.is_valid && (
                  <p className="mt-1">
                    تخفیف کسر شده: {Number(simResult.calculated_discount).toLocaleString('fa-IR')} تومان • مبلغ نهایی: {Number(simResult.final_amount).toLocaleString('fa-IR')} تومان
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Coupons Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {coupons.map((c) => (
              <div
                key={c.id}
                className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] hover:border-blue-500/30 rounded-3xl p-5 space-y-3 transition-all"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold font-mono text-white px-2.5 py-1 bg-white/[0.04] rounded-xl border border-white/10">
                    {c.code}
                  </span>
                  <span className="text-[11px] px-2.5 py-1 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    {c.discount_type === 'PERCENTAGE' ? `${c.discount_value}٪ تخفیف` : `${Number(c.discount_value).toLocaleString('fa-IR')} ت`}
                  </span>
                </div>

                <p className="text-xs text-slate-300">{c.description || 'بدون توضیح'}</p>

                <div className="text-[11px] text-slate-400 space-y-1 pt-2 border-t border-white/[0.06]">
                  <p>حداقل سفارش: {Number(c.min_order_amount).toLocaleString('fa-IR')} تومان</p>
                  {c.max_discount_amount && (
                    <p>سقف تخفیف: {Number(c.max_discount_amount).toLocaleString('fa-IR')} تومان</p>
                  )}
                  <p>دفعات استفاده: {c.uses_count} {c.max_uses > 0 ? `از ${c.max_uses}` : '(نامحدود)'}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* Tab 2: Automation Rules */
        <div className="space-y-4">
          {rules.length === 0 ? (
            <div className="bg-[#0e1628]/60 border border-white/[0.06] rounded-3xl p-12 text-center text-slate-400 text-xs">
              هیچ قانون اتوماسیونی تعریف نشده است.
            </div>
          ) : (
            rules.map((rule) => (
              <div
                key={rule.id}
                className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] rounded-3xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold text-white">{rule.name}</span>
                    <span className="text-xs px-2.5 py-1 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      محرک: {rule.trigger_display}
                    </span>
                    <span className="text-[11px] px-2 py-0.5 rounded-lg bg-emerald-500/10 text-emerald-400">
                      {rule.execution_count} بار اجرا شده
                    </span>
                  </div>

                  <p className="text-xs text-slate-400">{rule.description || 'اتوماسیون خودکار گردش‌کار فروشگاه'}</p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleTestRule(rule.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600/20 border border-blue-500/30 hover:bg-blue-600/30 text-blue-400 text-xs font-medium transition-all"
                  >
                    <Play className="w-3.5 h-3.5" />
                    <span>تست و شبیه‌سازی</span>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Create Coupon Modal */}
      {showCreateCoupon && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <form onSubmit={handleCreateCoupon} className="bg-[#0e1628] border border-white/[0.1] rounded-3xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Tag className="w-5 h-5 text-amber-400" />
              ایجاد کد تخفیف جدید
            </h2>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 mb-1">کد کوپن (انگلیسی)</label>
                <input
                  required
                  value={newCoupon.code}
                  onChange={(e) => setNewCoupon({ ...newCoupon, code: e.target.value.toUpperCase() })}
                  className="w-full px-3 py-2 bg-[#0b101d] border border-white/10 rounded-xl text-white font-mono uppercase"
                  placeholder="YALDA20"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">نوع تخفیف</label>
                <select
                  value={newCoupon.discount_type}
                  onChange={(e) => setNewCoupon({ ...newCoupon, discount_type: e.target.value })}
                  className="w-full px-3 py-2 bg-[#0b101d] border border-white/10 rounded-xl text-white"
                >
                  <option value="PERCENTAGE">درصدی (%)</option>
                  <option value="FIXED_AMOUNT">مبلغ ثابت (تومان)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">مقدار تخفیف</label>
                <input
                  type="number"
                  required
                  value={newCoupon.discount_value}
                  onChange={(e) => setNewCoupon({ ...newCoupon, discount_value: Number(e.target.value) })}
                  className="w-full px-3 py-2 bg-[#0b101d] border border-white/10 rounded-xl text-white"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">حداقل مبلغ سفارش (تومان)</label>
                <input
                  type="number"
                  value={newCoupon.min_order_amount}
                  onChange={(e) => setNewCoupon({ ...newCoupon, min_order_amount: Number(e.target.value) })}
                  className="w-full px-3 py-2 bg-[#0b101d] border border-white/10 rounded-xl text-white"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.06]">
              <button
                type="button"
                onClick={() => setShowCreateCoupon(false)}
                className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
              >
                انصراف
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium shadow-[0_0_15px_rgba(37,99,235,0.3)]"
              >
                ثبت کد تخفیف
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
