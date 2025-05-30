from django.http.response import HttpResponseBadRequest,HttpResponseNotAllowed,JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import service.main as service
from datetime import datetime

@csrf_exempt
def handleSaveSettings(request):
    if request.method=='POST':
        try:
            data=json.loads(request.body)
            res=service.get_phenology(data)
            return JsonResponse(res)
        except Exception as e:
            return HttpResponseBadRequest(e)
    else:
        return HttpResponseNotAllowed(["GET"])
    
@csrf_exempt
def handleMonthlyComposite(request):
    try:
        params_dict=request.GET
        start_date=params_dict['start_date']
        sdate=datetime.strptime(start_date,'%Y-%m')
        end_date=params_dict['end_date']
        edate=datetime.strptime(end_date,'%Y-%m')
        if (edate<sdate):
            raise Exception("End date cannot be prior to start date")
        
        res=service.get_monthly_composite(start_date,end_date)
        return JsonResponse(res,safe=False)
    except Exception as e:
        print(e)
        return HttpResponseBadRequest(e)

