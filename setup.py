"""
Setup script for StorySync package.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="storysync",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="StorySync - Production-grade story content synchronization service between MongoDB and Elasticsearch",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BrahmAksh/namah-schedule",
    packages=find_packages(exclude=["mongo_es_sync*"]),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Database",
        "Topic :: System :: Archiving :: Mirroring",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
            "pytest>=7.4.0",
            "pytest-mock>=3.11.0",
            "pytest-cov>=4.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "storysync=storysync.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "storysync": ["config/.env.example"],
    },
)
