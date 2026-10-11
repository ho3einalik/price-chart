'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Package,
  Boxes,
  ShoppingCart,
  CreditCard,
  Users,
  CheckSquare,
  Calendar,
  Layers,
  BarChart3
} from 'lucide-react';
import { cn } from '@/lib/utils';

const storeNavItems = [
  { href: '/', label: 'داشبورد و اقدامات', icon: LayoutDashboard },
  { href: '/products', label: 'کاتالوگ و کالاها', icon: Package },
  { href: '/inventory', label: 'موجودی و انبارها', icon: Boxes },
  { href: '/orders', label: 'مدیریت سفارشات', icon: ShoppingCart },
  { href: '/payments', label: 'تأیید فیش‌های واریزی', icon: CreditCard },
];

const teamNavItems = [
  { href: '/team', label: 'مدیریت تیم و دسترسی‌ها', icon: Users },
  { href: '/tasks', label: 'کارتابل و مدیریت وظایف', icon: CheckSquare },
];

const socialNavItems = [
  { href: '/social/calendar', label: 'تقویم محتوا و انتشار', icon: Calendar },
  { href: '/social/content', label: 'کارتابل و تأیید محتوا', icon: Layers },
  { href: '/social/analytics', label: 'آنالیز شبکه‌های اجتماعی', icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 min-h-[calc(100vh-4rem)] flex flex-col justify-between p-4 select-none shrink-0 border-l border-slate-800">
      <div className="space-y-6 overflow-y-auto">
        <div>
          <div className="px-3 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            فروشگاه و انبار
          </div>
          <nav className="space-y-1">
            {storeNavItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-xl font-medium text-xs transition-all',
                    isActive
                      ? 'bg-sky-600 text-white shadow-sm shadow-sky-900/50'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                  )}
                >
                  <Icon className={cn('w-4 h-4 shrink-0', isActive ? 'text-white' : 'text-slate-400')} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        <div>
          <div className="px-3 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            تیم و نیروی انسانی
          </div>
          <nav className="space-y-1">
            {teamNavItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-xl font-medium text-xs transition-all',
                    isActive
                      ? 'bg-sky-600 text-white shadow-sm shadow-sky-900/50'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                  )}
                >
                  <Icon className={cn('w-4 h-4 shrink-0', isActive ? 'text-white' : 'text-slate-400')} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        <div>
          <div className="px-3 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            شبکه‌های اجتماعی و محتوا
          </div>
          <nav className="space-y-1">
            {socialNavItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-xl font-medium text-xs transition-all',
                    isActive
                      ? 'bg-sky-600 text-white shadow-sm shadow-sky-900/50'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                  )}
                >
                  <Icon className={cn('w-4 h-4 shrink-0', isActive ? 'text-white' : 'text-slate-400')} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      <div className="pt-4 border-t border-slate-800 text-xs text-slate-500 text-center">
        <span>سامانه جامع عملیات شاپ‌پایلوت</span>
      </div>
    </aside>
  );
}
