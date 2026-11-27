// Hoops Report service worker: install support only.
// Pass-through on purpose: ratings data updates daily and must never be
// served stale from a cache. Every request goes straight to the network.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
