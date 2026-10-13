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
  X,
  Sparkles
} from 'lucide-react';
import { cn } from '@/lib/utils';

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

  // Month calculation
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const firstDayOfMonth = new Date(year, month, 1);
  const lastDayOfMonth = new Date(year, month + 1, 0);

  // Persian week starts Saturday (in JS getDay(): Sunday=0, Monday=1, ..., Saturday=6)
  // Converting to Saturday=0, Sunday=1, ..., Friday=6
  const startOffset = (firstDayOfMonth.getDay() + 1) % 7;
  const daysInMonth = lastDayOfMonth.getDate();

  // Previous month trailing days
  const prevMonthLastDay = new Date(year, month, 0).getDate();

  interface CalCell {
    date: Date;
    dateStr: string;
    dayNumber: number;
    isCurrentMonth: boolean;
    isToday: boolean;
    items: SocialContent[];
  }

  const calendarCells: CalCell[] = [];

  // Add trailing days from previous month
  for (let i = startOffset - 1; i >= 0; i--) {
    const d = new Date(year, month - 1, prevMonthLastDay - i);
    const dateStr = d.toISOString().slice(0, 10);
    const items = contents.filter((c) => c.scheduled_at && c.scheduled_at.startsWith(dateStr));
    calendarCells.push({
      date: d,
      dateStr,
      dayNumber: prevMonthLastDay - i,
      isCurrentMonth: false,
      isToday: false,
      items,
    });
  }

  // Add current month days
  const todayStr = new Date().toISOString().slice(0, 10);
  for (let day = 1; day <= daysInMonth; day++) {
    const d = new Date(year, month, day);
    const dateStr = d.toISOString().slice(0, 10);
    const items = contents.filter((c) => c.scheduled_at && c.scheduled_at.startsWith(dateStr));
    calendarCells.push({
      date: d,
      dateStr,
      dayNumber: day,
      isCurrentMonth: true,
      isToday: dateStr === todayStr,
      items,
    });
  }

  // Fill up remaining cells to complete grid row (multiple of 7)
  const remaining = (7 - (calendarCells.length % 7)) % 7;
  for (let day = 1; day <= remaining; day++) {
    const d = new Date(year, month + 1, day);
    const dateStr = d.toISOString().slice(0, 10);
    const items = contents.filter((c) => c.scheduled_at && c.scheduled_at.startsWith(dateStr));
    calendarCells.push({
      date: d,
      dateStr,
      dayNumber: day,
      isCurrentMonth: false,
      isToday: false,
      items,
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

  const getContentTypeBadge = (type: string) => {
    switch (type) {
      case 'REEL':
        return (
          <span className="flex items-center gap-1 text-[10px] text-pink-400 font-bold bg-pink-500/15 border border-pink-500/25 px-1.5 py-0.5 rounded-md">
            <Film className="w-3 h-3" />
            <span>ریلز</span>
          </span>
        );
      case 'CAROUSEL':
        return (
          <span className="flex items-center gap-1 text-[10px] text-indigo-400 font-bold bg-indigo-500/15 border border-indigo-500/25 px-1.5 py-0.5 rounded-md">
            <Layers className="w-3 h-3" />
            <span>اسلایدی</span>
          </span>
        );
      case 'STORY':
        return (
          <span className="flex items-center gap-1 text-[10px] text-amber-400 font-bold bg-amber-500/15 border border-amber-500/25 px-1.5 py-0.5 rounded-md">
            <Clock className="w-3 h-3" />
            <span>استوری</span>
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 text-[10px] text-cyan-400 font-bold bg-cyan-500/15 border border-cyan-500/25 px-1.5 py-0.5 rounded-md">
            <Image className="w-3 h-3" />
            <span>پست</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black text-white tracking-tight">تقویم محتوا و رسانه‌ها</h1>
            <span className="w-1.5 h-1.5 rounded-full bg-pink-500 animate-pulse" />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            برنامه‌ریزی منظم ریلزها، استوری‌ها و پست‌های اینستاگرام با تاییدیه‌های انتشار
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Month selector */}
          <div className="flex items-center gap-1.5 bg-[#0e1628] border border-white/[0.08] p-1.5 rounded-2xl">
            <button
              onClick={() => setCurrentDate(new Date(year, month - 1, 1))}
              className="p-1 hover:bg-white/[0.08] rounded-xl text-slate-300 hover:text-white transition-all cursor-pointer"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <span className="px-3 text-xs font-bold text-white min-w-[100px] text-center">
              {currentDate.toLocaleDateString('fa-IR', { month: 'long', year: 'numeric' })}
            </span>
            <button
              onClick={() => setCurrentDate(new Date(year, month + 1, 1))}
              className="p-1 hover:bg-white/[0.08] rounded-xl text-slate-300 hover:text-white transition-all cursor-pointer"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          </div>

          <button
            onClick={() => handleOpenScheduleForDate(new Date().toISOString().slice(0, 10))}
            className="flex items-center gap-2 bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white px-4 py-2.5 rounded-xl font-bold shadow-[0_0_18px_rgba(236,72,153,0.4)] transition-all text-xs cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>زمان‌بندی محتوا</span>
          </button>
        </div>
      </div>

      {/* Connected Channels Summary Bar */}
      <div className="flex flex-wrap items-center gap-3">
        {accounts.map((acc) => (
          <div
            key={acc.id}
            className="flex items-center gap-2.5 glass-card px-3.5 py-2 text-xs"
          >
            {acc.platform === 'INSTAGRAM' ? (
              <Instagram className="w-4 h-4 text-pink-400" />
            ) : (
              <Send className="w-4 h-4 text-cyan-400" />
            )}
            <span className="font-bold text-white">{acc.handle}</span>
            <span className="text-[11px] text-slate-400">
              ({acc.follower_count?.toLocaleString('fa-IR')} دنبال‌کننده)
            </span>
          </div>
        ))}
      </div>

      {/* Calendar Grid Container */}
      <div className="glass-card p-4 space-y-3">
        {/* Days of week header */}
        <div className="grid grid-cols-7 gap-2.5 text-center text-xs font-bold text-slate-400 py-1 border-b border-white/[0.06]">
          <div>شنبه</div>
          <div>یکشنبه</div>
          <div>دوشنبه</div>
          <div>سه‌شنبه</div>
          <div>چهارشنبه</div>
          <div>پنجشنبه</div>
          <div>جمعه</div>
        </div>

        {/* Days Grid with perfect alignment */}
        <div className="grid grid-cols-7 gap-2.5">
          {calendarCells.map((calDay, idx) => (
            <div
              key={idx}
              onClick={() => handleOpenScheduleForDate(calDay.dateStr)}
              className={cn(
                'p-2.5 rounded-2xl border flex flex-col justify-between transition-all cursor-pointer group min-h-[110px]',
                calDay.isToday
                  ? 'bg-pink-600/[0.08] border-pink-500/40 shadow-[0_0_15px_rgba(236,72,153,0.15)]'
                  : calDay.isCurrentMonth
                  ? 'bg-white/[0.02] border-white/[0.06] hover:border-cyan-400/40 hover:bg-white/[0.05]'
                  : 'bg-white/[0.005] border-transparent opacity-35 hover:opacity-70'
              )}
            >
              {/* Top of day cell */}
              <div className="flex items-center justify-between">
                <span
                  className={cn(
                    'text-xs font-mono font-bold w-6 h-6 rounded-full flex items-center justify-center transition-all',
                    calDay.isToday
                      ? 'bg-gradient-to-tr from-pink-600 to-purple-500 text-white shadow-[0_0_10px_rgba(236,72,153,0.7)]'
                      : 'text-slate-300 group-hover:text-white'
                  )}
                >
                  {calDay.dayNumber}
                </span>

                <span className="opacity-0 group-hover:opacity-100 text-[10px] text-pink-400 font-bold transition-opacity">
                  + انتشار
                </span>
              </div>

              {/* Items in day */}
              <div className="mt-2 space-y-1.5 flex-1">
                {(calDay.items || []).map((item) => (
                  <div
                    key={item.id}
                    onClick={(e) => e.stopPropagation()}
                    className="p-1.5 rounded-xl bg-[#0f172a] border border-white/[0.08] text-[11px] space-y-1 shadow-sm hover:border-pink-500/40 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      {getContentTypeBadge(item.content_type)}
                      <span className="text-[9px] text-slate-400 truncate max-w-[60px]">
                        {item.account_handle}
                      </span>
                    </div>
                    <p className="font-bold text-white truncate text-[11px] leading-tight">
                      {item.title}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Schedule Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#0b101d] rounded-3xl shadow-2xl max-w-lg w-full p-6 border border-white/10">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-4">
              <h3 className="font-bold text-base text-white flex items-center gap-2">
                <CalendarIcon className="w-4 h-4 text-pink-400" />
                زمان‌بندی انتشار محتوا
              </h3>
              <button
                onClick={() => setShowScheduleModal(false)}
                className="text-slate-400 hover:text-white p-1 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateContent} className="mt-5 space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-300 mb-1.5">موضوع یا عنوان محتوا *</label>
                <input
                  type="text"
                  required
                  placeholder="مثلاً: ریلز معرفی مانتو کتی ژاکارد..."
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-pink-500/60"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-300 mb-1.5">اکانت انتشار</label>
                  <select
                    value={formAccount}
                    onChange={(e) => setFormAccount(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl border border-white/[0.1] bg-[#0e1628] text-white focus:outline-none cursor-pointer"
                  >
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.platform_display} - {a.handle}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-slate-300 mb-1.5">قالب محتوا</label>
                  <select
                    value={formContentType}
                    onChange={(e) => setFormContentType(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl border border-white/[0.1] bg-[#0e1628] text-white focus:outline-none cursor-pointer"
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
                <label className="block font-bold text-slate-300 mb-1.5">متن کپشن یا پیام</label>
                <textarea
                  rows={3}
                  placeholder="کپشن جذاب، هشتگ‌ها و کال‌تواکشن دایرکت..."
                  value={formCaption}
                  onChange={(e) => setFormCaption(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-pink-500/60"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-300 mb-1.5">تاریخ انتشار</label>
                  <input
                    type="date"
                    value={modalDate}
                    onChange={(e) => setModalDate(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl border border-white/[0.1] bg-[#0e1628] text-white focus:outline-none cursor-pointer"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-300 mb-1.5">آدرس کاور / پیش‌نمایش</label>
                  <input
                    type="url"
                    placeholder="https://..."
                    value={formThumbnail}
                    onChange={(e) => setFormThumbnail(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-pink-500/60"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setShowScheduleModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white cursor-pointer"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2.5 rounded-xl font-bold bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white shadow-[0_0_15px_rgba(236,72,153,0.4)] cursor-pointer"
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
