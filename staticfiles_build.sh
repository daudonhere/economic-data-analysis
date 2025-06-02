set -e

echo "Mengumpulkan file statis..."
python3 manage.py collectstatic --noinput
echo "Selesai mengumpulkan file statis."