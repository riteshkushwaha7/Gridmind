import type { Metadata } from "next";
import { JetBrains_Mono, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { BottomNav } from "@/components/BottomNav";
import { PrototypeBadge } from "@/components/PrototypeBadge";
import { Providers } from "@/components/providers";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "GRIDMIND",
  description:
    "AI-driven EV charging optimisation and infrastructure planning for BESCOM.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${jakarta.variable} ${jetbrains.variable} min-h-screen bg-bm-mist pb-20 font-sans text-blueprint-navy antialiased dark:bg-bm-ink dark:text-blueprint-mist md:pb-0`}
      >
        <Providers>
          {children}
          <BottomNav />
          <PrototypeBadge />
        </Providers>
      </body>
    </html>
  );
}
