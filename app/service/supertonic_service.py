"""
Supertonic TTS (Text-to-Speech) 서비스

텍스트를 음성(WAV 파일)으로 변환합니다.
"""

import os
import sys
import json
import numpy as np
import soundfile as sf
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class SupertonicService:
    """Supertonic TTS를 사용한 TTS (Text-to-Speech) 서비스"""

    # Supertonic 모델 설정
    MODEL_PATH = os.getenv("SUPERTONIC_MODEL_PATH", "/app/supertonic/assets")
    DEFAULT_SPEAKER = os.getenv("SUPERTONIC_DEFAULT_SPEAKER", "M1")
    INFERENCE_STEPS = int(os.getenv("SUPERTONIC_INFERENCE_STEPS", "10"))

    # Supertonic 파이썬 경로 (Docker 환경)
    SUPERTONIC_PY_PATH = "/app/supertonic/py"

    # 지원 언어
    SUPPORTED_LANGUAGES = {
        "ko": "한국어",
        "en": "영어",
        "es": "스페인어",
        "pt": "포르투갈어",
        "fr": "프랑스어",
    }

    # 지원 화자 (남성: M1-M5, 여성: F1-F5)
    SUPPORTED_SPEAKERS = [
        "M1", "M2", "M3", "M4", "M5",
        "F1", "F2", "F3", "F4", "F5"
    ]

    # 최대 텍스트 길이
    MAX_TEXT_LENGTH = 500

    # 모델 로딩 상태
    _text_to_speech = None
    _initialized = False

    @staticmethod
    def initialize():
        """
        서버 시작 시 모델 로딩 (1회만 실행)

        Supertonic TTS 모델을 미리 로딩합니다.
        """
        if SupertonicService._initialized:
            print("⚠️ Supertonic은 이미 초기화되었습니다")
            return

        try:
            print("🔄 Supertonic TTS 모델 초기화 중...")

            # Supertonic 파이썬 경로 추가
            if SupertonicService.SUPERTONIC_PY_PATH not in sys.path:
                sys.path.insert(0, SupertonicService.SUPERTONIC_PY_PATH)

            # helper 모듈에서 load_text_to_speech 임포트
            from helper import load_text_to_speech

            # 모델 빌드
            print(f"  모델 경로: {SupertonicService.MODEL_PATH}")
            print(f"  기본 화자: {SupertonicService.DEFAULT_SPEAKER}")
            print(f"  추론 스텝: {SupertonicService.INFERENCE_STEPS}")
            print(f"  ONNX 모델 로드 중...")

            onnx_dir = os.path.join(SupertonicService.MODEL_PATH, "onnx")
            SupertonicService._text_to_speech = load_text_to_speech(
                onnx_dir=onnx_dir,
                use_gpu=False
            )

            SupertonicService._initialized = True
            print("✅ Supertonic TTS 초기화 완료")

        except ImportError as e:
            print(f"❌ Supertonic helper 모듈 임포트 오류: {str(e)}")
            print("   Supertonic이 올바르게 설치되지 않았습니다")
            raise
        except Exception as e:
            print(f"❌ Supertonic 초기화 오류: {str(e)}")
            raise

    @staticmethod
    def text_to_speech(
        text: str,
        language: str = "ko",
        speaker: Optional[str] = None
    ) -> bytes:
        """
        텍스트를 음성(WAV)으로 변환

        Args:
            text: 변환할 텍스트
            language: 언어 코드 (ko, en, es, pt, fr)
            speaker: 화자 코드 (M1-M5, F1-F5), 기본값은 DEFAULT_SPEAKER

        Returns:
            WAV 파일의 바이너리 데이터

        Raises:
            ValueError: 입력 검증 실패
            Exception: TTS 변환 오류
        """
        # 입력 검증
        SupertonicService.validate_text(text)

        # 화자 설정
        if speaker is None:
            speaker = SupertonicService.DEFAULT_SPEAKER
        if speaker not in SupertonicService.SUPPORTED_SPEAKERS:
            raise ValueError(
                f"지원하지 않는 화자입니다. 지원 화자: {SupertonicService.SUPPORTED_SPEAKERS}"
            )

        # 언어 검증
        if language not in SupertonicService.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"지원하지 않는 언어입니다. 지원 언어: {list(SupertonicService.SUPPORTED_LANGUAGES.keys())}"
            )

        # 모델 초기화 확인
        if not SupertonicService._initialized or SupertonicService._text_to_speech is None:
            raise Exception("Supertonic 모델이 초기화되지 않았습니다")

        try:
            print(f"🔄 TTS 변환 중... (텍스트: {text[:50]}..., 화자: {speaker}, 언어: {language})")

            # helper 모듈에서 load_voice_style 임포트
            from helper import load_voice_style

            # 화자 스타일 경로
            voice_style_path = os.path.join(
                SupertonicService.MODEL_PATH,
                "voice_styles",
                f"{speaker}.json"
            )

            # 음성 스타일 파일 존재 확인
            if not os.path.exists(voice_style_path):
                raise ValueError(
                    f"음성 스타일 파일을 찾을 수 없습니다: {voice_style_path}"
                )

            # 음성 스타일 로드
            style = load_voice_style([voice_style_path], verbose=False)

            # TTS 변환 (TextToSpeech 의 __call__ 메서드 사용)
            # 시그니처: __call__(text: str, lang: str, style: Style, total_step: int, speed: float)
            wav, duration = SupertonicService._text_to_speech(
                text=text,
                lang=language,
                style=style,
                total_step=SupertonicService.INFERENCE_STEPS,
                speed=1.0
            )

            # 음성 신호 추출 (duration에 따라 trim)
            sample_rate = SupertonicService._text_to_speech.sample_rate
            audio_length = int(sample_rate * duration[0].item())
            audio = wav[0, :audio_length]

            # WAV 파일로 변환
            wav_bytes = SupertonicService._numpy_to_wav(audio, sample_rate)

            print(f"✅ TTS 변환 완료 (크기: {len(wav_bytes)} bytes)")

            return wav_bytes

        except Exception as e:
            print(f"❌ TTS 변환 오류: {str(e)}")
            raise Exception(f"텍스트 음성 변환 중 오류가 발생했습니다: {str(e)}")

    @staticmethod
    def validate_text(text: str) -> bool:
        """
        입력 텍스트 검증

        Args:
            text: 검증할 텍스트

        Returns:
            유효하면 True

        Raises:
            ValueError: 검증 실패 이유
        """
        if not text:
            raise ValueError("텍스트가 비어있습니다")

        if not isinstance(text, str):
            raise ValueError("텍스트는 문자열이어야 합니다")

        if len(text) > SupertonicService.MAX_TEXT_LENGTH:
            raise ValueError(
                f"텍스트가 너무 깁니다 ({len(text)} > {SupertonicService.MAX_TEXT_LENGTH})"
            )

        return True

    @staticmethod
    def _numpy_to_wav(audio: np.ndarray, sample_rate: int = 24000) -> bytes:
        """
        Numpy 배열을 WAV 바이너리로 변환

        Args:
            audio: 음성 데이터 (numpy 배열)
            sample_rate: 샘플 레이트 (기본값: 24000 Hz)

        Returns:
            WAV 파일 바이너리

        Raises:
            Exception: 변환 오류
        """
        try:
            import io

            # 메모리에 WAV 파일 생성
            wav_buffer = io.BytesIO()

            # 샘플 값을 16-bit 정수로 정규화
            if audio.dtype != np.int16:
                # 정규화: -1.0 ~ 1.0 범위를 -32768 ~ 32767로 변환
                audio = np.clip(audio, -1.0, 1.0)
                audio = (audio * 32767).astype(np.int16)

            # WAV 파일 작성
            sf.write(wav_buffer, audio, sample_rate, format='WAV')

            # 바이너리 데이터 반환
            wav_bytes = wav_buffer.getvalue()
            wav_buffer.close()

            return wav_bytes

        except Exception as e:
            raise Exception(f"WAV 파일 생성 오류: {str(e)}")


