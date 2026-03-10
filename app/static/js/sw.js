self.addEventListener("push", (event) => {
  let payload = { title: "Chastease", body: "Neue Nachricht" };
  try {
    if (event.data) {
      payload = event.data.json();
    }
  } catch {
    // Fall back to default payload when parsing fails.
  }

  const title = payload.title || "Chastease";
  const options = {
    body: payload.body || "Neue Nachricht",
    data: payload.data || {},
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow("/"));
});
