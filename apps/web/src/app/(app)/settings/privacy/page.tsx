import { redirectToProfileSettings } from "@/lib/settings-redirect";

export default async function SettingsPrivacyRedirect() {
  await redirectToProfileSettings("/privacy");
}
