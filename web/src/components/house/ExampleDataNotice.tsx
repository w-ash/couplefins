import { FlaskConical } from "lucide-react";
import { WarningBanner } from "@/components/WarningBanner";

/** Tells the reader the House figures are illustrative, not the real ledger. */
export function ExampleDataNotice() {
  return (
    <WarningBanner role="status" icon={FlaskConical} title="Example figures">
      <p className="text-sm text-warning-muted-foreground">
        Alice and Bob are illustrative owners; the real house ledger replaces
        this section by section as it is built.
      </p>
    </WarningBanner>
  );
}
