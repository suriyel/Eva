/**
 * File tree / file content hooks — F22 §IC Section C.
 *
 * F22 §VRC docs-tree / markdown-preview / toc are consumers; the hook layer
 * only adds query-string encoding + Zod parse. Path traversal is rejected by
 * the backend (F20 PathTraversalError → HTTP 400) — the FE never sanitises.
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiClient } from "../client";
import { fileTreeSchema, fileContentSchema } from "../../lib/zod-schemas";
import type { z } from "zod";

type FileTree = z.infer<typeof fileTreeSchema>;
type FileContent = z.infer<typeof fileContentSchema>;

// Encode a path for use as a query-string value while preserving '/' so the
// backend's path-traversal probe (`..`) remains observable in the request URL
// (F22 22-09). encodeURIComponent would mangle slashes into %2F.
function encodePathQuery(p: string): string {
  // Encode the chars that are unsafe in a query value EXCEPT slash.
  return p.replace(/[#?&=+%]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
}

export function useFileTree(root: string | null): UseQueryResult<FileTree> {
  return useQuery<FileTree, Error>({
    queryKey: ["GET", "/api/files/tree", root],
    enabled: typeof root === "string" && root.length > 0,
    retry: false,
    queryFn: async () => {
      const url = `/api/files/tree?root=${encodePathQuery(root ?? "")}`;
      const raw = await apiClient.fetch<unknown>("GET", url);
      return fileTreeSchema.parse(raw);
    },
  });
}

export function useFileContent(path: string | null): UseQueryResult<FileContent> {
  return useQuery<FileContent, Error>({
    queryKey: ["GET", "/api/files/read", path],
    enabled: typeof path === "string" && path.length > 0,
    retry: false,
    queryFn: async () => {
      const url = `/api/files/read?path=${encodePathQuery(path ?? "")}`;
      const raw = await apiClient.fetch<unknown>("GET", url);
      return fileContentSchema.parse(raw);
    },
  });
}
