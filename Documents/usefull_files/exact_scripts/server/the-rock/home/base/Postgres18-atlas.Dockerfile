# Общий Postgres 18 сервера (контейнер `postgres` из ~/base/compose.yaml) с тем, что нужно атласу:
# pgvector — тип `vector` для векторов кадров (ревизия 0018); словари hunspell для поиска
# (ревизия 0002). Тот же Debian trixie, что в образе атласа: Debian сам кладёт словари в
# tsearch_data в UTF-8, русский копируется с «ё» → «е» (ru_ru_e) — файлы совпадают байт в байт.
# pg_trgm (ревизия 0023) уже есть в самом postgres:18. Кладёт рядом с compose.yaml и
# подключает deploy/setup-pg18.sh; данные и конфиг контейнера не меняются.

FROM postgres:18

RUN apt-get update \
    && apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-pgvector" \
        hunspell-ru hunspell-en-us \
    && cd "/usr/share/postgresql/${PG_MAJOR}/tsearch_data" \
    && sed 's/ё/е/g; s/Ё/Е/g' ru_ru.dict > ru_ru_e.dict \
    && sed 's/ё/е/g; s/Ё/Е/g' ru_ru.affix > ru_ru_e.affix \
    && rm -rf /var/lib/apt/lists/*
