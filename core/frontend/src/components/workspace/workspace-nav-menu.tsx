"use client";

import Link from "next/link";
import { LogOut, Settings, Github } from "lucide-react";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";
import { useSettingsDialog } from "./settings";

export function WorkspaceNavMenu() {
  const { openSettings } = useSettingsDialog();
  const { logout } = useAuth();
  const { locale } = useI18n();
  const it = locale === "it-IT";
  return <SidebarMenu>
    <SidebarMenuItem><SidebarMenuButton tooltip={it ? "Account e preferenze" : "Account & preferences"} onClick={() => openSettings("account")}><Settings /><span>{it ? "Account e preferenze" : "Account & preferences"}</span></SidebarMenuButton></SidebarMenuItem>
    <SidebarMenuItem><SidebarMenuButton asChild tooltip="GitHub"><Link href="https://github.com/ggmm82/righaven" target="_blank" rel="noopener noreferrer"><Github /><span>RigHaven · MIT</span></Link></SidebarMenuButton></SidebarMenuItem>
    <SidebarMenuItem><SidebarMenuButton onClick={() => void logout()} tooltip={it ? "Esci" : "Sign out"}><LogOut /><span>{it ? "Esci" : "Sign out"}</span></SidebarMenuButton></SidebarMenuItem>
  </SidebarMenu>;
}
