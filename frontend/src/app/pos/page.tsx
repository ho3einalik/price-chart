'use client';

import React, { useState, useEffect } from 'react';
import {
  Store,
  Barcode,
  Search,
  ShoppingCart,
  Plus,
  Minus,
  Trash2,
  CreditCard,
  Banknote,
  Building2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Printer,
  FileText,
  UserCheck,
  RefreshCw,
  X
} from 'lucide-react';
import { api } from '@/lib/api';

export default function POSPage() {
  const [terminals, setTerminals] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSession, setActiveSession] = useState<any>(null);
  const [variants, setVariants] = useState<any[]>([]);
  const [proformas, setProformas] = useState<any[]>([]);
  const [b2bClients, setB2bClients] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Cart State
  const [cart, setCart] = useState<{ variant: any; quantity: number; unit_price: number }[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [customerPhone, setCustomerPhone] = useState('09000000000');
  const [customerName, setCustomerName] = useState('خریدار حضوری');
  const [paymentMethod, setPaymentMethod] = useState<'POS_TERMINAL' | 'CASH_ON_DELIVERY'>('POS_TERMINAL');
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [lastReceipt, setLastReceipt] = useState<any>(null);

  // New session modal
  const [showSessionModal, setShowSessionModal] = useState(false);
  const [openingCash, setOpeningCash] = useState('0');
  const [selectedTerminalId, setSelectedTerminalId] = useState('');

  // Active Tab
  const [activeTab, setActiveTab] = useState<'pos' | 'proformas' | 'b2b'>('pos');

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [terminalsData, sessionsData, productsData, proformasData, clientsData] = await Promise.all([
        api.getPOSTerminals().catch(() => []),
        api.getPOSSessions().catch(() => []),
        api.getProducts().catch(() => []),
        api.getProformas().catch(() => []),
        api.getB2BClients().catch(() => []),
      ]);

      setTerminals(terminalsData || []);
      const openSession = (sessionsData || []).find((s: any) => s.status === 'OPEN');
      setSessions(sessionsData || []);
      setActiveSession(openSession || null);

      // Extract active variants
      const allVariants: any[] = [];
      const prodList = Array.isArray(productsData) ? productsData : productsData?.results || [];
      prodList.forEach((p: any) => {
        (p.variants || []).forEach((v: any) => {
          allVariants.push({
            ...v,
            productName: p.name,
            retail_price: Number(v.retail_price || 0),
          });
        });
      });
      setVariants(allVariants);

      setProformas(proformasData || []);
      setB2bClients(clientsData || []);

      if (terminalsData && terminalsData.length > 0) {
        setSelectedTerminalId(terminalsData[0].id);
      }
    } catch (err) {
      console.error('Error loading POS data:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleOpenSession() {
    if (!selectedTerminalId) return;
    try {
      const newSession = await api.createPOSSession({
        terminal: selectedTerminalId,
        opening_cash: Number(openingCash) || 0,
      });
      setActiveSession(newSession);
      setShowSessionModal(false);
      await loadData();
    } catch (err: any) {
      alert(`خطا در گشایش شیفت: ${err.message}`);
    }
  }

  async function handleCloseSession() {
    if (!activeSession) return;
    const cashStr = prompt('موجودی نقدی شمارش‌شده صندوق را وارد کنید (تومان):', String(activeSession.opening_cash));
    if (cashStr === null) return;

    try {
      await api.closePOSSession(activeSession.id, {
        closing_cash: Number(cashStr) || 0,
        notes: 'بستن شیفت صندوق توسط کاربر',
      });
      setActiveSession(null);
      await loadData();
    } catch (err: any) {
      alert(`خطا در بستن شیفت: ${err.message}`);
    }
  }

  function addToCart(variant: any) {
    const existingIndex = cart.findIndex((item) => item.variant.id === variant.id);
    if (existingIndex > -1) {
      const nextCart = [...cart];
      nextCart[existingIndex].quantity += 1;
      setCart(nextCart);
    } else {
      setCart([...cart, { variant, quantity: 1, unit_price: variant.retail_price }]);
    }
  }

  function updateQuantity(variantId: string, delta: number) {
    const nextCart = cart
      .map((item) => {
        if (item.variant.id === variantId) {
          const newQty = item.quantity + delta;
          return newQty > 0 ? { ...item, quantity: newQty } : null;
        }
        return item;
      })
      .filter(Boolean) as { variant: any; quantity: number; unit_price: number }[];
    setCart(nextCart);
  }

  function removeFromCart(variantId: string) {
    setCart(cart.filter((item) => item.variant.id !== variantId));
  }

  const subtotal = cart.reduce((sum, item) => sum + item.unit_price * item.quantity, 0);

  async function handleCheckout() {
    if (!activeSession) {
      alert('ابتدا باید یک شیفت صندوقداری باز کنید.');
      return;
    }
    if (cart.length === 0) {
      alert('سبد خرید صندوق خالی است.');
      return;
    }

    setCheckoutLoading(true);
    try {
      const res = await api.posQuickCheckout({
        session_id: activeSession.id,
        items: cart.map((i) => ({
          variant_id: i.variant.id,
          quantity: i.quantity,
          unit_price: i.unit_price,
        })),
        customer_phone: customerPhone,
        customer_name: customerName,
        payment_method: paymentMethod,
      });

      setLastReceipt({
        ...res,
        items: [...cart],
        date: new Date().toLocaleDateString('fa-IR'),
        time: new Date().toLocaleTimeString('fa-IR'),
        terminal: activeSession.terminal_name,
      });
      setCart([]);
      await loadData();
    } catch (err: any) {
      alert(`خطا در ثبت فروش: ${err.message}`);
    } finally {
      setCheckoutLoading(false);
    }
  }

  async function handleConvertProforma(id: string) {
    if (!confirm('آیا مایل به تبدیل این پیش‌فاکتور به سفارش قطعی و رزرو موجودی هستید؟')) return;
    try {
      const res = await api.convertProformaToOrder(id);
      alert(`سفارش ${res.order_number} صادر و موجودی کالاها رزرو گردید.`);
      await loadData();
    } catch (err: any) {
      alert(`خطا در تبدیل پیش‌فاکتور: ${err.message}`);
    }
  }

  const filteredVariants = variants.filter(
    (v) =>
      v.sku?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      v.barcode?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      v.productName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      v.name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#0b101d]/90 border border-white/[0.08] p-5 rounded-3xl backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Store className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              صندوق فروشگاهی حضوری (POS) و عمده‌فروشی B2B
              <span className="text-xs font-normal px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                تسویه بلادرنگ
              </span>
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              ثبت فاکتور سریع، کسر آنی از انبار فروشگاه، تسویه درگاه کارتخوان و مدیریت پیش‌فاکتورهای همکار
            </p>
          </div>
        </div>

        {/* Shift Badge & Actions */}
        <div className="flex items-center gap-3">
          {activeSession ? (
            <div className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/20 px-4 py-2.5 rounded-2xl">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              <div className="text-right">
                <div className="text-xs font-semibold text-emerald-300">
                  شیفت باز: {activeSession.terminal_name}
                </div>
                <div className="text-[11px] text-slate-400">
                  فروش شیفت: {Number(activeSession.total_sales || 0).toLocaleString('fa-IR')} تومان
                </div>
              </div>
              <button
                onClick={handleCloseSession}
                className="text-xs bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 px-3 py-1.5 rounded-xl transition-all"
              >
                بستن شیفت
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowSessionModal(true)}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2.5 rounded-2xl shadow-lg shadow-blue-600/30 transition-all"
            >
              <Clock className="w-4 h-4" />
              گشایش شیفت صندوق
            </button>
          )}

          <button
            onClick={loadData}
            title="بروزرسانی اطلاعات"
            className="w-10 h-10 rounded-2xl bg-white/[0.04] border border-white/[0.08] hover:bg-white/[0.08] text-slate-400 hover:text-white flex items-center justify-center transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-white/[0.08] pb-2">
        <button
          onClick={() => setActiveTab('pos')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            activeTab === 'pos'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
              : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
          }`}
        >
          <ShoppingCart className="w-4 h-4" />
          میز صندوقداری حضوری
        </button>
        <button
          onClick={() => setActiveTab('proformas')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            activeTab === 'proformas'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
              : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
          }`}
        >
          <FileText className="w-4 h-4" />
          پیش‌فاکتورهای رسمی B2B ({proformas.length})
        </button>
        <button
          onClick={() => setActiveTab('b2b')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            activeTab === 'b2b'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
              : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
          }`}
        >
          <Building2 className="w-4 h-4" />
          حساب همکاران عمده و سقف اعتبار ({b2bClients.length})
        </button>
      </div>

      {activeTab === 'pos' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Product Catalog & Search Column (7 Cols) */}
          <div className="lg:col-span-7 space-y-4">
            {/* Search Input */}
            <div className="relative">
              <Search className="w-5 h-5 absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="جستجو با نام کالا، بارکد خوان یا شناسه SKU..."
                className="w-full bg-[#0b101d]/90 border border-white/[0.08] focus:border-blue-500 rounded-2xl pr-12 pl-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition-all"
              />
            </div>

            {/* Grid of Variants */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 max-h-[600px] overflow-y-auto pr-1">
              {filteredVariants.map((v) => (
                <div
                  key={v.id}
                  onClick={() => addToCart(v)}
                  className="bg-[#0b101d]/80 hover:bg-[#131b2e] border border-white/[0.06] hover:border-blue-500/40 p-4 rounded-2xl cursor-pointer transition-all flex flex-col justify-between group"
                >
                  <div>
                    <div className="text-[11px] text-blue-400 font-mono tracking-wider">{v.sku}</div>
                    <div className="text-sm font-semibold text-white mt-1 group-hover:text-blue-300 transition-colors">
                      {v.productName}
                    </div>
                    {v.name && <div className="text-xs text-slate-400 mt-0.5">{v.name}</div>}
                  </div>
                  <div className="mt-3 pt-3 border-t border-white/[0.04] flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-400">
                      {Number(v.retail_price).toLocaleString('fa-IR')} ت
                    </span>
                    <button className="w-7 h-7 rounded-lg bg-blue-600/20 group-hover:bg-blue-600 text-blue-400 group-hover:text-white flex items-center justify-center transition-all">
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
              {filteredVariants.length === 0 && (
                <div className="col-span-full py-12 text-center text-slate-500 text-xs">
                  کالایی با این مشخصات یافت نشد.
                </div>
              )}
            </div>
          </div>

          {/* Active Register Cart (5 Cols) */}
          <div className="lg:col-span-5 bg-[#0b101d]/90 border border-white/[0.08] rounded-3xl p-5 backdrop-blur-xl flex flex-col justify-between h-[650px]">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <ShoppingCart className="w-4 h-4 text-blue-400" />
                  سبد خرید صندوق ({cart.length} ردیف)
                </h3>
                {cart.length > 0 && (
                  <button
                    onClick={() => setCart([])}
                    className="text-[11px] text-slate-400 hover:text-red-400 transition-colors"
                  >
                    خالی کردن سبد
                  </button>
                )}
              </div>

              {/* Cart Items List */}
              <div className="space-y-2 mt-3 max-h-[300px] overflow-y-auto pr-1">
                {cart.map((item) => (
                  <div
                    key={item.variant.id}
                    className="bg-white/[0.02] border border-white/[0.04] p-3 rounded-2xl flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-white truncate">
                        {item.variant.productName} - {item.variant.name || item.variant.sku}
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        {Number(item.unit_price).toLocaleString('fa-IR')} ت × {item.quantity} ={' '}
                        <span className="text-emerald-400 font-semibold">
                          {(item.unit_price * item.quantity).toLocaleString('fa-IR')} ت
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => updateQuantity(item.variant.id, -1)}
                        className="w-6 h-6 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-slate-300 flex items-center justify-center transition-all"
                      >
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="text-xs font-bold text-white w-5 text-center">{item.quantity}</span>
                      <button
                        onClick={() => updateQuantity(item.variant.id, 1)}
                        className="w-6 h-6 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-slate-300 flex items-center justify-center transition-all"
                      >
                        <Plus className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => removeFromCart(item.variant.id)}
                        className="text-slate-500 hover:text-red-400 ml-1 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
                {cart.length === 0 && (
                  <div className="py-12 text-center text-slate-500 text-xs">
                    سبد خرید خالی است. کالاها را از ستون روبرو انتخاب کنید.
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Checkout Controls */}
            <div className="pt-4 border-t border-white/[0.06] space-y-3">
              {/* Customer Inputs */}
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder="موبایل خریدار"
                  value={customerPhone}
                  onChange={(e) => setCustomerPhone(e.target.value)}
                  className="bg-black/30 border border-white/[0.08] text-xs text-white p-2 rounded-xl outline-none"
                />
                <input
                  type="text"
                  placeholder="نام خریدار"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  className="bg-black/30 border border-white/[0.08] text-xs text-white p-2 rounded-xl outline-none"
                />
              </div>

              {/* Payment Method Toggle */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setPaymentMethod('POS_TERMINAL')}
                  className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-xs font-semibold border transition-all ${
                    paymentMethod === 'POS_TERMINAL'
                      ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                      : 'bg-white/[0.02] border-white/[0.06] text-slate-400'
                  }`}
                >
                  <CreditCard className="w-3.5 h-3.5" />
                  کارتخوان (POS)
                </button>
                <button
                  type="button"
                  onClick={() => setPaymentMethod('CASH_ON_DELIVERY')}
                  className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-xs font-semibold border transition-all ${
                    paymentMethod === 'CASH_ON_DELIVERY'
                      ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                      : 'bg-white/[0.02] border-white/[0.06] text-slate-400'
                  }`}
                >
                  <Banknote className="w-3.5 h-3.5" />
                  وجه نقد
                </button>
              </div>

              {/* Total & Checkout Button */}
              <div className="flex items-center justify-between pt-2">
                <span className="text-xs text-slate-400">مبلغ قابل پرداخت:</span>
                <span className="text-lg font-black text-emerald-400">
                  {subtotal.toLocaleString('fa-IR')} تومان
                </span>
              </div>

              <button
                onClick={handleCheckout}
                disabled={checkoutLoading || cart.length === 0}
                className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white py-3.5 rounded-2xl text-xs font-bold shadow-lg shadow-emerald-600/30 transition-all flex items-center justify-center gap-2"
              >
                <CheckCircle2 className="w-4 h-4" />
                {checkoutLoading ? 'در حال ثبت فاکتور...' : 'ثبت فروش حضوری و صدور فاکتور'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Proformas Tab */}
      {activeTab === 'proformas' && (
        <div className="bg-[#0b101d]/90 border border-white/[0.08] rounded-3xl p-6 backdrop-blur-xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white">لیست پیش‌فاکتورهای صادرشده برای همکاران B2B</h3>
            <span className="text-xs text-slate-400">
              تبدیل هر پیش‌فاکتور به‌صورت خودکار موجودی انبار را رزرو کرده و سند طلب نسیه ایجاد می‌کند.
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="border-b border-white/[0.06] text-slate-400">
                  <th className="py-3 px-4">شماره پیش‌فاکتور</th>
                  <th className="py-3 px-4">شرکت / همکار</th>
                  <th className="py-3 px-4">مبلغ کل</th>
                  <th className="py-3 px-4">مهلت اعتبار</th>
                  <th className="py-3 px-4">وضعیت</th>
                  <th className="py-3 px-4 text-left">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {proformas.map((p) => (
                  <tr key={p.id} className="hover:bg-white/[0.02]">
                    <td className="py-3 px-4 font-mono text-blue-400">{p.invoice_number}</td>
                    <td className="py-3 px-4 font-semibold text-white">{p.client_name}</td>
                    <td className="py-3 px-4 text-emerald-400 font-bold">
                      {Number(p.grand_total).toLocaleString('fa-IR')} تومان
                    </td>
                    <td className="py-3 px-4 text-slate-400">{p.valid_until ? p.valid_until.slice(0, 10) : '-'}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 text-[11px]">
                        {p.status_display}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-left">
                      {p.status !== 'CONVERTED' && (
                        <button
                          onClick={() => handleConvertProforma(p.id)}
                          className="bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 px-3 py-1.5 rounded-xl transition-all"
                        >
                          تبدیل به سفارش قطعی
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {proformas.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500">
                      هیچ پیش‌فاکتوری ثبت نشده است.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* B2B Clients Tab */}
      {activeTab === 'b2b' && (
        <div className="bg-[#0b101d]/90 border border-white/[0.08] rounded-3xl p-6 backdrop-blur-xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white">پروفایل و سقف اعتبار خریداران عمده و سازمانی</h3>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="border-b border-white/[0.06] text-slate-400">
                  <th className="py-3 px-4">نام شرکت / فروشگاه</th>
                  <th className="py-3 px-4">شماره تماس</th>
                  <th className="py-3 px-4">سطح همکاری</th>
                  <th className="py-3 px-4">سقف اعتبار</th>
                  <th className="py-3 px-4">بدهی جاری</th>
                  <th className="py-3 px-4">اعتبار باقیمانده</th>
                  <th className="py-3 px-4">مهلت تسویه (روز)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {b2bClients.map((c) => (
                  <tr key={c.id} className="hover:bg-white/[0.02]">
                    <td className="py-3 px-4 font-semibold text-white">{c.company_name}</td>
                    <td className="py-3 px-4 font-mono text-slate-300">{c.customer_phone}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[11px]">
                        {c.tier_display}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      {Number(c.credit_limit).toLocaleString('fa-IR')} تومان
                    </td>
                    <td className="py-3 px-4 text-red-400">
                      {Number(c.current_debt).toLocaleString('fa-IR')} تومان
                    </td>
                    <td className="py-3 px-4 text-emerald-400 font-bold">
                      {Number(c.available_credit).toLocaleString('fa-IR')} تومان
                    </td>
                    <td className="py-3 px-4 text-slate-400">{c.payment_terms_days} روز</td>
                  </tr>
                ))}
                {b2bClients.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-slate-500">
                      هیچ پروفایل همکار عمده‌ای ثبت نشده است.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Instant Receipt Modal */}
      {lastReceipt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-[#0b101d] border border-white/[0.1] rounded-3xl max-w-sm w-full p-6 text-right space-y-4 shadow-2xl relative">
            <button
              onClick={() => setLastReceipt(null)}
              className="absolute left-4 top-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="text-center pb-3 border-b border-white/[0.06]">
              <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center mb-2">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h4 className="text-base font-bold text-white">رسید فروش و فاکتور صندوق</h4>
              <p className="text-xs text-slate-400 mt-1">شماره فاکتور: {lastReceipt.order_number}</p>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>صندوق:</span>
                <span className="text-white">{lastReceipt.terminal}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>زمان:</span>
                <span className="text-white">{lastReceipt.date} - {lastReceipt.time}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>روش پرداخت:</span>
                <span className="text-emerald-400 font-semibold">تأییدشده و تسویه کامل</span>
              </div>
              <div className="flex justify-between text-slate-400 pt-2 border-t border-white/[0.06]">
                <span className="font-bold text-white">مبلغ کل:</span>
                <span className="text-base font-black text-emerald-400">
                  {Number(lastReceipt.grand_total).toLocaleString('fa-IR')} تومان
                </span>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => window.print()}
                className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold py-2.5 rounded-xl flex items-center justify-center gap-2 transition-all"
              >
                <Printer className="w-4 h-4" />
                چاپ رسید فیش‌پرینتر
              </button>
              <button
                onClick={() => setLastReceipt(null)}
                className="bg-white/[0.06] hover:bg-white/[0.1] text-slate-300 text-xs px-4 py-2.5 rounded-xl transition-all"
              >
                بستن
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Open Session Modal */}
      {showSessionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-[#0b101d] border border-white/[0.1] rounded-3xl max-w-sm w-full p-6 text-right space-y-4 shadow-2xl relative">
            <button
              onClick={() => setShowSessionModal(false)}
              className="absolute left-4 top-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
            <h4 className="text-sm font-bold text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-400" />
              گشایش شیفت صندوقداری جدید
            </h4>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400 block mb-1">انتخاب پایانه صندوق:</label>
                <select
                  value={selectedTerminalId}
                  onChange={(e) => setSelectedTerminalId(e.target.value)}
                  className="w-full bg-black/40 border border-white/[0.08] text-white p-2.5 rounded-xl outline-none"
                >
                  {terminals.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.terminal_code})
                    </option>
                  ))}
                  {terminals.length === 0 && <option value="">پایانه‌ای ثبت نشده است</option>}
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">موجودی نقدی تنخواه آغازین (تومان):</label>
                <input
                  type="number"
                  value={openingCash}
                  onChange={(e) => setOpeningCash(e.target.value)}
                  className="w-full bg-black/40 border border-white/[0.08] text-white p-2.5 rounded-xl outline-none font-mono"
                />
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={handleOpenSession}
                className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold py-2.5 rounded-xl transition-all"
              >
                تأیید و آغاز شیفت
              </button>
              <button
                onClick={() => setShowSessionModal(false)}
                className="bg-white/[0.06] hover:bg-white/[0.1] text-slate-300 text-xs px-4 py-2.5 rounded-xl transition-all"
              >
                انصراف
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
