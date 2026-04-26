/**
 * Classifier prompt history hooks — F22 §IC Section B.
 */
import { z } from "zod";
import { createApiHook } from "../query-hook-factory";
import { classifierPromptSchema } from "../../lib/zod-schemas";

export const usePromptHistory = createApiHook({
  method: "GET",
  path: "/api/prompts/classifier",
  responseSchema: classifierPromptSchema,
});

export const useUpdateClassifierPrompt = createApiHook({
  method: "PUT",
  path: "/api/prompts/classifier",
  requestSchema: z.object({ content: z.string() }),
  responseSchema: classifierPromptSchema,
});
