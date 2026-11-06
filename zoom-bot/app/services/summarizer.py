# app/services/summarizer.py

import os
import time
import logging
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MAX_INPUT_CHARS = 4000

# Retry constants
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def detect_language(text: str) -> str:
    logger.info("[LANGUAGE] Detecting language...")
    prompt = f"What language is the following text? Return only the ISO code (for example bg, en, de, fr). Text:\n\n{text[:800]}"

    try:
        response = call_openai(prompt, system_message="Detect the language of the text. Return ISO code only.")
        lang = response.strip().lower()
        logger.info(f"[LANGUAGE] Detected language: {lang}")
        return lang if lang in ["bg", "en"] else "en"
    except Exception as e:
        logger.error(f"[LANGUAGE ERROR] {str(e)}")
        return "en"


def split_transcript(text: str, max_chars: int = MAX_INPUT_CHARS) -> List[str]:
    logger.info("[TRANSCRIPT] Splitting transcript...")
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) < max_chars:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            current = para + "\n\n"
    if current:
        chunks.append(current.strip())

    logger.info(f"[TRANSCRIPT] Split into {len(chunks)} chunks.")
    return chunks


def call_openai(prompt: str, system_message: str = "You are a helpful assistant.") -> str:
    """
    Calls OpenAI API with retries and timeout
    """
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                timeout=30,  # seconds timeout
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            retries += 1
            logger.warning(f"⚠️ OpenAI call failed (attempt {retries}): {e}")
            if retries < MAX_RETRIES:
                logger.info(f"🔄 Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("❌ All OpenAI retries failed.")
                raise e


def summarize_chunk(transcript_chunk: str, language: str) -> str:
    if language == "bg":
        prompt = f"""
        Summarize the following section from a Zoom meeting:

        ---
        {transcript_chunk}
        ---

        Use a clear style with bullets or paragraphs. Do not translate technical terms.
        """
    else:
        prompt = f"""
        Summarize the following section from a Zoom meeting:

        ---
        {transcript_chunk}
        ---

        Use clear bullet points or short paragraphs. Do not translate technical terms.
        """
    return call_openai(prompt)


def summarize_transcript(transcript: str, language: str = None) -> (str, List[str]):
    logger.info("[SUMMARY] Generating meeting summary...")

    if not language:
        language = detect_language(transcript)

    chunks = split_transcript(transcript)

    if len(chunks) == 1:
        logger.info("[SUMMARY] Single chunk detected, summarizing directly.")
        summary = summarize_chunk(chunks[0], language)
        return summary, [summary]

    logger.info(f"[SUMMARY] Processing {len(chunks)} chunks...")

    partial_summaries = []
    for i, chunk in enumerate(chunks):
        try:
            logger.info(f"[SUMMARY] Summarizing chunk {i + 1}/{len(chunks)}...")
            part = summarize_chunk(chunk, language)
            partial_summaries.append(part)
        except Exception as e:
            logger.error(f"[SUMMARY ERROR] Failed summarizing chunk {i + 1}: {str(e)}")

    if not partial_summaries:
        return "⚠️ Could not summarize the meeting.", []

    logger.info("[SUMMARY] Merging chunk summaries...")
    merged_text = "\n\n".join(partial_summaries)
    final_summary = summarize_chunk(merged_text, language)

    return final_summary, partial_summaries
