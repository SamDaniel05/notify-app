from django.http import JsonResponse
from django.urls import path
def health(_request):
    return JsonResponse({"status": "ok", "service": "notify-api"})
urlpatterns = [path("", health)]
