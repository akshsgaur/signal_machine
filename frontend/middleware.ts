import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

export const runtime = "nodejs";

const isProtectedRoute = createRouteMatcher([
  "/app(.*)",
  "/connect(.*)",
  "/run(.*)",
]);

export default clerkMiddleware((auth, req) => {
  if (isProtectedRoute(req)) auth.protect();
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).)+" , "/(api|trpc)(.*)"],
};
