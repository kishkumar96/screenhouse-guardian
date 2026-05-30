"""
Phase 1A role-based access helpers.

Groups:
  Observer  — can view and create observations
  Manager   — everything Observer can + exports + QR generation
  Admin     — everything Manager can + Django admin full access

Superusers bypass all group checks.
"""

from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def _login_redirect(next_url):
    """Return a redirect to the login page with the given next URL."""
    login_url = getattr(settings, 'LOGIN_URL', '/accounts/login/')
    return redirect(f'{login_url}?{urlencode({REDIRECT_FIELD_NAME: next_url})}')

GROUP_OBSERVER = 'Observer'
GROUP_MANAGER = 'Manager'
GROUP_ADMIN = 'Admin'


def user_in_group(user, group_name):
    """Return True if the active user belongs to the named group."""
    return user.is_active and user.groups.filter(name=group_name).exists()


def is_observer(user):
    """Observer-or-higher: Observer, Manager, Admin, or superuser."""
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=[GROUP_OBSERVER, GROUP_MANAGER, GROUP_ADMIN]).exists()


def is_manager(user):
    """Manager-or-higher: Manager, Admin, or superuser."""
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=[GROUP_MANAGER, GROUP_ADMIN]).exists()


def is_admin_role(user):
    """Admin role: Admin group or superuser."""
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=GROUP_ADMIN).exists()


def observer_required(view_func):
    """Decorator: redirect unauthenticated users to login; 403 for wrong role."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _login_redirect(request.get_full_path())
        if not is_observer(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped


def manager_required(view_func):
    """Decorator: redirect unauthenticated users to login; 403 for wrong role."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _login_redirect(request.get_full_path())
        if not is_manager(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped
