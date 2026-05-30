from django.shortcuts import render

from config.permissions import manager_required
from .services import (
    export_daily_round_items_csv_response,
    export_daily_round_items_excel_response,
    export_daily_rounds_csv_response,
    export_daily_rounds_excel_response,
    export_observations_csv_response,
    export_observations_excel_response,
    export_photo_metadata_csv_response,
    export_photo_metadata_excel_response,
    export_quantity_events_csv_response,
    export_quantity_events_excel_response,
    export_tracking_units_csv_response,
    export_tracking_units_excel_response,
    export_treatments_csv_response,
    export_treatments_excel_response,
)


@manager_required
def index(request):
    return render(request, 'exports/index.html')


@manager_required
def tracking_units_csv(request):
    return export_tracking_units_csv_response()


@manager_required
def tracking_units_excel(request):
    return export_tracking_units_excel_response()


@manager_required
def observations_csv(request):
    return export_observations_csv_response()


@manager_required
def observations_excel(request):
    return export_observations_excel_response()


@manager_required
def quantity_events_csv(request):
    return export_quantity_events_csv_response()


@manager_required
def quantity_events_excel(request):
    return export_quantity_events_excel_response()


@manager_required
def photo_metadata_csv(request):
    return export_photo_metadata_csv_response()


@manager_required
def photo_metadata_excel(request):
    return export_photo_metadata_excel_response()


@manager_required
def treatments_csv(request):
    return export_treatments_csv_response()


@manager_required
def treatments_excel(request):
    return export_treatments_excel_response()


@manager_required
def daily_rounds_csv(request):
    return export_daily_rounds_csv_response()


@manager_required
def daily_rounds_excel(request):
    return export_daily_rounds_excel_response()


@manager_required
def daily_round_items_csv(request):
    return export_daily_round_items_csv_response()


@manager_required
def daily_round_items_excel(request):
    return export_daily_round_items_excel_response()
