"""
Naver Clova Speech Recognition (STT) 서비스

음성 파일을 받아서 텍스트로 변환합니다.
"""

import os
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class ClovaSpeechService:
    """Naver Clova Speech API를 사용한 STT (Speech-to-Text) 서비스"""

    # Naver Clova Speech API 설정
    CLOVA_INVOKE_URL = "https://naveropenapi.apigw.ntruss.com/recog/v1/stt"
    CLIENT_ID = os.getenv("CLOVA_CLIENT_ID", "59owlszf8m")
    CLIENT_SECRET = os.getenv("CLOVA_CLIENT_SECRET", "QR8wSsWHVqr9zweAeB3yDCe9FkBc9avSNyXu1NaV")

    # 지원 언어
    SUPPORTED_LANGUAGES = {
        "Kor": "한국어",
        "Eng": "영어",
        "Jpn": "일본어",
        "Chn": "중국어(간체)",
    }

    # 지원 오디오 포맷
    SUPPORTED_FORMATS = ["mp3", "aac", "ac3", "ogg", "flac", "wav"]

    @staticmethod
    def recognize_speech(
        audio_data: bytes,
        language: str = "Kor",
        audio_format: str = "wav"
    ) -> Optional[str]:
        """
        음성 파일을 텍스트로 변환

        Args:
            audio_data: 음성 파일의 바이너리 데이터
            language: 언어 코드 (Kor, Eng, Jpn, Chn)
            audio_format: 오디오 포맷 (mp3, aac, ac3, ogg, flac, wav)

        Returns:
            인식된 텍스트, 또는 None (실패 시)

        Raises:
            ValueError: 입력 검증 실패
            Exception: API 호출 오류
        """
        # 입력 검증
        if not audio_data:
            raise ValueError("음성 데이터가 비어있습니다")

        if language not in ClovaSpeechService.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"지원하지 않는 언어입니다. 지원 언어: {list(ClovaSpeechService.SUPPORTED_LANGUAGES.keys())}"
            )

        if audio_format.lower() not in ClovaSpeechService.SUPPORTED_FORMATS:
            raise ValueError(
                f"지원하지 않는 오디오 포맷입니다. 지원 포맷: {ClovaSpeechService.SUPPORTED_FORMATS}"
            )

        # 음성 길이 제한 (최대 60초)
        # WAV 포맷 기준: 44.1kHz, 16-bit, mono = 176,400 bytes/second
        # 보수적으로 200KB 이상 = 60초 초과로 간주
        MAX_AUDIO_SIZE = 200 * 1024  # 200KB
        if len(audio_data) > MAX_AUDIO_SIZE:
            print(f"⚠️ 경고: 음성 파일이 클 수 있습니다 ({len(audio_data)} bytes)")

        try:
            # 요청 헤더
            headers = {
                "X-NCP-APIGW-API-KEY-ID": ClovaSpeechService.CLIENT_ID,
                "X-NCP-APIGW-API-KEY": ClovaSpeechService.CLIENT_SECRET,
                "Content-Type": "application/octet-stream",
            }

            # 요청 파라미터
            params = {
                "lang": language
            }

            print(f"🔄 Clova Speech 호출 중... (언어: {language})")

            # API 호출
            response = requests.post(
                ClovaSpeechService.CLOVA_INVOKE_URL,
                headers=headers,
                params=params,
                data=audio_data,
                timeout=30,
            )

            # 응답 검증
            if response.status_code != 200:
                error_msg = response.text
                print(f"❌ Clova Speech API 오류 ({response.status_code}): {error_msg}")
                raise ValueError(f"Clova Speech API 호출 실패: {response.status_code}")

            # 응답 파싱
            result = response.json()
            print(f"📊 Clova Speech API 응답: {result}")

            recognized_text = result.get("text", "").strip()

            if not recognized_text:
                print(f"⚠️ 인식된 텍스트가 없습니다")
                print(f"   API 응답 전체: {result}")
                # API가 인식하지 못한 경우도 실패 처리
                raise ValueError("음성에서 인식 가능한 텍스트가 없습니다")

            print(f"✅ Clova Speech 인식 성공")
            print(f"   인식된 텍스트: {recognized_text[:100]}...")

            return recognized_text

        except requests.exceptions.ConnectionError as e:
            raise Exception(
                f"Clova Speech 서버에 연결할 수 없습니다: {str(e)}"
            )
        except requests.exceptions.Timeout:
            raise Exception("Clova Speech 요청 타임아웃")
        except Exception as e:
            raise Exception(f"음성 인식 오류: {str(e)}")

    @staticmethod
    def validate_audio_file(
        audio_bytes: bytes,
        file_name: str
    ) -> bool:
        """
        오디오 파일 유효성 검사

        Args:
            audio_bytes: 오디오 파일 바이너리
            file_name: 파일 이름

        Returns:
            유효하면 True, 아니면 False

        Raises:
            ValueError: 검증 실패 이유
        """
        if not audio_bytes:
            raise ValueError("오디오 파일이 비어있습니다")

        # 파일 크기 검증 (최대 200KB)
        MAX_SIZE = 200 * 1024
        if len(audio_bytes) > MAX_SIZE:
            raise ValueError(f"오디오 파일이 너무 큽니다 ({len(audio_bytes)} bytes > {MAX_SIZE} bytes)")

        # 파일 확장자 검증
        file_ext = file_name.split(".")[-1].lower()
        if file_ext not in ClovaSpeechService.SUPPORTED_FORMATS:
            raise ValueError(
                f"지원하지 않는 파일 형식입니다 (.{file_ext}). 지원 형식: {ClovaSpeechService.SUPPORTED_FORMATS}"
            )

        # 매직 바이트 검증 (선택사항)
        # WAV: 52 49 46 46 (RIFF)
        # MP3: FF FB 또는 FF FA
        # 여기서는 생략 (필요시 추가)

        return True


