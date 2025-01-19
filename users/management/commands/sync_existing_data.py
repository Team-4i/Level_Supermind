from django.core.management.base import BaseCommand
from users.models import UserProfile, ART
from users.astra_utils import sync_to_astra

class Command(BaseCommand):
    help = 'Sync existing data from Django to Astra DB'

    def handle(self, *args, **options):
        self.stdout.write("Starting data sync to Astra DB...")

        # Sync UserProfiles
        self.stdout.write("\nSyncing UserProfiles...")
        profiles = UserProfile.objects.all()
        for profile in profiles:
            try:
                self.stdout.write(f"Syncing profile for {profile.user.username}")
                sync_to_astra(profile)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error syncing profile {profile.user.username}: {str(e)}"))

        # Sync ARTs
        self.stdout.write("\nSyncing ART requests...")
        arts = ART.objects.all()
        for art in arts:
            try:
                # Use analysis_query preview instead of product_name
                preview = art.analysis_query[:50] + "..." if len(art.analysis_query) > 50 else art.analysis_query
                self.stdout.write(f"Syncing ART: {preview}")
                sync_to_astra(art)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error syncing ART ID {art.id}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS("\nSync completed!")) 