import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/favicon.ico",
  "/_next(.*)",
]);

const isProtectedRoute = createRouteMatcher([
  "/app(.*)",
  "/connect(.*)",
  "/run(.*)",
]);

export default clerkMiddleware((auth, req) => {
  const { pathname, searchParams } = req.nextUrl;
  if ((pathname === "/sign-in" || pathname === "/sign-up") && searchParams.get("allow") !== "1") {
    return NextResponse.redirect(new URL("/", req.url));
  }
  if (isProtectedRoute(req)) auth.protect();
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
