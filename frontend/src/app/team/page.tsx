'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
  Users,
  UserPlus,
  Shield,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Ban,
  RotateCcw,
  Mail,
  Send,
  X,
  Plus
} from 'lucide-react';

interface Member {
  id: string;
  user: string;
  user_email: string;
  user_name: string;
  role: string;
  role_display: string;
  status: 'ACTIVE' | 'SUSPENDED';
  status_display: string;
  custom_permissions: string[];
  open_tasks_count: number;
  completed_tasks_count: number;
  created_at: string;
}

interface Invitation {
  id: string;
  email: string;
  role: string;
  role_display: string;
  inviter_name: string;
  status: string;
  status_display: string;
  created_at: string;
  expires_at: string;
}

const ROLES = [
  { value: 'BUSINESS_MANAGER', label: 'مدیر کسب‌وکار (Business Manager)' },
  { value: 'SOCIAL_MEDIA_MANAGER', label: 'مدیر شبکه‌های اجتماعی (Social Media Manager)' },
  { value: 'CONTENT_CREATOR', label: 'تولیدکننده محتوا (Content Creator)' },
  { value: 'OPS_MANAGER', label: 'مدیر عملیات و انبار (Ops Manager)' },
  { value: 'SUPPORT', label: 'پشتیبانی مشتریان (Customer Support)' },
  { value: 'ADMIN', label: 'مدیر فنی سیستم (System Admin)' },
];

const AVAILABLE_PERMISSIONS = [
  { id: 'team.manage_roles', label: 'مدیریت اعضا و دعوت‌ها' },
  { id: 'tasks.create', label: 'ایجاد و تخصیص وظایف' },
  { id: 'tasks.verify', label: 'تأیید و بازبینی وظایف تکمیل‌شده' },
  { id: 'content.create', label: 'ایجاد و تدوین محتوا' },
  { id: 'content.approve', label: 'تأیید نهایی محتوای سوشال' },
  { id: 'content.publish', label: 'انتشار مستقیم در شبکه‌ها' },
  { id: 'analytics.view', label: 'مشاهده گزارشات تحلیلی و مالی' },
];

