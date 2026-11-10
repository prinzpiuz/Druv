# music-sync: Sockseek (Soulseek downloader) plus the Python job that drives it.
# Every version is a build argument set from version.env through compose.

ARG DOTNET_SDK_IMAGE
ARG PYTHON_IMAGE

# Build Sockseek from source at a fixed commit. Upstream publishes no image tag
# that could be pinned.
FROM ${DOTNET_SDK_IMAGE} AS sockseek
ARG SOCKSEEK_VERSION
ARG SOCKSEEK_COMMIT
WORKDIR /src
RUN git clone --depth 1 --branch "${SOCKSEEK_VERSION}" https://github.com/fiso64/sockseek.git . \
    && test "$(git rev-parse HEAD)" = "${SOCKSEEK_COMMIT}" \
    && dotnet restore Sockseek.HelpGenerator/Sockseek.HelpGenerator.csproj \
    && dotnet publish Sockseek.Cli/Sockseek.Cli.csproj -c Release -r linux-x64 \
        -p:PublishSingleFile=true -p:PublishTrimmed=false -p:OpenApiGenerateDocuments=false \
        --self-contained=true -o /out \
    && rm -f /out/*.pdb

FROM ${PYTHON_IMAGE}
ARG MUTAGEN_VERSION
# libicu: .NET needs it for text handling. tini: forwards stop signals to the
# job, which stops Sockseek cleanly.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libicu72 tini \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "mutagen==${MUTAGEN_VERSION}"
COPY --from=sockseek /out/sockseek /usr/local/bin/sockseek
COPY music_sync.py navidrome_playlists.py /app/
ENV PYTHONUNBUFFERED=1 HOME=/tmp
USER 1000:1000
ENTRYPOINT ["/usr/bin/tini", "--", "python3", "/app/music_sync.py"]
