import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AuthProvider } from "@/components/auth/auth-provider";
import { AppShell } from "@/components/shell/app-shell";
import { SmoothScroll } from "@/components/shell/smooth-scroll";
import { TooltipProvider } from "@/components/ui/tooltip";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Heimdall",
  description: "AI brand governance. Nothing crosses unchecked.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <AuthProvider>
          <TooltipProvider delayDuration={200}>
            <SmoothScroll>
              <AppShell>{children}</AppShell>
            </SmoothScroll>
          </TooltipProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
