from django.shortcuts import render

from .services import (
    export_observations_csv_response,
    export_observations_excel_response,
    export_photo_metadata_csv_response,
    export_photo_metadata_excel_response,
    export_quantity_events_csv_response,
    export_quantity_events_excel_response,
    export_tracking_units_csv_response,
    export_tracking_units_excel_response,
)


def index(request):
    return render(request, 'exports/index.html')


def tracking_units_csv(request):
    return export_tracking_units_csv_response()


def tracking_units_excel(request):
    return export_tracking_units_excel_response()


def observations_csv(request):
    return export_observations_csv_response()


def observations_excel(request):
    return export_observations_excel_response()


def quantity_events_csv(request):
    return export_quantity_events_csv_response()


def quantity_events_excel(request):
    return export_quantity_events_excel_response()


def photo_metadata_csv(request):
    return export_photo_metadata_csv_response()


def photo_metadata_excel(request):
    return export_photo_metadata_excel_response()
