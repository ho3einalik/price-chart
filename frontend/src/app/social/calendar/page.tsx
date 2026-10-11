'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
  Calendar as CalendarIcon,
  Plus,
  Clock,
  Instagram,
  Send,
  Film,
  Image,
  Layers,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  X
} from 'lucide-react';

interface SocialContent {
  id: string;
  account: string | null;
  platform: string | null;
  platform_display: string | null;
  account_handle: string | null;
  content_type: 'POST' | 'REEL' | 'STORY' | 'CAROUSEL' | 'TELEGRAM_POST';
  content_type_display: string;
  title: string;
  caption: string;
  hashtags: string;
  thumbnail_url: string;
  status: 'IDEA' | 'IN_PRODUCTION' | 'READY_FOR_REVIEW' | 'APPROVED' | 'SCHEDULED' | 'PUBLISHED' | 'REJECTED';
  status_display: string;
  scheduled_at: string | null;
  published_at: string | null;
  published_url: string;
  latest_metrics: any;
}

export default function SocialCalendarPage() {
  const [contents, setContents] = useState<SocialContent[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentDate, setCurrentDate] = useState(new Date());

  // Quick schedule modal
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [modalDate, setModalDate] = useState('');
  const [formTitle, setFormTitle] = useState('');
  const [formCaption, setFormCaption] = useState('');
  const [formAccount, setFormAccount] = useState('');
  const [formCampaign, setFormCampaign] = useState('');
  const [formContentType, setFormContentType] = useState('REEL');
  const [formThumbnail, setFormThumbnail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [contentData, accountsData, campaignsData] = await Promise.all([
        api.getSocialContent(),
        api.getSocialAccounts(),
        api.getSocialCampaigns(),
      ]);
      setContents(Array.isArray(contentData) ? contentData : (contentData as any).results || []);
      setAccounts(Array.isArray(accountsData) ? accountsData : (accountsData as any).results || []);
      setCampaigns(Array.isArray(campaignsData) ? campaignsData : (campaignsData as any).results || []);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Generate 28 or 35 days for grid
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const firstDayOfMonth = new Date(year, month, 1);
  const lastDayOfMonth = new Date(year, month + 1, 0);

  // Persian week starts Saturday (index 6 in JS Sun=0..Sat=6)
  // Let's compute day cells for the calendar
  const daysInMonth = lastDayOfMonth.getDate();
  const calendarDays = [];

  for (let day = 1; day <= daysInMonth; day++) {
    const d = new Date(year, month, day);
    const dateStr = d.toISOString().slice(0, 10);
    const dayItems = contents.filter((c) => c.scheduled_at && c.scheduled_at.startsWith(dateStr));
    calendarDays.push({
      date: d,
      dateStr,
      dayNumber: day,
      items: dayItems,
      isToday: new Date().toISOString().slice(0, 10) === dateStr,
    });
  }

  const handleOpenScheduleForDate = (dateStr: string) => {
    setModalDate(dateStr);
    setShowScheduleModal(true);
  };

  const handleCreateContent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTitle.trim()) return;

    setIsSubmitting(true);
    try {
      const scheduledDateTime = modalDate ? `${modalDate}T18:00:00Z` : null;
      await api.createSocialContent({
        title: formTitle.trim(),
        caption: formCaption.trim(),
        account: formAccount || (accounts[0]?.id ?? null),
        campaign: formCampaign || null,
        content_type: formContentType,
        thumbnail_url: formThumbnail.trim(),
        scheduled_at: scheduledDateTime,
        status: scheduledDateTime ? 'SCHEDULED' : 'IDEA',
      });
      setShowScheduleModal(false);
      setFormTitle('');
      setFormCaption('');
      setFormThumbnail('');
      loadData();
    } catch (err: any) {
      alert(err.message || 'خطا در ثبت محتوا');
    } finally {
      setIsSubmitting(false);
    }
  };

  const getContentTypeIcon = (type: string) => {
    switch (type) {
      case 'REEL':
        return <Film className="w-3.5 h-3.5 text-pink-600" />;
      case 'CAROUSEL':
        return <Layers className="w-3.5 h-3.5 text-indigo-600" />;
      case 'STORY':
        return <Clock className="w-3.5 h-3.5 text-amber-600" />;
      default:
        return <Image className="w-3.5 h-3.5 text-sky-600" />;
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-800 flex items-center gap-3">
            <CalendarIcon className="w-7 h-7 text-pink-600" />
            تقویم محتوا و برنامه‌ریزی انتشار
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            برنامه‌ریزی منظم ریلزها، استوری‌ها و پست‌های اینستاگرام با تاییدیه‌های قبل از انتشار
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 bg-white border border-slate-200 p-1 rounded-xl shadow-2xs">
            <button
              onClick={() => setCurrentDate(new Date(year, month - 1, 1))}
              className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-600"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <span className="px-3 text-xs font-bold text-slate-800">
              {currentDate.toLocaleDateString('fa-IR', { month: 'long', year: 'numeric' })}
            </span>
            <button
              onClick={() => setCurrentDate(new Date(year, month + 1, 1))}
              className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-600"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          </div>
          <button
            onClick={() => handleOpenScheduleForDate(new Date().toISOString().slice(0, 10))}
            className="flex items-center gap-2 bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-700 hover:to-purple-700 text-white px-4 py-2.5 rounded-xl font-medium shadow-sm transition-all text-sm"
          >
            <Plus className="w-4 h-4" />
            <span>زمان‌بندی محتوای جدید</span>
          </button>
        </div>
      </div>

      {/* Connected Channels Summary Bar */}
      <div className="flex flex-wrap items-center gap-3">
        {accounts.map((acc) => (
          <div
            key={acc.id}
            className="flex items-center gap-2.5 bg-white border border-slate-200 px-3.5 py-2 rounded-xl text-xs shadow-2xs"
          >
            {acc.platform === 'INSTAGRAM' ? (
              <Instagram className="w-4 h-4 text-pink-600" />
            ) : (
              <Send className="w-4 h-4 text-sky-500" />
            )}
            <span className="font-bold text-slate-800">{acc.handle}</span>
            <span className="text-[11px] text-slate-400">
              ({acc.follower_count?.toLocaleString('fa-IR')} دنبال‌کننده)
            </span>
          </div>
        ))}
      </div>

      {/* Calendar Grid */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
        {/* Days of week header */}
        <div className="grid grid-cols-7 text-center py-2.5 bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-600">
          <div>شنبه</div>
          <div>یکشنبه</div>
          <div>دوشنبه</div>
          <div>سه‌شنبه</div>
          <div>چهارشنبه</div>
          <div>پنجشنبه</div>
          <div>جمعه</div>
        </div>

        {/* Days Grid */}
        <div className="grid grid-cols-7 divide-x divide-y divide-slate-100 min-h-[600px]">
          {calendarDays.map((calDay) => (
            <div
              key={calDay.dateStr}
              onClick={() => handleOpenScheduleForDate(calDay.dateStr)}
              className={`p-2 flex flex-col justify-between hover:bg-slate-50/80 transition-colors cursor-pointer group min-h-[120px] ${
                calDay.isToday ? 'bg-pink-50/30' : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <span
                  className={`text-xs font-bold w-6 h-6 rounded-full flex items-center justify-center ${
                    calDay.isToday ? 'bg-pink-600 text-white shadow-2xs' : 'text-slate-700'
                  }`}
                >
                  {calDay.dayNumber}
                </span>
                <button className="opacity-0 group-hover:opacity-100 text-[10px] text-pink-600 font-bold transition-opacity">
                  + زمان‌بندی
                </button>
              </div>

              {/* Items on this day */}
              <div className="mt-2 space-y-1.5 flex-1">
                {calDay.items.map((item) => (
                  <div
                    key={item.id}
                    onClick={(e) => {
                      e.stopPropagation();
                    }}
                    className={`p-1.5 rounded-lg border text-[11px] shadow-2xs flex items-start gap-1.5 ${
                      item.status === 'PUBLISHED'
                        ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                        : item.status === 'SCHEDULED'
                        ? 'bg-purple-50 border-purple-200 text-purple-900'
                        : 'bg-white border-slate-200 text-slate-800'
                    }`}
                  >
                    <div className="mt-0.5 shrink-0">{getContentTypeIcon(item.content_type)}</div>
                    <div className="truncate flex-1">
                      <p className="font-bold truncate leading-tight">{item.title}</p>
                      <span className="text-[9px] text-slate-500 block mt-0.5">
                        {item.account_handle} • {item.content_type_display}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Schedule Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 animate-scaleIn border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2">
                <CalendarIcon className="w-5 h-5 text-pink-600" />
                زمان‌بندی انتشار محتوا
              </h3>
              <button onClick={() => setShowScheduleModal(false)} className="text-slate-400 hover:text-slate-600 p-1">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateContent} className="mt-5 space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">موضوع یا عنوان محتوا *</label>
                <input
                  type="text"
                  required
                  placeholder="مثلاً: ریلز معرفی مانتو کتی ژاکارد..."
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-pink-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">اکانت انتشار</label>
                  <select
                    value={formAccount}
                    onChange={(e) => setFormAccount(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 bg-white focus:outline-none"
                  >
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.platform_display} - {a.handle}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">قالب محتوا</label>
                  <select
                    value={formContentType}
                    onChange={(e) => setFormContentType(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 bg-white focus:outline-none"
                  >
                    <option value="REEL">ریلز (Reels)</option>
                    <option value="POST">پست تک‌اسلایدی</option>
                    <option value="CAROUSEL">پست ورق‌زدنی (Carousel)</option>
                    <option value="STORY">استوری (Story)</option>
                    <option value="TELEGRAM_POST">پست تلگرام</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">متن کپشن یا پیام</label>
                <textarea
                  rows={3}
                  placeholder="کپشن جذاب، هشتگ‌ها و کال‌تواکشن دایرکت..."
                  value={formCaption}
                  onChange={(e) => setFormCaption(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-pink-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">تاریخ انتشار</label>
                  <input
                    type="date"
                    value={modalDate}
                    onChange={(e) => setModalDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 bg-white focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">آدرس کاور / پیش‌نمایش</label>
                  <input
                    type="url"
                    placeholder="https://..."
                    value={formThumbnail}
                    onChange={(e) => setFormThumbnail(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowScheduleModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 font-medium"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-xl font-bold bg-pink-600 hover:bg-pink-700 text-white shadow-sm"
                >
                  {isSubmitting ? 'در حال ثبت...' : 'ثبت در تقویم'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
