"""
MiniMax Video Generation Service.

Async service for image-to-video generation using the MiniMax API.
"""

import base64
import logging
import mimetypes
import time
from typing import Optional
import httpx
import config

logger = logging.getLogger(__name__)


class MiniMaxService:
    """Async client for MiniMax image-to-video API."""

    def __init__(self):
        self.api_key = config.MINIMAX_API_KEY
        self.base_url = config.MINIMAX_BASE_URL
        self.default_model = config.MINIMAX_DEFAULT_MODEL
        self._tasks: dict[str, dict] = {}

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def encode_image(self, image_bytes: bytes, filename: str) -> str:
        """Encode image as base64 data URI for MiniMax API."""
        mime = mimetypes.guess_type(filename)[0] or "image/jpeg"
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    async def create_video_task(
        self,
        image_base64: str,
        prompt: str,
        model: Optional[str] = None,
        prompt_optimizer: bool = True,
        duration: Optional[int] = None,
        fast_pretreatment: Optional[bool] = None,
        resolution: Optional[str] = None,
    ) -> str:
        """Create a video generation task and return task_id."""
        payload = {
            "model": model or self.default_model,
            "first_frame_image": image_base64,
            "prompt": prompt,
            "prompt_optimizer": prompt_optimizer,
        }
        if duration is not None:
            payload["duration"] = duration
        if fast_pretreatment is not None:
            payload["fast_pretreatment"] = fast_pretreatment
        if resolution is not None:
            payload["resolution"] = resolution
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/video_generation",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            task_id = data.get("task_id")
            if not task_id:
                raise ValueError(f"MiniMax video generation failed: {data}")

            self._tasks[task_id] = {
                "status": "Processing",
                "prompt": prompt,
                "video_url": None,
                "error": None,
                "created_at": time.time(),
            }
            return task_id

    async def query_task_status(self, task_id: str) -> dict:
        """Query task status and update internal tracking."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/query/video_generation",
                headers=self._headers(),
                params={"task_id": task_id},
            )
            resp.raise_for_status()
            data = resp.json()

        status = data.get("status", "Unknown")
        file_id = data.get("file_id")
        video_url = None

        if status == "Success" and file_id:
            video_url = await self.retrieve_file_url(file_id)

        if task_id in self._tasks:
            self._tasks[task_id]["status"] = status
            self._tasks[task_id]["video_url"] = video_url
            if status == "Fail":
                self._tasks[task_id]["error"] = data.get("base_resp", {}).get(
                    "status_msg", "Unknown error"
                )

        return {
            "task_id": task_id,
            "status": status,
            "file_id": file_id,
            "video_url": video_url,
        }

    async def retrieve_file_url(self, file_id: str) -> str:
        """Get download URL for a completed video file."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/files/retrieve",
                headers=self._headers(),
                params={"file_id": file_id},
            )
            resp.raise_for_status()
            data = resp.json()
            url = data.get("file", {}).get("download_url")
            if not url:
                raise ValueError(f"MiniMax file retrieve failed: {data}")
            return url

    def get_task(self, task_id: str) -> Optional[dict]:
        return self._tasks.get(task_id)

    def cleanup_old_tasks(self, max_age_seconds: int = 3600):
        """Remove tasks older than max_age_seconds."""
        now = time.time()
        to_delete = [
            tid
            for tid, t in self._tasks.items()
            if now - t["created_at"] > max_age_seconds
        ]
        for tid in to_delete:
            del self._tasks[tid]


# Singleton instance
minimax_service = MiniMaxService()
