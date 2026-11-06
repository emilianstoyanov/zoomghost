# app/services/transcriber.py

import os
import time
import glob
from openai import OpenAI
from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.utils import which
from app.logging_config import setup_logger

load_dotenv()

logger = setup_logger(__name__)

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)


def ensure_ffmpeg_available():
    AudioSegment.converter = which("ffmpeg")
    if not AudioSegment.converter:
        raise Exception("❌ ffmpeg not found! Please ensure ffmpeg is installed and in PATH.")


def transcribe_audio(filepath: str) -> str:
    ensure_ffmpeg_available()
    logger.info(f"[TRANSCRIBE] Uploading file: {filepath}")

    if not os.path.exists(filepath):
        raise Exception(f"[TRANSCRIBE ERROR] File not found: {filepath}")

    temp_validated = None
    try:
        file_ext = filepath.split('.')[-1].lower()

        # Validate the file and export it with pydub
        try:
            audio = AudioSegment.from_file(filepath)
            temp_validated = f"{filepath}_validated.{file_ext}"

            valid_formats = ['flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm']
            format_to_use = file_ext if file_ext in valid_formats else "mp3"
            if file_ext not in valid_formats:
                logger.warning(f"[TRANSCRIBE] Unsupported input format '{file_ext}' – exporting as mp3.")
            if file_ext == "m4a":
                format_to_use = "mp4"  # 🎯 Compatible with OpenAI Whisper

            audio.export(temp_validated, format=format_to_use)
            filepath = temp_validated
            logger.info(f"[TRANSCRIBE] Validated and exported file: {temp_validated}")
        except Exception as e:
            logger.warning(f"[TRANSCRIBE] Validation skipped: {str(e)}")

        valid_filepath = ensure_valid_audio_format(filepath)
        with open(valid_filepath, "rb") as audio_file:
            try:
                start_time = time.time()
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
                logger.info(f"[TRANSCRIBE] API call successful in {time.time() - start_time:.2f} seconds")
                transcript_text = response
            except Exception as api_error:
                logger.error(f"[TRANSCRIBE ERROR] API call failed: {str(api_error)}")
                raise api_error

        if valid_filepath != filepath and os.path.exists(valid_filepath):
            os.remove(valid_filepath)
            logger.info(f"[CLEANUP] Removed converted file: {valid_filepath}")

        if temp_validated and os.path.exists(temp_validated):
            os.remove(temp_validated)
            logger.info(f"[CLEANUP] Removed validated file: {temp_validated}")

        return transcript_text

    except Exception as e:
        logger.error(f"[TRANSCRIBE ERROR] {str(e)}")
        temp_files = glob.glob(f"{filepath}*")
        logger.error(f"[TRANSCRIBE ERROR] Related temp files: {temp_files}")
        raise e


def split_audio_file(filepath: str, max_duration_sec: int = 600) -> list[str]:
    """
    Split an audio file into parts of at most `max_duration_sec` seconds.
    """
    ensure_ffmpeg_available()
    logger.info(f"[AUDIO] Splitting file: {filepath}")

    try:
        audio = AudioSegment.from_file(filepath)
        total_ms = len(audio)
        max_ms = max_duration_sec * 1000

        chunks = []
        for i in range(0, total_ms, max_ms):
            part = audio[i:i + max_ms]
            chunk_path = f"{filepath}_part_{i // max_ms}.mp3"
            part.export(chunk_path, format="mp3", bitrate="128k")
            logger.info(f"[AUDIO] Exported chunk {i // max_ms}: {chunk_path}")
            chunks.append(chunk_path)

        logger.info(f"[AUDIO] Total chunks created: {len(chunks)}")
        return chunks
    except Exception as e:
        logger.error(f"[AUDIO ERROR] {str(e)}")
        raise e


def ensure_valid_audio_format(filepath: str) -> str:
    try:
        valid_formats = ['flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm']

        file_ext = filepath.split('.')[-1].lower()
        logger.info(f"[FORMAT] Checking file format: {file_ext}")

        if file_ext in valid_formats:
            logger.info(f"[FORMAT] File already valid: {file_ext}")
            return filepath

        output_path = f"{filepath.rsplit('.', 1)[0]}.mp3"
        logger.info(f"[FORMAT] Converting to MP3: {output_path}")

        audio = AudioSegment.from_file(filepath)

        export_format = "mp4" if file_ext == "m4a" else "mp3"
        audio.export(output_path, format=export_format, bitrate="128k")

        logger.info(f"[FORMAT] Successfully converted to {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"[FORMAT ERROR] Failed to convert: {str(e)}")
        return filepath