export default function TeamPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('CONTENT_CREATOR');
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [membersData, invitesData] = await Promise.all([
        api.getTeamMembers(),
        api.getTeamInvitations(),
      ]);
      setMembers(Array.isArray(membersData) ? membersData : (membersData as any).results || []);
      setInvitations(Array.isArray(invitesData) ? invitesData : (invitesData as any).results || []);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail) return;
    setIsSubmitting(true);
    setMessage(null);
    try {
      await api.sendTeamInvitation({
        email: inviteEmail,
        role: inviteRole,
        custom_permissions: selectedPermissions,
      });
      setMessage({ text: 'دعوت‌نامه با موفقیت ارسال شد.', type: 'success' });
      setShowInviteModal(false);
      setInviteEmail('');
      setSelectedPermissions([]);
      loadData();
    } catch (err: any) {
      setMessage({ text: err.message || 'خطا در ارسال دعوت‌نامه', type: 'error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSuspend = async (memberId: string) => {
    if (!confirm('آیا از تعلیق دسترسی این عضو اطمینان دارید؟')) return;
    try {
      await api.suspendTeamMember(memberId);
      loadData();
    } catch (err: any) {
      alert(err.message || 'خطا در تعلیق عضو');
    }
  };

  const handleReactivate = async (memberId: string) => {
    try {
      await api.reactivateTeamMember(memberId);
      loadData();
    } catch (err: any) {
      alert(err.message || 'خطا در فعال‌سازی عضو');
    }
  };

  const handleRevokeInvite = async (inviteId: string) => {
    if (!confirm('آیا از لغو این دعوت‌نامه اطمینان دارید؟')) return;
    try {
      await api.revokeTeamInvitation(inviteId);
      loadData();
    } catch (err: any) {
      alert(err.message || 'خطا در لغو دعوت‌نامه');
    }
  };

  const togglePermission = (permId: string) => {
    setSelectedPermissions((prev) =>
      prev.includes(permId) ? prev.filter((p) => p !== permId) : [...prev, permId]
    );
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-800 flex items-center gap-3">
            <Users className="w-7 h-7 text-sky-600" />
            مدیریت تیم، اعضا و سطوح دسترسی
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            تعریف نقش‌ها (RBAC)، دعوت همکاران، تقسیم وظایف روزمره و پایش عملکرد نیروی انسانی
          </p>
        </div>
        <button
          onClick={() => setShowInviteModal(true)}
          className="flex items-center gap-2 bg-sky-600 hover:bg-sky-700 text-white px-5 py-2.5 rounded-xl font-medium shadow-sm transition-all"
        >
          <UserPlus className="w-5 h-5" />
          <span>دعوت عضو جدید</span>
        </button>
      </div>

      {message && (
        <div
          className={`p-4 rounded-xl text-sm font-medium flex items-center justify-between ${
            message.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}
        >
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)}>
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Team Members Grid */}
      <div>
        <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
          <span>اعضای فعال فروشگاه</span>
          <span className="text-xs font-semibold bg-slate-100 text-slate-600 px-2.5 py-0.5 rounded-full">
            {members.length} نفر
          </span>
        </h2>

        {loading ? (
          <div className="p-8 text-center text-slate-400">در حال دریافت لیست تیم...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {members.map((member) => (
              <div
                key={member.id}
                className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden"
              >
                <div
                  className={`absolute top-0 right-0 left-0 h-1.5 ${
                    member.status === 'ACTIVE' ? 'bg-sky-500' : 'bg-rose-400'
                  }`}
                />
                <div className="flex items-start justify-between mt-1">
                  <div>
                    <h3 className="font-bold text-slate-800 text-base">
                      {member.user_name || 'کاربر بدون نام'}
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">{member.user_email}</p>
                  </div>
                  <span
                    className={`text-xs px-2.5 py-1 rounded-full font-semibold ${
                      member.status === 'ACTIVE'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-rose-50 text-rose-700 border border-rose-200'
                    }`}
                  >
                    {member.status_display}
                  </span>
                </div>

                <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-600 bg-slate-100 px-3 py-1 rounded-lg">
                    {member.role_display}
                  </span>
                  <div className="text-xs text-slate-500 flex items-center gap-3">
                    <span title="کارهای در جریان">
                      📋 <strong className="text-slate-800">{member.open_tasks_count}</strong> در جریان
                    </span>
                    <span title="کارهای تکمیل‌شده">
                      ✅ <strong className="text-emerald-600">{member.completed_tasks_count}</strong> انجام‌شده
                    </span>
                  </div>
                </div>

                {member.role !== 'OWNER' && (
                  <div className="mt-4 pt-3 border-t border-slate-100 flex justify-end gap-2">
                    {member.status === 'ACTIVE' ? (
                      <button
                        onClick={() => handleSuspend(member.id)}
                        className="text-xs font-medium text-rose-600 hover:text-rose-700 hover:bg-rose-50 px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
                      >
                        <Ban className="w-3.5 h-3.5" />
                        تعلیق دسترسی
                      </button>
                    ) : (
                      <button
                        onClick={() => handleReactivate(member.id)}
                        className="text-xs font-medium text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        فعال‌سازی مجدد
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pending Invitations Section */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
          <Mail className="w-5 h-5 text-amber-500" />
          <span>دعوت‌نامه‌های ارسالی در انتظار</span>
        </h2>

        {invitations.length === 0 ? (
          <p className="text-sm text-slate-500 py-4">دعوت‌نامه معلقی در حال حاضر وجود ندارد.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead className="bg-slate-50 text-slate-600 text-xs font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">ایمیل دعوت‌شونده</th>
                  <th className="py-3 px-4">نقش تعیین‌شده</th>
                  <th className="py-3 px-4">دعوت‌کننده</th>
                  <th className="py-3 px-4">وضعیت</th>
                  <th className="py-3 px-4 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {invitations.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50/50">
                    <td className="py-3 px-4 font-medium text-slate-800">{inv.email}</td>
                    <td className="py-3 px-4">
                      <span className="text-xs font-semibold bg-sky-50 text-sky-700 px-2 py-0.5 rounded-md">
                        {inv.role_display}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">{inv.inviter_name}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          inv.status === 'PENDING'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {inv.status_display}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {inv.status === 'PENDING' && (
                        <button
                          onClick={() => handleRevokeInvite(inv.id)}
                          className="text-xs text-rose-600 hover:text-rose-700 font-medium hover:underline"
                        >
                          لغو دعوت
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Invite Member Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 animate-scaleIn border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-sky-600" />
                دعوت همکار جدید به فروشگاه
              </h3>
              <button
                onClick={() => setShowInviteModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSendInvite} className="mt-5 space-y-5">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">
                  آدرس ایمیل همکار
                </label>
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">
                  نقش سازمانی پیش‌فرض
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-2">
                  دسترسی‌های سفارشی اختیاری
                </label>
                <div className="space-y-2 max-h-48 overflow-y-auto p-3 border border-slate-100 rounded-xl bg-slate-50/50">
                  {AVAILABLE_PERMISSIONS.map((perm) => (
                    <label
                      key={perm.id}
                      className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedPermissions.includes(perm.id)}
                        onChange={() => togglePermission(perm.id)}
                        className="rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                      />
                      <span>{perm.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="px-4 py-2 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-100"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-xl text-sm font-semibold bg-sky-600 hover:bg-sky-700 text-white flex items-center gap-2 shadow-sm disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                  <span>{isSubmitting ? 'در حال ارسال...' : 'ارسال دعوت‌نامه'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
