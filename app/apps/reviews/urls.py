"""Review URL routing. Prefixed with /api/reviews/"""
from django.urls import path
from apps.reviews import views

app_name = 'reviews'

urlpatterns = [
    path('', views.ReviewListView.as_view(), name='list'),
    path('my-review/', views.MyReviewView.as_view(), name='my-review'),
]
