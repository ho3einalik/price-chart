'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useStore } from '@/contexts/StoreContext';
import { PaymentTransaction } from '@/types';
import { formatCurrency, formatNumber, formatDate, cn } from '@/lib/utils';
import { CreditCard, CheckCircle2, XCircle, Search, Filter, Image, AlertCircle, Eye } from 'lucide-react';

export default function PaymentsPage() {
  const { activeStore } = useStore();
  const [payments, setPayments] = useState<PaymentTransaction[]>([]);
  const [statusFilter, setStatusFilter] = useState('PENDING_VERIFICATION');
  const [loading, setLoading] = useState(true);

  // Reject Modal
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<PaymentTransaction | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  // Receipt Preview
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  const loadPayments = async () => {
    if (!activeStore) return;
    setLoading(true);
    try {
      const data = await api.getPayments({
        status: statusFilter,
      });
      const list: PaymentTransaction[] = Array.isArray(data) ? data : data.results || [];
      setPayments(list);
    } catch (err) {
      console.error('Error loading payments', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeStore) {
      loadPayments();
    }
  }, [activeStore, statusFilter]);

  const handleVerify = async (paymentId: string) => {
    try {
      await api.verifyPayment(paymentId);
      await loadPayments();
    } catch (err: any) {
      alert(`خطا در تأیید تراکنش: ${err.message}`);
    }
  };

  const handleReject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rejectTarget) return;
    try {
      await api.rejectPayment(rejectTarget.id, rejectReason);
      setShowRejectModal(false);
      setRejectTarget(null);
      await loadPayments();
    } catch (err: any) {
      alert(`خطا در رد فیش: ${err.message}`);
    }
  };

  const currency = activeStore?.currency || 'IRT';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">کارتابل تأیید فیش‌های واریزی</h1>
          <p className="text-sm text-slate-500 mt-1">
            بررسی و انطباق فیش‌های کارت به کارت مشتریان شبکه‌های اجتماعی با صورتحساب بانکی
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setStatusFilter('PENDING_VERIFICATION')}
            className={cn(
              'text-xs font-bold px-3 py-1.5 rounded-xl transition',
              statusFilter === 'PENDING_VERIFICATION'
                ? 'bg-amber-100 text-amber-900'
                : 'text-slate-500 hover:bg-slate-100'
            )}
          >
            در انتظار بررسی و تأیید
          </button>
          <button
            onClick={() => setStatusFilter('VERIFIED')}
            className={cn(
              'text-xs font-bold px-3 py-1.5 rounded-xl transition',
              statusFilter === 'VERIFIED'
                ? 'bg-emerald-100 text-emerald-900'
                : 'text-slate-500 hover:bg-slate-100'
            )}
          >
            تأیید شده
          </button>
          <button
            onClick={() => setStatusFilter('REJECTED')}
            className={cn(
              'text-xs font-bold px-3 py-1.5 rounded-xl transition',
              statusFilter === 'REJECTED'
                ? 'bg-rose-100 text-rose-900'
                : 'text-slate-500 hover:bg-slate-100'
            )}
          >
            رد شده
          </button>
        </div>
      </div>

      {/* Payments Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">
              <tr>
                <th className="py-3.5 px-6">سفارش و مشتری</th>
                <th className="py-3.5 px-6">مبلغ واریزی</th>
                <th className="py-3.5 px-6">روش پرداخت</th>
                <th className="py-3.5 px-6">شناسه / ۴ رقم کارت</th>
                <th className="py-3.5 px-6 text-center">تصویر فیش</th>
                <th className="py-3.5 px-6 text-center">وضعیت</th>
                <th className="py-3.5 px-6 text-center">اقدام</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    در حال دریافت کارتابل تراکنش‌ها...
                  </td>
                </tr>
              ) : payments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    تراکنشی در این وضعیت وجود ندارد.
                  </td>
                </tr>
              ) : (
                payments.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/70 transition">
                    <td className="py-4 px-6">
                      <div className="font-bold font-mono text-slate-900">{p.order_number}</div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        <span>{p.customer_name}</span> &bull; <span>{formatDate(p.created_at)}</span>
                      </div>
                    </td>
                    <td className="py-4 px-6 font-bold text-slate-900">
                      {formatCurrency(p.amount, currency)}
                    </td>
                    <td className="py-4 px-6 text-xs text-slate-600">
                      <span className="bg-slate-100 px-2.5 py-1 rounded-md font-medium">
                        {p.method_display}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-xs">
                      {p.payer_card_mask && (
                        <div className="font-mono text-slate-700">کارت: {p.payer_card_mask}</div>
                      )}
                      {(p.tracking_code || p.reference_number) && (
                        <div className="font-mono text-slate-400 text-[11px]">
                          کد: {p.tracking_code || p.reference_number}
                        </div>
                      )}
                    </td>
                    <td className="py-4 px-6 text-center">
                      {p.receipt_image_url ? (
                        <button
                          onClick={() => setPreviewImage(p.receipt_image_url)}
                          className="inline-flex items-center gap-1 text-xs text-sky-600 hover:text-sky-800 font-medium"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>مشاهده</span>
                        </button>
                      ) : (
                        <span className="text-slate-300 text-xs">-</span>
                      )}
                    </td>
                    <td className="py-4 px-6 text-center">
                      <span
                        className={cn(
                          'inline-block px-2.5 py-1 rounded-full text-xs font-bold',
                          p.status === 'VERIFIED' && 'bg-emerald-100 text-emerald-800',
                          p.status === 'PENDING_VERIFICATION' && 'bg-amber-100 text-amber-800',
                          p.status === 'REJECTED' && 'bg-rose-100 text-rose-700'
                        )}
                      >
                        {p.status_display}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-center">
                      {p.status === 'PENDING_VERIFICATION' ? (
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => handleVerify(p.id)}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs px-3 py-1.5 rounded-lg transition shadow-sm"
                          >
                            تأیید فیش
                          </button>
                          <button
                            onClick={() => {
                              setRejectTarget(p);
                              setRejectReason('');
                              setShowRejectModal(true);
                            }}
                            className="text-xs font-medium text-rose-600 hover:bg-rose-50 px-2 py-1.5 rounded-lg transition"
                          >
                            رد فیش
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">
                          {p.verified_by_name ? `توسط ${p.verified_by_name}` : 'بررسی شده'}
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Reject Modal */}
      {showRejectModal && rejectTarget && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-100 space-y-5 animate-in fade-in zoom-in-95">
            <div>
              <h2 className="text-lg font-bold text-rose-600">رد فیش واریزی</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                فیش واریزی برای سفارش {rejectTarget.order_number} رد خواهد شد و سفارش در وضعیت معوق باقی می‌ماند.
              </p>
            </div>

            <form onSubmit={handleReject} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">علت رد فیش</label>
                <input
                  type="text"
                  required
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="مثال: فیش تکراری، عدم نشست در حساب بانکی، مبلغ ناکافی..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-rose-500 outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowRejectModal(false)}
                  className="text-sm font-medium text-slate-600 hover:text-slate-800 px-4 py-2"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="bg-rose-600 hover:bg-rose-700 text-white font-bold text-sm px-5 py-2.5 rounded-xl transition shadow-sm"
                >
                  رد قطعی فیش
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Image Preview Modal */}
      {previewImage && (
        <div
          onClick={() => setPreviewImage(null)}
          className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 cursor-pointer"
        >
          <div className="max-w-md max-h-[85vh] bg-white rounded-2xl overflow-hidden p-2 shadow-2xl">
            <img src={previewImage} alt="فیش واریزی" className="w-full h-auto object-contain rounded-xl" />
          </div>
        </div>
      )}
    </div>
  );
}
