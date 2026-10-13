'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import {
  RotateCcw,
  CheckCircle2,
  Clock,
  AlertTriangle,
  PackageCheck,
  ShieldAlert,
  ArrowRight,
  Filter
} from 'lucide-react';

export default function ReturnsPage() {
  const [returns, setReturns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRMA, setSelectedRMA] = useState<any | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  
  // Inspection decision state
  const [inspectDecisions, setInspectDecisions] = useState<Record<string, { action: string; condition: string }>>({});

  const fetchReturns = async () => {
    setLoading(true);
    try {
      const res = await api.getReturnRequests(statusFilter);
      const list = Array.isArray(res) ? res : (res?.results || []);
      setReturns(list);
      if (list.length > 0 && !selectedRMA) {
        setSelectedRMA(list[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReturns();
  }, [statusFilter]);

  const handleApprove = async (rmaId: string) => {
    try {
      await api.approveReturnRequest(rmaId);
      fetchReturns();
    } catch (err: any) {
      alert(err.message || 'خطا در تایید درخواست مرجوعی');
    }
  };

  const handleProcessInspection = async () => {
    if (!selectedRMA) return;
    const itemsData = (selectedRMA.items || []).map((i: any) => ({
      item_id: i.id,
      condition: inspectDecisions[i.id]?.condition || 'OPENED_GOOD',
      action: inspectDecisions[i.id]?.action || 'RESTOCK',
      notes: 'بررسی شده توسط انباردار'
    }));

    try {
      await api.inspectAndProcessReturn(selectedRMA.id, {
        inspection_items: itemsData,
        refund_status: 'REFUNDED'
      });
      alert('مرجوعی کارشناسی شد و اقلام به گردش انبار منتقل شدند.');
      fetchReturns();
    } catch (err: any) {
      alert(err.message || 'خطا در کارشناسی مرجوعی');
    }
  };

  return (
    <div className="flex-1 p-6 space-y-6 max-w-7xl mx-auto w-full text-slate-100">
      {/* Header */}
      <div className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] p-6 rounded-3xl shadow-xl flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-rose-600/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
            <RotateCcw className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">کارتابل مرجوعی‌ها و RMA</h1>
            <p className="text-xs text-slate-400 mt-1">مدیریت درخواست‌های بازگشت کالا، کارشناسی سلامت فیزیکی و هدایت هوشمند به انبار یا قرنطینه</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3.5 py-2 bg-[#0b101d] border border-white/10 rounded-2xl text-xs text-slate-300"
          >
            <option value="">همه وضعیت‌ها</option>
            <option value="REQUESTED">درخواست اولیه</option>
            <option value="APPROVED">تایید شده</option>
            <option value="COMPLETED">تکمیل و انبارداری شده</option>
          </select>
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Returns List (Left 5 Cols) */}
        <div className="lg:col-span-5 space-y-3">
          {loading ? (
            <div className="p-8 text-center text-slate-400 text-xs">در حال بارگذاری...</div>
          ) : returns.length === 0 ? (
            <div className="bg-[#0e1628]/60 border border-white/[0.06] rounded-3xl p-10 text-center text-slate-400 text-xs">
              هیچ درخواست مرجوعی ثبت نشده است.
            </div>
          ) : (
            returns.map((rma) => {
              const isSelected = selectedRMA?.id === rma.id;
              return (
                <div
                  key={rma.id}
                  onClick={() => setSelectedRMA(rma)}
                  className={`cursor-pointer p-4 rounded-3xl border transition-all ${
                    isSelected
                      ? 'bg-blue-600/10 border-blue-500/40 shadow-[0_0_20px_rgba(37,99,235,0.2)]'
                      : 'bg-[#0e1628]/80 border-white/[0.08] hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold font-mono text-white">{rma.rma_number}</span>
                    <span className="text-[11px] px-2 py-0.5 rounded-lg bg-slate-800 text-slate-300">
                      {rma.status_display}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 font-medium">{rma.customer_name} ({rma.customer_phone})</p>
                  <p className="text-[11px] text-slate-400 mt-1">سفارش: {rma.order_number}</p>

                  <div className="flex items-center justify-between mt-3 pt-2 border-t border-white/[0.04] text-[11px] text-slate-400">
                    <span>مبلغ استرداد: <strong className="text-slate-200">{Number(rma.refund_amount).toLocaleString('fa-IR')} تومان</strong></span>
                    <span>{rma.items?.length || 0} ردیف کالا</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* RMA Detail & Inspection Action (Right 7 Cols) */}
        <div className="lg:col-span-7">
          {selectedRMA ? (
            <div className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] rounded-3xl p-6 space-y-6">
              <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    مجوز مرجوعی {selectedRMA.rma_number}
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">سفارش مربوطه: {selectedRMA.order_number}</p>
                </div>

                <div className="flex items-center gap-2">
                  {selectedRMA.status === 'REQUESTED' && (
                    <button
                      onClick={() => handleApprove(selectedRMA.id)}
                      className="px-3.5 py-1.5 rounded-xl bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-600/30 text-xs font-medium"
                    >
                      تایید درخواست اولیه
                    </button>
                  )}
                </div>
              </div>

              {/* Customer Notes */}
              {selectedRMA.customer_notes && (
                <div className="p-3.5 rounded-2xl bg-white/[0.03] border border-white/[0.06] text-xs text-slate-300 space-y-1">
                  <span className="text-[11px] text-slate-400 font-medium">علت مرجوعی مشتری:</span>
                  <p>{selectedRMA.customer_notes}</p>
                </div>
              )}

              {/* Returned Items Inspection Table */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-200">اقلام مرجوعی و تصمیم انبارداری</h3>
                <div className="space-y-3">
                  {selectedRMA.items?.map((item: any) => (
                    <div
                      key={item.id}
                      className="p-4 rounded-2xl bg-[#0b101d] border border-white/[0.08] space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-xs font-bold text-white">{item.variant_name}</p>
                          <p className="text-[11px] text-slate-400 font-mono">{item.variant_sku} (تعداد: {item.quantity})</p>
                        </div>
                        <span className="text-[11px] px-2 py-0.5 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          {item.reason_display}
                        </span>
                      </div>

                      {selectedRMA.status !== 'COMPLETED' ? (
                        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-white/[0.06] text-xs">
                          <div>
                            <label className="block text-slate-400 text-[11px] mb-1">سلامت فیزیکی کالا</label>
                            <select
                              value={inspectDecisions[item.id]?.condition || 'OPENED_GOOD'}
                              onChange={(e) =>
                                setInspectDecisions({
                                  ...inspectDecisions,
                                  [item.id]: {
                                    ...(inspectDecisions[item.id] || { action: 'RESTOCK' }),
                                    condition: e.target.value
                                  }
                                })
                              }
                              className="w-full px-2.5 py-1.5 bg-[#0e1628] border border-white/10 rounded-xl text-white text-xs"
                            >
                              <option value="NEW_UNOPENED">پلمپ و دست‌نخورده</option>
                              <option value="OPENED_GOOD">باز شده اما کاملاً سالم</option>
                              <option value="DEFECTIVE">معیوب / خراب</option>
                              <option value="DAMAGED">آسیب‌دیده فیزیکی</option>
                            </select>
                          </div>

                          <div>
                            <label className="block text-slate-400 text-[11px] mb-1">تصمیم انبارداری</label>
                            <select
                              value={inspectDecisions[item.id]?.action || 'RESTOCK'}
                              onChange={(e) =>
                                setInspectDecisions({
                                  ...inspectDecisions,
                                  [item.id]: {
                                    ...(inspectDecisions[item.id] || { condition: 'OPENED_GOOD' }),
                                    action: e.target.value
                                  }
                                })
                              }
                              className="w-full px-2.5 py-1.5 bg-[#0e1628] border border-white/10 rounded-xl text-white text-xs"
                            >
                              <option value="RESTOCK">بازگشت به موجودی قابل فروش</option>
                              <option value="QUARANTINE_SCRAP">قرنطینه / ضایعات</option>
                            </select>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center gap-3 text-xs text-slate-400">
                          <span>وضعیت کارشناسی: <strong className="text-slate-200">{item.action_display}</strong></span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Complete RMA Action */}
              {selectedRMA.status !== 'COMPLETED' && (
                <div className="pt-4 border-t border-white/[0.06] flex items-center justify-between">
                  <div className="text-xs text-slate-400">
                    مبلغ بازگشت وجه: <strong className="text-emerald-400">{Number(selectedRMA.refund_amount).toLocaleString('fa-IR')} تومان</strong>
                  </div>

                  <button
                    onClick={handleProcessInspection}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium shadow-[0_0_20px_rgba(37,99,235,0.3)]"
                  >
                    <PackageCheck className="w-4 h-4" />
                    <span>تایید کارشناسی و ثبت در انبار</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center p-12 bg-[#0e1628]/40 border border-white/[0.06] rounded-3xl text-slate-500 text-xs">
              یک مرجوعی را جهت مشاهده جزئیات انتخاب کنید
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
