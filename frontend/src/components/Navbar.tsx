'use client';

import React from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useStore } from '@/contexts/StoreContext';
import { Store, User, LogOut, Bell, ChevronDown } from 'lucide-react';

export function Navbar() {
  const { user, logout } = useAuth();
  const { stores, activeStore, switchStore } = useStore();

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between sticky top-0 z-30 shadow-sm">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 text-sky-600 font-extrabold text-xl tracking-tight">
          <div className="w-8 h-8 rounded-lg bg-sky-600 text-white flex items-center justify-center font-black text-lg">
            S
          </div>
          <span>شاپ‌پایلوت</span>
          <span className="text-xs bg-sky-100 text-sky-700 font-medium px-2 py-0.5 rounded-full mr-1">
            نسخه آزمایشی
          </span>
        </div>

        {/* Store Switcher */}
        {stores.length > 0 && (
          <div className="relative flex items-center">
            <Store className="w-4 h-4 text-slate-400 ml-2" />
            <select
              value={activeStore?.id || ''}
              onChange={(e) => switchStore(e.target.value)}
              className="bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-lg focus:ring-sky-500 focus:border-sky-500 block py-1.5 px-3 pr-2 font-medium cursor-pointer"
            >
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.currency === 'IRT' ? 'تومان' : 'ریال'})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {user ? (
          <div className="flex items-center gap-4">
            <div className="text-left hidden sm:block">
              <div className="text-sm font-semibold text-slate-800">{user.full_name}</div>
              <div className="text-xs text-slate-500">{user.email || user.phone_number}</div>
            </div>
            <button
              onClick={logout}
              title="خروج از حساب کاربری"
              className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        ) : (
          <a
            href="/login"
            className="text-sm font-medium text-white bg-sky-600 hover:bg-sky-700 px-4 py-2 rounded-lg transition-colors"
          >
            ورود به سیستم
          </a>
        )}
      </div>
    </header>
  );
}
