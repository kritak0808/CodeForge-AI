import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import QueryProvider from '../providers/QueryProvider';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'CodeForge AI — Autonomous SDLC Platform',
  description:
    'Enterprise-grade autonomous software development lifecycle platform powered by multi-agent AI orchestration.',
  keywords: ['AI', 'SDLC', 'CodeForge', 'autonomous', 'agents', 'orchestration'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
