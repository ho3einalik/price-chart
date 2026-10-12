'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useStore } from '@/contexts/StoreContext';
import { Order } from '@/types';
import { formatCurrency, formatNumber, formatDate, cn } from '@/lib/utils';
import {
  ShoppingCart,
  Search,
  Filter,
  CheckCircle,
  Truck,
  XCircle,
  FileUp,
  Eye,
  Clock,
  Printer,
  X,
  ShieldAlert
} from 'lucide-react';

export default function OrdersPage() {
  const { activeStore } = useStore();
  const [orders, setOrders] = useState<Order[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [channelFilter, setChannelFilter] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  // Selected Order for Detail Drawer
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [orderRisk, setOrderRisk] = useState<any | null>(null);
  const [loadingRisk, setLoadingRisk] = useState<boolean>(false);

  // Fulfill Modal
  const [showFulfillModal, setShowFulfillModal] = useState(false);
  const [fulfillOrderTarget, setFulfillOrderTarget] = useState<Order | null>(null);
  const [trackingNumber, setTrackingNumber] = useState('');
  const [fulfillShippingCost, setFulfillShippingCost] = useState('');

  // Cancel Modal
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelOrderTarget, setCancelOrderTarget] = useState<Order | null>(null);
  const [cancelReason, setCancelReason] = useState('');

  // CSV Import Modal
  const [showImportModal, setShowImportModal] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<any | null>(null);

  const loadOrders = async () => {
    if (!activeStore) return;
    setLoading(true);
    try {
      const data = await api.getOrders({
        order_status: statusFilter,
        channel: channelFilter,
        search,
      });
      const list: Order[] = Array.isArray(data) ? data : data.results || [];
      setOrders(list);
    } catch (err) {
      console.error('Error loading orders', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeStore) {
      loadOrders();
    }
  }, [activeStore, statusFilter, channelFilter]);

  useEffect(() => {
    if (selectedOrder) {
      setLoadingRisk(true);
      setOrderRisk(null);
      api.getOrderRisk(selectedOrder.id)
        .then((res) => setOrderRisk(res))
        .catch((err) => console.error('Failed to evaluate risk', err))
        .finally(() => setLoadingRisk(false));
    } else {
      setOrderRisk(null);
    }
  }, [selectedOrder]);

  const handleFulfill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fulfillOrderTarget) return;
    try {
      await api.fulfillOrder(fulfillOrderTarget.id, {
        tracking_number: trackingNumber,
        shipping_cost: fulfillShippingCost ? Number(fulfillShippingCost) : undefined,
      });
      setShowFulfillModal(false);
      await loadOrders();
    } catch (err: any) {
      alert(`خطا در ثبت ارسال: ${err.message}`);
    }
  };

  const handleCancel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancelOrderTarget) return;
    try {
      await api.cancelOrder(cancelOrderTarget.id, cancelReason);
      setShowCancelModal(false);
      await loadOrders();
    } catch (err: any) {
      alert(`خطا در لغو سفارش: ${err.message}`);
    }
  };

  const handleImportCsv = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importFile) return;
    setImporting(true);
    setImportResult(null);
    try {
      const res = await api.importOrdersCsv(importFile);
      setImportResult(res);
      await loadOrders();
    } catch (err: any) {
      alert(`خطا در پردازش فایل CSV: ${err.message}`);
    } finally {
      setImporting(false);
    }
  };

  const currency = activeStore?.currency || 'IRT';

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black text-white tracking-tight">مدیریت سفارشات چندکاناله</h1>
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            پایش یکپارچه سفارشات ورودی از سایت، اینستاگرام، تلگرام و فاکتورهای دستی
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowImportModal(true)}
            className="inline-flex items-center gap-2 bg-white/[0.05] hover:bg-white/[0.1] text-slate-200 hover:text-white border border-white/[0.08] text-xs font-semibold px-4 py-2.5 rounded-xl transition cursor-pointer"
          >
            <FileUp className="w-4 h-4 text-cyan-400" />
            <span>ایمپورت اکسل / CSV</span>
          </button>
        </div>
      </div>

      {/* Filters and Search Bar */}
      <div className="glass-card p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-96">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadOrders()}
            placeholder="جستجوی شماره سفارش، نام مشتری یا تلفن..."
            className="w-full bg-white/[0.04] border border-white/[0.09] rounded-xl pr-10 pl-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400/60"
          />
          <Search className="w-4 h-4 text-slate-400 absolute right-3.5 top-3" />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#0e1628] border border-white/[0.09] text-slate-200 text-xs rounded-xl py-2 px-3 font-medium cursor-pointer focus:outline-none focus:border-cyan-400/60"
          >
            <option value="">همه وضعیت‌ها</option>
            <option value="CONFIRMED">تأیید شده (آماده بسته‌بندی)</option>
            <option value="FULFILLED">ارسال شده</option>
            <option value="COMPLETED">تکمیل شده</option>
            <option value="CANCELLED">لغو شده</option>
          </select>

          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="bg-[#0e1628] border border-white/[0.09] text-slate-200 text-xs rounded-xl py-2 px-3 font-medium cursor-pointer focus:outline-none focus:border-cyan-400/60"
          >
            <option value="">همه کانال‌ها</option>
            <option value="INSTAGRAM">اینستاگرام</option>
            <option value="TELEGRAM">تلگرام</option>
            <option value="WOOCOMMERCE">سایت (ووکامرس)</option>
            <option value="MANUAL">ثبت دستی</option>
          </select>
        </div>
      </div>

      {/* Orders Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead className="bg-white/[0.02] border-b border-white/[0.06] text-slate-400 font-semibold">
              <tr>
                <th className="py-3.5 px-6">شماره و کانال سفارش</th>
                <th className="py-3.5 px-6">مشتری و مقصد</th>
                <th className="py-3.5 px-6 text-center">وضعیت سفارش</th>
                <th className="py-3.5 px-6 text-center">وضعیت پرداخت</th>
                <th className="py-3.5 px-6 text-center">وضعیت ارسال</th>
                <th className="py-3.5 px-6">مبلغ نهایی</th>
                <th className="py-3.5 px-6 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    در حال دریافت سفارشات...
                  </td>
                </tr>
              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    سفارشی یافت نشد.
                  </td>
                </tr>
              ) : (
                orders.map((o) => (
                  <tr key={o.id} className="hover:bg-white/[0.03] transition-colors">
                    <td className="py-4 px-6">
                      <div className="font-bold font-mono text-white">{o.order_number}</div>
                      <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-2">
                        {/* Clean dark glass channel badge */}
                        <span className="bg-white/[0.05] border border-white/[0.08] text-cyan-300 font-semibold px-2 py-0.5 rounded-lg text-[10px]">
                          {o.channel_display}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">{formatDate(o.created_at)}</span>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <div className="font-bold text-slate-200">{o.customer?.full_name}</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        <span className="font-mono">{o.customer?.phone_number}</span>
                        {o.customer?.city && <span> &bull; {o.customer.city}</span>}
                      </div>
                    </td>
                    <td className="py-4 px-6 text-center">
                      {/* Clean dark glass order status pill */}
                      <span
                        className={cn(
                          'inline-block px-2.5 py-1 rounded-full text-[11px] font-bold border',
                          o.order_status === 'CONFIRMED' && 'bg-blue-500/15 border-blue-500/30 text-cyan-300 shadow-[0_0_10px_rgba(56,189,248,0.2)]',
                          o.order_status === 'FULFILLED' && 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.2)]',
                          o.order_status === 'CANCELLED' && 'bg-rose-500/15 border-rose-500/30 text-rose-300',
                          o.order_status === 'PENDING_CONFIRMATION' && 'bg-amber-500/15 border-amber-500/30 text-amber-300'
                        )}
                      >
                        {o.order_status_display}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-center">
                      <span
                        className={cn(
                          'inline-block px-2 py-0.5 rounded-lg text-[11px] font-semibold border',
                          o.payment_status === 'PAID' && 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300 font-bold',
                          o.payment_status === 'PENDING' && 'bg-amber-500/10 border-amber-500/25 text-amber-300',
                          o.payment_status === 'PARTIALLY_PAID' && 'bg-cyan-500/10 border-cyan-500/25 text-cyan-300'
                        )}
                      >
                        {o.payment_status_display}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-center">
                      <span
                        className={cn(
                          'inline-block px-2 py-0.5 rounded-lg text-[11px] font-medium border',
                          o.fulfillment_status === 'FULFILLED' && 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300 font-bold',
                          o.fulfillment_status === 'UNFULFILLED' && 'bg-white/[0.04] border-white/[0.07] text-slate-400'
                        )}
                      >
                        {o.fulfillment_status_display}
                      </span>
                    </td>
                    <td className="py-4 px-6 font-bold text-white font-mono">
                      {formatCurrency(o.grand_total, currency)}
                    </td>
                    <td className="py-4 px-6 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => setSelectedOrder(o)}
                          className="p-1.5 text-slate-400 hover:text-cyan-300 hover:bg-white/[0.06] rounded-xl transition cursor-pointer"
                          title="مشاهده جزئیات"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {o.order_status === 'CONFIRMED' && (
                          <button
                            onClick={() => {
                              setFulfillOrderTarget(o);
                              setTrackingNumber('');
                              setFulfillShippingCost(String(o.shipping_cost || ''));
                              setShowFulfillModal(true);
                            }}
                            className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-xl transition cursor-pointer"
                            title="ارسال و ثبت رهگیری"
                          >
                            <Truck className="w-4 h-4" />
                          </button>
                        )}
                        {o.order_status !== 'CANCELLED' && o.order_status !== 'COMPLETED' && (
                          <button
                            onClick={() => {
                              setCancelOrderTarget(o);
                              setCancelReason('');
                              setShowCancelModal(true);
                            }}
                            className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-xl transition cursor-pointer"
                            title="لغو سفارش"
                          >
                            <XCircle className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Order Detail Drawer */}
      {selectedOrder && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex justify-end">
          <div className="bg-[#0b101d] w-full max-w-lg h-full p-6 shadow-2xl overflow-y-auto space-y-6 border-r border-white/10 flex flex-col justify-between">
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-white/[0.08] pb-4">
                <div>
                  <h2 className="text-base font-black text-white font-mono">{selectedOrder.order_number}</h2>
                  <span className="text-[11px] text-slate-400">ثبت در {formatDate(selectedOrder.created_at)}</span>
                </div>
                <button
                  onClick={() => setSelectedOrder(null)}
                  className="p-1.5 text-slate-400 hover:text-white rounded-lg cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Customer Box */}
              <div className="bg-white/[0.03] border border-white/[0.06] p-4 rounded-2xl space-y-2 text-xs">
                <div className="font-bold text-white text-sm">{selectedOrder.customer.full_name}</div>
                <div className="text-slate-300">
                  شماره تماس: <span className="font-mono text-cyan-400">{selectedOrder.customer.phone_number}</span>
                </div>
                <div className="text-slate-400">
                  آدرس: {selectedOrder.customer.city}، {selectedOrder.customer.address_line}
                </div>
              </div>

              {/* AI Risk Assessment Card */}
              <div className="bg-white/[0.03] border border-white/[0.06] p-4 rounded-2xl space-y-2.5 text-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-cyan-400" />
                    <span className="font-bold text-white">ارزیابی هوشمند ریسک و تقلب (AI)</span>
                  </div>
                  {loadingRisk ? (
                    <span className="text-[10px] text-slate-400 animate-pulse">در حال تحلیل...</span>
                  ) : orderRisk ? (
                    <span
                      className={cn(
                        'text-[10px] font-bold px-2 py-0.5 rounded-full border',
                        orderRisk.risk_level === 'LOW' && 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
                        orderRisk.risk_level === 'MEDIUM' && 'bg-amber-500/10 text-amber-400 border-amber-500/30',
                        orderRisk.risk_level === 'HIGH' && 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                      )}
                    >
                      {orderRisk.risk_level === 'LOW' ? 'کم‌خطر (تأیید خودکار)' : orderRisk.risk_level === 'MEDIUM' ? 'ریسک متوسط' : 'پرخطر (نیازمند احراز)'}
                    </span>
                  ) : null}
                </div>

                {orderRisk && (
                  <div className="space-y-2 pt-2 border-t border-white/[0.04]">
                    <div className="text-slate-300 text-[11px] leading-relaxed">
                      <span className="text-slate-400 font-medium">اقدام پیشنهادی: </span>
                      <span className="text-cyan-300">{orderRisk.recommended_action}</span>
                    </div>
                    {orderRisk.flags && orderRisk.flags.length > 0 && (
                      <div className="space-y-1">
                        {orderRisk.flags.map((flag: any, idx: number) => (
                          <div
                            key={idx}
                            className="flex items-start gap-1.5 text-[11px] text-amber-300/90 bg-amber-500/10 p-2 rounded-lg border border-amber-500/20"
                          >
                            <span>⚠️</span>
                            <span>{flag.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Items */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">اقلام سفارش</h3>
                <div className="divide-y divide-white/[0.04] border border-white/[0.06] rounded-2xl overflow-hidden bg-white/[0.01]">
                  {selectedOrder.items?.map((item) => (
                    <div key={item.id} className="p-3.5 flex items-center justify-between text-xs">
                      <div>
                        <div className="font-bold text-white">{item.variant_name}</div>
                        <div className="text-[11px] font-mono text-slate-400">{item.variant_sku}</div>
                      </div>
                      <div className="text-left font-mono">
                        <div className="font-bold text-white">
                          {formatNumber(item.quantity)} × {formatCurrency(item.unit_price, currency)}
                        </div>
                        <div className="text-cyan-400 font-bold">{formatCurrency(item.total_price, currency)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Summary Financials */}
              <div className="bg-white/[0.03] border border-white/[0.06] p-4 rounded-2xl space-y-2 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>مجموع اقلام:</span>
                  <span className="font-mono text-slate-200">{formatCurrency(selectedOrder.total_items_price, currency)}</span>
                </div>
                {Number(selectedOrder.discount_amount) > 0 && (
                  <div className="flex justify-between text-rose-400">
                    <span>تخفیف:</span>
                    <span className="font-mono">- {formatCurrency(selectedOrder.discount_amount, currency)}</span>
                  </div>
                )}
                <div className="flex justify-between text-slate-400">
                  <span>هزینه ارسال:</span>
                  <span className="font-mono text-slate-200">{formatCurrency(selectedOrder.shipping_cost, currency)}</span>
                </div>
                <div className="border-t border-white/[0.06] pt-2 flex justify-between font-bold text-sm text-white">
                  <span>مبلغ کل سفارش:</span>
                  <span className="font-mono text-cyan-400">{formatCurrency(selectedOrder.grand_total, currency)}</span>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-white/[0.08]">
              <button
                onClick={() => setSelectedOrder(null)}
                className="w-full py-2.5 bg-white/[0.06] hover:bg-white/[0.12] text-white font-medium rounded-xl text-xs cursor-pointer"
              >
                بستن پنجره
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Fulfill Modal */}
      {showFulfillModal && fulfillOrderTarget && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-[#0b101d] rounded-3xl max-w-md w-full p-6 shadow-2xl border border-white/10 space-y-5">
            <div>
              <h2 className="text-base font-bold text-white">ارسال سفارش و ثبت کد رهگیری</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                سفارش {fulfillOrderTarget.order_number} برای مشتری {fulfillOrderTarget.customer.full_name}
              </p>
            </div>

            <form onSubmit={handleFulfill} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">کد رهگیری پستی / تیپاکس</label>
                <input
                  type="text"
                  required
                  value={trackingNumber}
                  onChange={(e) => setTrackingNumber(e.target.value)}
                  placeholder="مثال: ۲۴ رقمی پست یا کد تیپاکس..."
                  className="w-full bg-white/[0.04] border border-white/[0.1] text-white rounded-xl px-3.5 py-2.5 text-xs font-mono focus:border-cyan-400/70 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">هزینه واقعی ارسال (تومان)</label>
                <input
                  type="number"
                  value={fulfillShippingCost}
                  onChange={(e) => setFulfillShippingCost(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.1] text-white rounded-xl px-3.5 py-2.5 text-xs font-mono focus:border-cyan-400/70 outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setShowFulfillModal(false)}
                  className="text-xs font-medium text-slate-400 hover:text-white px-4 py-2 cursor-pointer"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-5 py-2.5 rounded-xl transition shadow-[0_0_15px_rgba(16,185,129,0.4)] cursor-pointer"
                >
                  تأیید ارسال مرسوله
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cancel Modal */}
      {showCancelModal && cancelOrderTarget && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-[#0b101d] rounded-3xl max-w-md w-full p-6 shadow-2xl border border-white/10 space-y-5">
            <div>
              <h2 className="text-base font-bold text-rose-400">لغو سفارش و آزادسازی موجودی</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                با لغو سفارش {cancelOrderTarget.order_number}، اقلام رزرو شده مجدداً به انبار بازمی‌گردند.
              </p>
            </div>

            <form onSubmit={handleCancel} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">علت لغو سفارش</label>
                <input
                  type="text"
                  required
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  placeholder="مثال: درخواست انصراف مشتری، عدم واریز وجه..."
                  className="w-full bg-white/[0.04] border border-white/[0.1] text-white rounded-xl px-3.5 py-2.5 text-xs focus:border-rose-400/70 outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setShowCancelModal(false)}
                  className="text-xs font-medium text-slate-400 hover:text-white px-4 py-2 cursor-pointer"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs px-5 py-2.5 rounded-xl transition shadow-[0_0_15px_rgba(244,63,94,0.4)] cursor-pointer"
                >
                  لغو قطعی سفارش
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CSV Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-[#0b101d] rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-white/10 space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">ایمپورت هوشمند سفارشات از فایل CSV</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  فایل باید شامل customer_name, customer_phone, sku, quantity, unit_price باشد.
                </p>
              </div>
              <button
                onClick={() => setShowImportModal(false)}
                className="text-slate-400 hover:text-white p-1 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleImportCsv} className="space-y-4">
              <div className="border border-dashed border-white/15 rounded-2xl p-6 text-center hover:bg-white/[0.02] transition cursor-pointer">
                <input
                  type="file"
                  accept=".csv"
                  required
                  onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500 cursor-pointer"
                />
              </div>

              {importResult && (
                <div className="bg-white/[0.03] p-4 rounded-xl text-xs space-y-1.5 border border-white/[0.06]">
                  <div className="font-bold text-white">نتیجه پردازش فایل:</div>
                  <div className="text-emerald-400 font-semibold">
                    سفارشات ایجاد شده با موفقیت: {formatNumber(importResult.created)}
                  </div>
                  {importResult.failed > 0 && (
                    <div className="text-rose-400 font-semibold">
                      خطا در پردازش: {formatNumber(importResult.failed)} ردیف
                    </div>
                  )}
                  {importResult.errors?.length > 0 && (
                    <div className="text-slate-400 max-h-32 overflow-y-auto space-y-1 pt-1">
                      {importResult.errors.map((er: any, i: number) => (
                        <div key={i} className="text-rose-400">
                          ردیف {er.row}: {er.error}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setShowImportModal(false)}
                  className="text-xs font-medium text-slate-400 hover:text-white px-4 py-2 cursor-pointer"
                >
                  بستن
                </button>
                <button
                  type="submit"
                  disabled={importing || !importFile}
                  className="bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs px-5 py-2.5 rounded-xl transition shadow-[0_0_15px_rgba(37,99,235,0.4)] disabled:opacity-50 cursor-pointer"
                >
                  {importing ? 'در حال ایمپورت...' : 'شروع پردازش و بارگذاری'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
