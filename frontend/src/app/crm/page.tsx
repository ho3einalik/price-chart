'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import {
  Users,
  MessageSquare,
  Sparkles,
  Send,
  RefreshCw,
  Search,
  Crown,
  HeartHandshake,
  AlertOctagon,
  Clock,
  Instagram,
  SendHorizontal
} from 'lucide-react';

export default function CRMPage() {
  const [activeTab, setActiveTab] = useState<'profiles' | 'inbox'>('profiles');
  
  // CRM Profiles state
  const [profiles, setProfiles] = useState<any[]>([]);
  const [segmentsSummary, setSegmentsSummary] = useState<any[]>([]);
  const [selectedSegment, setSelectedSegment] = useState('');
  const [search, setSearch] = useState('');
  const [loadingProfiles, setLoadingProfiles] = useState(false);

  // Social Inbox state
  const [threads, setThreads] = useState<any[]>([]);
  const [selectedThread, setSelectedThread] = useState<any | null>(null);
  const [messageInput, setMessageInput] = useState('');
  const [aiGenerating, setAiGenerating] = useState(false);
  const [loadingInbox, setLoadingInbox] = useState(false);

  const fetchProfiles = async () => {
    setLoadingProfiles(true);
    try {
      const [profRes, segRes] = await Promise.all([
        api.getCRMProfiles({ segment: selectedSegment, search }),
        api.getCRMSegmentsSummary(),
      ]);
      setProfiles(Array.isArray(profRes) ? profRes : (profRes?.results || []));
      setSegmentsSummary(Array.isArray(segRes) ? segRes : []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingProfiles(false);
    }
  };

  const fetchInbox = async () => {
    setLoadingInbox(true);
    try {
      const res = await api.getInboxThreads();
      const list = Array.isArray(res) ? res : (res?.results || []);
      setThreads(list);
      if (list.length > 0 && !selectedThread) {
        setSelectedThread(list[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingInbox(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'profiles') {
      fetchProfiles();
    } else {
      fetchInbox();
    }
  }, [activeTab, selectedSegment, search]);

  const handleRecalculateRFM = async () => {
    try {
      const res = await api.recalculateCRM();
      alert(res.message);
      fetchProfiles();
    } catch (err: any) {
      alert(err.message || 'خطا در محاسبه');
    }
  };

  const handleSuggestAIReply = async () => {
    if (!selectedThread) return;
    setAiGenerating(true);
    try {
      const res = await api.suggestAIReply(selectedThread.id);
      setMessageInput(res.suggested_text);
    } catch (err: any) {
      alert(err.message || 'خطا در تولید پاسخ هوش مصنوعی');
    } finally {
      setAiGenerating(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedThread || !messageInput.trim()) return;
    try {
      await api.sendInboxMessage(selectedThread.id, messageInput.trim());
      setMessageInput('');
      fetchInbox();
    } catch (err: any) {
      alert(err.message || 'خطا در ارسال پیام');
    }
  };

  return (
    <div className="flex-1 p-6 space-y-6 max-w-7xl mx-auto w-full text-slate-100">
      {/* Header */}
      <div className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] p-6 rounded-3xl shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-cyan-600/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <MessageSquare className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">مدیریت مشتریان و صندوق پیام‌های یکپارچه</h1>
            <p className="text-xs text-slate-400 mt-1">بخش‌بندی RFM، ارزش طول عمر (LTV)، پاسخ هوشمند دایرکت و تاریخچه مکالمات</p>
          </div>
        </div>

        {activeTab === 'profiles' && (
          <button
            onClick={handleRecalculateRFM}
            className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-blue-600/20 border border-blue-500/30 hover:bg-blue-600/30 text-blue-400 text-xs font-medium transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>محاسبه مجدد شاخص‌های RFM</span>
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-white/[0.06] pb-3">
        <button
          onClick={() => setActiveTab('profiles')}
          className={`flex items-center gap-2 px-5 py-2 rounded-2xl text-xs font-medium transition-all ${
            activeTab === 'profiles'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>دایرکتوری مشتریان و RFM</span>
        </button>
        <button
          onClick={() => setActiveTab('inbox')}
          className={`flex items-center gap-2 px-5 py-2 rounded-2xl text-xs font-medium transition-all ${
            activeTab === 'inbox'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>صندوق پیام‌ها و دایرکت ({threads.length})</span>
        </button>
      </div>

      {/* Tab 1: CRM Profiles */}
      {activeTab === 'profiles' ? (
        <div className="space-y-6">
          {/* RFM Segment Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {segmentsSummary.map((s) => (
              <div
                key={s.segment}
                onClick={() => setSelectedSegment(selectedSegment === s.segment ? '' : s.segment)}
                className={`cursor-pointer p-4 rounded-2xl border transition-all ${
                  selectedSegment === s.segment
                    ? 'bg-blue-600/20 border-blue-500/40 shadow-[0_0_15px_rgba(37,99,235,0.25)]'
                    : 'bg-[#0e1628]/60 border-white/[0.06] hover:border-white/10'
                }`}
              >
                <p className="text-xs text-slate-400">{s.label}</p>
                <div className="flex items-baseline justify-between mt-2">
                  <span className="text-lg font-bold text-white">{s.count}</span>
                  <span className="text-[11px] text-slate-400">{Number(s.total_revenue).toLocaleString('fa-IR')} ت</span>
                </div>
              </div>
            ))}
          </div>

          {/* Search bar */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute right-4 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجو با نام یا شماره تماس مشتری..."
              className="w-full pr-11 pl-4 py-3 bg-[#0e1628]/80 border border-white/10 rounded-2xl text-xs text-white placeholder-slate-500"
            />
          </div>

          {/* Profiles Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {loadingProfiles ? (
              <div className="col-span-full p-12 text-center text-slate-400 text-xs">در حال بارگذاری مشتریان...</div>
            ) : profiles.length === 0 ? (
              <div className="col-span-full bg-[#0e1628]/60 border border-white/[0.06] rounded-3xl p-12 text-center text-slate-400 text-xs">
                مشتری‌ای مطابق با فیلتر یافت نشد.
              </div>
            ) : (
              profiles.map((p) => (
                <div
                  key={p.id}
                  className="bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] hover:border-blue-500/30 rounded-3xl p-5 space-y-4 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-white">{p.customer?.full_name}</h3>
                      <p className="text-xs text-slate-400 mt-0.5">{p.customer?.phone_number}</p>
                    </div>
                    <span className="text-[11px] px-2.5 py-1 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      {p.segment_display}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 py-3 border-y border-white/[0.06] text-center">
                    <div>
                      <p className="text-[10px] text-slate-400">سفارش‌ها</p>
                      <p className="text-xs font-bold text-white mt-1">{p.frequency_orders_count}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400">LTV (خرید کل)</p>
                      <p className="text-xs font-bold text-emerald-400 mt-1">{Number(p.monetary_total_spent).toLocaleString('fa-IR')} ت</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400">فاصله خرید</p>
                      <p className="text-xs font-bold text-white mt-1">{p.recency_days} روز</p>
                    </div>
                  </div>

                  <div className="text-[11px] text-slate-400 flex items-center justify-between">
                    <span>شهر: {p.customer?.city || 'نامشخص'}</span>
                    <span>میانگین سفارش: {Number(p.average_order_value).toLocaleString('fa-IR')} ت</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : (
        /* Tab 2: Unified Social Inbox */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[500px]">
          {/* Thread List (Left 4 Cols) */}
          <div className="lg:col-span-4 space-y-3">
            {loadingInbox ? (
              <div className="p-8 text-center text-slate-400 text-xs">در حال بارگذاری گفتگوها...</div>
            ) : threads.length === 0 ? (
              <div className="bg-[#0e1628]/60 border border-white/[0.06] rounded-3xl p-10 text-center text-slate-400 text-xs">
                گفتگویی در صندوق پیام‌ها وجود ندارد.
              </div>
            ) : (
              threads.map((t) => {
                const isSelected = selectedThread?.id === t.id;
                return (
                  <div
                    key={t.id}
                    onClick={() => setSelectedThread(t)}
                    className={`cursor-pointer p-4 rounded-3xl border transition-all ${
                      isSelected
                        ? 'bg-blue-600/10 border-blue-500/40 shadow-[0_0_20px_rgba(37,99,235,0.2)]'
                        : 'bg-[#0e1628]/80 border-white/[0.08] hover:border-white/20'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-bold text-white">{t.contact_name}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-lg bg-pink-500/10 text-pink-400 border border-pink-500/20">
                        {t.channel_display}
                      </span>
                    </div>

                    <p className="text-xs text-slate-400 truncate">{t.last_message_preview || 'پیام جدید'}</p>
                    <span className="text-[10px] text-slate-500 mt-2 block">{t.contact_handle}</span>
                  </div>
                );
              })
            )}
          </div>

          {/* Active Chat Conversation (Right 8 Cols) */}
          <div className="lg:col-span-8 flex flex-col bg-[#0e1628]/80 backdrop-blur-xl border border-white/[0.08] rounded-3xl p-5">
            {selectedThread ? (
              <>
                {/* Chat Top bar */}
                <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
                  <div>
                    <h2 className="text-sm font-bold text-white">{selectedThread.contact_name}</h2>
                    <p className="text-xs text-slate-400">{selectedThread.contact_handle} • {selectedThread.channel_display}</p>
                  </div>
                  <button
                    onClick={handleSuggestAIReply}
                    disabled={aiGenerating}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:opacity-90 text-white text-xs font-medium shadow-[0_0_15px_rgba(99,102,241,0.3)] disabled:opacity-50"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                    <span>{aiGenerating ? 'در حال تولید پاسخ...' : 'پیشنهاد پاسخ با هوش مصنوعی'}</span>
                  </button>
                </div>

                {/* Message List */}
                <div className="flex-1 py-4 space-y-3 overflow-y-auto max-h-[380px]">
                  {selectedThread.messages?.map((m: any) => {
                    const isAgent = m.sender_type === 'AGENT';
                    return (
                      <div
                        key={m.id}
                        className={`flex flex-col ${isAgent ? 'items-end' : 'items-start'}`}
                      >
                        <div
                          className={`max-w-[75%] p-3.5 rounded-2xl text-xs leading-relaxed ${
                            isAgent
                              ? 'bg-blue-600 text-white rounded-br-none shadow-[0_0_15px_rgba(37,99,235,0.2)]'
                              : 'bg-white/[0.05] border border-white/[0.08] text-slate-200 rounded-bl-none'
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{m.text}</p>
                        </div>
                        <span className="text-[10px] text-slate-500 mt-1 px-1">
                          {isAgent ? (m.is_ai_generated ? 'هوش مصنوعی (تایید شده)' : 'پشتیبان') : selectedThread.contact_name}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* Message Input Box */}
                <form onSubmit={handleSendMessage} className="pt-3 border-t border-white/[0.06] flex items-center gap-2">
                  <input
                    value={messageInput}
                    onChange={(e) => setMessageInput(e.target.value)}
                    placeholder="پاسخ را بنویسید یا از دکمه پیشنهاد هوش مصنوعی استفاده کنید..."
                    className="flex-1 px-4 py-2.5 bg-[#0b101d] border border-white/10 rounded-2xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                  <button
                    type="submit"
                    className="p-2.5 rounded-2xl bg-blue-600 hover:bg-blue-500 text-white shadow-[0_0_15px_rgba(37,99,235,0.3)]"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-500 text-xs">
                یک مکالمه را جهت مشاهده و پاسخ انتخاب کنید
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
