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
  X
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

  const handleFulfill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fulfillOrderTarget) return;
    try {
      await api.fulfillOrder(fulfillOrderTarget.id, {
        tracking_number: trackingNumber,
        shipping_cost: fulfillShippingCost ? parseFloat(fulfillShippingCost) : undefined,
      });
      setShowFulfillModal(false);
      setFulfillOrderTarget(null);
      await loadOrders();
    } catch (err: any) {
      alert(`خطا در ثبت ارسال سفارش: ${err.message}`);
    }
  };

  const handleCancel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancelOrderTarget) return;
    try {
      await api.cancelOrder(cancelOrderTarget.id, cancelReason);
      setShowCancelModal(false);
      setCancelOrderTarget(null);
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
      alert(`خطا در ایمپورت فایل: ${err.message}`);
    } finally {
      setImporting(false);
    }
  };

  const currency = activeStore?.currency || 'IRT';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">سفارشات و فروش چندکاناله</h1>
          <p className="text-sm text-slate-500 mt-1">
            پیگیری وضعیت سفارشات اینستاگرام، تلگرام، سایت و دستی به همراه چرخه بسته‌بندی و ارسال
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setShowImportModal(true);
              setImportResult(null);
            }}
            className="inline-flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-sm px-4 py-2.5 rounded-xl transition shadow-sm"
          >
            <FileUp className="w-4 h-4" />
            <span>ایمپورت فایل اکسل/CSV</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-96">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadOrders()}
            placeholder="جستجوی شماره سفارش، نام مشتری یا تلفن..."
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pr-10 pl-4 py-2 text-sm focus:ring-2 focus:ring-sky-500 focus:bg-white outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute right-3.5 top-3" />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm rounded-xl py-2 px-3 font-medium cursor-pointer"
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
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm rounded-xl py-2 px-3 font-medium cursor-pointer"
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
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">
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
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    در حال دریافت سفارشات...
                  </td>
                </tr>
              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    سفارشی یافت نشد.
                  </td>
                </tr>
              ) : (
                orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50/70 transition">
                    <td className="py-4 px-6">
                      <div className="font-bold font-mono text-slate-900">{o.order_number}</div>
                      <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                        <span className="bg-sky-50 text-sky-700 px-2 py-0.5 rounded font-medium">
                          {o.channel_display}
                        </span>
                        <span>{formatDate(o.created_at)}</span>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <div className="font-bold text-slate-800">{o.customer?.full_name}</div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        <span className="font-mono">{o.customer?.phone_number}</span>
                        {o.customer?.city && <span> &bull; {o.customer.city}</span>}
                      </div>
                    </td>
                    <td className="py-4 px-6 text-center">
                      <span
                        className={cn(
                          'inline-block px-2.5 py-1 rounded-full text-xs font-bold',
                          o.order_status === 'CONFIRMED' && 'bg-sky-100 text-sky-800',
                          o.order_status === 'FULFILLED' && 'bg-emerald-100 text-emerald-800',
                          o.order_status === 'CANCELLED' && 'bg-rose-100 text-rose-700',
                          o.order_status === 'PENDING_CONFIRMATION' && 'bg-amber-100 text-amber-800'
                        )}
                      >
                        {o.order_status_display}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-center">
                      <span
                        className={cn(
                          'inline-block px-2 py-0.5 rounded text-xs font-medium',
                          o.payment_status === 'PAID' && 'text-emerald-700 font-bold',
                          o.payment_status === 'PENDING' && 'text-amber-600',
                          o.payment_status === 'PARTIALLY_PAID' && 'text-sky-600 font-semibold'
                        )}
                      >
                        {o.payment_status_display}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-center">
                      <span
                        className={cn(
                          'inline-block px-2 py-0.5 rounded text-xs font-medium',
                          o.fulfillment_status === 'FULFILLED' && 'text-emerald-700 font-bold',
                          o.fulfillment_status === 'UNFULFILLED' && 'text-slate-500'
                        )}
                      >
                        {o.fulfillment_status_display}
                      </span>
                    </td>
                    <td className="py-4 px-6 font-bold text-slate-900">
                      {formatCurrency(o.grand_total, currency)}
                    </td>
                    <td className="py-4 px-6 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => setSelectedOrder(o)}
                          className="p-1.5 text-slate-600 hover:text-sky-600 hover:bg-sky-50 rounded-lg transition"
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
                            className="p-1.5 text-slate-600 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition"
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
                            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
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
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex justify-end">
          <div className="bg-white w-full max-w-lg h-full p-6 shadow-2xl overflow-y-auto space-y-6 animate-in slide-in-from-left duration-300">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h2 className="text-lg font-black text-slate-900 font-mono">{selectedOrder.order_number}</h2>
                <span className="text-xs text-slate-400">ثبت در {formatDate(selectedOrder.created_at)}</span>
              </div>
              <button
                onClick={() => setSelectedOrder(null)}
                className="p-2 text-slate-400 hover:text-slate-600 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Customer Box */}
            <div className="bg-slate-50 p-4 rounded-2xl space-y-2 text-xs">
              <div className="font-bold text-slate-800 text-sm">{selectedOrder.customer.full_name}</div>
              <div className="text-slate-600">
                شماره تماس: <span className="font-mono">{selectedOrder.customer.phone_number}</span>
              </div>
              <div className="text-slate-600">
                آدرس: {selectedOrder.customer.city}، {selectedOrder.customer.address_line}
              </div>
            </div>

            {/* Items */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">اقلام سفارش</h3>
              <div className="divide-y divide-slate-100 border border-slate-100 rounded-xl overflow-hidden">
                {selectedOrder.items.map((it) => (
                  <div key={it.id} className="p-3 text-xs flex justify-between items-center bg-white">
                    <div>
                      <div className="font-bold text-slate-800">{it.variant_name}</div>
                      <div className="text-slate-400 font-mono text-[11px]">{it.variant_sku}</div>
                    </div>
                    <div className="text-left">
                      <div className="font-bold text-slate-900">
                        {formatNumber(it.quantity)} &times; {formatCurrency(it.unit_price, currency)}
                      </div>
                      <div className="text-slate-500 font-semibold">{formatCurrency(it.total_price, currency)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Financials */}
            <div className="bg-slate-50 p-4 rounded-2xl space-y-2 text-xs">
              <div className="flex justify-between text-slate-600">
                <span>مجموع اقلام:</span>
                <span>{formatCurrency(selectedOrder.total_items_price, currency)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>هزینه ارسال:</span>
                <span>{formatCurrency(selectedOrder.shipping_cost, currency)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>تخفیف:</span>
                <span>{formatCurrency(selectedOrder.discount_amount, currency)}</span>
              </div>
              <div className="flex justify-between text-sm font-bold text-slate-900 pt-2 border-t border-slate-200">
                <span>مبلغ قابل پرداخت:</span>
                <span>{formatCurrency(selectedOrder.grand_total, currency)}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Fulfill Modal */}
      {showFulfillModal && fulfillOrderTarget && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-100 space-y-5 animate-in fade-in zoom-in-95">
            <div>
              <h2 className="text-lg font-bold text-slate-900">تأیید ارسال و صدور مرسوله</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                سفارش {fulfillOrderTarget.order_number} برای {fulfillOrderTarget.customer.full_name}
              </p>
            </div>

            <form onSubmit={handleFulfill} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  کد رهگیری پستی / بارنامه
                </label>
                <input
                  type="text"
                  required
                  value={trackingNumber}
                  onChange={(e) => setTrackingNumber(e.target.value)}
                  placeholder="مثال: 2149802111000..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm font-mono focus:ring-2 focus:ring-sky-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  هزینه واقعی حمل (تومان)
                </label>
                <input
                  type="number"
                  value={fulfillShippingCost}
                  onChange={(e) => setFulfillShippingCost(e.target.value)}
                  placeholder="45000"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-sky-500 outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowFulfillModal(false)}
                  className="text-sm font-medium text-slate-600 hover:text-slate-800 px-4 py-2"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm px-5 py-2.5 rounded-xl transition shadow-sm"
                >
                  تأیید و ارسال سفارش
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cancel Modal */}
      {showCancelModal && cancelOrderTarget && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-100 space-y-5 animate-in fade-in zoom-in-95">
            <div>
              <h2 className="text-lg font-bold text-rose-600">لغو سفارش و آزادسازی موجودی</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                با لغو سفارش {cancelOrderTarget.order_number}، اقلام رزرو شده مجدداً به انبار بازمی‌گردند.
              </p>
            </div>

            <form onSubmit={handleCancel} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">علت لغو سفارش</label>
                <input
                  type="text"
                  required
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  placeholder="مثال: درخواست انصراف مشتری، عدم واریز وجه..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-rose-500 outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCancelModal(false)}
                  className="text-sm font-medium text-slate-600 hover:text-slate-800 px-4 py-2"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="bg-rose-600 hover:bg-rose-700 text-white font-bold text-sm px-5 py-2.5 rounded-xl transition shadow-sm"
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
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-100 space-y-5 animate-in fade-in zoom-in-95">
            <div>
              <h2 className="text-lg font-bold text-slate-900">ایمپورت هوشمند سفارشات از فایل CSV</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                فایل باید شامل ستون‌های customer_name, customer_phone, sku, quantity, unit_price باشد.
              </p>
            </div>

            <form onSubmit={handleImportCsv} className="space-y-4">
              <div className="border-2 border-dashed border-slate-200 rounded-2xl p-6 text-center hover:bg-slate-50 transition cursor-pointer">
                <input
                  type="file"
                  accept=".csv"
                  required
                  onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-sky-50 file:text-sky-700 hover:file:bg-sky-100"
                />
              </div>

              {importResult && (
                <div className="bg-slate-50 p-4 rounded-xl text-xs space-y-1.5 border border-slate-200">
                  <div className="font-bold text-slate-800">نتیجه پردازش فایل:</div>
                  <div className="text-emerald-700 font-semibold">
                    سفارشات ایجاد شده با موفقیت: {formatNumber(importResult.created)}
                  </div>
                  {importResult.failed > 0 && (
                    <div className="text-rose-700 font-semibold">
                      خطا در پردازش: {formatNumber(importResult.failed)} ردیف
                    </div>
                  )}
                  {importResult.errors?.length > 0 && (
                    <div className="text-slate-500 max-h-32 overflow-y-auto space-y-1 pt-1">
                      {importResult.errors.map((er: any, i: number) => (
                        <div key={i} className="text-rose-600">
                          ردیف {er.row}: {er.error}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowImportModal(false)}
                  className="text-sm font-medium text-slate-600 hover:text-slate-800 px-4 py-2"
                >
                  بستن
                </button>
                <button
                  type="submit"
                  disabled={importing || !importFile}
                  className="bg-sky-600 hover:bg-sky-700 text-white font-bold text-sm px-5 py-2.5 rounded-xl transition shadow-sm disabled:opacity-50"
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
