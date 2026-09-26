from django.core.management.base import BaseCommand

from ranker.public_article_pages import write_public_article_pages


class Command(BaseCommand):
    help = "Generate crawlable article pages in the frontend build served by Nginx."

    def handle(self, *args, **options):
        self.stdout.write(f"Generated {write_public_article_pages()} article pages")
