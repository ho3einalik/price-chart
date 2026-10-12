'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
  CheckSquare,
  Plus,
  Clock,
  User,
  Calendar,
  Filter,
  MessageSquare,
  Send,
  X,
  ShieldCheck,
  ListTodo,
  Columns
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Task {
  id: string;
  title: string;
  description: string;
  category: string | null;
  category_name: string | null;
  category_color: string | null;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
  priority_display: string;
  status: 'BACKLOG' | 'TODO' | 'IN_PROGRESS' | 'IN_REVIEW' | 'COMPLETED' | 'CANCELLED';
  status_display: string;
  creator_name: string;
  assignee: string | null;
  assignee_name: string | null;
  reviewer_name: string | null;
  start_date: string | null;
  due_date: string | null;
  is_overdue: boolean;
  estimated_hours: number;
  actual_hours: number;
  requires_verification: boolean;
  completion_evidence: string;
  checklist_total: number;
  checklist_completed: number;
  created_at: string;
}

interface TaskDetail extends Task {
  checklist_items: Array<{
    id: string;
    title: string;
    is_completed: boolean;
    completed_by_name: string | null;
    completed_at: string | null;
  }>;
  comments: Array<{
    id: string;
    author_name: string;
    content: string;
    created_at: string;
  }>;
  activity_logs: Array<{
    id: string;
    actor_name: string;
    action_type: string;
    note: string;
    created_at: string;
  }>;
}

