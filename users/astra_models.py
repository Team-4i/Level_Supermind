from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model

class UserProfileAstra(Model):
    __keyspace__ = 'django_keyspace'
    __table_name__ = 'user_profile_astra'
    
    user_id = columns.UUID(primary_key=True)
    username = columns.Text(required=True, index=True)
    bio = columns.Text()
    company_name = columns.Text()
    website = columns.Text()
    industry = columns.Text()
    research_interests = columns.Text()
    preferred_platforms = columns.Text()
    created_at = columns.DateTime()
    updated_at = columns.DateTime()

class ARTAstra(Model):
    __keyspace__ = 'django_keyspace'
    __table_name__ = 'art_astra'
    
    id = columns.UUID(primary_key=True)
    user_id = columns.UUID(required=True, index=True)
    analysis_query = columns.Text(required=True)
    keywords = columns.List(value_type=columns.Text())
    content = columns.Map(key_type=columns.Text(), value_type=columns.Text())
    analysis_result = columns.Text()
    web_analysis_result = columns.Text()
    overall_analysis = columns.Text()
    created_at = columns.DateTime()
    updated_at = columns.DateTime()

    class Meta:
        table_name = 'art_astra' 