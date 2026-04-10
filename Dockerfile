FROM python:3.12-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY fonts/ fonts/
COPY examples/ examples/

# Install the package
RUN pip install --no-cache-dir .

# Tell Typeset where bundled fonts are
ENV TYPESET_FONT_PATH=/app/fonts

# Default: run the server with bundled examples
# Override with custom --templates path for production use
EXPOSE 8190

ENTRYPOINT ["typeset"]
CMD ["serve", "--templates", "/app/examples", "--host", "0.0.0.0", "--port", "8190"]
