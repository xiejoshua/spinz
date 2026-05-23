// T141 — Web Push service worker.
//
// Handles:
//   - install/activate: claim clients immediately so the first subscribe
//     can deliver a push without a reload.
//   - push: render the OS notification from the JSON payload the backend
//     WebPushAdapter sends. Payload shape: {title, body, click_url, type, tag}.
//   - notificationclick: focus an existing tab pointing at click_url, or
//     open a new one.
//
// Kept plain-JS (no TS) because Next.js serves this directly from /public
// without going through the build pipeline.

self.addEventListener("install", (_event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch (_e) {
    return;
  }
  const title = payload.title || "auxd";
  const options = {
    body: payload.body || "",
    tag: payload.tag || "auxd",
    data: {
      click_url: payload.click_url || "/",
      type: payload.type || "",
    },
    icon: "/icon-192.png",
    badge: "/icon-192.png",
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const click_url = event.notification.data?.click_url || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      const existing = wins.find((w) => w.url.includes(click_url));
      if (existing) {
        return existing.focus();
      }
      return self.clients.openWindow(click_url);
    })
  );
});
