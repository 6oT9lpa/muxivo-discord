from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class MediaAttachmentRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attachment_id: str = Field(min_length=1, max_length=128, pattern=r"^[0-9A-Za-z_.:-]+$")
    download_url: HttpUrl | None = Field(default=None, max_length=2_048)
    media_reference: str | None = Field(default=None, min_length=1, max_length=512)
    file_name: str | None = Field(default=None, max_length=255)
    content_type: str = Field(min_length=1, max_length=127)
    file_size: int = Field(gt=0, le=104_857_600)
    width: int | None = Field(default=None, gt=0, le=100_000)
    height: int | None = Field(default=None, gt=0, le=100_000)

    @model_validator(mode="after")
    def require_one_source(self) -> "MediaAttachmentRequest":
        if (self.download_url is None) == (self.media_reference is None):
            raise ValueError("exactly one media source is required")
        if self.download_url is not None and self.download_url.scheme != "https":
            raise ValueError("download_url must use HTTPS")
        return self
