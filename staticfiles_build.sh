set -e
echo "collecting static files..."
python manage.py collectstatic --noinput
echo "finished collecting static files."