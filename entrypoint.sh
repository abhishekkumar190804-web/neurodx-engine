#!/bin/bash
# entrypoint.sh

# Set defaults if env vars are not defined
: "${MONGODB_URI:=mongodb://localhost:27017}"
: "${DB_NAME:=gre_prep}"
: "${GEMINI_API_KEY:=demo_gemini_key}"
: "${OPENAI_API_KEY:=demo_openai_key}"

# Write to .env (optional, for libraries like python-dotenv)
cat <<EOF > .env
MONGODB_URI=${MONGODB_URI}
DB_NAME=${DB_NAME}
GEMINI_API_KEY=${GEMINI_API_KEY}
OPENAI_API_KEY=${OPENAI_API_KEY}
EOF

echo "Using MONGODB_URI=${MONGODB_URI}"
echo "Using DB_NAME=${DB_NAME}"

# Start FastAPI
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}