# ============================================================================
# 테스트
# ============================================================================

def test_supertonic_service():
    """Supertonic Service 테스트"""
    print("=" * 60)
    print("Supertonic Service 테스트")
    print("=" * 60)

    print("\n✅ 설정 확인:")
    print(f"  모델 경로: {SupertonicService.MODEL_PATH}")
    print(f"  기본 화자: {SupertonicService.DEFAULT_SPEAKER}")
    print(f"  추론 스텝: {SupertonicService.INFERENCE_STEPS}")

    print("\n✅ 지원 언어:")
    for lang_code, lang_name in SupertonicService.SUPPORTED_LANGUAGES.items():
        print(f"  - {lang_code}: {lang_name}")

    print("\n✅ 지원 화자:")
    for speaker in SupertonicService.SUPPORTED_SPEAKERS:
        print(f"  - {speaker}")

    print("\n📝 테스트 케이스:")
    print("  1. 텍스트 검증 성공")
    try:
        SupertonicService.validate_text("테스트 텍스트입니다")
        print("  ✅ 유효한 텍스트 검증 성공")
    except ValueError as e:
        print(f"  ❌ 검증 실패: {str(e)}")

    print("  2. 빈 텍스트 거부")
    try:
        SupertonicService.validate_text("")
        print("  ❌ 검증 실패 (빈 텍스트를 통과함)")
    except ValueError as e:
        print(f"  ✅ 예상대로 거부됨: {str(e)}")

    print("  3. 너무 긴 텍스트 거부")
    try:
        SupertonicService.validate_text("가" * 501)
        print("  ❌ 검증 실패 (너무 긴 텍스트를 통과함)")
    except ValueError as e:
        print(f"  ✅ 예상대로 거부됨: {str(e)}")

    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    test_supertonic_service()
