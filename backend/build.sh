uv sync

uv run python manage.py collectstatic --no-input

uv run python manage.py migrate

uv run python manage.py import_places

uv run python manage.py createsuperuser --noinput