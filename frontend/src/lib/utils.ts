import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number | string | null | undefined, currency: string = 'IRT'): string {
  if (amount === null || amount === undefined || amount === '') return '۰ تومان';
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '۰ تومان';

  const formatted = Math.round(num).toLocaleString('fa-IR');
  const unit = currency === 'IRR' ? 'ریال' : 'تومان';
  return `${formatted} ${unit}`;
}

export function formatNumber(num: number | string | null | undefined): string {
  if (num === null || num === undefined) return '۰';
  const n = typeof num === 'string' ? parseInt(num, 10) : num;
  return isNaN(n) ? '۰' : n.toLocaleString('fa-IR');
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '-';
  try {
    const d = new Date(dateString);
    return new Intl.DateTimeFormat('fa-IR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d);
  } catch {
    return dateString;
  }
}
