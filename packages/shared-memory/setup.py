from setuptools import setup, find_packages

setup(
    name="shared-memory",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "redis>=5.0.3",
        "psycopg2-binary>=2.9.9",
        "sqlalchemy>=2.0.28",
        "qdrant-client>=1.8.0",
        "pydantic>=2.6.4"
    ],
    description="Shared python memory utility drivers and sync algorithms for CodeForge AI"
)
