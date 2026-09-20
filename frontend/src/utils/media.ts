/**
 * Resolves a reliable, authenticated URL for rendering a video thumbnail.
 */
export function getThumbnailUrl(
  thumbnailUrl?: string | null,
  thumbnailPath?: string | null,
  videoId?: string | null
): string | null {
  const token = localStorage.getItem("access_token");
  const tokenParam = token ? `token=${encodeURIComponent(token)}` : "";

  if (thumbnailUrl) {
    if (thumbnailUrl.startsWith("http://") || thumbnailUrl.startsWith("https://")) {
      return thumbnailUrl;
    }
    const separator = thumbnailUrl.includes("?") ? "&" : "?";
    return tokenParam ? `${thumbnailUrl}${separator}${tokenParam}` : thumbnailUrl;
  }

  if (videoId) {
    return `/api/videos/${videoId}/thumbnail${tokenParam ? `?${tokenParam}` : ""}`;
  }

  if (thumbnailPath) {
    const filename = thumbnailPath.split("/").pop();
    const id = filename ? filename.replace(/\.[^/.]+$/, "") : null;
    if (id) {
      return `/api/videos/${id}/thumbnail${tokenParam ? `?${tokenParam}` : ""}`;
    }
  }

  return null;
}
