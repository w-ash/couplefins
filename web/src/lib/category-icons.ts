import type { LucideIcon } from "lucide-react";
import {
  ArrowLeftRight,
  Briefcase,
  Car,
  CreditCard,
  DollarSign,
  Gift,
  HeartPulse,
  Home,
  Key,
  Landmark,
  Music,
  Package,
  Plane,
  ShoppingBag,
  Sparkles,
  Sun,
  Tag,
  Tent,
  UtensilsCrossed,
  Wallet,
} from "lucide-react";

export const CATEGORY_ICON_REGISTRY: Record<string, LucideIcon> = {
  wallet: Wallet,
  home: Home,
  car: Car,
  "utensils-crossed": UtensilsCrossed,
  sun: Sun,
  "shopping-bag": ShoppingBag,
  "heart-pulse": HeartPulse,
  music: Music,
  plane: Plane,
  tent: Tent,
  gift: Gift,
  landmark: Landmark,
  package: Package,
  briefcase: Briefcase,
  "arrow-left-right": ArrowLeftRight,
  key: Key,
  "dollar-sign": DollarSign,
  "credit-card": CreditCard,
  sparkles: Sparkles,
  tag: Tag,
};

export const ICON_OPTIONS: Array<{ name: string; Icon: LucideIcon }> =
  Object.entries(CATEGORY_ICON_REGISTRY).map(([name, Icon]) => ({
    name,
    Icon,
  }));

export function getCategoryGroupIcon(icon: string | null): LucideIcon {
  if (icon && icon in CATEGORY_ICON_REGISTRY) {
    return CATEGORY_ICON_REGISTRY[icon];
  }
  return Tag;
}
