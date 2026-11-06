import type { MetadataRoute } from "next";

// Installable app on phones and desktops ("Add to Home screen" / "Install app").
// It opens the same workspace; nothing is cached offline, so every page and answer
// still comes from this RigHaven.
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/workspace",
    name: "RigHaven",
    short_name: "RigHaven",
    description: "A home and on-demand toolbox for goal-driven agent teams.",
    start_url: "/workspace",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#172c33",
    theme_color: "#172c33",
    icons: [
      { src: "/rh-app/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/rh-app/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/rh-app/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
