'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useStore } from '@/contexts/StoreContext';
import { Store, User, LogOut, Bell, ChevronDown, Sparkles, Check, CheckCheck, X } from 'lucide-react';
import { api } from '@/lib/api';

export function Navbar() {
  const { user, logout } = useAuth();
  const { stores, activeStore, switchStore } = useStore();

  const [notifications, setNotifications] = useState<any[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);

  useEffect(() => {
    if (user && activeStore) {
      loadNotifications();
    }
  }, [user, activeStore]);

  const loadNotifications = async () => {
    try {
      const data = await api.getNotifications(false);
      const list = Array.isArray(data) ? data : (data as any)?.results || [];
      setNotifications(list);
    } catch {
      // silent fallback
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      setNotifications([]);
    } catch (err) {
      console.error(err);
    }
  };

  const handleMarkRead = async (id: string) => {
    try {
      await api.markNotificationRead(id);
      setNotifications(notifications.filter((n) => n.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <header className="h-16 bg-[#080c17]/75 backdrop-blur-xl border-b border-white/[0.06] px-6 flex items-center justify-between sticky top-0 z-30 shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
      {/* Brand & Store Selector */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-cyan-400 text-white flex items-center justify-center font-black text-base shadow-[0_0_15px_rgba(56,189,248,0.5)]">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-base tracking-tight text-white flex items-center gap-2">
            شاپ‌پایلوت
            <span className="text-[10px] font-semibold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-2 py-0.5 rounded-full">
              هوشمند
            </span>
          </span>
        </div>

        {/* Store Switcher */}
        {stores.length > 0 && (
          <div className="relative flex items-center bg-white/[0.03] border border-white/[0.08] hover:border-white/20 transition-all rounded-xl px-3 py-1.5">
            <Store className="w-4 h-4 text-cyan-400 ml-2" />
            <select
              value={activeStore?.id || ''}
              onChange={(e) => switchStore(e.target.value)}
              className="bg-transparent text-slate-200 text-xs font-medium cursor-pointer focus:outline-none appearance-none pr-1 pl-4"
            >
              {stores.map((s) => (
                <option key={s.id} value={s.id} className="bg-[#0b101d] text-slate-200">
                  {s.name} ({s.currency === 'IRT' ? 'تومان' : 'ریال'})
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 pointer-events-none absolute left-2.5" />
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4">
        {/* Live operational badge */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span>سامانه فعال</span>
        </div>

        {/* Notification Bell */}
        {user && (
          <div className="relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              title="اعلان‌های سیستم"
              className="relative p-2 text-slate-400 hover:text-white hover:bg-white/[0.06] rounded-xl border border-white/[0.05] transition-all cursor-pointer"
            >
              <Bell className="w-4 h-4" />
              {notifications.length > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 text-[10px] font-bold text-white flex items-center justify-center">
                  {notifications.length}
                </span>
              )}
            </button>

            {/* Notification Dropdown */}
            {showNotifications && (
              <div className="absolute left-0 mt-3 w-80 bg-[#0b101d] border border-white/[0.1] rounded-2xl shadow-2xl p-4 z-50 text-right space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                  <span className="text-xs font-bold text-white">اعلان‌های درون‌برنامه‌ای</span>
                  {notifications.length > 0 && (
                    <button
                      onClick={handleMarkAllRead}
                      className="text-[11px] text-blue-400 hover:text-blue-300 flex items-center gap-1 cursor-pointer"
                    >
                      <CheckCheck className="w-3 h-3" />
                      خوانده شدن همه
                    </button>
                  )}
                </div>

                <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                  {notifications.map((n) => (
                    <div
                      key={n.id}
                      onClick={() => handleMarkRead(n.id)}
                      className="p-2.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.04] cursor-pointer transition-all space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-white">{n.title}</span>
                        <span className="text-[10px] text-slate-400">{n.category_display}</span>
                      </div>
                      <p className="text-[11px] text-slate-300 leading-relaxed">{n.message}</p>
                    </div>
                  ))}
                  {notifications.length === 0 && (
                    <div className="py-6 text-center text-xs text-slate-500">
                      اعلان خوانده‌نشده‌ای وجود ندارد.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {user ? (
          <div className="flex items-center gap-3">
            <div className="text-left hidden sm:block">
              <div className="text-xs font-semibold text-slate-200">{user.full_name}</div>
              <div className="text-[10px] text-slate-400">{user.email || user.phone_number}</div>
            </div>
            <button
              onClick={logout}
              title="خروج از حساب"
              className="p-2 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-xl border border-white/[0.05] hover:border-rose-500/20 transition-all cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <a
            href="/login"
            className="text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-xl shadow-[0_0_15px_rgba(37,99,235,0.4)] transition-all"
          >
            ورود به سیستم
          </a>
        )}
      </div>
    </header>
  );
}
