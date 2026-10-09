"""Apple Vision OCR. Extracted text is evidence, never a model-generated quote."""

from pathlib import Path


def read_text(path: Path) -> str:
    try:
        import Vision
        from Foundation import NSURL
    except ImportError:
        raise ValueError("Install Apple Vision bindings with uv sync --extra models.") from None
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["en-US"])
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(
        NSURL.fileURLWithPath_(str(path)), {}
    )
    success, error = handler.performRequests_error_([request], None)
    if not success:
        raise ValueError("Apple Vision could not read this frame.")
    return "\n".join(
        str(result.topCandidates_(1)[0].string())
        for result in request.results() or []
        if result.topCandidates_(1)
    )
