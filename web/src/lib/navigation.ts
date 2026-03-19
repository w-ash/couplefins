import type { LucideIcon } from "lucide-react";
import {
  ArrowLeftRight,
  HandCoins,
  LayoutDashboard,
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

/** Primary nav — shown in sidebar and bottom tab bar. */
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

/** Secondary nav — shown in sidebar and mobile "More" sheet. */
export const SECONDARY_ROUTES: NavRoute[] = [
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/settings", label: "Settings", icon: Settings },
];
