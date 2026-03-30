import { useEffect, useState } from "react";
import { subscribe } from "@/lib/event-source";

export interface UploadProgress {
  current: number;
  total: number;
  detail: string;
}

export function useUploadProgress(active: boolean): UploadProgress | null {
  const [progress, setProgress] = useState<UploadProgress | null>(null);

  useEffect(() => {
    if (!active) {
      setProgress(null);
      return;
    }

    return subscribe((data) => {
      if (
        data.type === "progress" &&
        data.operation === "upload" &&
        typeof data.current === "number" &&
        typeof data.total === "number" &&
        typeof data.detail === "string"
      ) {
        setProgress({
          current: data.current,
          total: data.total,
          detail: data.detail,
        });
      }
    });
  }, [active]);

  return progress;
}
