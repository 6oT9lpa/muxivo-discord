export function isDiscordActivityLaunch(search: string): boolean {
  const params = new URLSearchParams(search);
  return params.has("frame_id") || params.has("instance_id");
}
