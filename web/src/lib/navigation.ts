import type { LucideIcon } from "lucide-react";
import {
  ArrowLeftRight,
  HandCoins,
  House,
  LayoutDashboard,
  MessageCircle,
  PieChart,
  Settings,
  TrendingUp,
  Upload,
} from "lucide-react";

export interface NavRoute {
  to: string;
  label: string;
  shortLabel?: string;
  icon: LucideIcon;
}

/** Primary nav — the five bottom-bar tabs, also in the sidebar. */
export const PRIMARY_ROUTES: NavRoute[] = [
  { to: "/", label: "Dashboard", shortLabel: "Home", icon: LayoutDashboard },
  {
    to: "/transactions",
    label: "Transactions",
    shortLabel: "Txns",
    icon: ArrowLeftRight,
  },
  { to: "/settle", label: "Settle Up", shortLabel: "Settle", icon: HandCoins },
  { to: "/budget", label: "Budget", icon: PieChart },
  { to: "/insights", label: "Insights", icon: TrendingUp },
];

/** Secondary nav — the sidebar and the mobile "More" sheet. */
export const SECONDARY_ROUTES: NavRoute[] = [
  { to: "/house", label: "House", icon: House },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/settings", label: "Settings", icon: Settings },
];

/** Chat nav — only shown when chat is available. */
export const CHAT_ROUTE: NavRoute = {
  to: "/ask",
  label: "Ask",
  icon: MessageCircle,
};
