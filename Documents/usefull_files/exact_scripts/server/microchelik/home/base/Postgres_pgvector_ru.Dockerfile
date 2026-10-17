FROM postgres:18

# For immich!
# After bump: rebuild, restart, in the immich DB run
# ALTER EXTENSION vchord UPDATE;  REINDEX INDEX face_index;  REINDEX INDEX clip_index;
ARG VCHORD_VERSION=1.1.1
ADD https://github.com/tensorchord/VectorChord/releases/download/${VCHORD_VERSION}/postgresql-18-vchord_${VCHORD_VERSION}-1_amd64.deb /tmp/vchord.deb

RUN apt-get update \
    && apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-pgvector" /tmp/vchord.deb \
        hunspell-ru hunspell-en-us \
    && cd "/usr/share/postgresql/${PG_MAJOR}/tsearch_data" \
    && sed 's/ё/е/g; s/Ё/Е/g' ru_ru.dict > ru_ru_e.dict \
    && sed 's/ё/е/g; s/Ё/Е/g' ru_ru.affix > ru_ru_e.affix \
    && rm -rf /var/lib/apt/lists/* /tmp/vchord.deb