const COLUMNS = [
  { id: 'TODO', title: 'در انتظار انجام', color: 'border-white/[0.08] bg-white/[0.02]', badge: 'bg-white/[0.05] text-slate-300' },
  { id: 'IN_PROGRESS', title: 'در حال انجام', color: 'border-blue-500/30 bg-blue-500/[0.04]', badge: 'bg-blue-500/20 text-cyan-300' },
  { id: 'IN_REVIEW', title: 'در انتظار بازبینی', color: 'border-amber-500/30 bg-amber-500/[0.04]', badge: 'bg-amber-500/20 text-amber-300' },
  { id: 'COMPLETED', title: 'تکمیل شده', color: 'border-emerald-500/30 bg-emerald-500/[0.04]', badge: 'bg-emerald-500/20 text-emerald-300' },
];

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [teamMembers, setTeamMembers] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterMyTasks, setFilterMyTasks] = useState(false);
  const [filterCategory, setFilterCategory] = useState('');
  const [filterPriority, setFilterPriority] = useState('');
  const [viewMode, setViewMode] = useState<'kanban' | 'list'>('kanban');

  // Modals & Details
  const [selectedTask, setSelectedTask] = useState<TaskDetail | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);

  // Create Form State
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newCategory, setNewCategory] = useState('');
  const [newPriority, setNewPriority] = useState('MEDIUM');
  const [newAssignee, setNewAssignee] = useState('');
  const [newDueDate, setNewDueDate] = useState('');
  const [newRequiresVerification, setNewRequiresVerification] = useState(false);
  const [newChecklist, setNewChecklist] = useState<string[]>(['']);

  // Detail Drawer Actions
  const [newComment, setNewComment] = useState('');
  const [newChecklistTitle, setNewChecklistTitle] = useState('');
  const [reviewFeedback, setReviewFeedback] = useState('');

  useEffect(() => {
    loadInitialData();
  }, [filterMyTasks, filterCategory, filterPriority]);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      const [tasksRes, catsRes, membersRes, sumRes] = await Promise.all([
        api.getTasks({
          my_tasks: filterMyTasks || undefined,
          category: filterCategory || undefined,
          priority: filterPriority || undefined,
        }),
        api.getTaskCategories(),
        api.getTeamMembers(),
        api.getTaskSummary(),
      ]);

      setTasks(Array.isArray(tasksRes) ? tasksRes : (tasksRes as any).results || []);
      setCategories(Array.isArray(catsRes) ? catsRes : (catsRes as any).results || []);
      setTeamMembers(Array.isArray(membersRes) ? membersRes : (membersRes as any).results || []);
      setSummary(sumRes);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDetail = async (taskId: string) => {
    setIsDetailLoading(true);
    try {
      const detail = await api.getTaskDetail(taskId);
      setSelectedTask(detail);
    } catch (err: any) {
      alert('خطا در بارگذاری جزئیات وظیفه: ' + err.message);
    } finally {
      setIsDetailLoading(false);
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    try {
      await api.createTask({
        title: newTitle.trim(),
        description: newDesc.trim(),
        category: newCategory || null,
        priority: newPriority,
        assignee: newAssignee || null,
        due_date: newDueDate || null,
        requires_verification: newRequiresVerification,
        checklist_items: newChecklist.filter((c) => c.trim()),
      });

      setShowCreateModal(false);
      setNewTitle('');
      setNewDesc('');
      setNewChecklist(['']);
      loadInitialData();
    } catch (err: any) {
      alert(err.message || 'خطا در ثبت وظیفه');
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!selectedTask) return;
    try {
      const updated = await api.updateTaskStatus(selectedTask.id, newStatus);
      setSelectedTask(updated);
      loadInitialData();
    } catch (err: any) {
      alert(err.message || 'خطا در تغییر وضعیت');
    }
  };

  const handleVerify = async (approved: boolean) => {
    if (!selectedTask) return;
    try {
      const updated = await api.verifyTask(selectedTask.id, approved, reviewFeedback);
      setSelectedTask(updated);
      setReviewFeedback('');
      loadInitialData();
    } catch (err: any) {
      alert(err.message || 'خطا در ثبت نتیجه بازبینی');
    }
  };

  const handleToggleChecklist = async (itemId: string) => {
    if (!selectedTask) return;
    try {
      await api.toggleTaskChecklistItem(selectedTask.id, itemId);
      const refreshed = await api.getTaskDetail(selectedTask.id);
      setSelectedTask(refreshed);
      loadInitialData();
    } catch (err: any) {
      alert(err.message || 'خطا در تغییر چک‌لیست');
    }
  };

  const handleAddChecklist = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask || !newChecklistTitle.trim()) return;
    try {
      await api.addTaskChecklistItem(selectedTask.id, newChecklistTitle.trim());
      setNewChecklistTitle('');
      const refreshed = await api.getTaskDetail(selectedTask.id);
      setSelectedTask(refreshed);
      loadInitialData();
    } catch (err: any) {
      alert(err.message || 'خطا در افزودن مورد چک‌لیست');
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask || !newComment.trim()) return;
    try {
      await api.addTaskComment(selectedTask.id, newComment.trim());
      setNewComment('');
      const refreshed = await api.getTaskDetail(selectedTask.id);
      setSelectedTask(refreshed);
    } catch (err: any) {
      alert(err.message || 'خطا در ثبت نظر');
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black text-white tracking-tight">کارتابل و مدیریت وظایف</h1>
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            پیگیری کارهای روزمره انبار، بسته‌بندی، تولید محتوا و فروش با چک‌لیست هوشمند
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="bg-white/[0.04] p-1 rounded-2xl flex items-center gap-1 border border-white/[0.07]">
            <button
              onClick={() => setViewMode('kanban')}
              className={cn(
                'p-2 rounded-xl text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer',
                viewMode === 'kanban'
                  ? 'bg-blue-600 text-white shadow-[0_0_15px_rgba(37,99,235,0.5)] font-bold'
                  : 'text-slate-400 hover:text-white'
              )}
            >
              <Columns className="w-3.5 h-3.5" />
              <span>برد کانبان</span>
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'p-2 rounded-xl text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer',
                viewMode === 'list'
                  ? 'bg-blue-600 text-white shadow-[0_0_15px_rgba(37,99,235,0.5)] font-bold'
                  : 'text-slate-400 hover:text-white'
              )}
            >
              <ListTodo className="w-3.5 h-3.5" />
              <span>لیست جدولی</span>
            </button>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2.5 rounded-xl font-bold shadow-[0_0_18px_rgba(37,99,235,0.45)] transition-all text-xs cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>ایجاد وظیفه جدید</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-[11px] text-slate-400 block font-medium">کل وظایف</span>
            <strong className="text-xl font-black text-white block">{summary.total}</strong>
          </div>
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-[11px] text-cyan-400 block font-medium">در حال انجام</span>
            <strong className="text-xl font-black text-cyan-300 block">{summary.in_progress}</strong>
          </div>
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-[11px] text-amber-400 block font-medium">در انتظار بازبینی</span>
            <strong className="text-xl font-black text-amber-300 block">{summary.in_review}</strong>
          </div>
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-[11px] text-emerald-400 block font-medium">تکمیل شده</span>
            <strong className="text-xl font-black text-emerald-300 block">{summary.completed}</strong>
          </div>
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-[11px] text-rose-400 block font-medium">مهلت گذشته</span>
            <strong className="text-xl font-black text-rose-300 block">{summary.overdue}</strong>
          </div>
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-[11px] text-indigo-400 block font-medium">کارهای من</span>
            <strong className="text-xl font-black text-indigo-300 block">{summary.my_tasks}</strong>
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div className="glass-card p-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setFilterMyTasks(!filterMyTasks)}
            className={cn(
              'px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border cursor-pointer',
              filterMyTasks
                ? 'bg-blue-600/25 border-cyan-400/40 text-cyan-300 shadow-[0_0_12px_rgba(56,189,248,0.3)]'
                : 'bg-white/[0.04] text-slate-300 border-white/[0.08] hover:bg-white/[0.08]'
            )}
          >
            👤 وظایف اختصاص‌یافته به من
          </button>

          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="px-3 py-1.5 rounded-xl border border-white/[0.09] text-xs bg-[#0e1628] text-slate-200 focus:outline-none cursor-pointer"
          >
            <option value="">همه دسته‌بندی‌ها</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>

          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
            className="px-3 py-1.5 rounded-xl border border-white/[0.09] text-xs bg-[#0e1628] text-slate-200 focus:outline-none cursor-pointer"
          >
            <option value="">همه اولویت‌ها</option>
            <option value="LOW">پایین</option>
            <option value="MEDIUM">متوسط</option>
            <option value="HIGH">بالا</option>
            <option value="URGENT">فوری و اضطراری</option>
          </select>
        </div>

        <span className="text-xs text-slate-400">
          تعداد وظایف: <strong className="text-white">{tasks.length}</strong>
        </span>
      </div>

      {/* Kanban Board View */}
      {viewMode === 'kanban' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {COLUMNS.map((col) => {
            const colTasks = tasks.filter((t) => t.status === col.id);
            return (
              <div
                key={col.id}
                className={cn('border rounded-3xl p-3.5 flex flex-col min-h-[500px]', col.color)}
              >
                <div className="flex items-center justify-between pb-3 border-b border-white/[0.07] mb-3">
                  <h3 className="font-bold text-xs text-white tracking-wide">{col.title}</h3>
                  <span className={cn('text-[11px] font-bold px-2 py-0.5 rounded-full border border-white/[0.08]', col.badge)}>
                    {colTasks.length}
                  </span>
                </div>

                <div className="space-y-3 flex-1 overflow-y-auto">
                  {colTasks.map((task) => (
                    <div
                      key={task.id}
                      onClick={() => handleOpenDetail(task.id)}
                      className="bg-[#0e1526]/85 border border-white/[0.08] hover:border-cyan-400/50 rounded-2xl p-3.5 shadow-md hover:shadow-[0_0_15px_rgba(56,189,248,0.2)] transition-all cursor-pointer group"
                    >
                      <div className="flex items-start justify-between gap-2">
                        {task.category_name && (
                          <span
                            className="text-[10px] font-semibold px-2 py-0.5 rounded-md text-white"
                            style={{ backgroundColor: task.category_color || '#3B82F6' }}
                          >
                            {task.category_name}
                          </span>
                        )}
                        <span
                          className={cn(
                            'text-[10px] font-bold px-1.5 py-0.5 rounded',
                            task.priority === 'URGENT'
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                              : task.priority === 'HIGH'
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                              : 'bg-white/[0.05] text-slate-400'
                          )}
                        >
                          {task.priority_display}
                        </span>
                      </div>

                      <h4 className="font-bold text-xs text-slate-200 mt-2 line-clamp-2 leading-relaxed group-hover:text-cyan-300 transition-colors">
                        {task.title}
                      </h4>

                      <div className="mt-3 pt-2.5 border-t border-white/[0.06] flex items-center justify-between text-[11px] text-slate-400">
                        <div className="flex items-center gap-1.5 truncate">
                          <User className="w-3 h-3 text-slate-400 shrink-0" />
                          <span className="truncate">{task.assignee_name || 'بدون مسئول'}</span>
                        </div>

                        {task.checklist_total > 0 && (
                          <span className="text-[10px] bg-white/[0.05] border border-white/[0.08] px-1.5 py-0.5 rounded text-slate-300 font-medium">
                            {task.checklist_completed}/{task.checklist_total} ✓
                          </span>
                        )}
                      </div>

                      {task.due_date && (
                        <div
                          className={cn(
                            'mt-2 text-[10px] flex items-center gap-1 font-medium',
                            task.is_overdue ? 'text-rose-400 font-bold' : 'text-slate-400'
                          )}
                        >
                          <Clock className="w-3 h-3" />
                          <span>مهلت: {task.due_date}</span>
                          {task.is_overdue && <span>(معوق)</span>}
                        </div>
                      )}

                      {task.requires_verification && (
                        <div className="mt-2 text-[10px] text-indigo-300 bg-indigo-500/15 border border-indigo-500/30 px-2 py-0.5 rounded flex items-center gap-1 font-semibold">
                          <ShieldCheck className="w-3 h-3" />
                          <span>الزام تأیید ناظر</span>
                        </div>
                      )}
                    </div>
                  ))}

                  {colTasks.length === 0 && (
                    <div className="h-28 flex items-center justify-center text-xs text-slate-500 border border-dashed border-white/[0.08] rounded-2xl">
                      وظیفه‌ای وجود ندارد
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* List View */
        <div className="glass-card overflow-hidden">
          <table className="w-full text-right text-xs">
            <thead className="bg-white/[0.03] text-slate-400 border-b border-white/[0.06]">
              <tr>
                <th className="py-3 px-4">عنوان وظیفه</th>
                <th className="py-3 px-4">دسته‌بندی</th>
                <th className="py-3 px-4">اولویت</th>
                <th className="py-3 px-4">وضعیت</th>
                <th className="py-3 px-4">مسئول انجام</th>
                <th className="py-3 px-4">مهلت</th>
                <th className="py-3 px-4">چک‌لیست</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04] text-slate-300">
              {tasks.map((task) => (
                <tr
                  key={task.id}
                  onClick={() => handleOpenDetail(task.id)}
                  className="hover:bg-white/[0.03] cursor-pointer transition-colors"
                >
                  <td className="py-3 px-4 font-bold text-white">{task.title}</td>
                  <td className="py-3 px-4">{task.category_name || '-'}</td>
                  <td className="py-3 px-4 font-semibold">{task.priority_display}</td>
                  <td className="py-3 px-4">
                    <span className="bg-white/[0.05] border border-white/[0.08] text-slate-300 px-2 py-0.5 rounded-full text-[11px]">
                      {task.status_display}
                    </span>
                  </td>
                  <td className="py-3 px-4">{task.assignee_name || 'بدون مسئول'}</td>
                  <td className="py-3 px-4">{task.due_date || '-'}</td>
                  <td className="py-3 px-4">
                    {task.checklist_total > 0 ? `${task.checklist_completed}/${task.checklist_total}` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Task Detail Drawer */}
      {selectedTask && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-md flex justify-end">
          <div className="bg-[#0b101d] w-full max-w-xl h-full shadow-2xl p-6 overflow-y-auto border-r border-white/10 flex flex-col justify-between">
            <div>
              {/* Header */}
              <div className="flex items-start justify-between border-b border-white/[0.08] pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        'text-xs font-bold px-2.5 py-0.5 rounded-full',
                        selectedTask.priority === 'URGENT'
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          : 'bg-white/[0.05] text-slate-400'
                      )}
                    >
                      {selectedTask.priority_display}
                    </span>
                    {selectedTask.category_name && (
                      <span className="text-xs font-semibold bg-blue-500/20 text-cyan-300 border border-cyan-400/30 px-2.5 py-0.5 rounded-full">
                        {selectedTask.category_name}
                      </span>
                    )}
                  </div>
                  <h2 className="text-lg font-black text-white mt-2">{selectedTask.title}</h2>
                </div>
                <button
                  onClick={() => setSelectedTask(null)}
                  className="text-slate-400 hover:text-white p-1 rounded-lg cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Status Switcher Bar */}
              <div className="mt-4 p-3 bg-white/[0.03] rounded-2xl border border-white/[0.06] flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300">وضعیت فعلی:</span>
                <div className="flex items-center gap-1.5">
                  {COLUMNS.map((col) => (
                    <button
                      key={col.id}
                      onClick={() => handleStatusChange(col.id)}
                      className={cn(
                        'text-xs px-2.5 py-1 rounded-xl font-semibold transition-all cursor-pointer',
                        selectedTask.status === col.id
                          ? 'bg-blue-600 text-white shadow-[0_0_12px_rgba(37,99,235,0.6)] font-bold'
                          : 'bg-white/[0.04] text-slate-400 hover:text-white border border-white/[0.06]'
                      )}
                    >
                      {col.title}
                    </button>
                  ))}
                </div>
              </div>

              {/* Details & Metadata */}
              <div className="mt-5 grid grid-cols-2 gap-4 text-xs bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4">
                <div>
                  <span className="text-slate-400 block">مسئول انجام:</span>
                  <strong className="text-slate-200 mt-0.5 block">{selectedTask.assignee_name || 'تخصیص‌نیافته'}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block">ناظر / تاییدکننده:</span>
                  <strong className="text-slate-200 mt-0.5 block">{selectedTask.reviewer_name || 'مالک فروشگاه'}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block">مهلت انجام:</span>
                  <strong className={cn('mt-0.5 block', selectedTask.is_overdue ? 'text-rose-400' : 'text-slate-200')}>
                    {selectedTask.due_date || 'تعیین نشده'}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-400 block">ثبت‌کننده:</span>
                  <strong className="text-slate-200 mt-0.5 block">{selectedTask.creator_name}</strong>
                </div>
              </div>

              {/* Description */}
              {selectedTask.description && (
                <div className="mt-5">
                  <h4 className="text-xs font-bold text-slate-300 mb-1.5">دستورالعمل و توضیحات:</h4>
                  <p className="text-xs text-slate-300 leading-relaxed bg-white/[0.02] p-3 rounded-2xl border border-white/[0.05]">
                    {selectedTask.description}
                  </p>
                </div>
              )}

              {/* Checklist Section */}
              <div className="mt-6">
                <h4 className="text-xs font-bold text-white mb-3 flex items-center justify-between">
                  <span>چک‌لیست مراحل انجام</span>
                  <span className="text-[11px] text-slate-400 font-semibold">
                    {(selectedTask.checklist_items || []).filter((i) => i.is_completed).length} از {(selectedTask.checklist_items || []).length} انجام شده
                  </span>
                </h4>

                <div className="space-y-2">
                  {(selectedTask.checklist_items || []).map((item) => (
                    <div
                      key={item.id}
                      onClick={() => handleToggleChecklist(item.id)}
                      className={cn(
                        'flex items-center gap-2.5 p-2.5 rounded-xl border text-xs cursor-pointer transition-all',
                        item.is_completed
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-slate-400 line-through'
                          : 'bg-white/[0.03] border-white/[0.08] text-slate-200 hover:border-cyan-400/50'
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={item.is_completed}
                        readOnly
                        className="rounded border-white/20 text-blue-600 focus:ring-0"
                      />
                      <span>{item.title}</span>
                    </div>
                  ))}
                </div>

                <form onSubmit={handleAddChecklist} className="mt-3 flex gap-2">
                  <input
                    type="text"
                    placeholder="مورد جدید به چک‌لیست..."
                    value={newChecklistTitle}
                    onChange={(e) => setNewChecklistTitle(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400/60"
                  />
                  <button
                    type="submit"
                    className="px-3 py-2 bg-white/[0.08] hover:bg-white/[0.14] text-white text-xs font-semibold rounded-xl cursor-pointer"
                  >
                    افزودن
                  </button>
                </form>
              </div>

              {/* Review & Verification Section */}
              {selectedTask.requires_verification && selectedTask.status === 'IN_REVIEW' && (
                <div className="mt-6 p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl">
                  <h4 className="text-xs font-bold text-amber-300 flex items-center gap-1.5 mb-2">
                    <ShieldCheck className="w-4 h-4 text-amber-400" />
                    وظیفه آماده بازبینی و تأیید ناظر است
                  </h4>
                  {selectedTask.completion_evidence && (
                    <p className="text-xs text-amber-200 mb-3 bg-black/20 p-2.5 rounded-xl border border-amber-500/20">
                      <strong>شواهد ثبت‌شده توسط همکار:</strong> {selectedTask.completion_evidence}
                    </p>
                  )}
                  <input
                    type="text"
                    placeholder="بازخورد یا نکات اصلاحی..."
                    value={reviewFeedback}
                    onChange={(e) => setReviewFeedback(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-amber-500/30 text-xs bg-black/30 text-white mb-3 focus:outline-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleVerify(true)}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold shadow-[0_0_12px_rgba(16,185,129,0.4)] flex-1 cursor-pointer"
                    >
                      ✓ تأیید نهایی
                    </button>
                    <button
                      onClick={() => handleVerify(false)}
                      className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-bold shadow-[0_0_12px_rgba(244,63,94,0.4)] flex-1 cursor-pointer"
                    >
                      ✕ درخواست اصلاحات
                    </button>
                  </div>
                </div>
              )}

              {/* Comments Discussion */}
              <div className="mt-8 border-t border-white/[0.08] pt-5">
                <h4 className="text-xs font-bold text-white mb-3 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-cyan-400" />
                  <span>گفتگو و یادداشت‌های همکاران</span>
                </h4>

                <div className="space-y-3 mb-4">
                  {(selectedTask.comments || []).map((comment) => (
                    <div key={comment.id} className="bg-white/[0.03] p-3 rounded-2xl border border-white/[0.06] text-xs">
                      <div className="flex justify-between items-center text-[10px] text-slate-400 mb-1">
                        <strong className="text-slate-200">{comment.author_name}</strong>
                        <span>{comment.created_at?.slice(0, 10)}</span>
                      </div>
                      <p className="text-slate-300">{comment.content}</p>
                    </div>
                  ))}
                  {(selectedTask.comments || []).length === 0 && (
                    <p className="text-xs text-slate-500 py-2">هنوز نظری ثبت نشده است.</p>
                  )}
                </div>

                <form onSubmit={handleAddComment} className="flex gap-2">
                  <input
                    type="text"
                    placeholder="نوشتن نظر یا توضیح جدید..."
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400/60"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl flex items-center gap-1 shadow-[0_0_12px_rgba(37,99,235,0.4)] cursor-pointer"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>ارسال</span>
                  </button>
                </form>
              </div>
            </div>

            <div className="pt-4 border-t border-white/[0.08] mt-6">
              <button
                onClick={() => setSelectedTask(null)}
                className="w-full py-2.5 bg-white/[0.06] hover:bg-white/[0.12] text-white font-medium rounded-xl text-xs cursor-pointer"
              >
                بستن پنجره
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Task Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#0b101d] rounded-3xl shadow-2xl max-w-xl w-full p-6 border border-white/10 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-4">
              <h3 className="font-bold text-base text-white flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-cyan-400" />
                تعریف وظیفه جدید
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-white p-1 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">عنوان وظیفه *</label>
                <input
                  type="text"
                  required
                  placeholder="مثلاً: فیلمبرداری ریلز، شمارش موجودی انبار..."
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400/60"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">توضیحات و دستورالعمل</label>
                <textarea
                  rows={3}
                  placeholder="جزئیات و نکات کلیدی برای همکار مسئول..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400/60"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">دسته‌بندی</label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-white/[0.1] text-xs bg-[#0e1628] text-white focus:outline-none cursor-pointer"
                  >
                    <option value="">بدون دسته‌بندی</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">اولویت انجام</label>
                  <select
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-white/[0.1] text-xs bg-[#0e1628] text-white focus:outline-none cursor-pointer"
                  >
                    <option value="LOW">پایین</option>
                    <option value="MEDIUM">متوسط</option>
                    <option value="HIGH">بالا</option>
                    <option value="URGENT">فوری / اضطراری</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">مسئول انجام</label>
                  <select
                    value={newAssignee}
                    onChange={(e) => setNewAssignee(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-white/[0.1] text-xs bg-[#0e1628] text-white focus:outline-none cursor-pointer"
                  >
                    <option value="">انتخاب نشده</option>
                    {teamMembers.map((m) => (
                      <option key={m.user} value={m.user}>
                        {m.user_name || m.user_email} ({m.role_display})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">مهلت انجام</label>
                  <input
                    type="date"
                    value={newDueDate}
                    onChange={(e) => setNewDueDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-white/[0.1] text-xs bg-[#0e1628] text-white focus:outline-none cursor-pointer"
                  />
                </div>
              </div>

              <div>
                <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-slate-300">
                  <input
                    type="checkbox"
                    checked={newRequiresVerification}
                    onChange={(e) => setNewRequiresVerification(e.target.checked)}
                    className="rounded border-white/20 text-blue-600 focus:ring-0"
                  />
                  <span>الزام تأیید ناظر (وظیفه قبل از تکمیل، به مرحله بازبینی می‌رود)</span>
                </label>
              </div>

              {/* Checklist items creation */}
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">چک‌لیست مراحل اولیه</label>
                <div className="space-y-2">
                  {newChecklist.map((item, idx) => (
                    <input
                      key={idx}
                      type="text"
                      placeholder={`مرحله ${idx + 1}...`}
                      value={item}
                      onChange={(e) => {
                        const updated = [...newChecklist];
                        updated[idx] = e.target.value;
                        setNewChecklist(updated);
                      }}
                      className="w-full px-3 py-2 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs text-white placeholder-slate-500 focus:outline-none"
                    />
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setNewChecklist([...newChecklist, ''])}
                  className="mt-2 text-xs text-cyan-400 hover:text-cyan-300 font-bold cursor-pointer"
                >
                  + افزودن مرحله دیگر به چک‌لیست
                </button>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white cursor-pointer"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white shadow-[0_0_15px_rgba(37,99,235,0.4)] cursor-pointer"
                >
                  ایجاد وظیفه
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
