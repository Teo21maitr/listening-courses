"""User-facing errors. Messages are safe to return to the frontend as-is."""


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidFileError(AppError):
    """Not a PDF, wrong extension or wrong content type."""


class FileTooLargeError(AppError):
    status_code = 413


class UnknownLanguageError(AppError):
    pass


class EmptyPdfError(AppError):
    pass


class ScannedPdfError(AppError):
    pass


class UnreadablePdfError(AppError):
    pass


class JobNotFoundError(AppError):
    status_code = 404


class AudioNotReadyError(AppError):
    status_code = 409


class TTSNotInstalledError(AppError):
    status_code = 500


class UnknownEngineError(AppError):
    status_code = 500


class VoiceModelMissingError(AppError):
    status_code = 500


class FfmpegMissingError(AppError):
    status_code = 500


class AudioGenerationError(AppError):
    status_code = 500


class AudioAssemblyError(AppError):
    status_code = 500
