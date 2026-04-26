/**
 * Settings/general hooks — F22 §IC Section A.
 * Wraps GET/PUT /api/settings/general via the F12 createApiHook factory.
 */
import { z } from "zod";
import { createApiHook } from "../query-hook-factory";
import {
  generalSettingsSchema,
  updateGeneralSettingsRequestSchema,
  testConnectionRequestSchema,
  testConnectionResultSchema,
} from "../../lib/zod-schemas";

export const useGeneralSettings = createApiHook({
  method: "GET",
  path: "/api/settings/general",
  responseSchema: generalSettingsSchema,
});

export const useUpdateGeneralSettings = createApiHook({
  method: "PUT",
  path: "/api/settings/general",
  requestSchema: updateGeneralSettingsRequestSchema,
  responseSchema: generalSettingsSchema,
});

export const useTestConnection = createApiHook({
  method: "POST",
  path: "/api/settings/classifier/test",
  requestSchema: testConnectionRequestSchema,
  responseSchema: testConnectionResultSchema,
});

export const useUpdateClassifierConfig = createApiHook({
  method: "PUT",
  path: "/api/settings/classifier",
  requestSchema: z
    .object({
      base_url: z.string(),
      provider: z.string().optional(),
      strict_schema_override: z.boolean().nullable().optional(),
      enabled: z.boolean().optional(),
    })
    .passthrough(),
  responseSchema: z.unknown(),
});
