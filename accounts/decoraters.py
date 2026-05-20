from django.shortcuts import redirect


def admin_required(view_func):

    def wrapper(request, *args, **kwargs):

        if request.user.is_authenticated:

            if request.user.role == 'admin':
                return view_func(request, *args, **kwargs)

        return redirect('login')

    return wrapper


def manager_required(view_func):

    def wrapper(request, *args, **kwargs):

        if request.user.is_authenticated:

            if request.user.role in ['admin', 'manager']:
                return view_func(request, *args, **kwargs)

        return redirect('login')

    return wrapper


def employee_required(view_func):

    def wrapper(request, *args, **kwargs):

        if request.user.is_authenticated:

            if request.user.role in [
                'admin',
                'manager',
                'employee'
            ]:
                return view_func(request, *args, **kwargs)

        return redirect('login')

    return wrapper


def customer_required(view_func):

    def wrapper(request, *args, **kwargs):

        if request.user.is_authenticated:

            if request.user.role == 'customer':
                return view_func(request, *args, **kwargs)

        return redirect('login')

    return wrapper