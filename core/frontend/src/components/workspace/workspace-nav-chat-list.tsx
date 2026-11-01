"use client";

import { Home, MessagesSquare, Layers, Wrench, Library, Users, Settings2, ShieldCheck, Gauge, ListChecks, Database } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";

export function WorkspaceNavChatList() {
  const { locale } = useI18n();
  const {user}=useAuth();
  const it = locale === "it-IT";
  const pathname = usePathname();
  const groups = [
    { label: it ? "Lavoro" : "Workspace", items: [
      { href: "/workspace", label: it ? "Panoramica" : "Overview", icon: Home },
      { href: "/workspace/chats", label: it ? "Attività e risultati" : "Tasks & results", icon: MessagesSquare },
      { href: "/workspace/recipes", label: it ? "Ricette" : "Recipes", icon: ListChecks },
    ] },
    { label: it ? "Cassetta degli attrezzi" : "Toolbox", items: [
      { href: "/workspace/environments", label: it ? "Ambienti" : "Environments", icon: Layers },
      { href: "/workspace/capabilities", label: it ? "Strumenti e skill" : "Tools & skills", icon: Wrench },
      { href: "/workspace/gallery", label: "Community Gallery", icon: Library },
    ] },
    { label: it ? "Configurazione" : "Configuration", items: [
      ...(user?.system_role==="admin"?[{href:"/workspace/users",label:it?"Gestione utenti":"User administration",icon:Users}]:[]),
      {href:"/workspace/connections",label:it?"Connessioni":"Connections",icon:Database},
      {href:"/workspace/policies",label:"Policy Book",icon:ShieldCheck},
      {href:"/workspace/usage",label:it?"Uso delle macchine":"Machine usage",icon:Gauge},
      {href:"/workspace/maintenance",label:it?"Manutenzione e ripristino":"Maintenance & reset",icon:Settings2},
      { href: "/workspace/harness", label: it ? "Modelli e risorse" : "Models & resources", icon: Settings2 },
    ] },
  ];
  return <>{groups.map(group => <SidebarGroup key={group.label}>
    <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
    <SidebarMenu>{group.items.map(({href,label,icon:Icon}) => <SidebarMenuItem key={href}>
      <SidebarMenuButton asChild tooltip={label} isActive={href === "/workspace" ? pathname === href : pathname.startsWith(href)}>
        <Link href={href}><Icon /><span>{label}</span></Link>
      </SidebarMenuButton>
    </SidebarMenuItem>)}</SidebarMenu>
  </SidebarGroup>)}</>;
}
