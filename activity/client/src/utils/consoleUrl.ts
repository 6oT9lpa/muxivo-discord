/** Configuration-only URL for a fresh Muxivo Console browser sign-in. */

export function consoleUrl(
  configuredValue = import.meta.env.VITE_MUXIVO_CONSOLE_URL,
  allowInsecureHttp = import.meta.env.DEV,
): string | null {
  const value = configuredValue?.trim();
  if (!value) return null;

  try {
    const url = new URL(value);
    const supportedProtocol =
      url.protocol === "https:" || (allowInsecureHttp && url.protocol === "http:");
    if (!supportedProtocol || url.username || url.password) return null;
    return url.toString();
  } catch {
    return null;
  }
}