# ============================================================================
# 테스트
# ============================================================================

def test_clova_speech():
    """Clova Speech Service 테스트"""
    print("=" * 60)
    print("Clova Speech Service 테스트")
    print("=" * 60)

    print("\n✅ 설정 확인:")
    print(f"  Client ID: {ClovaSpeechService.CLIENT_ID}")
    print(f"  Client Secret: {ClovaSpeechService.CLIENT_SECRET[:10]}...")
    print(f"  Invoke URL: {ClovaSpeechService.CLOVA_INVOKE_URL}")

    print("\n✅ 지원 언어:")
    for lang_code, lang_name in ClovaSpeechService.SUPPORTED_LANGUAGES.items():
        print(f"  - {lang_code}: {lang_name}")

    print("\n✅ 지원 오디오 포맷:")
    for fmt in ClovaSpeechService.SUPPORTED_FORMATS:
        print(f"  - {fmt}")

    print("\n📝 테스트 케이스:")
    print("  1. 유효한 오디오 파일 검증")
    try:
        # 테스트용 더미 WAV 파일 (최소 크기)
        dummy_wav = b"RIFF" + b"\x00" * 36 + b"WAVEfmt " + b"\x00" * 100
        ClovaSpeechService.validate_audio_file(dummy_wav, "test.wav")
        print("  ✅ WAV 파일 검증 성공")
    except ValueError as e:
        print(f"  ❌ 검증 실패: {str(e)}")

    print("  2. 지원하지 않는 포맷 거부")
    try:
        ClovaSpeechService.validate_audio_file(b"test", "test.xyz")
        print("  ❌ 검증 실패 (지원하지 않는 포맷을 통과함)")
    except ValueError as e:
        print(f"  ✅ 예상대로 거부됨: {str(e)}")

    print("  3. 빈 오디오 파일 거부")
    try:
        ClovaSpeechService.validate_audio_file(b"", "test.wav")
        print("  ❌ 검증 실패 (빈 파일을 통과함)")
    except ValueError as e:
        print(f"  ✅ 예상대로 거부됨: {str(e)}")

    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    test_clova_speech()
