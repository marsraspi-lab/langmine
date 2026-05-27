"""yt-dlp + ffmpeg audio adapter — wraps audio.py behind AudioProcessor port."""

from langmine.domain.ports import AudioProcessor
from langmine.audio import download_audio, clip_audio


class YtdlpAudioAdapter(AudioProcessor):
    """Downloads audio via yt-dlp and clips via ffmpeg."""

    def download(self, video_id: str, output_dir: str) -> str:
        return download_audio(video_id, output_dir=output_dir)

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
