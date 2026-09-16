import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000',
  ),
  title: 'GuidePost Health — LLM testing and RAG learning',
  description:
    'An assistant for exploring NHS symptom guidance with links to the original sources.',
  openGraph: {
    title: 'GuidePost Health — LLM testing and RAG learning',
    description:
      'Explore NHS symptom guidance with links to the original sources.',
    type: 'website',
    images: [
      { url: '/og.png', width: 1731, height: 909, alt: 'GuidePost Health' },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'GuidePost Health — LLM testing and RAG learning',
    description:
      'Explore NHS symptom guidance with links to the original sources.',
    images: ['/og.png'],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
