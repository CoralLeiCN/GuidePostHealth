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
  title: 'NextStep — NHS-guided health assistant',
  description:
    'A source-grounded assistant for understanding sensible next steps from NHS symptom guidance.',
  openGraph: {
    title: 'NextStep — NHS-guided health assistant',
    description:
      'Understand sensible next steps with answers grounded in reviewed NHS symptom guidance.',
    type: 'website',
    images: [{ url: '/og.png', width: 1731, height: 909, alt: 'NextStep' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'NextStep — NHS-guided health assistant',
    description:
      'Understand sensible next steps with answers grounded in reviewed NHS symptom guidance.',
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
