from django.shortcuts import render

def sheet(request):
    return render(request, "charsheet/charsheet.html")