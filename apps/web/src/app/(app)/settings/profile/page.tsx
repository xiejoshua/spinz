import { redirectToProfileSettings } from "@/lib/settings-redirect";

/** Legacy /settings/profile → /profile/{handle}/settings (Profile section inline) */
export default async function SettingsProfileRedirect() {
  await redirectToProfileSettings();
}
