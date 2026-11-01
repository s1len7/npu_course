"""Hailo-8L Whisper(base)를 Wyoming STT 서버로 노출한다 (HA Wyoming 통합용).

hailo-apps의 speech_recognition 파이프라인을 재사용하고, 두 가지만 바꾼다.
- 언어 토큰을 <|en|>에서 지정 언어로
- HailoRT 멀티프로세스 서비스 사용 (Frigate와 NPU 공유)
"""

import argparse
import asyncio
import logging
import sys
from functools import partial
from pathlib import Path

import numpy as np
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler, AsyncServer

APP_DIR = Path.home() / "hailo-apps/hailo_apps/python/standalone_apps/speech_recognition"
MODEL_DIR = Path("/usr/local/hailo/resources/models/hailo8l")
ENCODER = MODEL_DIR / "base-whisper-encoder-5s_h8l.hef"
DECODER = MODEL_DIR / "base-whisper-decoder-fixed-sequence-matmul-split_h8l.hef"
RATE = 16000
RESULT_TIMEOUT_S = 30

sys.path.insert(0, str(APP_DIR))
import whisper_pipeline  # noqa: E402
from audio_utils import improve_audio, preprocess_audio  # noqa: E402
from postprocessing import clean_transcription  # noqa: E402

logger = logging.getLogger("hailo_whisper")


_VDevice = whisper_pipeline.VDevice


class SharedVDevice(_VDevice):
    @staticmethod
    def create_params():
        params = _VDevice.create_params()
        params.multi_process_service = True
        return params


whisper_pipeline.VDevice = SharedVDevice


class HailoWhisper(whisper_pipeline.WhisperPipeline):
    language = "ko"

    def _build_forced_decoder_ids(self):
        tokens = ("<|startoftranscript|>", f"<|{self.language}|>", "<|transcribe|>", "<|notimestamps|>")
        ids = [self.tokenizer.convert_tokens_to_ids(t) for t in tokens]
        if self.tokenizer.unk_token_id in ids:
            raise ValueError(f"Unsupported language: {self.language}")
        return ids

    def transcribe(self, audio: np.ndarray) -> str:
        audio, start = improve_audio(audio)
        if start is None:
            return ""
        chunk = self.get_chunk_length()
        texts = []
        for mel in preprocess_audio(audio, chunk_length=chunk, chunk_offset=max(start - 0.2, 0)):
            self.send_data(mel)
            texts.append(self._results_q.get(timeout=RESULT_TIMEOUT_S))
        return clean_transcription(" ".join(texts)).strip()

    def is_alive(self) -> bool:
        return self._thread.is_alive()


class Handler(AsyncEventHandler):
    def __init__(self, info: Info, model: HailoWhisper, lock: asyncio.Lock, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.info = info
        self.model = model
        self.lock = lock
        self.converter = AudioChunkConverter(rate=RATE, width=2, channels=1)
        self.audio = bytearray()

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self.info.event())
            return True
        if Transcribe.is_type(event.type) or AudioStart.is_type(event.type):
            if AudioStart.is_type(event.type):
                self.audio.clear()
            return True
        if AudioChunk.is_type(event.type):
            self.audio += self.converter.convert(AudioChunk.from_event(event)).audio
            return True
        if AudioStop.is_type(event.type):
            pcm = np.frombuffer(bytes(self.audio), dtype=np.int16).astype(np.float32) / 32768.0
            self.audio.clear()
            text = ""
            if len(pcm) > 0:
                async with self.lock:
                    if not self.model.is_alive():
                        logger.error("Hailo inference thread is not running")
                    else:
                        loop = asyncio.get_running_loop()
                        try:
                            text = await loop.run_in_executor(None, self.model.transcribe, pcm)
                        except Exception:
                            logger.exception("Transcription failed")
            logger.info(f"Transcript ({len(pcm) / RATE:.1f}s audio): {text!r}")
            await self.write_event(Transcript(text=text).event())
            return False
        return True


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="tcp://127.0.0.1:10301")
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    HailoWhisper.language = args.language
    model = HailoWhisper(str(ENCODER), str(DECODER), variant="base", add_embed=True)
    await asyncio.sleep(3)
    if not model.is_alive():
        raise SystemExit("Failed to start Hailo inference (is the NPU shared via hailort.service?)")

    info = Info(asr=[AsrProgram(
        name="hailo-whisper",
        description="Whisper base on Hailo-8L",
        attribution=Attribution(name="Hailo", url="https://github.com/hailo-ai/hailo-apps"),
        installed=True,
        version="base-h8l",
        models=[AsrModel(
            name="whisper-base-h8l",
            description="Whisper base (5s window) on Hailo-8L",
            attribution=Attribution(name="OpenAI", url="https://github.com/openai/whisper"),
            installed=True,
            version="base",
            languages=[args.language],
        )],
    )])
    logger.info(f"Ready on {args.uri} (language={args.language})")
    server = AsyncServer.from_uri(args.uri)
    await server.run(partial(Handler, info, model, asyncio.Lock()))


if __name__ == "__main__":
    asyncio.run(main())
