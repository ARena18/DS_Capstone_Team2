import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from pathlib import Path


class DatabaseManager:
    """
    PostgreSQL connection manager using SQLAlchemy.
    Reads connection params from environment variables.
    """
    
    def __init__(self):
        self.engine = self._create_engine()
    
    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine from environment variables."""
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "transit_db")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "postgres")
        
        conn_str = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        return create_engine(conn_str, pool_pre_ping=True, pool_size=5, max_overflow=10)
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = self.engine.connect()
        try:
            yield conn
        finally:
            conn.close()
    
    def create_tables(self):
        """Execute schema SQL file to create tables."""
        schema_path = Path(__file__).parent.parent / "data_pipeline" / "transit_schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with schema_path.open("r") as f:
            sql = f.read()
        
        with self.engine.begin() as conn:
            conn.execute(text(sql))
        
        print("Tables created successfully")