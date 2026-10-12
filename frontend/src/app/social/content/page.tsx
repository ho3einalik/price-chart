'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
  Layers,
  CheckCircle2,
  AlertCircle,
  Clock,
  Instagram,
  Send,
  ExternalLink,
  BarChart2,
  X,
  MessageSquare,
  ThumbsUp,
  Bookmark,
  Share2,
  Sparkles,
  ShoppingBag
} from 'lucide-react';

interface SocialContent {
  id: string;
  account: string | null;
  platform: string | null;
  platform_display: string | null;
  account_handle: string | null;
  campaign_name: string | null;
  content_type: string;
  content_type_display: string;
  title: string;
  caption: string;
  hashtags: string;
  thumbnail_url: string;
  status: string;
  status_display: string;
  creator_name: string;
  assignee_name: string | null;
  scheduled_at: string | null;
  published_at: string | null;
  published_url: string;
  destination_url: string;
  latest_metrics: {
    reach: number;
    impressions: number;
    likes: number;
    comments: number;
    saves: number;
    shares: number;
    engagement_rate: number;
    attributed_revenue: number;
  } | null;
}

export default function SocialContentPage() {
  const [contents, setContents] = useState<SocialContent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'ALL' | 'READY_FOR_REVIEW' | 'SCHEDULED' | 'PUBLISHED'>('ALL');

  // Modals
  const [selectedReviewContent, setSelectedReviewContent] = useState<SocialContent | null>(null);
  const [reviewAction, setReviewAction] = useState<'APPROVED' | 'CHANGES_REQUESTED'>('APPROVED');
  const [reviewFeedback, setReviewFeedback] = useState('');

  const [selectedMetricContent, setSelectedMetricContent] = useState<SocialContent | null>(null);
  const [metricReach, setMetricReach] = useState('');
  const [metricLikes, setMetricLikes] = useState('');
  const [metricComments, setMetricComments] = useState('');
  const [metricSaves, setMetricSaves] = useState('');
  const [metricShares, setMetricShares] = useState('');
  const [metricRevenue, setMetricRevenue] = useState('');
  const [metricOrders, setMetricOrders] = useState('');

  const [selectedPublishContent, setSelectedPublishContent] = useState<SocialContent | null>(null);
  const [publishUrl, setPublishUrl] = useState('');

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (activeTab !== 'ALL') {
        params.status = activeTab;
      }
      const res = await api.getSocialContent(params);
      setContents(Array.isArray(res) ? res : (res as any).results || []);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReviewContent) return;
    try {
      await api.reviewContent(selectedReviewContent.id, reviewAction, reviewFeedback);
      setSelectedReviewContent(null);
      setReviewFeedback('');
      loadData();
    } catch (err: any) {
      alert(err.message || 'خطا در ثبت نتیجه بررسی');
    }
  };

  const handlePublishSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPublishContent) return;
    try {
      await api.publishContent(selectedPublishContent.id, publishUrl);
      setSelectedPublishContent(null);
      setPublishUrl('');
      loadData();
    } catch (err: any) {
      alert(err.message || 'خطا در ثبت انتشار');
    }
  };

  const handleMetricSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMetricContent) return;
    try {
      await api.recordContentMetrics(selectedMetricContent.id, {
        reach: parseInt(metricReach) || 0,
        likes: parseInt(metricLikes) || 0,
        comments: parseInt(metricComments) || 0,
        saves: parseInt(metricSaves) || 0,
        shares: parseInt(metricShares) || 0,
        attributed_revenue: parseFloat(metricRevenue) || 0,
        attributed_orders_count: parseInt(metricOrders) || 0,
      });
      setSelectedMetricContent(null);
      resetMetricForm();
      loadData();
    } catch (err: any) {
      alert(err.message || 'خطا در ثبت آمار');
    }
  };

  const resetMetricForm = () => {
    setMetricReach('');
    setMetricLikes('');
    setMetricComments('');
    setMetricSaves('');
    setMetricShares('');
    setMetricRevenue('');
    setMetricOrders('');
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-800 flex items-center gap-3">
            <Layers className="w-7 h-7 text-indigo-600" />
            کارتابل بررسی و تایید محتوا
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            جریان تأیید پیش از انتشار ریلزها و پست‌ها، ثبت بازخورد ادیتور و پیگیری نتایج اینستاگرام
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab('ALL')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'ALL' ? 'bg-indigo-600 text-white shadow-xs' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          همه محتواها
        </button>
        <button
          onClick={() => setActiveTab('READY_FOR_REVIEW')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
            activeTab === 'READY_FOR_REVIEW'
              ? 'bg-amber-600 text-white shadow-xs'
              : 'text-amber-800 bg-amber-50 hover:bg-amber-100'
          }`}
        >
          <span>در انتظار تأیید و بازبینی</span>
        </button>
        <button
          onClick={() => setActiveTab('SCHEDULED')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'SCHEDULED' ? 'bg-purple-600 text-white shadow-xs' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          زمان‌بندی‌شده
        </button>
        <button
          onClick={() => setActiveTab('PUBLISHED')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'PUBLISHED' ? 'bg-emerald-600 text-white shadow-xs' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          منتشر‌شده در پیج
        </button>
      </div>

      {/* Content List Cards */}
      {loading ? (
        <div className="p-8 text-center text-slate-400">در حال بارگذاری کارتابل محتوا...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {contents.map((item) => (
            <div
              key={item.id}
              className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between"
            >
              <div>
                {/* Media thumbnail preview */}
                <div className="h-44 bg-slate-100 relative overflow-hidden flex items-center justify-center">
                  {item.thumbnail_url ? (
                    <img
                      src={item.thumbnail_url}
                      alt={item.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="text-slate-400 text-xs flex flex-col items-center gap-1">
                      <Layers className="w-8 h-8 opacity-40" />
                      <span>پیش‌نمایش تصویر موجود نیست</span>
                    </div>
                  )}

                  <div className="absolute top-3 right-3 flex items-center gap-1.5">
                    <span className="bg-slate-900/80 backdrop-blur-xs text-white text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                      <Instagram className="w-3 h-3 text-pink-400" />
                      {item.content_type_display}
                    </span>
                  </div>

                  <div className="absolute top-3 left-3">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full shadow-2xs ${
                        item.status === 'PUBLISHED'
                          ? 'bg-emerald-600 text-white'
                          : item.status === 'READY_FOR_REVIEW'
                          ? 'bg-amber-500 text-white'
                          : item.status === 'SCHEDULED'
                          ? 'bg-purple-600 text-white'
                          : 'bg-slate-800 text-white'
                      }`}
                    >
                      {item.status_display}
                    </span>
                  </div>
                </div>

                {/* Content Info */}
                <div className="p-4 space-y-3">
                  <div>
                    <h3 className="font-bold text-sm text-slate-800 leading-snug line-clamp-1">
                      {item.title}
                    </h3>
                    <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                      {item.caption || 'بدون کپشن اولیه'}
                    </p>
                    {item.hashtags && (
                      <p className="text-[11px] text-sky-600 mt-1 truncate">{item.hashtags}</p>
                    )}
                  </div>

                  <div className="text-[11px] text-slate-500 pt-3 border-t border-slate-100 flex items-center justify-between">
                    <span>تولید: {item.creator_name}</span>
                    {item.scheduled_at && (
                      <span className="text-purple-700 font-medium">
                        انتشار: {item.scheduled_at.slice(0, 10)}
                      </span>
                    )}
                  </div>

                  {/* Performance Snapshot Pill */}
                  {item.latest_metrics && (
                    <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100 flex items-center justify-between text-xs">
                      <div>
                        <span className="text-[10px] text-slate-400 block">نرخ تعامل (ER):</span>
                        <strong className="text-pink-600 font-black">
                          {item.latest_metrics.engagement_rate}%
                        </strong>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] text-slate-400 block">بازدید (Reach):</span>
                        <strong className="text-slate-800">
                          {item.latest_metrics.reach.toLocaleString('fa-IR')}
                        </strong>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] text-slate-400 block">لایک / سیو:</span>
                        <span className="text-slate-700 font-semibold">
                          {item.latest_metrics.likes} / {item.latest_metrics.saves}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="p-4 pt-0 space-y-2">
                {item.status === 'READY_FOR_REVIEW' && (
                  <button
                    onClick={() => setSelectedReviewContent(item)}
                    className="w-full py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold shadow-xs transition-colors"
                  >
                    🔍 بررسی و تأیید محتوا
                  </button>
                )}

                {item.status === 'APPROVED' && (
                  <button
                    onClick={() => {
                      setSelectedPublishContent(item);
                      setPublishUrl(item.published_url || '');
                    }}
                    className="w-full py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-bold shadow-xs transition-colors"
                  >
                    🚀 ثبت انتشار در شبکه
                  </button>
                )}

                {item.status === 'PUBLISHED' && (
                  <div className="flex gap-2">
                    {item.published_url && (
                      <a
                        href={item.published_url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-1 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold text-center flex items-center justify-center gap-1"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        <span>مشاهده پست</span>
                      </a>
                    )}
                    <button
                      onClick={() => {
                        setSelectedMetricContent(item);
                        if (item.latest_metrics) {
                          setMetricReach(String(item.latest_metrics.reach));
                          setMetricLikes(String(item.latest_metrics.likes));
                          setMetricComments(String(item.latest_metrics.comments));
                          setMetricSaves(String(item.latest_metrics.saves));
                          setMetricShares(String(item.latest_metrics.shares));
                          setMetricRevenue(String(item.latest_metrics.attributed_revenue));
                        }
                      }}
                      className="flex-1 py-2 bg-pink-50 hover:bg-pink-100 text-pink-700 rounded-xl text-xs font-bold flex items-center justify-center gap-1 border border-pink-200"
                    >
                      <BarChart2 className="w-3.5 h-3.5" />
                      <span>ثبت آمار تعامل</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {contents.length === 0 && (
            <div className="col-span-full p-12 text-center text-slate-400 bg-white border border-slate-200 rounded-2xl">
              هیچ محتوایی در این وضعیت یافت نشد.
            </div>
          )}
        </div>
      )}

      {/* Review Modal */}
      {selectedReviewContent && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 animate-scaleIn border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-sm text-slate-800">بررسی و داوری محتوا</h3>
              <button onClick={() => setSelectedReviewContent(null)}>
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>

            <form onSubmit={handleReviewSubmit} className="mt-4 space-y-4 text-xs">
              <div>
                <span className="text-slate-400 block mb-1">عنوان محتوا:</span>
                <strong className="text-slate-800 block text-sm">{selectedReviewContent.title}</strong>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">تصمیم ناظر</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setReviewAction('APPROVED')}
                    className={`py-2 rounded-xl font-bold transition-all border ${
                      reviewAction === 'APPROVED'
                        ? 'bg-emerald-600 text-white border-emerald-600'
                        : 'bg-white text-slate-600 border-slate-200'
                    }`}
                  >
                    ✓ تأیید برای انتشار
                  </button>
                  <button
                    type="button"
                    onClick={() => setReviewAction('CHANGES_REQUESTED')}
                    className={`py-2 rounded-xl font-bold transition-all border ${
                      reviewAction === 'CHANGES_REQUESTED'
                        ? 'bg-rose-600 text-white border-rose-600'
                        : 'bg-white text-slate-600 border-slate-200'
                    }`}
                  >
                    ✕ درخواست اصلاحات
                  </button>
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">نکات و بازخورد به ادیتور</label>
                <textarea
                  rows={3}
                  placeholder="نکات ویرایش، اصلاح فونت کاور، تغییر موزیک..."
                  value={reviewFeedback}
                  onChange={(e) => setReviewFeedback(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setSelectedReviewContent(null)}
                  className="px-4 py-2 rounded-xl text-slate-600 font-medium"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl font-bold bg-indigo-600 hover:bg-indigo-700 text-white"
                >
                  ثبت تصمیم
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Record Metrics Modal */}
      {selectedMetricContent && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 animate-scaleIn border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-sm text-slate-800 flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-pink-600" />
                ثبت دستی آمار و تعاملات اینستاگرام
              </h3>
              <button onClick={() => setSelectedMetricContent(null)}>
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>

            <form onSubmit={handleMetricSubmit} className="mt-4 space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">بازدید یکتا (Reach)</label>
                  <input
                    type="number"
                    required
                    placeholder="مثلاً: 14500"
                    value={metricReach}
                    onChange={(e) => setMetricReach(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">تعداد لایک‌ها</label>
                  <input
                    type="number"
                    placeholder="مثلاً: 980"
                    value={metricLikes}
                    onChange={(e) => setMetricLikes(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">کامنت‌ها</label>
                  <input
                    type="number"
                    placeholder="120"
                    value={metricComments}
                    onChange={(e) => setMetricComments(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">سیوها (Save)</label>
                  <input
                    type="number"
                    placeholder="340"
                    value={metricSaves}
                    onChange={(e) => setMetricSaves(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">شیرها (Share)</label>
                  <input
                    type="number"
                    placeholder="85"
                    value={metricShares}
                    onChange={(e) => setMetricShares(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-100">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">سفارشات منتسب (عدد)</label>
                  <input
                    type="number"
                    placeholder="مثلاً: 15"
                    value={metricOrders}
                    onChange={(e) => setMetricOrders(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">فروش منتسب (تومان)</label>
                  <input
                    type="number"
                    placeholder="مثلاً: 45000000"
                    value={metricRevenue}
                    onChange={(e) => setMetricRevenue(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setSelectedMetricContent(null)}
                  className="px-4 py-2 rounded-xl text-slate-600 font-medium"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl font-bold bg-pink-600 hover:bg-pink-700 text-white shadow-xs"
                >
                  ثبت آمار عملکرد
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Publish Modal */}
      {selectedPublishContent && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 animate-scaleIn border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-sm text-slate-800">ثبت لینک انتشار محتوا</h3>
              <button onClick={() => setSelectedPublishContent(null)}>
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>

            <form onSubmit={handlePublishSubmit} className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">لینک مستقیم اینستاگرام یا تلگرام</label>
                <input
                  type="url"
                  placeholder="https://instagram.com/p/..."
                  value={publishUrl}
                  onChange={(e) => setPublishUrl(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setSelectedPublishContent(null)}
                  className="px-4 py-2 rounded-xl text-slate-600 font-medium"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl font-bold bg-purple-600 hover:bg-purple-700 text-white shadow-xs"
                >
                  تأیید و ثبت وضعیت انتشار
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
