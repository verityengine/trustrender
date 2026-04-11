FROM python:3.12-slim

ARG TYPST_VERSION=0.14.2

WORKDIR /app

# Install Typst CLI binary (server requires subprocess backend for killable timeouts)
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends curl xz-utils ca-certificates; \
    ARCH="$(dpkg --print-architecture)"; \
    case "${ARCH}" in \
        amd64) TYPST_ARCH="x86_64-unknown-linux-musl" ;; \
        arm64) TYPST_ARCH="aarch64-unknown-linux-musl" ;; \
        *) echo "Unsupported architecture: ${ARCH}"; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-${TYPST_ARCH}.tar.xz" \
        -o /tmp/typst.tar.xz; \
    tar -xf /tmp/typst.tar.xz -C /tmp; \
    mv "/tmp/typst-${TYPST_ARCH}/typst" /usr/local/bin/typst; \
    chmod +x /usr/local/bin/typst; \
    rm -rf /tmp/typst*; \
    apt-get purge -y curl xz-utils; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*; \
    typst --version

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY fonts/ fonts/
COPY examples/ examples/

# Install the package
RUN pip install --no-cache-dir .

# Tell Formforge where bundled fonts are
ENV FORMFORGE_FONT_PATH=/app/fonts
ENV FORMFORGE_TEMPLATES_DIR=/app/examples

# Default: run the server with bundled examples
# Override templates: docker run -e FORMFORGE_TEMPLATES_DIR=/templates ...
EXPOSE 8190

ENTRYPOINT ["formforge"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8190"]
