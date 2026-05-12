import type { BusinessSetupChannel } from "@/lib/api";

export const CHANNEL_ERROR_NO_ACTIVE = "กรุณาเลือกช่องทางขายอย่างน้อย 1 ช่องทาง";
export const CHANNEL_ERROR_TOTAL_NOT_100 = "สัดส่วนรายได้ของช่องทางที่เลือกต้องรวมกันเป็น 100%";

const REVENUE_SHARE_EPSILON = 0.01;

export interface ChannelMixValidation {
  activeChannels: BusinessSetupChannel[];
  totalRevenueShare: number;
  error: string | null;
  isValid: boolean;
}

export function validateChannelMix(channels: BusinessSetupChannel[]): ChannelMixValidation {
  const activeChannels = channels.filter((channel) => channel.is_active);
  const totalRevenueShare = activeChannels.reduce(
    (sum, channel) => sum + channel.revenue_share_pct,
    0
  );

  if (activeChannels.length === 0) {
    return {
      activeChannels,
      totalRevenueShare,
      error: CHANNEL_ERROR_NO_ACTIVE,
      isValid: false,
    };
  }

  if (Math.abs(totalRevenueShare - 100) > REVENUE_SHARE_EPSILON) {
    return {
      activeChannels,
      totalRevenueShare,
      error: CHANNEL_ERROR_TOTAL_NOT_100,
      isValid: false,
    };
  }

  return {
    activeChannels,
    totalRevenueShare,
    error: null,
    isValid: true,
  };
}
