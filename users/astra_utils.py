from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
from cassandra.policies import RetryPolicy, RoundRobinPolicy, ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cqlengine.connection import register_connection, set_default_connection
from django.conf import settings
import uuid
from datetime import datetime
from cassandra.cqlengine import connection
import logging
from cassandra.cqlengine.query import BatchQuery
from django.core.cache import cache
from functools import lru_cache, wraps
from asgiref.sync import async_to_sync
import asyncio
import threading

logger = logging.getLogger(__name__)

def get_astra_session():
    """Get or create Astra DB session"""
    try:
        if connection.cluster is not None and not connection.cluster.is_shutdown:
            return connection.session
        return setup_astra_connection()
    except Exception as e:
        logger.error(f"Error in get_astra_session: {str(e)}")
        raise

def setup_astra_connection():
    try:
        # Ensure schema management is allowed
        import os
        os.environ['CQLENG_ALLOW_SCHEMA_MANAGEMENT'] = '1'
        
        # Close any existing connections
        if connection.cluster is not None:
            connection.cluster.shutdown()
        if connection.session is not None:
            connection.session.shutdown()

        # Create execution profile with more lenient timeouts
        profile = ExecutionProfile(
            request_timeout=30,
            retry_policy=RetryPolicy(),
            load_balancing_policy=RoundRobinPolicy(),
            consistency_level=ConsistencyLevel.LOCAL_QUORUM
        )
        
        cloud_config = {
            'secure_connect_bundle': settings.ASTRA_DB_SECURE_BUNDLE_PATH
        }
        
        auth_provider = PlainTextAuthProvider(
            settings.ASTRA_DB_CLIENT_ID,
            settings.ASTRA_DB_CLIENT_SECRET
        )
        
        # Create cluster with simplified configuration
        cluster = Cluster(
            cloud=cloud_config,
            auth_provider=auth_provider,
            execution_profiles={EXEC_PROFILE_DEFAULT: profile},
            protocol_version=4,
            connect_timeout=30,
            control_connection_timeout=30,
            idle_heartbeat_interval=30
        )
        
        # Connect and create session
        session = cluster.connect(wait_for_all_pools=True)
        
        # Set the keyspace
        session.set_keyspace(settings.ASTRA_DB_KEYSPACE)
        
        # Register connection
        register_connection(str(session), session=session)
        set_default_connection(str(session))
        
        # Sync tables after connection
        from cassandra.cqlengine.management import sync_table, create_keyspace_simple
        from .astra_models import UserProfileAstra, ARTAstra
        
        # Create keyspace if it doesn't exist (Astra DB manages this automatically)
        if not settings.ASTRA_DB_KEYSPACE in connection.cluster.metadata.keyspaces:
            create_keyspace_simple(settings.ASTRA_DB_KEYSPACE, replication_factor=3)
        
        # Just sync the tables without additional properties
        sync_table(UserProfileAstra)
        sync_table(ARTAstra)
        
        # After sync, alter the tables with desired properties if needed
        session = connection.get_session()
        
        # Define table properties as CQL
        alter_table_properties = """
        ALTER TABLE {}.{} 
        WITH bloom_filter_fp_chance = 0.01
        AND caching = {{'keys': 'ALL', 'rows_per_partition': 'NONE'}}
        AND compaction = {{'class': 'org.apache.cassandra.db.compaction.UnifiedCompactionStrategy'}}
        AND compression = {{'chunk_length_in_kb': '64', 'class': 'org.apache.cassandra.io.compress.LZ4Compressor'}}
        AND read_repair = 'BLOCKING';
        """
        
        # Apply properties to both tables
        for table in ['user_profile_astra', 'art_astra']:
            try:
                session.execute(
                    alter_table_properties.format(settings.ASTRA_DB_KEYSPACE, table)
                )
            except Exception as table_error:
                logger.warning(f"Could not alter table {table} properties: {str(table_error)}")
        
        logger.info("Successfully connected to Astra DB and synced tables")
        return session
        
    except Exception as e:
        logger.error(f"Failed to connect to Astra DB: {str(e)}")
        raise

def async_sync_to_astra(func):
    @wraps(func)
    def wrapper(instance, *args, **kwargs):
        if not settings.ENABLE_ASTRA_SYNC:
            return
        
        # Run the sync in a separate thread
        thread = threading.Thread(
            target=lambda: func(instance, *args, **kwargs),
            daemon=True
        )
        thread.start()
        
    return wrapper

@async_sync_to_astra
def sync_to_astra(instance):
    """Async wrapper around the original sync function"""
    from .astra_models import UserProfileAstra, ARTAstra
    from .models import UserProfile, ART
    
    try:
        # Ensure connection is active
        if connection.cluster is None or connection.session is None:
            setup_astra_connection()
            
        # Create a batch operation
        with BatchQuery() as b:
            if isinstance(instance, UserProfile):
                user_id = uuid.UUID(int=instance.user.id)
                # Simple update or create without LWT
                UserProfileAstra.batch(b).create(
                    user_id=user_id,
                    username=instance.user.username,
                    bio=instance.bio or '',
                    company_name=instance.company_name or '',
                    website=instance.website or '',
                    industry=instance.industry or '',
                    research_interests=instance.research_interests or '',
                    preferred_platforms=instance.preferred_platforms or '',
                    created_at=instance.created_at,
                    updated_at=instance.updated_at
                )
                
            elif isinstance(instance, ART):
                art_id = uuid.UUID(int=instance.id)
                # Simple update or create without LWT
                ARTAstra.batch(b).create(
                    id=art_id,
                    user_id=uuid.UUID(int=instance.user.id),
                    analysis_query=instance.analysis_query,
                    keywords=instance.keywords,
                    content=instance.content,
                    analysis_result=instance.analysis_result or '',
                    web_analysis_result=instance.web_analysis_result or '',
                    overall_analysis=instance.overall_analysis or '',
                    created_at=instance.created_at,
                    updated_at=instance.updated_at
                )
                
    except Exception as e:
        logger.error(f"Error in sync_to_astra: {str(e)}")