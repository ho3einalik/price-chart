import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/contexts/AuthContext';
import { StoreProvider } from '@/contexts/StoreContext';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';

export const metadata: Metadata = {
  title: 'شاپ‌پایلوت | مرکز عملیات و هوش تجاری فروشگاه‌های آنلاین',
  description: 'پلتفرم جامع مدیریت سفارشات، انبارداری چندکاناله، سودآوری و هوش تجاری',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl">
      <body className="min-h-screen bg-slate-50 antialiased flex flex-col font-sans">
        <AuthProvider>
          <StoreProvider>
            <Navbar />
            <div className="flex flex-1">
              <Sidebar />
              <main className="flex-1 p-6 lg:p-8 max-w-7xl mx-auto w-full">
                {children}
              </main>
            </div>
          </StoreProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
