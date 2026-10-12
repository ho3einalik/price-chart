export interface User {
  id: string;
  email: string | null;
  phone_number: string | null;
  full_name: string;
  is_active: boolean;
  date_joined: string;
}

export interface Business {
  id: string;
  name: string;
  created_at: string;
}

export interface Store {
  id: string;
  business: string;
  business_name: string;
  name: string;
  currency: 'IRT' | 'IRR';
  timezone: string;
  is_active: boolean;
  my_role: string;
  created_at: string;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
}

export interface ProductVariant {
  id: string;
  product: string;
  name: string;
  sku: string;
  barcode: string | null;
  cost_price: string;
  retail_price: string;
  wholesale_price: string | null;
  weight_grams: number;
  is_active: boolean;
  total_on_hand: number;
  total_available: number;
}

export interface Product {
  id: string;
  name: string;
  slug: string;
  category: string | null;
  category_name?: string;
  brand: string;
  description: string;
  status: 'DRAFT' | 'ACTIVE' | 'ARCHIVED';
  variants: ProductVariant[];
  created_at: string;
}

export interface Warehouse {
  id: string;
  name: string;
  code: string;
  address: string;
  is_default: boolean;
  is_active: boolean;
}

export interface InventoryBalance {
  id: string;
  warehouse: string;
  warehouse_name: string;
  variant: string;
  variant_sku: string;
  variant_name: string;
  product_name: string;
  on_hand_quantity: number;
  reserved_quantity: number;
  quarantined_quantity: number;
  incoming_quantity: number;
  available: number;
  reorder_point: number;
}

export interface OrderItem {
  id: string;
  variant: string;
  variant_sku: string;
  variant_name: string;
  quantity: number;
  unit_price: string;
  cost_price_snapshot: string;
  unit_discount: string;
  total_price: string;
}

export interface Customer {
  id: string;
  full_name: string;
  phone_number: string;
  email: string | null;
  city: string;
  province: string;
  postal_code: string;
  address_line: string;
}

export interface Order {
  id: string;
  order_number: string;
  channel: string;
  channel_display: string;
  customer: Customer;
  warehouse: string;
  warehouse_name: string;
  order_status: 'DRAFT' | 'PENDING_CONFIRMATION' | 'CONFIRMED' | 'PROCESSING' | 'PARTIALLY_FULFILLED' | 'FULFILLED' | 'COMPLETED' | 'CANCELLED';
  order_status_display: string;
  payment_status: 'PENDING' | 'PARTIALLY_PAID' | 'PAID' | 'REFUNDED' | 'FAILED';
  payment_status_display: string;
  fulfillment_status: 'UNFULFILLED' | 'PARTIALLY_FULFILLED' | 'FULFILLED' | 'RETURNED';
  fulfillment_status_display: string;
  currency: string;
  total_items_price: string;
  discount_amount: string;
  shipping_cost: string;
  tax_amount: string;
  grand_total: string;
  notes: string;
  items: OrderItem[];
  created_at: string;
}

export interface PaymentTransaction {
  id: string;
  order: string;
  order_number: string;
  customer_name: string;
  method: string;
  method_display: string;
  amount: string;
  currency: string;
  status: 'PENDING_VERIFICATION' | 'VERIFIED' | 'REJECTED' | 'REFUNDED';
  status_display: string;
  reference_number: string;
  tracking_code: string;
  payer_card_mask: string;
  receipt_image_url: string;
  verified_by_name: string | null;
  verified_at: string | null;
  rejection_reason: string;
  created_at: string;
}

export interface DailyAction {
  id: string;
  action_key: string;
  title: string;
  explanation: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  severity_display: string;
  status: 'NEW' | 'ACKNOWLEDGED' | 'IN_PROGRESS' | 'RESOLVED' | 'DISMISSED';
  status_display: string;
  suggested_action: string;
  evidence: any;
  assigned_to_name: string | null;
  resolution_note: string;
  resolved_at: string | null;
  created_at: string;
}

export interface OverviewMetrics {
  currency: string;
  period_days: number;
  gross_sales: number;
  discounts: number;
  net_sales: number;
  shipping_collected: number;
  paid_revenue: number;
  outstanding_amount: number;
  order_count: number;
  cancelled_orders_count: number;
  average_order_value: number;
  gross_profit: number;
  gross_profit_margin_pct: number;
  inventory_valuation: number;
  inventory_units_on_hand: number;
  low_stock_count: number;
  out_of_stock_count: number;
  channels: {
    channel: string;
    channel_name: string;
    order_count: number;
    revenue: number;
  }[];
  daily_sales: {
    date: string;
    revenue: number;
    order_count: number;
  }[];
  top_products: {
    variant_sku: string;
    variant_name: string;
    total_quantity: number;
    total_sales: string;
  }[];
}
