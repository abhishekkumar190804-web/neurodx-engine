#!/bin/bash
# entrypoint.sh

# Set defaults if env vars are not defined
: "${MONGO_URI:=mongodb+srv://abhishekkumar190804_db_user:Abhi%401908@neurobx.o07nree.mongodb.net/}"
: "${DB_NAME:=gre_prep}"
: "${OPENAI_API_KEY:=demo_openai_key}"

# Write to .env (optional, for libraries like python-dotenv)
cat <<EOF > .env
MONGO_URI=${MONGO_URI}
DB_NAME=${DB_NAME}
OPENAI_API_KEY=${OPENAI_API_KEY}
EOF

echo "Using MONGO_URI=${MONGO_URI}"
echo "Using DB_NAME=${DB_NAME}"

# Start FastAPI
exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}