import { api } from "./client";

/**
 * Open a file the API serves (a PDF) in a new tab. Files are only served to
 * logged-in users, never by public URL, so we fetch the bytes and show a blob.
 * The tab is opened first, inside the click, so pop-up blockers allow it.
 */
export async function openFile(url: string, params?: Record<string, string | number>) {
  const tab = window.open("", "_blank");
  try {
    const { blob } = await api.download(url, params);
    const blobUrl = URL.createObjectURL(blob);
    if (tab) tab.location.href = blobUrl;
    else window.location.href = blobUrl;
  } catch (error) {
    tab?.close();
    throw error;
  }
}
