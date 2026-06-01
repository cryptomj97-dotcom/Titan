import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "TITAN",
  description: "TITAN trading AI war room",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
