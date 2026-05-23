import { z } from "zod";

export const signupSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters")
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
