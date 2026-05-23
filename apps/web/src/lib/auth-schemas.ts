import { z } from "zod";

export const signupSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z
    .string()
    // Backend authoritative: auth/routes.py Field(min_length=12) AND
    // auth/service.py _PASSWORD_MIN_LEN = 12. Frontend mirrors so users
    // see the constraint at the field level instead of a generic 422.
    .min(12, "Password must be at least 12 characters")
    .max(128, "Password must be at most 128 characters"),
  handle: z
    .string()
    .min(3, "Handle must be at least 3 characters")
    .max(24, "Handle must be at most 24 characters")
    .regex(/^[a-z0-9_]+$/, "Handle can only contain lowercase letters, numbers, and underscores"),
});

export type SignupFormValues = z.infer<typeof signupSchema>;

export const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
