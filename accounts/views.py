from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

User = get_user_model()



# def login_view(request):
#     if request.method == "POST":
#         username = request.POST.get("username")
#         password = request.POST.get("password")

#         user = authenticate(request, username=username, password=password)

#         if user is not None:
#             login(request, user)

#             # 🔥 ROLE BASED REDIRECT
#             if user.role == "employee":
#                 return redirect("dashboard")

#             elif user.role == "customer":
#                 return redirect("customer_home")

#             else:
#                 return redirect("admin:index")

#         else:
#             messages.error(request, "Invalid credentials")

#     return render(request, "login.html")


def login_view(request):

    if request.method == "POST":

        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user_obj = User.objects.get(email=email)

            user = authenticate(
                request,
                username=user_obj.username,
                password=password
            )

        except User.DoesNotExist:
            user = None

        if user is not None:

            login(request, user)
            
            return redirect("home")

        else:
            messages.error(request, "Invalid credentials")

    return render(request, "login.html")

def logout_view(request):
    logout(request)
    return redirect("login")


def signup_view(request):

    if request.method == "POST":

        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        # Validation
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect("signup")

        # Check existing email
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("signup")

        # Username generate from email
        username = email.split("@")[0]

        # Avoid duplicate usernames
        if User.objects.filter(username=username).exists():
            username = f"{username}{User.objects.count() + 1}"

        # Create user
        user = User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=make_password(password),
        )

        messages.success(request, "Account created successfully")
        return redirect("login")

    return render(request, "signup.html")