/**
 * createApiHook — F12 TanStack Query hook factory.
 * GET → useQuery ; POST/PUT → useMutation. Enforces /api/ prefix and Zod parsing.
 */
import {
  useQuery,
  useMutation,
  type UseMutationOptions,
  type UseQueryOptions,
  type UseQueryResult,
  type UseMutationResult,
} from "@tanstack/react-query";
import type { ZodSchema } from "zod";
import { apiClient, HttpError } from "./client";

export { HttpError };

export interface RouteSpec<Req, Resp> {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  requestSchema?: ZodSchema<Req>;
  responseSchema: ZodSchema<Resp>;
}

export type QueryHookOptions<Resp> = Omit<
  UseQueryOptions<Resp, Error, Resp>,
  "queryKey" | "queryFn"
>;
export type MutationHookOptions<Req, Resp> = UseMutationOptions<
  Resp,
  Error,
  Req,
  unknown
>;

export type QueryHook<Resp> = (
  opts?: QueryHookOptions<Resp>,
) => UseQueryResult<Resp>;
export type MutationHook<Req, Resp> = (
  opts?: MutationHookOptions<Req, Resp>,
) => UseMutationResult<Resp, Error, Req, unknown>;

// Overloads: narrow return by the `method` literal so consumers get the
// correct hook signature without an explicit cast.
export function createApiHook<Req, Resp>(
  route: RouteSpec<Req, Resp> & { method: "GET" },
): QueryHook<Resp>;
export function createApiHook<Req, Resp>(
  route: RouteSpec<Req, Resp> & { method: "POST" | "PUT" | "DELETE" },
): MutationHook<Req, Resp>;
export function createApiHook<Req, Resp>(
  route: RouteSpec<Req, Resp>,
): QueryHook<Resp> | MutationHook<Req, Resp>;
export function createApiHook<Req, Resp>(
  route: RouteSpec<Req, Resp>,
): QueryHook<Resp> | MutationHook<Req, Resp> {
  if (!route.path.startsWith("/api/")) {
    throw new Error(`route.path must start with /api/ (got ${route.path})`);
  }
  const { method, path, requestSchema, responseSchema } = route;

  if (method === "GET") {
    const hook: QueryHook<Resp> = (opts) => {
      // eslint-disable-next-line react-hooks/rules-of-hooks
      return useQuery<Resp, Error, Resp>({
        queryKey: [method, path],
        queryFn: async () => {
          const raw = await apiClient.fetch<unknown>(method, path);
          return responseSchema.parse(raw);
        },
        ...(opts ?? {}),
      });
    };
    return hook;
  }

  const hook: MutationHook<Req, Resp> = (opts) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useMutation<Resp, Error, Req, unknown>({
      mutationFn: async (req: Req) => {
        if (requestSchema) requestSchema.parse(req);
        const raw = await apiClient.fetch<unknown>(method, path, req);
        return responseSchema.parse(raw);
      },
      ...(opts ?? {}),
    });
  };
  return hook;
}
