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
import { cn } from '@/lib/utils';

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
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black text-white tracking-tight">مدیریت تیم و دسترسی‌ها</h1>
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            تعریف نقش‌ها (RBAC)، دعوت همکاران، تقسیم وظایف روزمره و پایش عملکرد نیروی انسانی
          </p>
        </div>
        <button
          onClick={() => setShowInviteModal(true)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-xl font-bold shadow-[0_0_18px_rgba(37,99,235,0.45)] transition-all text-xs cursor-pointer"
        >
          <UserPlus className="w-4 h-4" />
          <span>دعوت عضو جدید</span>
        </button>
      </div>

      {message && (
        <div
          className={cn(
            'p-3.5 rounded-2xl text-xs font-semibold flex items-center justify-between border',
            message.type === 'success'
              ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/15 border-rose-500/30 text-rose-300'
          )}
        >
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)} className="cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Team Members Grid */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <h2 className="text-sm font-bold text-white">اعضای فعال فروشگاه</h2>
          <span className="text-[11px] font-bold bg-white/[0.05] border border-white/[0.08] text-cyan-300 px-2 py-0.5 rounded-full font-mono">
            {members.length} نفر
          </span>
        </div>

        {loading ? (
          <div className="p-8 text-center text-slate-500 text-xs">در حال دریافت لیست تیم...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {members.map((member) => (
              <div
                key={member.id}
                className="glass-card p-5 relative overflow-hidden group hover:border-cyan-400/40"
              >
                {/* Glowing top line indicator */}
                <div
                  className={cn(
                    'absolute top-0 right-0 left-0 h-1 transition-all',
                    member.status === 'ACTIVE'
                      ? 'bg-gradient-to-r from-blue-600 to-cyan-400 shadow-[0_0_12px_rgba(56,189,248,0.7)]'
                      : 'bg-rose-500'
                  )}
                />

                <div className="flex items-start justify-between mt-1">
                  <div>
                    <h3 className="font-bold text-white text-sm">
                      {member.user_name || 'کاربر بدون نام'}
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5 font-mono">{member.user_email}</p>
                  </div>

                  {/* Clean dark glass status badge */}
                  <span
                    className={cn(
                      'text-[11px] px-2.5 py-0.5 rounded-full font-bold border',
                      member.status === 'ACTIVE'
                        ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.2)]'
                        : 'bg-rose-500/15 border-rose-500/30 text-rose-300'
                    )}
                  >
                    {member.status_display}
                  </span>
                </div>

                <div className="mt-4 pt-3.5 border-t border-white/[0.06] flex items-center justify-between">
                  {/* Clean dark role badge */}
                  <span className="text-[11px] font-semibold text-cyan-300 bg-white/[0.04] border border-white/[0.08] px-2.5 py-1 rounded-xl">
                    {member.role_display}
                  </span>
                  <div className="text-[11px] text-slate-400 flex items-center gap-3">
                    <span title="کارهای در جریان">
                      📋 <strong className="text-white font-mono">{member.open_tasks_count}</strong>
                    </span>
                    <span title="کارهای تکمیل‌شده">
                      ✅ <strong className="text-emerald-400 font-mono">{member.completed_tasks_count}</strong>
                    </span>
                  </div>
                </div>

                {member.role !== 'OWNER' && (
                  <div className="mt-4 pt-3 border-t border-white/[0.06] flex justify-end gap-2">
                    {member.status === 'ACTIVE' ? (
                      <button
                        onClick={() => handleSuspend(member.id)}
                        className="text-xs font-medium text-rose-400 hover:text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 px-3 py-1.5 rounded-xl transition-all flex items-center gap-1.5 cursor-pointer"
                      >
                        <Ban className="w-3.5 h-3.5" />
                        <span>تعلیق دسترسی</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => handleReactivate(member.id)}
                        className="text-xs font-medium text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 px-3 py-1.5 rounded-xl transition-all flex items-center gap-1.5 cursor-pointer"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>فعال‌سازی مجدد</span>
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
      <div className="glass-card p-6 space-y-4">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Mail className="w-4 h-4 text-amber-400" />
          <span>دعوت‌نامه‌های ارسالی در انتظار</span>
        </h2>

        {invitations.length === 0 ? (
          <p className="text-xs text-slate-500 py-3">دعوت‌نامه معلقی در حال حاضر وجود ندارد.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead className="bg-white/[0.02] text-slate-400 font-semibold border-b border-white/[0.06]">
                <tr>
                  <th className="py-3 px-4">ایمیل دعوت‌شونده</th>
                  <th className="py-3 px-4">نقش تعیین‌شده</th>
                  <th className="py-3 px-4">دعوت‌کننده</th>
                  <th className="py-3 px-4">وضعیت</th>
                  <th className="py-3 px-4 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {invitations.map((inv) => (
                  <tr key={inv.id} className="hover:bg-white/[0.02]">
                    <td className="py-3.5 px-4 font-medium text-white font-mono">{inv.email}</td>
                    <td className="py-3.5 px-4">
                      {/* Clean dark glass role badge */}
                      <span className="text-[11px] font-semibold bg-white/[0.04] border border-white/[0.08] text-cyan-300 px-2.5 py-1 rounded-lg">
                        {inv.role_display}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-400">{inv.inviter_name}</td>
                    <td className="py-3.5 px-4">
                      {/* Clean dark glass invitation status */}
                      <span
                        className={cn(
                          'text-[11px] px-2.5 py-0.5 rounded-full font-bold border',
                          inv.status === 'PENDING'
                            ? 'bg-amber-500/15 border border-amber-500/30 text-amber-300 shadow-[0_0_10px_rgba(245,158,11,0.2)]'
                            : 'bg-white/[0.05] border-white/[0.08] text-slate-300'
                        )}
                      >
                        {inv.status_display}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      {inv.status === 'PENDING' && (
                        <button
                          onClick={() => handleRevokeInvite(inv.id)}
                          className="text-xs text-rose-400 hover:text-rose-300 font-medium hover:underline cursor-pointer"
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
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#0b101d] rounded-3xl shadow-2xl max-w-lg w-full p-6 border border-white/10">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-4">
              <h3 className="font-bold text-base text-white flex items-center gap-2">
                <UserPlus className="w-4 h-4 text-cyan-400" />
                دعوت همکار جدید به فروشگاه
              </h3>
              <button
                onClick={() => setShowInviteModal(false)}
                className="text-slate-400 hover:text-white p-1 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSendInvite} className="mt-5 space-y-5">
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">
                  آدرس ایمیل همکار *
                </label>
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400/60 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">
                  نقش سازمانی پیش‌فرض
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-white/[0.1] bg-[#0e1628] text-white text-xs focus:outline-none cursor-pointer"
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-2">
                  دسترسی‌های سفارشی اختیاری
                </label>
                <div className="space-y-2 max-h-48 overflow-y-auto p-3 border border-white/[0.08] rounded-2xl bg-white/[0.02]">
                  {AVAILABLE_PERMISSIONS.map((perm) => (
                    <label
                      key={perm.id}
                      className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer hover:text-white"
                    >
                      <input
                        type="checkbox"
                        checked={selectedPermissions.includes(perm.id)}
                        onChange={() => togglePermission(perm.id)}
                        className="rounded border-white/20 text-blue-600 focus:ring-0"
                      />
                      <span>{perm.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white cursor-pointer"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2.5 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white flex items-center gap-2 shadow-[0_0_15px_rgba(37,99,235,0.4)] disabled:opacity-50 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
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
