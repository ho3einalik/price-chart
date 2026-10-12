'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import {
  Truck,
  Plus,
  Search,
  CheckCircle2,
  Clock,
  ArrowDownToLine,
  Building2,
  Phone,
  AlertCircle,
  FileText
} from 'lucide-react';

export default function SuppliersPage() {
  const [activeTab, setActiveTab] = useState<'pos' | 'suppliers'>('pos');
  const [pos, setPos] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  // Modals
  const [showCreateSupplier, setShowCreateSupplier] = useState(false);
  const [newSupplier, setNewSupplier] = useState({ name: '', contact_name: '', phone_number: '', lead_time_days: 3 });
  
  const [receiveModalPO, setReceiveModalPO] = useState<any | null>(null);
  const [receiveQuantities, setReceiveQuantities] = useState<Record<string, number>>({});

  const fetchData = async () => {
    setLoading(true);
    try {
      const [posRes, suppRes] = await Promise.all([
        api.getPurchaseOrders(),
        api.getSuppliers(search),
      ]);
      setPos(Array.isArray(posRes) ? posRes : (posRes?.results || []));
      setSuppliers(Array.isArray(suppRes) ? suppRes : (suppRes?.results || []));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [search]);

  const handleCreateSupplier = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createSupplier(newSupplier);
      setShowCreateSupplier(false);
      setNewSupplier({ name: '', contact_name: '', phone_number: '', lead_time_days: 3 });
      fetchData();
    } catch (err: any) {
      alert(err.message || 'خطا در ثبت تامین‌کننده');
    }
  };

  const handleApprovePO = async (poId: string) => {
    try {
      await api.approvePurchaseOrder(poId);
      fetchData();
    } catch (err: any) {
      alert(err.message || 'خطا در تایید سفارش خرید');
    }
  };

  const handleReceiveGoods = async () => {
    if (!receiveModalPO) return;
    const receipts = Object.entries(receiveQuantities || {})
      .filter(([_, qty]) => Number(qty) > 0)
      .map(([itemId, qty]) => ({ item_id: itemId, quantity_received: Number(qty) }));

    if (receipts.length === 0) {
      alert('لطفاً تعداد دریافتی حداقل یک کالا را مشخص کنید.');
      return;
    }

    try {
      await api.receivePOGoods(receiveModalPO.id, receipts);
      setReceiveModalPO(null);
      setReceiveQuantities({});
      fetchData();
    } catch (err: any) {
      alert(err.message || 'خطا در رسید انبار');
    }
  };

  return (
    <div className="flex-1 p-6 space-y-6 max-w-7xl mx-auto w-full text-slate-100">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] p-6 rounded-3xl shadow-xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
            <Truck className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">تامین‌کنندگان و سفارشات خرید (PO)</h1>
            <p className="text-xs text-slate-400 mt-1">مدیریت تامین، سفارشات خرید، رسید مستقیم به انبار و پیگیری موجودی در راه</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCreateSupplier(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-all shadow-[0_0_20px_rgba(37,99,235,0.3)]"
          >
            <Plus className="w-4 h-4" />
            <span>ثبت تامین‌کننده جدید</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-white/[0.06] pb-3">
        <button
          onClick={() => setActiveTab('pos')}
          className={`px-5 py-2 rounded-2xl text-xs font-medium transition-all ${
            activeTab === 'pos'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          سفارشات خرید (PO) ({pos.length})
        </button>
        <button
          onClick={() => setActiveTab('suppliers')}
          className={`px-5 py-2 rounded-2xl text-xs font-medium transition-all ${
            activeTab === 'suppliers'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          دایرکتوری تامین‌کنندگان ({suppliers.length})
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="p-12 text-center text-slate-400 text-xs">در حال بارگذاری اطلاعات...</div>
      ) : activeTab === 'pos' ? (
        <div className="grid grid-cols-1 gap-4">
          {pos.length === 0 ? (
            <div className="bg-[#0e1628]/60 border border-white/[0.06] rounded-3xl p-12 text-center text-slate-400 text-xs">
              هیچ سفارش خریدی ثبت نشده است.
            </div>
          ) : (
            pos.map((po) => (
              <div
                key={po.id}
                className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] hover:border-blue-500/30 rounded-3xl p-5 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold text-white font-mono">{po.po_number}</span>
                    <span className="text-xs px-2.5 py-1 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      {po.supplier_name}
                    </span>
                    <span className="text-[11px] px-2 py-0.5 rounded-lg bg-white/[0.04] text-slate-300">
                      انبار مقصد: {po.warehouse_name}
                    </span>
                    <span className="text-xs px-2.5 py-1 rounded-xl bg-slate-800 text-slate-300">
                      {po.status_display}
                    </span>
                  </div>

                  <div className="text-xs text-slate-400 flex items-center gap-4">
                    <span>مبلغ کل: <strong className="text-slate-200">{Number(po.total_amount).toLocaleString('fa-IR')} {po.currency}</strong></span>
                    <span>اقلام: <strong className="text-slate-200">{po.items?.length || 0} ردیف</strong></span>
                    {po.expected_delivery_date && (
                      <span>تحویل پیش‌بینی‌شده: {po.expected_delivery_date}</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {po.status === 'DRAFT' && (
                    <button
                      onClick={() => handleApprovePO(po.id)}
                      className="px-3 py-1.5 rounded-xl bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-600/30 text-xs font-medium transition-all"
                    >
                      تایید سفارش (Approve)
                    </button>
                  )}

                  {['APPROVED', 'SENT', 'PARTIALLY_RECEIVED'].includes(po.status) && (
                    <button
                      onClick={() => {
                        setReceiveModalPO(po);
                        const initial: Record<string, number> = {};
                        po.items?.forEach((i: any) => {
                          initial[i.id] = i.remaining_quantity;
                        });
                        setReceiveQuantities(initial);
                      }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-all shadow-[0_0_15px_rgba(37,99,235,0.25)]"
                    >
                      <ArrowDownToLine className="w-3.5 h-3.5" />
                      <span>رسید و ورود به انبار</span>
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {suppliers.map((s) => (
            <div
              key={s.id}
              className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] rounded-3xl p-5 space-y-3"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-blue-400" />
                  {s.name}
                </h3>
                <span className="text-[11px] px-2 py-0.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {s.payment_terms === 'CASH' ? 'تسویه نقدی' : s.payment_terms}
                </span>
              </div>

              <div className="text-xs text-slate-400 space-y-1">
                {s.contact_name && <p>مسئول فروش: {s.contact_name}</p>}
                {s.phone_number && <p className="flex items-center gap-1.5"><Phone className="w-3.5 h-3.5 text-slate-500" /> {s.phone_number}</p>}
                <p>زمان ارسال: {s.lead_time_days} روز کاری</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Receive Goods Modal */}
      {receiveModalPO && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#0e1628] border border-white/[0.1] rounded-3xl p-6 max-w-lg w-full space-y-4 shadow-2xl">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <ArrowDownToLine className="w-5 h-5 text-blue-400" />
              رسید کالاهای سفارش خرید {receiveModalPO.po_number}
            </h2>
            <p className="text-xs text-slate-400">تعداد اقلام تحویل‌گرفته‌شده را وارد نمایید. این عملیات مستقیماً موجودی فیزیکی انبار را افزایش می‌دهد.</p>

            <div className="space-y-3 max-h-60 overflow-y-auto pr-1">
              {receiveModalPO.items?.map((item: any) => (
                <div key={item.id} className="flex items-center justify-between p-3 rounded-2xl bg-white/[0.03] border border-white/[0.06]">
                  <div>
                    <p className="text-xs font-medium text-white">{item.variant_name}</p>
                    <p className="text-[11px] text-slate-400 font-mono">{item.variant_sku} (مانده: {item.remaining_quantity})</p>
                  </div>
                  <input
                    type="number"
                    min="0"
                    max={item.remaining_quantity}
                    value={receiveQuantities[item.id] || 0}
                    onChange={(e) => setReceiveQuantities({ ...receiveQuantities, [item.id]: Number(e.target.value) })}
                    className="w-20 px-3 py-1.5 bg-[#0b101d] border border-white/10 rounded-xl text-center text-xs text-white"
                  />
                </div>
              ))}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.06]">
              <button
                onClick={() => setReceiveModalPO(null)}
                className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
              >
                انصراف
              </button>
              <button
                onClick={handleReceiveGoods}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium shadow-[0_0_15px_rgba(37,99,235,0.3)]"
              >
                ثبت رسید در انبار
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Supplier Modal */}
      {showCreateSupplier && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <form onSubmit={handleCreateSupplier} className="bg-[#0e1628] border border-white/[0.1] rounded-3xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Building2 className="w-5 h-5 text-blue-400" />
              افزودن تامین‌کننده جدید
            </h2>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 mb-1">نام شرکت / تامین‌کننده</label>
                <input
                  required
                  value={newSupplier.name}
                  onChange={(e) => setNewSupplier({ ...newSupplier, name: e.target.value })}
                  className="w-full px-3 py-2 bg-[#0b101d] border border-white/10 rounded-xl text-white"
                  placeholder="مثال: بازرگانی پارس"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">نام رابط / مسئول فروش</label>
                <input
                  value={newSupplier.contact_name}
                  onChange={(e) => setNewSupplier({ ...newSupplier, contact_name: e.target.value })}
                  className="w-full px-3 py-2 bg-[#0b101d] border border-white/10 rounded-xl text-white"
                  placeholder="مثال: آقای کریمی"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">شماره تماس</label>
                <input
                  value={newSupplier.phone_number}
                  onChange={(e) => setNewSupplier({ ...newSupplier, phone_number: e.target.value })}
                  className="w-full px-3 py-2 bg-[#0b101d] border border-white/10 rounded-xl text-white"
                  placeholder="0912..."
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.06]">
              <button
                type="button"
                onClick={() => setShowCreateSupplier(false)}
                className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
              >
                انصراف
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium shadow-[0_0_15px_rgba(37,99,235,0.3)]"
              >
                ثبت تامین‌کننده
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
