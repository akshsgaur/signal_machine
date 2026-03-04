/** @type {import('next').NextConfig} */
const nextConfig = {
  serverExternalPackages: ["@clerk/nextjs", "@clerk/backend", "@clerk/shared"],
  webpack: (config, { nextRuntime }) => {
    if (nextRuntime === "edge") {
      config.resolve.conditionNames = [
        "edge-light",
        "worker",
        "browser",
        "import",
        "module",
        "require",
        "default",
      ];
    }
    return config;
  },
};

export default nextConfig;
