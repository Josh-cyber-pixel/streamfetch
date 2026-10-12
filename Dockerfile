FROM python:3.12-slim

# ffmpeg is needed for muxing separate streams and for audio extraction.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

ENV STREAMFETCH_DOWNLOAD_DIR=/data
ENV STREAMFETCH_HOST=0.0.0.0
ENV STREAMFETCH_PORT=8000
VOLUME ["/data"]
EXPOSE 8000

CMD ["python", "-m", "streamfetch.web.app"]
