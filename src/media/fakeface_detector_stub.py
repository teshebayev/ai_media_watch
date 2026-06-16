"""FakeFace детектор (Студент 6, ТЗ §13, кейс 9).

Возвращает поля media_anomalies из ТЗ §5. Для MVP:
  - has_face — реальная детекция через OpenCV Haar cascade (если cv2 установлен);
  - possible_deepfake / synthetic_voice_suspected / lip_sync_anomaly — эвристические
    флаги. Полноценную модель (FaceForensics++/DFDC/FakeAVCeleb) подключает Студент 6;
    для хакатона значения можно проставлять вручную по размеченным примерам.

Запуск:
    python -m src.media.fakeface_detector_stub path/to/video_or_frame
"""

from __future__ import annotations

import sys


def _detect_face_opencv(image_path: str) -> bool:
    """has_face через Haar cascade. Если cv2 не установлен — None (неизвестно)."""
    try:
        import cv2
    except ImportError:
        return False
    img = cv2.imread(image_path)
    if img is None:
        return False
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    return len(faces) > 0


def analyze(video_path: str, frame_path: str | None = None) -> dict:
    """media_anomalies. frame_path — извлечённый кадр для детекции лица (опц.)."""
    has_face = _detect_face_opencv(frame_path) if frame_path else False
    return {
        "has_face": has_face,
        # TODO (Студент 6): заменить эвристики на реальную deepfake-модель.
        "possible_deepfake": False,
        "synthetic_voice_suspected": False,
        "lip_sync_anomaly": False,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    print(analyze(sys.argv[1], frame_path=sys.argv[1]))
