export const MONARCH_COLUMNS = [
  "Date",
  "Merchant",
  "Category",
  "Account",
  "Original Statement",
  "Notes",
  "Amount",
  "Tags",
] as const;

export function validateCsvHeaders(file: File): Promise<string | null> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => {
      const text = reader.result as string;
      // Strip UTF-8 BOM if present
      const clean = text.startsWith("\uFEFF") ? text.slice(1) : text;
      const firstLine = clean.split(/\r?\n/)[0];
      if (!firstLine?.trim()) {
        resolve("File appears to be empty.");
        return;
      }
      const headers = firstLine
        .split(",")
        .map((h) => h.trim().replace(/^"|"$/g, ""));
      const headerSet = new Set(headers);
      const missing = MONARCH_COLUMNS.filter((col) => !headerSet.has(col));
      if (missing.length > 0) {
        resolve(
          `Missing required columns: ${missing.join(", ")}. This doesn't look like a Monarch Money export.`,
        );
        return;
      }
      resolve(null);
    };
    reader.onerror = () => resolve("Could not read the file.");
    reader.readAsText(file.slice(0, 4096));
  });
}
