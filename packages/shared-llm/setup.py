from setuptools import setup, find_packages

setup(
    name="shared-llm",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "openai>=1.12.0",
        "anthropic>=0.18.0",
        "google-generativeai>=0.3.0",
        "tiktoken>=0.5.0",
        "tenacity>=8.2.0",
        "pydantic>=2.6.4",
        "httpx>=0.25.0",
    ],
)
