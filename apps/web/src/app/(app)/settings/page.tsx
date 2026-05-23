import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = {
  title: "Settings — auxd",
};

export default function SettingsIndexPage() {
  // No standalone landing surface — bounce to the most-used sub-page so the
  // top-level /settings URL is never a blank slate.
  redirect("/settings/profile");
}
