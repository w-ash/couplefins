import { Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ManualCreditDialog } from "@/components/house/ManualCreditDialog";
import { ManualEntriesList } from "@/components/house/ManualEntriesList";
import { SectionHeader } from "@/components/SectionHeader";
import type { Owner } from "@/lib/house";

/** Credits entered by hand: closing through escrow, an early premium. */
export function ManualCreditsSection({ owners }: { owners: Owner[] }) {
  const [open, setOpen] = useState(false);
  return (
    <Card as="section" aria-labelledby="house-credits">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionHeader
          id="house-credits"
          title="Recorded credits"
          description="Contributions that passed through no imported account."
        />
        <Button
          variant="secondary"
          icon={<Plus className="size-4" />}
          onClick={() => setOpen(true)}
        >
          Record a credit
        </Button>
      </div>
      <div className="mt-3">
        <ManualEntriesList owners={owners} />
      </div>
      <ManualCreditDialog
        open={open}
        owners={owners}
        onClose={() => setOpen(false)}
      />
    </Card>
  );
}
