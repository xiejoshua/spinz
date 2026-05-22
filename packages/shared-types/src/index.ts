// @auxd/shared-types — placeholder.
// Real types land via openapi-typescript codegen from the FastAPI OpenAPI
// schema in T028. Until then, only this greeting export exists so the
// monorepo scaffold can verify workspace resolution end-to-end.

export function greeting(): string {
  return "Hello from @auxd/shared-types.";
}
