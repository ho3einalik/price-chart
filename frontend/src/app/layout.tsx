import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/contexts/AuthContext';
import { StoreProvider } from '@/contexts/StoreContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';

export const metadata: Metadata = {
  title: 'شاپ‌پایلوت | مرکز عملیات و هوش تجاری فروشگاه آنلاین',
  description: 'پلتفرم جامع مدیریت سفارشات، انبارداری چندکاناله، سودآوری و هوش تجاری',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl" className="dark">
      <body className="min-h-screen bg-[var(--bg-main)] text-[var(--text-main)] antialiased flex flex-col font-sans relative overflow-x-hidden transition-colors duration-300">
        <ThemeProvider>
          {/* Atmospheric Ambient Glows */}
          <div className="ambient-glow-bg">
            <div className="ambient-glow-orange" />
            <div className="ambient-glow-blue" />
            <div className="ambient-glow-purple" />
          </div>

          <AuthProvider>
            <StoreProvider>
              <div className="relative z-10 flex flex-col min-h-screen">
                <Navbar />
                <div className="flex flex-1 p-3 sm:p-5 gap-3 sm:gap-5">
                  <Sidebar />
                  <main className="flex-1 min-w-0 pb-10">
                    {children}
                  </main>
                </div>
              </div>
            </StoreProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
