import httpx
import pathlib
import re
from amdea.controller.safety import check_path_allowed
from amdea.execution.browser import download_from_page

MAX_DOWNLOAD_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

class DownloadError(Exception): pass
class FileTooLargeError(DownloadError): pass

async def download_url(url: str, destination: str) -> str:
    """Download a file from a direct HTTPS URL with size limits."""
    check, reason = check_path_allowed(destination)
    if not check:
        raise PermissionError(reason)
        
    dest_path = pathlib.Path(destination).expanduser().resolve()
    dest_path.mkdir(parents=True, exist_ok=True)

    # Sanitize filename from URL
    filename = url.split("/")[-1].split("?")[0] or "downloaded_file"
    filename = re.sub(r'[^\w\-_\. ]', '_', filename)
    save_path = dest_path / filename

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            # 1. HEAD request for size check
            head = await client.head(url)
            size = int(head.headers.get("Content-Length", 0))
            if size > MAX_DOWNLOAD_SIZE_BYTES:
                raise FileTooLargeError(f"File size {size} bytes exceeds limit of {MAX_DOWNLOAD_SIZE_BYTES}")

            # 2. Streaming GET
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                total_bytes = 0
                with open(save_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        total_bytes += len(chunk)
                        if total_bytes > MAX_DOWNLOAD_SIZE_BYTES:
                            save_path.unlink(missing_ok=True)
                            raise FileTooLargeError("Download exceeded size limit during streaming.")
                        f.write(chunk)
        return str(save_path)

    except httpx.TimeoutException:
        raise DownloadError("Download timed out.")
    except httpx.HTTPStatusError as e:
        raise DownloadError(f"HTTP Error {e.response.status_code}: {url}")
    except Exception as e:
        raise DownloadError(f"Unexpected download error: {str(e)}")

async def download_file(url: str = None, selector: str = None, destination: str = "~/Downloads") -> str:
    """Interface for direct, attribute-based, or browser-triggered downloads."""
    if url:
        return await download_url(url, destination)
    elif selector:
        # Try to see if it's an image we can just get the URL for
        from amdea.execution.browser import get_element_attribute
        img_src = await get_element_attribute(selector, "src")
        if img_src:
            if img_src.startswith("data:"):
                # Handle data-uri if needed, but for now just fallback to click
                pass
            else:
                return await download_url(img_src, destination)
        
        return await download_from_page(selector, destination)
    else:
        raise ValueError("Either 'url' or 'selector' must be provided.")
