'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useStore } from '@/contexts/StoreContext';
import { InventoryBalance, Warehouse } from '@/types';
import { formatNumber, cn } from '@/lib/utils';
import { Boxes, AlertTriangle, Search, ShoppingBag, X } from 'lucide-react';

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
  // Slow Movers / Dead Stock
  const [slowMovers, setSlowMovers] = useState<any>(null);

  const loadBalances = async () => {
    if (!activeStore) return;
    setLoading(true);
    try {
      const [balData, whData, suggData, slowData] = await Promise.all([
        api.getInventoryBalances({
          warehouse: selectedWarehouse,
          low_stock: lowStockOnly,
          search,
        }),
        api.getWarehouses(),
        api.getReorderSuggestions(),
        api.getSlowMovers(60).catch(() => null),
      ]);
      const bList = Array.isArray(balData) ? balData : balData.results || [];
      const wList = Array.isArray(whData) ? whData : whData.results || [];
      setBalances(bList);
      setWarehouses(wList);
      setSuggestions(suggData || []);
      setSlowMovers(slowData);
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

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black text-white tracking-tight">موجودی و انبارداری</h1>
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            کنترل دقیق موجودی فیزیکی، مقادیر رزرو شده در سفارشات و موجودی قابل فروش لحظه‌ای
          </p>
        </div>
      </div>

      {/* Reorder Suggestions Banner (if any) */}
      {suggestions.length > 0 && (
        <div className="glass-card p-5 border-amber-500/30 bg-amber-500/[0.06] space-y-3">
          <div className="flex items-center gap-2 text-amber-300 font-bold text-xs">
            <ShoppingBag className="w-4 h-4 text-amber-400" />
            <span>پیشنهاد سفارش مجدد (تأمین کالا)</span>
            <span className="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full mr-2">
              {formatNumber(suggestions.length)} قلم نیازمند خرید
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {suggestions.slice(0, 3).map((sugg) => (
              <div key={sugg.sku} className="p-3.5 rounded-2xl bg-white/[0.03] border border-white/[0.08] text-xs space-y-1.5">
                <div className="font-bold text-slate-200">{sugg.product_name} ({sugg.variant_name})</div>
                <div className="font-mono text-slate-400 text-[11px]">{sugg.sku}</div>
                <div className="flex items-center justify-between text-slate-400 pt-1.5 border-t border-white/[0.05]">
                  <span>موجودی: <strong className="text-rose-400 font-bold">{formatNumber(sugg.available)}</strong></span>
                  <span>پیشنهاد خرید: <strong className="text-emerald-400 font-bold">{formatNumber(sugg.suggested_quantity)} عدد</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Slow Movers / Dead Stock Liquidation Banner */}
      {slowMovers && slowMovers.slow_mover_count > 0 && (
        <div className="glass-card p-5 border-purple-500/30 bg-purple-500/[0.06] space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-purple-300 font-bold text-xs">
              <Boxes className="w-4 h-4 text-purple-400" />
              <span>کالاهای راکد و خواب سرمایه (عدم فروش در ۶۰ روز گذشته)</span>
              <span className="text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full mr-2">
                {formatNumber(slowMovers.slow_mover_count)} قلم راکد
              </span>
            </div>
            <div className="text-xs text-purple-200">
              مجموع سرمایه راکد انبار:{' '}
              <strong className="text-amber-400 font-bold">
                {Number(slowMovers.total_trapped_capital || 0).toLocaleString('fa-IR')} تومان
              </strong>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {(slowMovers.items || []).slice(0, 3).map((item: any) => (
              <div key={item.sku} className="p-3.5 rounded-2xl bg-white/[0.03] border border-white/[0.08] text-xs space-y-1.5">
                <div className="font-bold text-slate-200">{item.product_name}</div>
                <div className="font-mono text-slate-400 text-[11px]">{item.sku}</div>
                <div className="flex items-center justify-between text-slate-400 pt-1.5 border-t border-white/[0.05]">
                  <span>موجودی راکد: <strong className="text-white font-bold">{formatNumber(item.total_on_hand)}</strong></span>
                  <span className="text-purple-300 font-semibold">{item.recommendation_text}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="glass-card p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-96">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadBalances()}
            placeholder="جستجوی نام کالا یا SKU..."
            className="w-full bg-white/[0.04] border border-white/[0.09] rounded-xl pr-10 pl-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400/60"
          />
          <Search className="w-4 h-4 text-slate-400 absolute right-3.5 top-3" />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <select
            value={selectedWarehouse}
            onChange={(e) => setSelectedWarehouse(e.target.value)}
            className="bg-[#0e1628] border border-white/[0.09] text-slate-200 text-xs rounded-xl py-2 px-3 font-medium cursor-pointer focus:outline-none focus:border-cyan-400/60"
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
            className={cn(
              'text-xs font-bold px-3 py-2 rounded-xl border transition-all flex items-center gap-1.5 cursor-pointer',
              lowStockOnly
                ? 'bg-rose-500/20 border-rose-500/40 text-rose-300 shadow-[0_0_12px_rgba(244,63,94,0.3)]'
                : 'bg-white/[0.04] border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.08]'
            )}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>فقط کسری موجودی</span>
          </button>
        </div>
      </div>

      {/* Balances Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead className="bg-white/[0.02] border-b border-white/[0.06] text-slate-400 font-semibold">
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
            <tbody className="divide-y divide-white/[0.04]">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    در حال بارگذاری موجودی انبارها...
                  </td>
                </tr>
              ) : balances.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    موردی یافت نشد.
                  </td>
                </tr>
              ) : (
                balances.map((b) => (
                  <tr key={b.id} className="hover:bg-white/[0.03] transition-colors">
                    <td className="py-4 px-6">
                      <div className="font-bold text-white">{b.product_name}</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        <span>{b.variant_name}</span> &bull;{' '}
                        <span className="text-cyan-400 font-medium">{b.warehouse_name}</span>
                      </div>
                    </td>
                    <td className="py-4 px-6 font-mono text-[11px] text-slate-400">{b.variant_sku}</td>
                    <td className="py-4 px-6 text-center font-bold text-slate-200">
                      {formatNumber(b.on_hand_quantity)}
                    </td>
                    <td className="py-4 px-6 text-center text-amber-400 font-medium">
                      {formatNumber(b.reserved_quantity)}
                    </td>
                    <td className="py-4 px-6 text-center">
                      <span
                        className={cn(
                          'inline-block font-bold px-2.5 py-1 rounded-full text-[11px]',
                          b.available <= b.reorder_point
                            ? 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
                            : 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                        )}
                      >
                        {formatNumber(b.available)} عدد
                      </span>
                    </td>
                    <td className="py-4 px-6 text-center text-slate-500 font-mono text-xs">
                      {formatNumber(b.reorder_point)}
                    </td>
                    <td className="py-4 px-6 text-center">
                      <button
                        onClick={() => handleOpenAdjust(b)}
                        className="text-[11px] font-semibold bg-white/[0.05] hover:bg-white/[0.1] text-slate-200 hover:text-white border border-white/[0.08] px-3 py-1.5 rounded-xl transition cursor-pointer"
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
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-[#0b101d] rounded-3xl max-w-md w-full p-6 shadow-2xl border border-white/10 space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">تعدیل موجودی فیزیکی انبار</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  تغییر تعداد برای {activeItem.product_name} ({activeItem.variant_sku}) در {activeItem.warehouse_name}
                </p>
              </div>
              <button
                onClick={() => setShowAdjustModal(false)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveAdjustment} className="space-y-4">
              <div className="bg-white/[0.03] border border-white/[0.06] p-3 rounded-2xl text-xs space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-400">موجودی فعلی:</span>
                  <span className="font-bold text-slate-200">{activeItem.on_hand_quantity} عدد</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">رزرو شده در سفارشات:</span>
                  <span className="font-bold text-amber-400">{activeItem.reserved_quantity} عدد</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">
                  موجودی فیزیکی جدید (شمارش شده)
                </label>
                <input
                  type="number"
                  min="0"
                  required
                  value={newOnHand}
                  onChange={(e) => setNewOnHand(Number(e.target.value))}
                  className="w-full bg-white/[0.04] border border-white/[0.1] text-white rounded-xl px-3.5 py-2.5 text-xs font-bold focus:border-cyan-400/70 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">علت یا شرح انبارگردانی</label>
                <input
                  type="text"
                  required
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  placeholder="مثال: انبارگردانی پایان هفته، خطای ثبت قبلی، ضایعات..."
                  className="w-full bg-white/[0.04] border border-white/[0.1] text-white rounded-xl px-3.5 py-2.5 text-xs focus:border-cyan-400/70 outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setShowAdjustModal(false)}
                  className="text-xs font-medium text-slate-400 hover:text-white px-4 py-2 cursor-pointer"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs px-5 py-2.5 rounded-xl transition shadow-[0_0_15px_rgba(37,99,235,0.4)] cursor-pointer"
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
