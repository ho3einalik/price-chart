'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
  CheckSquare,
  Plus,
  Clock,
  AlertTriangle,
  User,
  CheckCircle2,
  Calendar,
  Filter,
  MessageSquare,
  Send,
  X,
  FileText,
  ShieldCheck,
  ChevronRight,
  ListTodo,
  Columns
} from 'lucide-react';

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
  { id: 'TODO', title: 'در انتظار انجام', color: 'border-slate-300 bg-slate-50/50' },
  { id: 'IN_PROGRESS', title: 'در حال انجام', color: 'border-sky-300 bg-sky-50/30' },
  { id: 'IN_REVIEW', title: 'در انتظار بازبینی و تأیید', color: 'border-amber-300 bg-amber-50/30' },
  { id: 'COMPLETED', title: 'تکمیل شده', color: 'border-emerald-300 bg-emerald-50/30' },
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
  const [newReviewer, setNewReviewer] = useState('');
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
        reviewer: newReviewer || null,
        due_date: newDueDate || null,
        requires_verification: newRequiresVerification,
        checklist_items: newChecklist.filter((c) => c.trim().length > 0),
      });

      setShowCreateModal(false);
      resetCreateForm();
      loadInitialData();
    } catch (err: any) {
      alert(err.message || 'خطا در ثبت وظیفه');
    }
  };

  const resetCreateForm = () => {
    setNewTitle('');
    setNewDesc('');
    setNewCategory('');
    setNewPriority('MEDIUM');
    setNewAssignee('');
    setNewReviewer('');
    setNewDueDate('');
    setNewRequiresVerification(false);
    setNewChecklist(['']);
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
    <div className="space-y-6 animate-fadeIn">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-800 flex items-center gap-3">
            <CheckSquare className="w-7 h-7 text-sky-600" />
            کارتابل و مدیریت هوشمند وظایف
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            پیگیری کارهای روزمره انبار، بسته‌بندی، تولید محتوا و فروش با قابلیت چک‌لیست و تأیید ناظر
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="bg-slate-100 p-1 rounded-xl flex items-center gap-1 border border-slate-200">
            <button
              onClick={() => setViewMode('kanban')}
              className={`p-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                viewMode === 'kanban' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <Columns className="w-4 h-4" />
              <span>برد کانبان</span>
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                viewMode === 'list' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <ListTodo className="w-4 h-4" />
              <span>لیست جدولی</span>
            </button>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 bg-sky-600 hover:bg-sky-700 text-white px-4 py-2.5 rounded-xl font-medium shadow-sm transition-all text-sm"
          >
            <Plus className="w-4 h-4" />
            <span>ایجاد وظیفه جدید</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm">
            <span className="text-xs text-slate-500 block">کل وظایف</span>
            <strong className="text-xl font-black text-slate-800 mt-1 block">{summary.total}</strong>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm">
            <span className="text-xs text-sky-600 font-semibold block">در حال انجام</span>
            <strong className="text-xl font-black text-sky-700 mt-1 block">{summary.in_progress}</strong>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm">
            <span className="text-xs text-amber-600 font-semibold block">در انتظار بازبینی</span>
            <strong className="text-xl font-black text-amber-700 mt-1 block">{summary.in_review}</strong>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm">
            <span className="text-xs text-emerald-600 font-semibold block">تکمیل شده</span>
            <strong className="text-xl font-black text-emerald-700 mt-1 block">{summary.completed}</strong>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm">
            <span className="text-xs text-rose-600 font-semibold block">مهلت گذشته (معوق)</span>
            <strong className="text-xl font-black text-rose-700 mt-1 block">{summary.overdue}</strong>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm">
            <span className="text-xs text-indigo-600 font-semibold block">کارهای من</span>
            <strong className="text-xl font-black text-indigo-700 mt-1 block">{summary.my_tasks}</strong>
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white border border-slate-200 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setFilterMyTasks(!filterMyTasks)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
              filterMyTasks
                ? 'bg-sky-50 text-sky-700 border-sky-300'
                : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
            }`}
          >
            👤 وظایف اختصاص‌یافته به من
          </button>

          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-xs bg-white text-slate-700 focus:outline-none"
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
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-xs bg-white text-slate-700 focus:outline-none"
          >
            <option value="">همه اولویت‌ها</option>
            <option value="LOW">پایین</option>
            <option value="MEDIUM">متوسط</option>
            <option value="HIGH">بالا</option>
            <option value="URGENT">فوری و اضطراری</option>
          </select>
        </div>

        <span className="text-xs text-slate-400">
          تعداد وظایف: <strong className="text-slate-700">{tasks.length}</strong>
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
                className={`border rounded-2xl p-3 flex flex-col min-h-[500px] ${col.color}`}
              >
                <div className="flex items-center justify-between pb-3 border-b border-slate-200 mb-3">
                  <h3 className="font-bold text-sm text-slate-800">{col.title}</h3>
                  <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-white text-slate-600 border border-slate-200 shadow-2xs">
                    {colTasks.length}
                  </span>
                </div>

                <div className="space-y-3 flex-1 overflow-y-auto">
                  {colTasks.map((task) => (
                    <div
                      key={task.id}
                      onClick={() => handleOpenDetail(task.id)}
                      className="bg-white border border-slate-200/80 rounded-xl p-3.5 shadow-xs hover:shadow-md transition-all cursor-pointer group"
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
                          className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                            task.priority === 'URGENT'
                              ? 'bg-rose-100 text-rose-700'
                              : task.priority === 'HIGH'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {task.priority_display}
                        </span>
                      </div>

                      <h4 className="font-bold text-xs text-slate-800 mt-2 line-clamp-2 leading-relaxed group-hover:text-sky-600 transition-colors">
                        {task.title}
                      </h4>

                      <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                        <div className="flex items-center gap-1.5 truncate">
                          <User className="w-3 h-3 text-slate-400 shrink-0" />
                          <span className="truncate">{task.assignee_name || 'بدون مسئول'}</span>
                        </div>

                        {task.checklist_total > 0 && (
                          <span className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded text-slate-600 font-medium">
                            {task.checklist_completed}/{task.checklist_total} ✓
                          </span>
                        )}
                      </div>

                      {task.due_date && (
                        <div
                          className={`mt-2 text-[10px] flex items-center gap-1 font-medium ${
                            task.is_overdue ? 'text-rose-600' : 'text-slate-400'
                          }`}
                        >
                          <Clock className="w-3 h-3" />
                          <span>مهلت: {task.due_date}</span>
                          {task.is_overdue && <span className="text-rose-600 font-bold">(معوق)</span>}
                        </div>
                      )}

                      {task.requires_verification && (
                        <div className="mt-2 text-[10px] text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded flex items-center gap-1 font-semibold">
                          <ShieldCheck className="w-3 h-3" />
                          <span>الزام تأیید ناظر</span>
                        </div>
                      )}
                    </div>
                  ))}

                  {colTasks.length === 0 && (
                    <div className="h-28 flex items-center justify-center text-xs text-slate-400 border border-dashed border-slate-200 rounded-xl">
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
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
          <table className="w-full text-right text-xs">
            <thead className="bg-slate-50 text-slate-600 border-b border-slate-200">
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
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {tasks.map((task) => (
                <tr
                  key={task.id}
                  onClick={() => handleOpenDetail(task.id)}
                  className="hover:bg-slate-50/70 cursor-pointer"
                >
                  <td className="py-3 px-4 font-bold text-slate-800">{task.title}</td>
                  <td className="py-3 px-4">{task.category_name || '-'}</td>
                  <td className="py-3 px-4 font-semibold">{task.priority_display}</td>
                  <td className="py-3 px-4">
                    <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full text-[11px]">
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

      {/* Task Detail Drawer / Modal */}
      {selectedTask && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex justify-end">
          <div className="bg-white w-full max-w-xl h-full shadow-2xl p-6 overflow-y-auto animate-slideLeft border-r border-slate-200 flex flex-col justify-between">
            <div>
              {/* Header */}
              <div className="flex items-start justify-between border-b border-slate-100 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                        selectedTask.priority === 'URGENT'
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {selectedTask.priority_display}
                    </span>
                    {selectedTask.category_name && (
                      <span className="text-xs font-semibold bg-sky-50 text-sky-700 px-2.5 py-0.5 rounded-full">
                        {selectedTask.category_name}
                      </span>
                    )}
                  </div>
                  <h2 className="text-lg font-black text-slate-800 mt-2">{selectedTask.title}</h2>
                </div>
                <button
                  onClick={() => setSelectedTask(null)}
                  className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Status Switcher Bar */}
              <div className="mt-4 p-3 bg-slate-50 rounded-xl border border-slate-100 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">وضعیت فعلی:</span>
                <div className="flex items-center gap-1.5">
                  {COLUMNS.map((col) => (
                    <button
                      key={col.id}
                      onClick={() => handleStatusChange(col.id)}
                      className={`text-xs px-2.5 py-1 rounded-lg font-semibold transition-all ${
                        selectedTask.status === col.id
                          ? 'bg-sky-600 text-white shadow-xs'
                          : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {col.title}
                    </button>
                  ))}
                </div>
              </div>

              {/* Details & Metadata */}
              <div className="mt-5 grid grid-cols-2 gap-4 text-xs bg-white border border-slate-100 rounded-xl p-4">
                <div>
                  <span className="text-slate-400 block">مسئول انجام:</span>
                  <strong className="text-slate-800 mt-0.5 block">{selectedTask.assignee_name || 'تخصیص‌نیافته'}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block">ناظر / تاییدکننده:</span>
                  <strong className="text-slate-800 mt-0.5 block">{selectedTask.reviewer_name || 'مالک فروشگاه'}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block">مهلت انجام:</span>
                  <strong className={`mt-0.5 block ${selectedTask.is_overdue ? 'text-rose-600' : 'text-slate-800'}`}>
                    {selectedTask.due_date || 'تعیین نشده'}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-400 block">ثبت‌کننده:</span>
                  <strong className="text-slate-800 mt-0.5 block">{selectedTask.creator_name}</strong>
                </div>
              </div>

              {/* Description */}
              {selectedTask.description && (
                <div className="mt-5">
                  <h4 className="text-xs font-bold text-slate-700 mb-1.5">دستورالعمل و توضیحات:</h4>
                  <p className="text-xs text-slate-600 leading-relaxed bg-slate-50/70 p-3 rounded-xl border border-slate-100">
                    {selectedTask.description}
                  </p>
                </div>
              )}

              {/* Checklist Section */}
              <div className="mt-6">
                <h4 className="text-xs font-bold text-slate-800 mb-3 flex items-center justify-between">
                  <span>چک‌لیست مراحل انجام</span>
                  <span className="text-[11px] text-slate-500 font-semibold">
                    {selectedTask.checklist_items.filter((i) => i.is_completed).length} از {selectedTask.checklist_items.length} انجام شده
                  </span>
                </h4>

                <div className="space-y-2">
                  {selectedTask.checklist_items.map((item) => (
                    <div
                      key={item.id}
                      onClick={() => handleToggleChecklist(item.id)}
                      className={`flex items-center gap-2.5 p-2.5 rounded-xl border text-xs cursor-pointer transition-all ${
                        item.is_completed
                          ? 'bg-emerald-50/50 border-emerald-200 text-slate-500 line-through'
                          : 'bg-white border-slate-200 text-slate-800 hover:border-sky-300'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={item.is_completed}
                        readOnly
                        className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
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
                    className="flex-1 px-3 py-1.5 rounded-xl border border-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
                  />
                  <button
                    type="submit"
                    className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl"
                  >
                    افزودن
                  </button>
                </form>
              </div>

              {/* Review & Verification Section */}
              {selectedTask.requires_verification && selectedTask.status === 'IN_REVIEW' && (
                <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-2xl">
                  <h4 className="text-xs font-bold text-amber-900 flex items-center gap-1.5 mb-2">
                    <ShieldCheck className="w-4 h-4 text-amber-700" />
                    وظیفه آماده بازبینی و تأیید ناظر است
                  </h4>
                  {selectedTask.completion_evidence && (
                    <p className="text-xs text-amber-800 mb-3 bg-white/70 p-2 rounded-lg">
                      <strong>شواهد ثبت‌شده توسط همکار:</strong> {selectedTask.completion_evidence}
                    </p>
                  )}
                  <input
                    type="text"
                    placeholder="بازخورد یا نکات اصلاحی..."
                    value={reviewFeedback}
                    onChange={(e) => setReviewFeedback(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-amber-300 text-xs bg-white mb-3 focus:outline-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleVerify(true)}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-xs flex-1"
                    >
                      ✓ تأیید نهایی و اتمام وظیفه
                    </button>
                    <button
                      onClick={() => handleVerify(false)}
                      className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold shadow-xs flex-1"
                    >
                      ✕ درخواست اصلاحات
                    </button>
                  </div>
                </div>
              )}

              {/* Comments Discussion */}
              <div className="mt-8 border-t border-slate-100 pt-5">
                <h4 className="text-xs font-bold text-slate-800 mb-3 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-slate-500" />
                  <span>گفتگو و یادداشت‌های همکاران</span>
                </h4>

                <div className="space-y-3 mb-4">
                  {selectedTask.comments.map((comment) => (
                    <div key={comment.id} className="bg-slate-50 p-3 rounded-xl border border-slate-100 text-xs">
                      <div className="flex justify-between items-center text-[10px] text-slate-400 mb-1">
                        <strong className="text-slate-700">{comment.author_name}</strong>
                        <span>{comment.created_at?.slice(0, 10)}</span>
                      </div>
                      <p className="text-slate-700">{comment.content}</p>
                    </div>
                  ))}
                  {selectedTask.comments.length === 0 && (
                    <p className="text-xs text-slate-400 py-2">هنوز نظری ثبت نشده است.</p>
                  )}
                </div>

                <form onSubmit={handleAddComment} className="flex gap-2">
                  <input
                    type="text"
                    placeholder="نوشتن نظر یا توضیح جدید..."
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-xl border border-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold rounded-xl flex items-center gap-1 shadow-xs"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>ارسال</span>
                  </button>
                </form>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 mt-6">
              <button
                onClick={() => setSelectedTask(null)}
                className="w-full py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium rounded-xl text-xs"
              >
                بستن پنجره
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Task Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-xl w-full p-6 animate-scaleIn border border-slate-200 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2">
                <CheckSquare className="w-5 h-5 text-sky-600" />
                تعریف وظیفه جدید
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">عنوان وظیفه *</label>
                <input
                  type="text"
                  required
                  placeholder="مثلاً: فیلمبرداری ریلز مانتو، شمارش موجودی انبار..."
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">توضیحات و دستورالعمل</label>
                <textarea
                  rows={3}
                  placeholder="جزئیات و نکات کلیدی برای همکار مسئول..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">دسته‌بندی</label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
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
                  <label className="block text-xs font-bold text-slate-700 mb-1">اولویت انجام</label>
                  <select
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
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
                  <label className="block text-xs font-bold text-slate-700 mb-1">مسئول انجام</label>
                  <select
                    value={newAssignee}
                    onChange={(e) => setNewAssignee(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
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
                  <label className="block text-xs font-bold text-slate-700 mb-1">مهلت انجام (Deadline)</label>
                  <input
                    type="date"
                    value={newDueDate}
                    onChange={(e) => setNewDueDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                  />
                </div>
              </div>

              <div>
                <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-slate-700">
                  <input
                    type="checkbox"
                    checked={newRequiresVerification}
                    onChange={(e) => setNewRequiresVerification(e.target.checked)}
                    className="rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                  />
                  <span>الزام تأیید ناظر (وظیفه قبل از تکمیل، به مرحله بازبینی می‌رود)</span>
                </label>
              </div>

              {/* Checklist items creation */}
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">چک‌لیست مراحل اولیه</label>
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
                      className="w-full px-3 py-1.5 rounded-xl border border-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
                    />
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setNewChecklist([...newChecklist, ''])}
                  className="mt-2 text-xs text-sky-600 hover:text-sky-700 font-bold"
                >
                  + افزودن مرحله دیگر به چک‌لیست
                </button>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-100"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-sky-600 hover:bg-sky-700 text-white shadow-sm"
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
