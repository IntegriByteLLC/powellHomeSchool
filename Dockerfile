FROM postgres:16

RUN apt-get update && apt-get install -y \
    postgresql-server-dev-16 \
    build-essential \
    git \
    vim \
 && git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git \
 && cd pgvector && make && make install \
 && rm -rf /var/lib/apt/lists/*
