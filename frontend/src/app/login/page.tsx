'use client';

import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { LogIn, UserPlus, Key, Mail, Building, ArrowLeft } from 'lucide-react';

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Form states
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [businessName, setBusinessName] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        await register({
          email: email.trim(),
          full_name: fullName.trim(),
          password,
          business_name: businessName.trim(),
        });
      } else {
        await login({
          email: email.trim(),
          password,
        });
      }
      router.push('/');
    } catch (err: any) {
      setError(err.message || 'خطا در احراز هویت. اطلاعات ورودی را بررسی نمایید.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setError('');
    setLoading(true);
    try {
      await login({
        email: 'demo@shoppilot.io',
        password: 'password123',
      });
      router.push('/');
    } catch (err: any) {
      setError(err.message || 'خطا در ورود به حساب دمو');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full bg-white p-8 rounded-3xl border border-slate-200 shadow-xl space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-sky-600 text-white items-center justify-center font-black text-2xl shadow-md shadow-sky-600/30">
            S
          </div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">
            {isRegister ? 'ثبت‌نام فروشگاه جدید در شاپ‌پایلوت' : 'ورود به پنل مدیریت شاپ‌پایلوت'}
          </h2>
          <p className="text-xs text-slate-500">
            {isRegister
              ? 'اطلاعات فروشگاه خود را وارد کنید تا حساب اختصاصی شما ساخته شود'
              : 'برای دسترسی به داشبورد و مدیریت چندکاناله وارد شوید'}
          </p>
        </div>

        {error && (
          <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl font-medium">
            {error}
          </div>
        )}

        {/* Demo Fast Login Pill */}
        {!isRegister && (
          <div className="bg-sky-50 border border-sky-100 p-3 rounded-xl flex items-center justify-between">
            <div className="text-xs text-sky-900 font-medium">حساب نمایشی (Demo Account) آماده است</div>
            <button
              type="button"
              onClick={handleDemoLogin}
              disabled={loading}
              className="text-xs font-bold bg-sky-600 hover:bg-sky-700 text-white px-3 py-1.5 rounded-lg transition shadow-sm"
            >
              ورود سریع دمو
            </button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegister && (
            <>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">نام و نام خانوادگی</label>
                <div className="relative">
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="مثال: علی احمدی"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-sky-500 focus:bg-white outline-none transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">نام کسب‌وکار یا برند</label>
                <div className="relative">
                  <input
                    type="text"
                    required
                    value={businessName}
                    onChange={(e) => setBusinessName(e.target.value)}
                    placeholder="مثال: برند پوشاک شیک‌پوش"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-sky-500 focus:bg-white outline-none transition"
                  />
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">ایمیل یا نام کاربری</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@domain.com"
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-sky-500 focus:bg-white outline-none transition"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">رمز عبور</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="حداقل ۸ کاراکتر"
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-sky-500 focus:bg-white outline-none transition"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-slate-900 hover:bg-slate-800 text-white font-bold py-3 rounded-xl transition shadow-md flex items-center justify-center gap-2 text-sm mt-2 disabled:opacity-50"
          >
            {loading ? 'در حال ارسال اطلاعات...' : isRegister ? 'ایجاد حساب کاربری' : 'ورود به حساب کاربری'}
          </button>
        </form>

        <div className="pt-2 border-t border-slate-100 text-center">
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister);
              setError('');
            }}
            className="text-xs text-sky-600 hover:text-sky-700 font-semibold"
          >
            {isRegister
              ? 'قبلاً ثبت‌نام کرده‌اید؟ وارد شوید'
              : 'فروشگاه جدید دارید؟ ثبت‌نام و ساخت کسب‌وکار'}
          </button>
        </div>
      </div>
    </div>
  );
}
