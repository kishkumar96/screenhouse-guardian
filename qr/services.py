"""
QR code generation service.

The QR code encodes the absolute URL to the future observation form:
    /observe/<unit_code>/

This path is stable — it is based on unit_code, not a database PK.
Reprinting/regenerating a QR code must never create a new TrackingUnit.
"""

import io

import qrcode
from django.core.files.base import ContentFile

from inventory.models import TrackingUnit  # noqa: F401 — kept for callers who import from here


def build_observation_url(tracking_unit, *, request=None, base_url=None):
    """
    Return the URL the QR code should encode for this tracking unit.

    Priority:
      1. request — uses request.build_absolute_uri() (correct scheme/host)
      2. base_url — concatenates base_url + path (useful in tests / management commands)
      3. neither  — returns the relative path only
    """
    path = f'/observe/{tracking_unit.unit_code}/'

    if request is not None:
        return request.build_absolute_uri(path)

    if base_url is not None:
        return base_url.rstrip('/') + path

    return path


def generate_qr_for_tracking_unit(tracking_unit, *, request=None, base_url=None):
    """
    Generate a QR PNG image and save it to tracking_unit.qr_code.

    - Does NOT create a new TrackingUnit.
    - Overwrites any existing QR image for this unit.
    - Calls save=True so the change is persisted immediately.
    - Returns the same tracking_unit instance (already saved).
    """
    url = build_observation_url(tracking_unit, request=request, base_url=base_url)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color='black', back_color='white')

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    filename = f'qr_{tracking_unit.unit_code}.png'
    tracking_unit.qr_code.save(filename, ContentFile(buffer.read()), save=True)

    return tracking_unit
