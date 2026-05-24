import { redirectToProfileSettings } from "@/lib/settings-redirect";

export default async function SettingsNotificationsRedirect() {
  await redirectToProfileSettings("/notifications");
}
