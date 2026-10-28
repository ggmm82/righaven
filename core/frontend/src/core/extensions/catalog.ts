import type { Translations } from "@/core/i18n/locales/types";

import type { LoadedContribution } from "./registry";

// Discovery metadata only: catalog entries never enter the runtime module loader.
export const extensionCatalog = [
  {
    key: "agentTeams",
    package: "righaven_core-extension-agent-teams",
    namespace: "community.agent-teams",
  },
  {
    key: "bookmarks",
    package: "righaven_core-extension-bookmarks",
    namespace: "community.bookmarks",
    icon: "bookmark",
  },
  {
    key: "context",
    package: "righaven_core-extension-jev-context",
    namespace: "community.jev-context",
  },
  {
    key: "classify",
    package: "righaven_core-extension-jev-classify",
    namespace: "community.jev-classify",
  },
  {
    key: "screening",
    package: "righaven_core-extension-jev-screening",
    namespace: null,
  },
  {
    key: "workflows",
    package: "righaven_core-extension-workflows",
    namespace: "community.workflows",
  },
  {
    key: "retrieval",
    package: "righaven_core-extension-retrieval",
    namespace: "example.retrieval",
  },
  { key: "example", package: "righaven_core-extension-example", namespace: null },
] as const;

export interface ExtensionCatalogEntry {
  id: string;
  title: string;
  description: string;
  package?: string;
  guide?: string;
  icon?: string;
  loaded?: LoadedContribution;
}

export function extensionDirectory(
  loaded: LoadedContribution[],
  copy: Translations["extensions"]["catalog"],
): ExtensionCatalogEntry[] {
  const entries: ExtensionCatalogEntry[] = extensionCatalog.map((item) => ({
    id: item.namespace ?? `catalog/${item.key}`,
    ...copy[item.key],
    package: item.package,
    guide: `https://github.com/ggmm82/righaven/tree/main/examples/${item.package}#readme`,
    icon: "icon" in item ? item.icon : undefined,
    loaded: loaded.find((entry) => entry.namespace === item.namespace),
  }));
  const known = new Set<string | null>(
    extensionCatalog.map((item) => item.namespace),
  );
  for (const entry of loaded) {
    if (known.has(entry.namespace)) continue;
    entries.push({
      id: entry.namespace,
      title: entry.title,
      description: entry.description,
      loaded: entry,
    });
  }
  return entries;
}
