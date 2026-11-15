import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rabt — no result left behind",
  description: "Sehatna-style care-loop companion for screening results (synthetic demo)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;600;700&family=Source+Sans+3:wght@400;600;700&family=Syne:wght@600;700;800&display=swap"
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
