import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rabt — no result left behind",
  description:
    "Care-loop companion for screening follow-up, designed to sit alongside a patient app such as Sehatna. Synthetic demo only.",
  openGraph: {
    title: "Rabt — no result left behind",
    description: "Synthetic care-loop demo for screening follow-up in Abu Dhabi-style programmes.",
    url: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
    siteName: "Rabt",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Rabt" }],
    type: "website",
  },
  manifest: "/manifest.webmanifest",
  applicationName: "Rabt",
  appleWebApp: { capable: true, title: "Rabt", statusBarStyle: "default" },
  icons: {
    icon: [
      { url: "/icons/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Rabt — no result left behind",
    description: "Synthetic care-loop demo. No result left behind.",
    images: ["/og.png"],
  },
};

export const viewport: Viewport = {
  themeColor: "#0e8f9e",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;600;700&family=Noto+Sans+Bengali:wght@400;600;700&family=Noto+Sans+Devanagari:wght@400;600;700&family=Noto+Sans+Malayalam:wght@400;600;700&family=Source+Sans+3:wght@400;600;700&family=Syne:wght@600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="app-bg" aria-hidden />
        {children}
      </body>
    </html>
  );
}
