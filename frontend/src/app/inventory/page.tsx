'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useStore } from '@/contexts/StoreContext';
import { InventoryBalance, Warehouse } from '@/types';
import { formatCurrency, formatNumber } from '@/lib/utils';
import { Boxes, Sliders, AlertTriangle, Search, Filter, ShoppingBag } from 'lucide-react';

export default function InventoryPage() {
  const { activeStore } = useStore();
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [selectedWarehouse, setSelectedWarehouse] = useState('');
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  // Adjustment Modal
  const [showAdjustModal, setShowAdjustModal] = useState(false);
  const [activeItem, setActiveItem] = useState<InventoryBalance | null>(null);
  const [newOnHand, setNewOnHand] = useState<number>(0);
  const [adjustReason, setAdjustReason] = useState('');

  // Reorder Suggestions
  const [suggestions, setSuggestions] = useState<any[]>([]);

  const loadBalances = async () => {
    if (!activeStore) return;
    setLoading(true);
    try {
      const [balData, whData, suggData] = await Promise.all([
        api.getInventoryBalances({
          warehouse: selectedWarehouse,
          low_stock: lowStockOnly,
          search,
        }),
        api.getWarehouses(),
        api.getReorderSuggestions(),
      ]);
      const bList = Array.isArray(balData) ? balData : balData.results || [];
      const wList = Array.isArray(whData) ? whData : whData.results || [];
      setBalances(bList);
      setWarehouses(wList);
      setSuggestions(suggData || []);
    } catch (err) {
      console.error('Error loading inventory balances', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeStore) {
      loadBalances();
    }
  }, [activeStore, selectedWarehouse, lowStockOnly]);

  const handleOpenAdjust = (item: InventoryBalance) => {
    setActiveItem(item);
    setNewOnHand(item.on_hand_quantity);
    setAdjustReason('');
    setShowAdjustModal(true);
  };

  const handleSaveAdjustment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeItem) return;
    try {
      await api.adjustStock({
        warehouse_id: activeItem.warehouse,
        variant_id: activeItem.variant,
        new_on_hand: Number(newOnHand),
        reason: adjustReason,
      });
      setShowAdjustModal(false);
      await loadBalances();
    } catch (err: any) {
      alert(`خطا در ثبت تعدیل انبار: ${err.message}`);
    }
  };

  const currency = activeStore?.currency || 'IRT';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">موجودی و انبارها</h1>
          <p className="text-sm text-slate-500 mt-1">
            کنترل دقیق موجودی فیزیکی، مقادیر رزرو شده در سفارشات و موجودی قابل فروش لحظه‌ای
          </p>
        </div>
      </div>

      {/* Reorder Suggestions Banner (if any) */}
      {suggestions.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-amber-800 font-bold text-sm">
            <ShoppingBag className="w-5 h-5 text-amber-600" />
            <span>پیشنهاد سفارش مجدد (تأمین کالا)</span>
            <span className="text-xs bg-amber-200 text-amber-900 px-2 py-0.5 rounded-full mr-2">
              {formatNumber(suggestions.length)} قلم نیازمند خرید
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {suggestions.slice(0, 3).map((sugg) => (
              <div key={sugg.sku} className="bg-white p-3.5 rounded-xl border border-amber-100 text-xs space-y-1">
                <div className="font-bold text-slate-800">{sugg.product_name} ({sugg.variant_name})</div>
                <div className="font-mono text-slate-500 text-[11px]">{sugg.sku}</div>
                <div className="flex items-center justify-between text-slate-600 pt-1 border-t border-slate-50">
                  <span>موجودی فعلی: <strong className="text-rose-600">{formatNumber(sugg.available)}</strong></span>
                  <span>پیشنهاد سفارش: <strong className="text-emerald-600">{formatNumber(sugg.suggested_quantity)} عدد</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-96">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadBalances()}
            placeholder="جستجوی نام کالا یا SKU..."
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pr-10 pl-4 py-2 text-sm focus:ring-2 focus:ring-sky-500 focus:bg-white outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute right-3.5 top-3" />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <select
            value={selectedWarehouse}
            onChange={(e) => setSelectedWarehouse(e.target.value)}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm rounded-xl py-2 px-3 font-medium cursor-pointer"
          >
            <option value="">همه انبارها</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>

          <button
            onClick={() => setLowStockOnly(!lowStockOnly)}
            className={`text-xs font-bold px-3 py-2 rounded-xl border transition flex items-center gap-1.5 ${
              lowStockOnly
                ? 'bg-rose-50 border-rose-200 text-rose-700'
                : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>فقط کسری موجودی</span>
          </button>
        </div>
      </div>

      {/* Balances Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">
              <tr>
                <th className="py-3.5 px-6">کالا و انبار</th>
                <th className="py-3.5 px-6">کد کالا (SKU)</th>
                <th className="py-3.5 px-6 text-center">موجودی فیزیکی</th>
                <th className="py-3.5 px-6 text-center">رزرو شده</th>
                <th className="py-3.5 px-6 text-center">موجودی قابل فروش</th>
                <th className="py-3.5 px-6 text-center">نقطه سفارش</th>
                <th className="py-3.5 px-6 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    در حال بارگذاری موجودی انبارها...
                  </td>
                </tr>
              ) : balances.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    موردی یافت نشد.
                  </td>
                </tr>
              ) : (
                balances.map((b) => (
                  <tr key={b.id} className="hover:bg-slate-50/70 transition">
                    <td className="py-4 px-6">
                      <div className="font-bold text-slate-900">{b.product_name}</div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        <span>{b.variant_name}</span> &bull;{' '}
                        <span className="text-sky-600 font-medium">{b.warehouse_name}</span>
                      </div>
                    </td>
                    <td className="py-4 px-6 font-mono text-xs text-slate-600">{b.variant_sku}</td>
                    <td className="py-4 px-6 text-center font-bold text-slate-800">
                      {formatNumber(b.on_hand_quantity)}
                    </td>
                    <td className="py-4 px-6 text-center text-amber-700 font-medium">
                      {formatNumber(b.reserved_quantity)}
                    </td>
                    <td className="py-4 px-6 text-center">
                      <span
                        className={`inline-block font-bold px-2.5 py-1 rounded-full text-xs ${
                          b.available <= b.reorder_point
                            ? 'bg-rose-100 text-rose-700'
                            : 'bg-emerald-100 text-emerald-800'
                        }`}
                      >
                        {formatNumber(b.available)} عدد
                      </span>
                    </td>
                    <td className="py-4 px-6 text-center text-slate-400 text-xs">
                      {formatNumber(b.reorder_point)}
                    </td>
                    <td className="py-4 px-6 text-center">
                      <button
                        onClick={() => handleOpenAdjust(b)}
                        className="text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg transition"
                      >
                        تعدیل دستی
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Stock Adjustment Modal */}
      {showAdjustModal && activeItem && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-100 space-y-5 animate-in fade-in zoom-in-95">
            <div>
              <h2 className="text-lg font-bold text-slate-900">تعدیل موجودی فیزیکی انبار</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                تغییر تعداد برای {activeItem.product_name} ({activeItem.variant_sku}) در {activeItem.warehouse_name}
              </p>
            </div>

            <form onSubmit={handleSaveAdjustment} className="space-y-4">
              <div className="bg-slate-50 p-3 rounded-xl text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-500">موجودی فعلی:</span>
                  <span className="font-bold text-slate-800">{activeItem.on_hand_quantity} عدد</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">رزرو شده در سفارشات:</span>
                  <span className="font-bold text-amber-600">{activeItem.reserved_quantity} عدد</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  موجودی فیزیکی جدید (شمارش شده)
                </label>
                <input
                  type="number"
                  min="0"
                  required
                  value={newOnHand}
                  onChange={(e) => setNewOnHand(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm font-bold focus:ring-2 focus:ring-sky-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">علت یا شرح انبارگردانی</label>
                <input
                  type="text"
                  required
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  placeholder="مثال: انبارگردانی پایان هفته، خطای ثبت قبلی، ضایعات..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-sky-500 outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAdjustModal(false)}
                  className="text-sm font-medium text-slate-600 hover:text-slate-800 px-4 py-2"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="bg-sky-600 hover:bg-sky-700 text-white font-bold text-sm px-5 py-2.5 rounded-xl transition shadow-sm"
                >
                  ثبت گردش و تعدیل
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
