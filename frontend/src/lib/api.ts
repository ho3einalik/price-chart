const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

class ApiClient {
  private getHeaders(extraHeaders: Record<string, string> = {}): HeadersInit {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...extraHeaders,
    };

    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('shoppilot_access_token');
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      const activeStoreId = localStorage.getItem('shoppilot_active_store_id');
      if (activeStoreId) {
        headers['x-store-id'] = activeStoreId;
      }
    }
    return headers;
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const headers = this.getHeaders(options.headers as Record<string, string>);

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 401 && typeof window !== 'undefined') {
      // Token expired or invalid
      // localStorage.removeItem('shoppilot_access_token');
    }

    if (!response.ok) {
      let errorMsg = `Error ${response.status}: ${response.statusText}`;
      try {
        const errorData = await response.json();
        errorMsg = errorData.error || errorData.detail || JSON.stringify(errorData);
      } catch {}
      throw new Error(errorMsg);
    }

    return response.json();
  }

  // Auth
  async login(credentials: { email?: string; phone_number?: string; password: string }) {
    return this.request<{ user: any; access: string; refresh: string }>('/auth/login/', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  }

  async register(data: { email?: string; phone_number?: string; full_name: string; password: string; business_name?: string }) {
    return this.request<{ user: any; access: string; refresh: string }>('/auth/register/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getMe() {
    return this.request<any>('/auth/me/');
  }

  // Tenancy
  async getStores() {
    return this.request<{ results: any[] } | any[]>('/tenancy/stores/');
  }

  async createStore(data: { name: string; currency?: string }) {
    return this.request<any>('/tenancy/stores/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Analytics
  async getOverviewMetrics(days: number = 30) {
    return this.request<any>(`/analytics/overview/?days=${days}`);
  }

  // Daily Action Center
  async getDailyActions() {
    return this.request<{ results: any[] } | any[]>('/daily-actions/');
  }

  async updateDailyActionStatus(id: string, status: string, note?: string) {
    return this.request<any>(`/daily-actions/${id}/update-status/`, {
      method: 'POST',
      body: JSON.stringify({ status, resolution_note: note || '' }),
    });
  }

  // Catalog
  async getProducts(params?: { search?: string; status?: string; category?: string }) {
    const q = new URLSearchParams();
    if (params?.search) q.append('search', params.search);
    if (params?.status) q.append('status', params.status);
    if (params?.category) q.append('category', params.category);
    return this.request<{ results: any[] } | any[]>(`/catalog/products/?${q.toString()}`);
  }

  async getCategories() {
    return this.request<{ results: any[] } | any[]>('/catalog/categories/');
  }

  async createProduct(data: any) {
    return this.request<any>('/catalog/products/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Inventory
  async getInventoryBalances(params?: { low_stock?: boolean; warehouse?: string; search?: string }) {
    const q = new URLSearchParams();
    if (params?.low_stock) q.append('low_stock', 'true');
    if (params?.warehouse) q.append('warehouse', params.warehouse);
    if (params?.search) q.append('search', params.search);
    return this.request<{ results: any[] } | any[]>(`/inventory/balances/?${q.toString()}`);
  }

  async getWarehouses() {
    return this.request<{ results: any[] } | any[]>('/inventory/warehouses/');
  }

  async adjustStock(data: { warehouse_id: string; variant_id: string; new_on_hand: number; reason?: string }) {
    return this.request<any>('/inventory/adjustments/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getReorderSuggestions() {
    return this.request<any[]>('/inventory/reorder-suggestions/');
  }

  // Orders
  async getOrders(params?: { order_status?: string; payment_status?: string; channel?: string; search?: string }) {
    const q = new URLSearchParams();
    if (params?.order_status) q.append('order_status', params.order_status);
    if (params?.payment_status) q.append('payment_status', params.payment_status);
    if (params?.channel) q.append('channel', params.channel);
    if (params?.search) q.append('search', params.search);
    return this.request<{ results: any[] } | any[]>(`/orders/?${q.toString()}`);
  }

  async getOrder(id: string) {
    return this.request<any>(`/orders/${id}/`);
  }

  async createOrder(data: any) {
    return this.request<any>('/orders/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async cancelOrder(id: string, reason?: string) {
    return this.request<any>(`/orders/${id}/cancel/`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || '' }),
    });
  }

  async fulfillOrder(id: string, data?: { tracking_number?: string; shipping_cost?: number }) {
    return this.request<any>(`/orders/${id}/fulfill/`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    });
  }

  async importOrdersCsv(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {};
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('shoppilot_access_token');
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const activeStoreId = localStorage.getItem('shoppilot_active_store_id');
      if (activeStoreId) headers['x-store-id'] = activeStoreId;
    }

    const response = await fetch(`${API_BASE_URL}/orders/import-csv/`, {
      method: 'POST',
      headers,
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`Import failed with status ${response.status}`);
    }
    return response.json();
  }

  // Payments
  async getPayments(params?: { status?: string; method?: string }) {
    const q = new URLSearchParams();
    if (params?.status) q.append('status', params.status);
    if (params?.method) q.append('method', params.method);
    return this.request<{ results: any[] } | any[]>(`/payments/?${q.toString()}`);
  }

  async verifyPayment(id: string) {
    return this.request<any>(`/payments/${id}/verify/`, {
      method: 'POST',
    });
  }

  async rejectPayment(id: string, reason: string) {
    return this.request<any>(`/payments/${id}/reject/`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  // Fulfillment
  async getShipments() {
    return this.request<{ results: any[] } | any[]>('/fulfillment/');
  }

  async getPackingSlip(shipmentId: string) {
    return this.request<any>(`/fulfillment/${shipmentId}/packing-slip/`);
  }

  // Team Management & RBAC
  async getTeamMembers() {
    return this.request<{ results: any[] } | any[]>('/tenancy/memberships/');
  }

  async suspendTeamMember(id: string) {
    return this.request<any>(`/tenancy/memberships/${id}/suspend/`, {
      method: 'POST',
    });
  }

  async reactivateTeamMember(id: string) {
    return this.request<any>(`/tenancy/memberships/${id}/reactivate/`, {
      method: 'POST',
    });
  }

  async getTeamInvitations() {
    return this.request<{ results: any[] } | any[]>('/tenancy/invitations/');
  }

  async sendTeamInvitation(data: { email: string; role: string; custom_permissions?: string[] }) {
    return this.request<any>('/tenancy/invitations/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async revokeTeamInvitation(id: string) {
    return this.request<any>(`/tenancy/invitations/${id}/revoke/`, {
      method: 'POST',
    });
  }

  async acceptTeamInvitation(token: string) {
    return this.request<any>('/tenancy/invitations/accept/', {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
  }

  // Tasks Management
  async getTaskCategories() {
    return this.request<{ results: any[] } | any[]>('/tasks/categories/');
  }

  async createTaskCategory(data: { name: string; color?: string; icon?: string }) {
    return this.request<any>('/tasks/categories/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getTasks(params?: {
    status?: string;
    priority?: string;
    category?: string;
    assignee?: string;
    my_tasks?: boolean;
    overdue?: boolean;
  }) {
    const q = new URLSearchParams();
    if (params?.status) q.append('status', params.status);
    if (params?.priority) q.append('priority', params.priority);
    if (params?.category) q.append('category', params.category);
    if (params?.assignee) q.append('assignee', params.assignee);
    if (params?.my_tasks) q.append('my_tasks', 'true');
    if (params?.overdue) q.append('overdue', 'true');
    return this.request<{ results: any[] } | any[]>(`/tasks/tasks/?${q.toString()}`);
  }

  async getTaskDetail(id: string) {
    return this.request<any>(`/tasks/tasks/${id}/`);
  }

  async createTask(data: any) {
    return this.request<any>('/tasks/tasks/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateTaskStatus(id: string, status: string, completion_evidence?: string) {
    return this.request<any>(`/tasks/tasks/${id}/status/`, {
      method: 'POST',
      body: JSON.stringify({ status, completion_evidence: completion_evidence || '' }),
    });
  }

  async verifyTask(id: string, approved: boolean, feedback?: string) {
    return this.request<any>(`/tasks/tasks/${id}/verify/`, {
      method: 'POST',
      body: JSON.stringify({ approved, feedback: feedback || '' }),
    });
  }

  async addTaskComment(id: string, content: string) {
    return this.request<any>(`/tasks/tasks/${id}/comments/`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  async addTaskChecklistItem(id: string, title: string) {
    return this.request<any>(`/tasks/tasks/${id}/checklist/`, {
      method: 'POST',
      body: JSON.stringify({ title }),
    });
  }

  async toggleTaskChecklistItem(taskId: string, itemId: string) {
    return this.request<any>(`/tasks/tasks/${taskId}/checklist/${itemId}/toggle/`, {
      method: 'POST',
    });
  }

  async getTaskSummary() {
    return this.request<{
      total: number;
      todo: number;
      in_progress: number;
      in_review: number;
      completed: number;
      overdue: number;
      my_tasks: number;
    }>('/tasks/tasks/summary/');
  }

  // Social Media Operations & Planner
  async getSocialAccounts() {
    return this.request<{ results: any[] } | any[]>('/social/accounts/');
  }

  async createSocialAccount(data: any) {
    return this.request<any>('/social/accounts/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getSocialCampaigns() {
    return this.request<{ results: any[] } | any[]>('/social/campaigns/');
  }

  async createSocialCampaign(data: any) {
    return this.request<any>('/social/campaigns/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getSocialContent(params?: {
    status?: string;
    content_type?: string;
    account?: string;
    campaign?: string;
    start_date?: string;
    end_date?: string;
  }) {
    const q = new URLSearchParams();
    if (params?.status) q.append('status', params.status);
    if (params?.content_type) q.append('content_type', params.content_type);
    if (params?.account) q.append('account', params.account);
    if (params?.campaign) q.append('campaign', params.campaign);
    if (params?.start_date) q.append('start_date', params.start_date);
    if (params?.end_date) q.append('end_date', params.end_date);
    return this.request<{ results: any[] } | any[]>(`/social/content/?${q.toString()}`);
  }

  async getSocialContentDetail(id: string) {
    return this.request<any>(`/social/content/${id}/`);
  }

  async createSocialContent(data: any) {
    return this.request<any>('/social/content/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async submitContentForReview(id: string) {
    return this.request<any>(`/social/content/${id}/submit-review/`, {
      method: 'POST',
    });
  }

  async reviewContent(id: string, action: string, feedback?: string) {
    return this.request<any>(`/social/content/${id}/review/`, {
      method: 'POST',
      body: JSON.stringify({ action, feedback: feedback || '' }),
    });
  }

  async scheduleContent(id: string, scheduled_at: string) {
    return this.request<any>(`/social/content/${id}/schedule/`, {
      method: 'POST',
      body: JSON.stringify({ scheduled_at }),
    });
  }

  async publishContent(id: string, published_url?: string) {
    return this.request<any>(`/social/content/${id}/publish/`, {
      method: 'POST',
      body: JSON.stringify({ published_url: published_url || '' }),
    });
  }

  async recordContentMetrics(id: string, data: any) {
    return this.request<any>(`/social/content/${id}/metrics/`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getSocialAnalyticsSummary(days: number = 30) {
    return this.request<any>(`/social/analytics/summary/?days=${days}`);
  }

  // Feature Entitlements & Modularity
  async getFeatureCatalog() {
    return this.request<{
      tier: string;
      tier_display: string;
      features: Array<{
        key: string;
        name_fa: string;
        description_fa: string;
        category: string;
        is_core: boolean;
        is_entitled: boolean;
        is_active: boolean;
        min_tier: string;
        depends_on: string[];
        missing_dependencies: string[];
        dependents: string[];
        integrations: string[];
        impact_warning_fa: string;
      }>;
    }>('/features/catalog/');
  }

  async toggleFeature(feature: string, enabled: boolean) {
    return this.request<{
      feature: string;
      is_active: boolean;
      action: string;
      message: string;
      active_dependents_affected: string[];
    }>('/features/toggle/', {
      method: 'POST',
      body: JSON.stringify({ feature, enabled }),
    });
  }

  async updateSubscriptionTier(tier: string) {
    return this.request<{
      tier: string;
      tier_display: string;
      message: string;
    }>('/features/tier/', {
      method: 'POST',
      body: JSON.stringify({ tier }),
    });
  }

  async getIntegrations() {
    return this.request<Record<string, {
      name: string;
      display_name_fa: string;
      description_fa: string;
      status: string;
      is_ready: boolean;
      message: string;
    }>>('/features/integrations/');
  }

  async configureIntegration(name: string, state: string, credentials?: Record<string, any>) {
    return this.request<any>('/features/integrations/configure/', {
      method: 'POST',
      body: JSON.stringify({ name, state, credentials: credentials || {} }),
    });
  }
}

export const api = new ApiClient();
