from django.core.management.base import BaseCommand

from ranker.public_sitemap import write_public_sitemap


class Command(BaseCommand):
    help = "Regenerate the public sitemap in the frontend build served by Nginx."

    def handle(self, *args, **options):
        self.stdout.write(f"Generated {write_public_sitemap()}")
