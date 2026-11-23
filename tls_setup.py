"""Configure trusted CA roots for both GUI and collector processes.

Does NOT disable SSL/TLS verification. Honours an explicitly configured
SSL_CERT_FILE; otherwise uses certifi when available.
"""
import os
from pathlib import Path


def configure_ca():
    explicit = os.environ.get("SSL_CERT_FILE", "")
    if explicit:
        return "environment" if Path(explicit).is_file() else "invalid-environment"
    try:
        import certifi
    except ImportError:
        return "system"
    cafile = certifi.where()
    if Path(cafile).is_file():
        os.environ["SSL_CERT_FILE"] = cafile
        return "certifi"
    return "system"
