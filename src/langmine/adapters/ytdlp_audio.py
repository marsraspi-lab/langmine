"""yt-dlp + ffmpeg audio adapter — wraps audio.py behind AudioProcessor port."""

from langmine.audio import capture_frame, clip_audio, download_audio
from langmine.domain.ports import AudioProcessor


class YtdlpAudioAdapter(AudioProcessor):
    """Downloads audio via yt-dlp and clips via ffmpeg."""

    def __init__(self, user_agent: str = ""):
        self._user_agent = user_agent

    def download(self, video_id: str, output_dir: str) -> str:
        return download_audio(
            video_id, output_dir=output_dir, user_agent=self._user_agent
        )

    def clip(
        self,
        audio_path: str,
        start_ms: float,
        end_ms: float,
        pad_before_ms: int,
        pad_after_ms: int,
        output_dir: str,
        sentence_id: str,
    ) -> str:
        return clip_audio(
            audio_path=audio_path,
            start_ms=start_ms,
            end_ms=end_ms,
            pad_before_ms=pad_before_ms,
            pad_after_ms=pad_after_ms,
            output_dir=output_dir,
            sentence_id=sentence_id,
        )

    def capture_frame(
        self,
        video_id: str,
        timestamp_ms: float,
        output_dir: str,
        sentence_id: str,
    ) -> str | None:
        return capture_frame(
            video_id_or_url=video_id,
            timestamp_ms=timestamp_ms,
            output_dir=output_dir,
            sentence_id=sentence_id,
        )
