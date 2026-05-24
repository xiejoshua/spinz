import { redirectToProfileSettings } from "@/lib/settings-redirect";

/** Legacy /settings → /profile/{handle}/settings */
export default async function SettingsIndexRedirect() {
  await redirectToProfileSettings();
}
