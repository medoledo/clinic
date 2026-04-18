from django.shortcuts import render


def handler404(request, exception):
    """Custom 404 — page not found."""
    return render(request, '404.html', status=404)


def handler500(request):
    """Custom 500 — internal server error."""
    return render(request, '500.html', status=500)
