/**
 * Skills tree + install/pull hooks — F22 §IC Section B.
 */
import { createApiHook } from "../query-hook-factory";
import {
  skillTreeResponseSchema,
  skillsInstallRequestSchema,
  skillsInstallResultSchema,
} from "../../lib/zod-schemas";

export const useSkillTree = createApiHook({
  method: "GET",
  path: "/api/skills/tree",
  responseSchema: skillTreeResponseSchema,
});

export const useSkillsInstall = createApiHook({
  method: "POST",
  path: "/api/skills/install",
  requestSchema: skillsInstallRequestSchema,
  responseSchema: skillsInstallResultSchema,
});

export const useSkillsPull = createApiHook({
  method: "POST",
  path: "/api/skills/pull",
  requestSchema: skillsInstallRequestSchema,
  responseSchema: skillsInstallResultSchema,
});
