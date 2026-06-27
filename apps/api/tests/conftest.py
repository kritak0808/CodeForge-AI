import asyncio
from unittest.mock import patch
import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings
settings.KAFKA_DISABLED = False

from app.database import Base, get_db
from main import app
from httpx import AsyncClient, ASGITransport

@pytest.fixture(scope="session", autouse=True)
def mock_kafka():
    with patch("event_publisher.KafkaProducer", side_effect=Exception("Mock Kafka Down")):
        with patch("event_publisher.KafkaConsumer", side_effect=Exception("Mock Kafka Down")):
            with patch("kafka.KafkaProducer", side_effect=Exception("Mock Kafka Down")):
                with patch("kafka.KafkaConsumer", side_effect=Exception("Mock Kafka Down")):
                    yield

# InMemory SQLite URL for async testing
DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function", autouse=True)
async def setup_db():
    # Initialize schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session
        await session.close()

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    # Override get_db dependency
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
        
    app.dependency_overrides.clear()
