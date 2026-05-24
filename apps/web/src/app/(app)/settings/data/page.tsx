import { redirectToProfileSettings } from "@/lib/settings-redirect";

export default async function SettingsDataRedirect() {
  await redirectToProfileSettings("/data");
}
