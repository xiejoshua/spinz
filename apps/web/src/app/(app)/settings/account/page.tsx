import { redirectToProfileSettings } from "@/lib/settings-redirect";

/** Legacy /settings/account → /profile/{handle}/settings (Account section inline) */
export default async function SettingsAccountRedirect() {
  await redirectToProfileSettings();
}
