FROM postgres:18

RUN apt-get update \
    && apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-pgvector" \
        hunspell-ru hunspell-en-us \
    && cd "/usr/share/postgresql/${PG_MAJOR}/tsearch_data" \
    && sed 's/ё/е/g; s/Ё/Е/g' ru_ru.dict > ru_ru_e.dict \
    && sed 's/ё/е/g; s/Ё/Е/g' ru_ru.affix > ru_ru_e.affix \
    && rm -rf /var/lib/apt/lists/*
