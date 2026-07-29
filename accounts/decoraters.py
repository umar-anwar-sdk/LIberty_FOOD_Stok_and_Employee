from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def is_admin(user):
    """Treat Django superusers and application admins as administrators."""
    return user.is_authenticated and (user.is_superuser or user.role == "admin")


def role_required(*roles):
    """Require login plus one of the supplied application roles; otherwise 403."""
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if is_admin(request.user) or request.user.role in roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have permission to access this page.")
        return wrapper
    return decorator


def admin_required(view_func):
    return role_required()(view_func)


def employee_required(view_func):
    return role_required('employee')(view_func)


def customer_required(view_func):
    return role_required('customer')(view_func)
