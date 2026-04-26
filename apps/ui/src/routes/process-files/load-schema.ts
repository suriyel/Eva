/**
 * loadProcessFileSchema — F22 §IC Section D.
 * Looks up the Zod schema registered for ``file`` in ``processFileSchemas``.
 * Throws ``Error('schema not found')`` when the file is outside the whitelist.
 */
import type { z } from "zod";
import { processFileSchemas } from "../../lib/zod-schemas";

export function loadProcessFileSchema(file: string): z.ZodTypeAny {
  const s = processFileSchemas[file];
  if (!s) {
    throw new Error(`schema not found for ${file}`);
  }
  return s;
}
